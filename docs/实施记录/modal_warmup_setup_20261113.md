# Modal 预热定时任务（2026-11-13）

用户 2026-11-13 15:27 下令：最终目标是脱离 Muse，Modal 重部署依赖 Muse 与目标不符；试下预热后的情况，如果可以，那就提前预热。

## 1. 预热实测结果

- Modal 端点 `https://whddwdzcxm--b-debate-llm-serve.us-east.modal.run/v1/chat/completions`（应用 b-debate-llm，vLLM + Qwen2.5-7B-Instruct-AWQ，T4 15GB）。
- 15:23 时 curl 15 秒超时（HTTP 000）、子代理两次探测 0.3 秒断连，看似已死；但 15:27 主代理发一次 warmup 请求后立即回 200（"Hello"），30 秒后再测仍 200。**结论：应用没死，只是缩容到零（scaledown 900 秒）；预热能唤醒，预热后可用。**
- 独立预热脚本实测：`python3 modal_warmup.py` → `{"status": "ok", "http_code": 200, "elapsed_ms": 665, "error": null}`，exit 0；curl 直测 200，0.78 秒（热容器）。

## 2. 关键发现：代理路由（影响 debate_run.py 的 Modal 调用）

- 预热脚本第一版复用 `debate_run.py` 的 `_opener()`（把 :3128 改写成 :3130），结果 264ms 即断连（Remote end closed connection）；改回环境代理原值（:3128 出口代理）后立即 200。
- **原因**：:3130 是 Tailscale 隧道代理，只通 Tailscale 内网；Modal 是公网地址，该走 :3128 出口代理。`debate_run.py` 的 `_opener()` 对所有请求（含 Modal）都改写成 :3130，**这可能是 14:30 辩论时 Modal“已死”的真正原因——不是应用死了，是沙箱 Python 代码的代理路由错了**（curl 经 :3128 一直是通的）。
- 本任务只做预热定时任务，未改 `debate_run.py` 的 `_opener()`。建议后续单独验证并修 `debate_run.py` 的 Modal 代理路由（公网地址用 :3128，Tailscale 地址才用 :3130），否则辩论内嵌的 `modal_warmup()` 与 `modal_chat()` 仍可能因代理路由失败、被迫走 hub 回落。

## 3. 预热脚本

- 位置：`~/workspace/goals/a/hidden_files/b_debate/modal_warmup.py`（Python，仅标准库）。
- 用法：`python3 modal_warmup.py`，输出一行 JSON（status、http_code、elapsed_ms、error）。
- 预热失败不抛异常、不阻塞辩论（辩论自有 hub 回落 LongCat-2.5）。Modal 端点无鉴权，预热请求不含任何密钥。

## 4. 三个定时预热 cron（交易日周一至五，归属 goal a，全部 enabled）

| cron ID | 时间 | 供哪场辩论 | 下次运行 |
|---|---|---|---|
| modal-warmup-1025 | 10:25 | 10:30 持仓辩论（b-debate-1000） | 2026-11-16（周一）10:25 |
| modal-warmup-1355 | 13:55 | 14:00 持仓辩论（b-debate-1400） | 2026-11-16（周一）13:55 |
| modal-warmup-1425 | 14:25 | 14:30 买入辩论（daily-stock-pick） | 2026-11-16（周一）14:25 |

每个 cron 只跑预热脚本，不下单、不改任何交易文件；失败静默（辩论自有 hub 回落），成功也不发消息。

## 5. 买入辩论的预热核查

- `buy_debate.py` 的 `main()` 开头已调 `dr.modal_warmup()`（第 347 行，读候选后、建包前），与 `debate_run.py` 一致（fire-and-forget，timeout 10 秒）。**无需重复加。**
- 注意：`modal_warmup()` 是 fire-and-forget、不等容器就绪；容器 2–3 分钟冷启动期间首个真实调用仍可能撞冷容器。本次三个定时预热 cron 在辩论前 5 分钟触发，正好覆盖冷启动窗口。

## 6. 脱离 Muse

预热是定时任务自动跑（cron），不依赖 Muse 人工干预，不重部署 Modal 应用，符合脱离 Muse 目标。预热失败时辩论自动回落 hub，不阻塞。
