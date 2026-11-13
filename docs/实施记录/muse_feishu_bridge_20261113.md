# Muse–飞书桥搭建记录（2026-11-13 晚）

目的：把 Muse（沙箱云端 agent）接入飞书，让 Muse 能在飞书里收发消息，用户、chief agent、Muse 三方能在同一个飞书讨论组里直接交流，不再经 chief agent 以 [Muse] 前缀中转。

## 架构

```
飞书群 / 私聊 ──(im.message.receive_v1, WebSocket 长连接)──> 桥 (laptop)
桥 ──append──> ~/sys2/inbox/feishu_to_muse.jsonl
沙箱 hook feishu-muse-inbox (60 秒轮询) ──新行──> 唤醒 Muse worker
Muse worker ──append──> ~/sys2/inbox/muse_to_feishu.jsonl (经 laptop_ssh.sh)
桥 outbox 线程 (5 秒轮询) ──im.v1.messages API──> 飞书群 / 私聊
```

- 监听与发送同在一个进程（bridge.py），两个方向互相独立。
- 凭据只读 `~/sys2/config/feishu_muse.env`（600 权限，FEISHU_APP_ID、FEISHU_APP_SECRET 两行），不写进任何报告、日志、GitHub。
- 与 chief agent 的飞书应用完全独立（不同 App ID、不同机器人、不同长连接；同一应用多客户端会随机分发事件，故必须分开）。

## 文件清单

笔记本：
| 文件 | 说明 |
|---|---|
| `~/sys2/muse_bridge/bridge.py` | 桥主程序：长连接监听 + outbox 发送 |
| `~/sys2/muse_bridge/README.md` | 桥说明（与本文同源，留档笔记本） |
| `~/sys2/muse_bridge/bridge.log` | 运行日志（可能含会话 token，不外传） |
| `~/sys2/muse_bridge/outbox.offset` | outbox 已处理行数（发送端进度） |
| `~/.config/systemd/user/muse-feishu-bridge.service` | systemd 用户服务，Restart=always |
| `~/sys2/inbox/feishu_to_muse.jsonl` | 入站：飞书消息，一行一条（桥写入） |
| `~/sys2/inbox/muse_to_feishu.jsonl` | 出站：Muse 回复，一行一条（Muse 写入，桥发送） |
| `~/sys2/config/feishu_muse.env` | Muse 专用飞书应用凭据（600） |

沙箱：
- `~/hooks/scripts/feishu-muse-inbox.sh`：60 秒轮询 laptop 的 feishu_to_muse.jsonl，新行即唤醒。
- hook id `feishu-muse-inbox`（已启用，poll 60 秒）。

## 依赖与关键 API（实测确认，非臆测）

- Python 3.12（系统），`lark-oapi==1.7.5`。安装：`python3 -m pip install --user --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple lark-oapi`。默认 PyPI 太慢（7 秒才回简单页，6 分钟装不完），改走清华镜像后 14 秒装完。`pip3` 命令不存在，用 `python3 -m pip`。PEP 668 拦系统级安装，`--user` + `--break-system-packages` 绕过（只写 ~/.local，不动系统 Python）。venv 路线走不通：`ensurepip` 缺失，`get-pip.py` 从 bootstrap.pypa.io 下载超时。
- 官方 SDK 的 WebSocket 客户端是 `lark_oapi.ws.Client`（不是网上旧文章的 `lark_oapi.websocket.WebSocketClient`，1.7.5 里没有这个模块）。构造：`Client(app_id, app_secret, event_handler=handler, auto_reconnect=True)`，`start()` 阻塞，SDK 内置心跳与自动重连，无需手动 ping。
- 事件分发：`EventDispatcherHandlerBuilder(encrypt_key, verification_token).register_p2_im_message_receive_v1(handler).build()`。构造须传 encrypt_key 与 verification_token（无默认值）；桥里传空字符串——WebSocket 长连接靠 App ID/Secret 鉴权，这两个是 Webhook 模式用的，空串可建 handler 且长连接已通。若应用在控制台开启了事件加密，须把真实 Encrypt Key 填进 feishu_muse.env 并改桥读取，否则事件解密失败。
- 收消息事件：`im.message.receive_v1`，handler 收 `P2ImMessageReceiveV1`，正文在 `event.message.body.content`（JSON 串 `{"text": ...}`），发送者在 `event.sender.id`，会话在 `event.message.chat_id`。
- 发消息：`CreateMessageRequest.builder().receive_id_type("chat_id").request_body(CreateMessageRequestBody.builder().receive_id(chat_id).msg_type("text").content(json.dumps({"text": text}, ensure_ascii=False)).build()).build()`，`client.im.v1.message.create(req)`。已用 builder 链实测构造通过。

## 验证证据（2026-11-13 晚）

- 凭据有效：token 接口 `POST /open-apis/auth/v3/tenant_access_token/internal`，http 200、code 0、has_token True。
- 长连接已通：`connected to wss://msg-frontier.feishu.cn/ws/v2?...`，25 秒前台试跑无断开；systemd 服务 active，Restart=always。
- 发送链路已通（接线验证）：往 muse_to_feishu.jsonl 写一条假 chat_id 测试行，桥 3 次尝试发送，飞书 API 返回 code 230001 invalid receive_id（假 ID 预期错误，证明调用已到达飞书且鉴权通过）；3 次后跳过，offset 推进。测试行与 offset 已清理。
- hook 已通（干跑验证）：feishu_to_muse.jsonl 为空时 silent（inbox missing）；写入一条合成测试行后 dry_run 判 wake，payload 含完整消息字段；测试行已删，state 未消耗（dry_run 不写 state）。
- 服务：`systemctl --user is-active muse-feishu-bridge.service` 为 active。

## 待用户配合（端到端实测前必须做）

1. **飞书控制台配置 Muse 应用**（若还没做）：在开放平台打开 Muse 专用应用——开机器人能力；事件订阅切为“使用长连接接收事件”（桥已在线，保存时不会报“无在线长连接”）；订阅 `im.message.receive_v1`；权限开 `im:message`（收发消息）、`im:message:send_as_bot`（以机器人身份发）与群消息读取；创建新版本并发布。
2. **把 Muse 机器人加进飞书讨论组**（与 chief agent 机器人“海王星”同一群），或在私聊里直接给 Muse 机器人发消息。
3. **实测**：在群里 @Muse 机器人发一句话 → 稍等约 1 分钟，Muse 应在主聊天被唤醒并回复进群。若收不到，检查第 1 步的事件订阅与权限是否已发布。

## 已知注意点

- 桥日志 bridge.log 含 WebSocket 会话 token（access_key/ticket），只留在笔记本，不进 GitHub、不外传。
- outbox 发送失败重试 3 次后跳过（防坏行卡住队列），失败写日志。
- 入站只处理文本消息（msg_type=text）；其他类型（图片/文件/卡片）会落盘 raw_content，暂不解析。
- 凭据值绝不写进报告、日志、GitHub；本记录只写文件路径。
