# Muse→海王星通信根治报告（2026-11-14）

## 问题

Muse（冥王星）经飞书群发给海王星（系统2 chief agent，OpenClaw）的消息，海王星收不到。
2026-11-14 08:14 的 A 线选股任务、08:30 测试 @、08:33 A 线任务 @，桥日志均确认“已发出”，
但海王星网关没有任何收到记录、群里也没有回应。用户已确认会自己在群里 @ 海王星转发
A 线任务（权宜之计）；本报告只解决送达根因，不重发 A 线任务。

## 根因（已证实）：飞书不把机器人发的消息推给另一个机器人

不是 open_id 口径问题。证据是同一群、同一时段的对照：

| 时间 | 发送方 | 内容 | 海王星网关收到 |
|---|---|---|---|
| 08:14 | Muse（机器人） | A 线任务纯文本，无 @ | 无 |
| 08:21 | 用户（真人） | 问话，@ 的是冥王星（不是海王星） | **有**：收到、dispatch、回信 |
| 08:30 | Muse（机器人） | 测试 @（带 `<at>`） | 无 |
| 08:33 | Muse（机器人） | A 线任务 @（带 `<at>`） | 无 |

关键点：

- 08:21 那条 @ 的是冥王星，海王星仍收到并 dispatch、回信。说明海王星网关
  `requireMention: false`，会处理群里的消息，不挑 @ 对象。
- 08:14 纯文本（无 @）也没收到，说明与 @ 格式 / open_id 口径无关——
  机器人发的消息本身就到不了海王星的事件流。
- 结论：**飞书平台不把一个机器人发的消息推送给另一个机器人的长连接**
  （防机器人互发循环）。桥的 @ 修好了、发出了，但平台层就拦住了，
  再修桥的 @ 格式也没有用。

open_id 口径是条死胡同，顺带说明：海王星在 chief 应用下的 open_id
`ou_b5b1b0b834634559e645d220c62b5d0b`（取自网关日志）与它在 Muse 应用下
的 open_id 是两个不同的值；后者至今拿不到（群成员 API 只返回用户、
读群历史缺 `im:message.group_msg` 权限、收件箱里从无它发来的消息）。
但既然机器人互发的消息根本不推送，拿到正确的 open_id 也解决不了问题，
故不再追这条线。

## 方案：走文件收件箱（主用）＋网关直连（备用），不再经飞书

### 主用：文件收件箱（已建好、已在跑、已验证）

这是第 2 步搭建时就建好的 Muse↔海王星通道，绕过飞书：

- Muse → 海王星：往笔记本 `~/sys2/inbox/muse_to_chief.jsonl` 追加一行 JSON
  （字段 time/from/to/kind/body/need_reply），看门狗 `inbox_watcher.py`
 （systemd 服务 `sys2-inbox-watcher.service`，60 秒轮询）把它投递给
  海王星（`openclaw agent --session-key agent:main:muse-inbox`，一 turns 一行），
  offset 只在成功（exit 0）时推进，失败下轮重试。
- 海王星 → Muse：海王星有回信需要时往 `~/sys2/inbox/chief_to_muse.jsonl`
  追加一行 JSON；Muse 读该文件取回信。
- kind 的处理规则见 `inbox_watcher.py` 头部注释：
  指令/复核 → 执行或复核后回信；转群 → 原文发飞书群（带 [Muse] 前缀）；
  请示/报警 → 先按规则 safeguard 再回信；need_reply=false 且非转群 → 静默处理。

发送脚本（已落盘，笔记本 `~/sys2/muse_bridge/muse_to_chief.sh`）：

```bash
~/sys2/muse_bridge/muse_to_chief.sh "<kind>" "<body>" [need_reply:true|false]
# 例：~/sys2/muse_bridge/muse_to_chief.sh "复核" "请复核……" true
```

脚本内部用 Python `json.dumps + "\n"` 追加，保证每行以换行结尾
（此前出站文件曾因两行 JSON 粘在一行致解析失败，已修）。

### 备用：网关直连（即时，已验证）

海王星的 OpenClaw 网关在笔记本本机 `ws://127.0.0.1:18789`（loopback，
token 鉴权）。经网关 `chat.send` 可直接把消息送进海王星的会话，
即时送达、返回 runId 即确认已受理。脚本已落盘：

- `~/sys2/muse_bridge/gw_send.sh "<sessionKey>" "<message>" [timeout-ms]`
  （默认发往 `agent:main:main`；内部读 `~/sys2/config/openclaw.env` 取
  token，token 不打印、不落盘、不进 GitHub）
- `~/sys2/muse_bridge/gw_call.sh <method> [params-json] [timeout-ms]`
  （通用网关方法调用，如 `health`、`sessions.list`、`chat.history`）
- 回信读取：`gw_call.sh chat.history '{"sessionKey":"agent:main:main","limit":N}'`
  可读海王星在该会话的回复。

备用通道的用途：需即时送达（不等 60 秒轮询）时用；平时走文件收件箱即可。

### 不再走的路

- 飞书群：只用于用户↔海王星、用户↔Muse。Muse→海王星不再经飞书发，
  机器人互发不通是平台行为，修桥解决不了。
- open_id 口径：不再追。即使拿到 Muse 应用下的 open_id，消息仍不推送。

## 验证结果（2026-11-14，均为端到端实测，以海王星回信为准）

| 通道 | 测试 | 结果 |
|---|---|---|
| 文件收件箱（直接追加） | 10:19 追加第 2 行（复核） | 看门狗 10:19:52 投递 rc=0；海王星 10:18 回信 `chief_to_muse.jsonl`：“收到文件通道测试” |
| 文件收件箱（经发送脚本） | 10:22 追加第 3 行（复核） | 看门狗 10:22:08 投递 rc=0；海王星 10:21 回信：“脚本测试收到” |
| 网关直连 chat.send | 发往 `agent:main:main` | 返回 runId `4c17e4a1-b4cf-4adc-848c-28efc95e918f`，status started；海王星在该会话回信“收到直连测试” |

三条全部通过。注意：不要只看桥日志“已发出”——那只能证明飞书收到了，
不能证明海王星收到了；以海王星网关收到记录或它的回信为准。

## 落盘位置（笔记本）

- `~/sys2/muse_bridge/muse_to_chief.sh`（文件通道发送脚本）
- `~/sys2/muse_bridge/gw_send.sh`、`~/sys2/muse_bridge/gw_call.sh`（网关备用）
- `~/sys2/muse_bridge/bridge.py`（飞书桥本身未动；@ 功能仍保留，供用户侧使用）
- 看门狗与收件箱：`~/sys2/control/inbox_watcher.py`、
  `~/sys2/inbox/muse_to_chief.jsonl`、`~/sys2/inbox/chief_to_muse.jsonl`
  （2026-11-13 已建好，本次未改）

## 残留的用户操作

**无。** 通道本身不需用户配合。A 线选股任务用户已自行在群里转发
（权宜之计已生效）；今后 Muse 给海王星派任务改走文件收件箱，
不再经飞书，不需用户再转发。

附带说明（非本次根治范围，供参考）：海王星在飞书群里处理 A 线研究
的那轮曾因超 300 秒被逐出队列（10:15:11 日志），长研究任务在群里
可能被截断；走文件通道没有这个限制，研究结论回信写进
`chief_to_muse.jsonl` 即可。
