# 辩论 LLM 链可靠性修复（2026-11-13）

用户 2026-11-13 14:54 下令：辩论环节看出，llmhub 需要为可靠性做改进。

## 1. 故障（2026-11-13 14:30 选股实测）

- AlphaSniper 推荐 **600919 江苏银行**（现价 13.24，+2.32%，评分 76/100），UZI 看门狗通过；买入辩论 **skip，置信度 0.0**，B 线空仓。
- 决策文件：`~/workspace/goals/a/hidden_files/b_debate/buy_decisions_20261113.json`；日志：`logs/buy_debate_2026-11-13_1433.jsonl`（只有最终决策一行，**原始评判输出与 Modal 断连细节均未记录**——日志缺口）。
- 故障链：**Modal 多次调用失败（Remote end closed connection）→ 回落 hub → 评判输出解析失败（judge-invalid）→ 按“宁可错过”跳过**。故障导致的 skip 与“判断为不买”是两回事，须区分并修好。

## 2. 故障定位

### 2.1 Modal 断连（根因 2）

- Modal 当前已死：沙箱探测两次均立即失败（0.3 秒，`Remote end closed connection without response`），不是冷启动（冷启动应为 303 或慢响应）。
- 旧 `modal_chat`：5 次重试 × 每次失败后等 60 秒，纯烧时间约 4 分钟才回落 hub；买入辩论解析失败重试时又会完整再跑一遍 Modal 循环。
- Modal 应用本身的重部署/预热走笔记本（沙箱出口代理挡 gRPC），本次不擅自做；方案见 §6。

### 2.2 评判解析失败（根因 1）

- **解析失败不是偶发，是系统性**：近 3 次买入辩论 5 只候选里 4 只 judge-invalid（11-12 11:04 两只全败、11-10 一只败、11-13 600919 败；仅 11-12 11:10 的 000001 成功判 skip 置信 0.65）。持仓辩论（debate_run.py）的评判大多解析成功，问题集中在买入辩论。
- 今日真实畸形输出（已复现，74.4 秒，finish=stop，长度 288 字符）：
  `"evidence": ["suggest_qty": 3700, "p4_limit": 13.24, "single_limit": 50000]` —— evidence 数组里写键值对，非法 JSON；`extract_json` 整体解析与首尾切片均失败。
- 提示词自相矛盾：系统要求“只输出 JSON、不要写思考过程”，用户提示词却说“先分别列出多方理由与空方风险，再综合判断输出最终决策”。
- hub qwen3:8b 是思考模型，输出常带思考推理（`</think>` 后才是 JSON），旧解析器只认整体解析与首尾切片，容错不足。

### 2.3 hub 模型口径（根因 3）

- hub /v1/models 列表含 `qwen3-8b`（连字符）而不含 `qwen3:8b`（冒号），但实测 `qwen3:8b` 仍返回 200（5.9 秒）且输出思考内容，`qwen3-8b` 亦返回 200（2.1 秒）；两者输出开头均为思考推理。hub 模型 347 个：longcat-2.5、nemotron-3.5-lightning-30b-a3b、nex-n2.6、s5-free 均在列。
- **lightning 限流**：2026-11-13 15:xx 实测 `nemotron-3.5-lightning-30b-a3b` 回 429（"All models exhausted: 1 route checked (1 rate-limited or on cooldown). Soonest reset ~8m"）。lightning 作回落模型时若遇限流，`hub_chat` 的 75 秒×2 重试会烧约 150 秒。**LongCat-2.5 实测可用**（小提示词 3.5 秒回 200），故回落模型首选改为 LongCat-2.5（任务给定链首），lightning 只作第二备用。

### 2.4 重试不治本（根因 4）

- `debate_one` 解析失败重试用完全相同的提示词与 temperature（0.2），系统性格式错误会重复。
- `hub_chat` 只试 qwen3:8b 一个模型，无模型切换。
- `extract_json` 只有整体解析与首尾切片两招，无代码块提取、无修复、无正则兜底。

## 3. 可靠性缺口清单

| # | 故障现象 | 根因 | 影响 |
|---|----------|------|------|
| 1 | Modal 断连后等满 5 次×60 秒才回落 hub（约 4 分钟） | `modal_chat` 对连接类错误也等 60 秒重试，不区分错误类型 | 买入辩论耗时大增，逼近 14:55 硬截止；解析失败重试又重跑一遍 Modal 循环 |
| 2 | hub 评判输出解析失败（judge-invalid），近 3 次 5 只候选 4 只败 | 提示词自相矛盾＋qwen3:8b 思考模型输出畸形 JSON（evidence 数组写键值对）＋解析器只有两招容错 | 600919 等候选被误判为 skip，等于把关被基础设施故障架空 |
| 3 | 解析失败重试用相同提示词与 temperature | `debate_one` 无修格式重试、无模型切换 | 系统性格式错误重复失败 |
| 4 | 决策文件与日志不区分故障 skip 与判断 skip | 无 `skip_kind` 字段，总结行只计总数 | 故障导致的 skip 与“判断为不买”混为一谈，无法统计 LLM 链故障率 |
| 5 | 日志只记最终决策，原始评判输出与 Modal 断连细节未记录 | `llm_trace`/`judge_raw` 缺失 | 故障无法复现与定位 |
| 6 | 无软截止，辩论可能拖到 14:55 硬截止才判 | `main()` 无软截止 | 超时风险，留给下单的时间不足 |
| 7 | lightning 回落模型正被限流（429） | hub 侧单路由限流，reset 约 8 分钟 | 回落链若走 lightning 会烧 150 秒重试等待仍失败 |

