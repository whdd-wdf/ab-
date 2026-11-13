# 代理路由修复记录（2026-11-13）

## 1. 根因

- `debate_run.py` 的 `_opener()` 不分 URL，一律把环境代理 `:3128` 改写成 `:3130`（Tailscale 隧道代理，只通内网）。
- Modal 端点是公网地址 `https://whddwdzcxm--b-debate-llm-serve.us-east.modal.run`，该走 `:3128` 出口代理；走 `:3130` 时 264ms 即断连。
- **结论修正：14:30 买入辩论时 Modal“已死”是误判——应用没死，是沙箱 Python 代码代理路由错了。** curl 经 `:3128` 一直是通的；预热请求经 `:3128` 立即回 200。
- hub（`http://100.125.193.42:3001`，Tailscale 内网）走 `:3130` 是对的，不动。

## 2. 改动（`debate_run.py`，备份 `debate_run.py.bak-20261113-proxy`）

- 新增 `_env_proxy_url()`：返回环境代理原值（`:3128`），走公网。
- `_tunnel_proxy_url()` 改为基于 `_env_proxy_url()` 派生（`:3128` → `:3130`），只用于内网。
- 新增 `_is_tailscale_url(url)`：`100.x.x.x` 或 `*.ts.net` 判内网。
- `_opener(url=None)`：按 URL 分流；内网走隧道代理（`:3130`），公网走出口代理（`:3128`）；`url=None` 时默认出口代理。
- 三处调用点：`hub_request()` → `_opener(url)`；`modal_warmup()` 与 `modal_chat()` → `_opener(MODAL_URL)`。
- 只改代理路由；辩论逻辑、闸门、置信度阈值、超时与回落链均未动。
- 未动：`modal_warmup.py`（独立脚本，已用 `:3128`）、三个预热 cron、`debate_packet.py`。

## 3. 验证

- 路由单元检查：hub `100.125.193.42` → True（`:3130`）；Modal → False（`:3128`）；`foo.ts.net` → True；`example.com` → False。
- `modal_warmup()`：1.24 秒，无异常；`modal_chat()` 小请求（max_tokens=1）：0.76 秒，`err=None`，content `Hello`，`fin=length`，HTTP 200。
- `hub_chat()` LongCat-2.5 小提示词：2.56 秒，`err=None`，HTTP 200。
- `buy_debate.py` 干跑（600919 当日真实数据，`--deadline 23:55 --out /tmp/buy_decisions_dryrun_proxy.json`）：11.2 秒；判 buy qty=3700 @13.24，置信 0.75，gate pass，errors 空，`llm_trace` parse1 ok；全程无“Modal 失败回落 hub”输出，**Modal 主路走通**。此前 hub 回落干跑为 15.6–15.8 秒。
- 结论：Modal 主路已通；14:30 故障根因是代理路由，不是应用死亡；**重部署不需要**。

## 4. 后续

- 下周一（2026-11-16）10:30 辩论将是首次实战检验（预热 cron 10:25 先唤醒，辩论走 Modal 主路）。
- 预热定时任务仍保留（冷启动 2–3 分钟，提前唤醒仍有价值）。