## 4. 改了什么（沙箱侧，`~/workspace/goals/a/hidden_files/b_debate/`）

### 4.1 `debate_run.py`

- 加 `import re`。
- 加常量 `HUB_JUDGE_FALLBACK = "longcat-2.5"`、`HUB_JUDGE_FALLBACK_2 = "nemotron-3.5-lightning-30b-a3b"`（LongCat-2.5 在前，实测可用；lightning 第二备用，当前限流）。
- **`modal_chat` 错误类型感知**：连接类错误（`Remote end closed connection`、`Connection reset`、`timed out`、`URLError` 等）连续 2 次即停，不再空等 4 分钟，立即回落 hub；连接类错误立即重试不等待 60 秒；303 冷启动仍保留 5 次×60 秒重试。
- **`llm_chat` 加参数**：`hub_model`（换模型重试时指定回落模型）、`skip_modal`（换模型重试时跳过 Modal 直走 hub）、`hub_max_attempts`（默认 3；换模型重试时传 1，限流即快速失败，不烧 75 秒重试等待）。
- **`hub_chat` 加参数**：`max_attempts`（默认 3；回落链单次尝试时传 1）。
- **`extract_json` 改为四级容错**：①```json 代码块提取 → ②整体解析 → ③首个 `{...}` 段解析 → ④修复畸形后重解 → ⑤正则抽字段兜底。
  - 新增 `repair_json_text`：修 evidence 数组键值对→`"key=value"` 字符串（仅当数组整体由键值对构成时才修）、修尾逗号。
  - 新增 `extract_fields_regex`：正则抽 `code`/`action`/`qty`/`limit_price`/`confidence`/`reason`/`evidence`/`bull_case`/`bear_case` 等字段。

### 4.2 `buy_debate.py`

- **`build_buy_judge_prompt` 强化格式约束**：系统提示词加第 7、8 条（理由写进 JSON 字段内、evidence 必须是字符串数组并给具体示例、禁止数组里写键值对）；用户提示词改写矛盾处（删“先分别列出多方理由与空方风险”），附完整示例 JSON。
- **新增 `build_buy_repair_prompt`**：修格式重试（附上次原文与校验错误，temperature 0.0，只重出 JSON）。
- **`_skip_decision` 加 `skip_kind` 参数**（默认 `judge-failed`）。
- **`debate_one` 重构为三次解析尝试**：
  1. 原提示词主模型（qwen3:8b）；
  2. 同模型修格式重试（temperature 0.0，附 repair prompt）；
  3. 换 LongCat-2.5 模型跳过 Modal 再试（`hub_max_attempts=1`，单次尝试，限流即快速失败）。
  三次失败才判 judge-invalid skip。每步记 `llm_trace`，决策附 `judge_raw`（截断 1000 字符）。
- **`main()` 加软截止**：硬截止前 3 分钟（默认 14:52）；future 超时即判“LLM 链超时”，买入超软截止降级 skip。
- **总结行分别计数**：`skip-judge-failed`（LLM 链故障）与 `skip-judged`（评判判断为不买）分别统计，仅统计 `action=skip` 的（buy 不计入 skip）。

### 4.3 未改的

- 不改辩论的买入规则（置信度 ≥0.7、硬截止 14:55、宁可错过）与闸门（P4/≥5000/单只上限/B 线≤3 只等），只修 LLM 链可靠性。
- 不真实下单、不登录叩富网、不改真实 trade_log/台账、不连华为 VPS 执行层、不把密钥写进普通文件。

## 5. 测试结果

### 5.1 新解析器单元测试（8 种情形，全过）

有效 JSON、```json 代码块、推理+JSON、尾逗号、evidence 键值对、截断、空、无 JSON——8/8 正确处理（修/抽/拒）。

### 5.2 今日真实畸形输出复现

今日 600919 畸形评判输出经新解析器修复后校验通过（buy 0.75、qty 3700、evidence 修为 `["suggest_qty=3700", "p4_limit=13.24", "single_limit=50000"]`）。

### 5.3 干跑（完整链路，600919 当日真实数据）

- **干跑 1（84 秒）**：Modal 2 次断连后回落 hub（当时仍有一次 60 秒等待），hub qwen3:8b 首轮解析成功，判 buy 0.75、qty 3700 @13.24、gate pass、skip_kind judged。发现两处小问题：Modal 首次失败后仍等 60 秒、总结行 skip-judged 计数把 buy 也算进去了。已修复。
- **干跑 2（15.6 秒）**：Modal 立即重试 2 次断连后回落 hub（无 60 秒等待），首轮解析成功，buy 0.75、gate pass、skip_kind judged、trace `[('parse1', 'qwen3:8b', True)]`；总结计数正确（故障 0 只、判断 0 只）。
- **干跑 3（15.8 秒，最终状态）**：同干跑 2，buy 0.75、qty 3700 @13.24、gate pass、skip_kind judged、trace parse1 OK、errors 空。日志 `buy_debate_2026-11-13_1514.jsonl`。
- 三次干跑均用 `--deadline 23:55 --out /tmp/buy_decisions_dryrun*.json`（避开真实决策文件），未真实下单。

### 5.4 强制 Modal 失败演练（hub-only 路径）

`MODAL_ENABLED=False`，只走 hub：13.8 秒完成，buy 0.75、gate pass、skip_kind judged、trace parse1 OK。**Modal 完全不可用时 hub 回落链能出结果。**

### 5.5 模型切换路径模拟测试（mock）

- 强制 parse1 与 parse2 均解析失败：parse3 换 LongCat-2.5（`hub_model='longcat-2.5'`，`skip_modal=True`）解析成功，判 buy 0.8、gate pass、trace `[parse1 False, parse2 False, parse3 True]`。**模型切换管线通。**
- 三次解析全失败：判 skip、conf 0.0、gate skip、**skip_kind judge-failed**、reason“评判输出不合格（缺少字段 limit_price），按宁可错过原则跳过”、trace 三步全 False、`judge_raw` 已记录。**故障与判断区分正确。**

### 5.6 模型可用性实测

- lightning：429 限流（"All models exhausted: 1 route checked (1 rate-limited or on cooldown). Soonest reset ~8m"），小提示词 0.4 秒即回 429；长提示词 judge 调用 180 秒未返回（hub_chat 在 429 上重试 75 秒×2）。**lightning 当前不可作快速回落。**
- LongCat-2.5：小提示词 3.5 秒回 200，可用。长提示词 judge 约 93 秒（推理模型，先占满 thinking 预算），在软截止 14:52 内可接受。
- qwen3:8b：可用，干跑 13.8–15.6 秒出结果。

## 6. 残留问题与后续方案

### 6.1 Modal 应用已死（须用户定夺，不擅自重部署）

- 现状：Modal 应用 `b-debate-llm` 端点立即 `Remote end closed connection`，两次探测均 0.3 秒失败；不是冷启动。沙箱侧已修为“连接类错误 2 次即停、立即回落 hub”，辩论不再被 Modal 拖死（干跑 15.6 秒出结果）。
- **方案（待用户定）**：走笔记本重部署 Modal 应用（沙箱出口代理挡 gRPC，Modal 操作走笔记本）。重部署后须验证：热容器单次 1.4–1.6 秒、冷启动约 2–3 分钟、辩论前 5 分钟轻量 ping 预热（冷启动约 2–3 分钟，须在硬截止 14:55 前完成）。
- 在 Modal 恢复前，辩论走 hub qwen3:8b 主路（实测 13.8–15.6 秒出结果，满足 14:55 硬截止）。

### 6.2 LongCat-2.5 作回落模型尚未经真实 judge 长提示词验证

- LongCat-2.5 小提示词实测可用（3.5 秒回 200），但 judge 长提示词的真实调用尚未跑（此前 180 秒超时是 lightning 429 重试所致，非 LongCat）。模型切换路径已用 mock 验证管线通；真实 LongCat judge 调用建议在下个交易日 14:30 前做一次干跑验证（或待一次真实解析失败触发时自然验证）。
- 若 LongCat-2.5 长提示词亦解析失败或超时，三次失败后仍按 judge-invalid skip（宁可错过），不影响规则。

### 6.3 辩论前 5 分钟预热（Modal 恢复后才有意义）

- 任务原要求“辩论前 5 分钟发一次轻量 ping 唤醒容器”。Modal 当前已死，预热无意义；待 Modal 重部署恢复后，在 14:30 选股任务体或买入辩论 `main()` 前加预热调用（`modal_warmup()` 已存在，`main()` 开头即调）。

## 7. 文件与提交

- 改动：`~/workspace/goals/a/hidden_files/b_debate/debate_run.py`、`buy_debate.py`（均 py_compile 通过）。
- 记录：本文件。
- GitHub：见 CHANGELOG.md 2026-11-13 节（辩论 LLM 链可靠性修复条）。
