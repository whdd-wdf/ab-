# 笔记本搭建预案（2026-11-13）

> 用户 2026-11-13 16:35 下令：先做预案，评估什么级别模型、及提示词、还有什么 AI agent，最好设计一个搭建流程；在这些明确的情况下问题可以解决；这次来真的，在笔记本上搭建。
>
> 本预案只依据已验证事实写结论；凡属推断处明确标注“推断”，不把推断写成结论。

## 背景与已验证事实

### 两轮盒内验证均未达标（报告 `docs/实施记录/ops_build_test_20261113.md`，commit 99d5f88）

- 盒内 AI（Simular Box，4 CPU / 7.7GB / 无 GPU）只凭 GitHub 能写出可编译的操作侧四脚本（合规 276 行、执行器 318 行、门控 147 行、fillwatch 261 行），但不能独自排错搭通。
- 自测 23/32 = 71.9%（合规 4/4、门控 9/9、执行器 9/14、fillwatch 1/5），目标 ≥80%（26/32）。对接验证按规则跳过。
- AI 自修 bug 两轮均零有效改动：
- qwen2.5:3b（3B）：第一轮输出截断致语法不通过；第二轮输出与原文逐字相同（NOOP）。
- qwen2.5-coder:7b（7B）：生成更干净（无截断/语法错误），但同样定位不到调用不一致处；第一轮只做症状级改动（`move_order` 加 `isdir` 分支，没动调用方、没补 return，重测仍 9/14，失败输出变为 `AttributeError`）；第二轮两份输出与第一轮逐字节相同（md5 核对一致），模型自我重复。
- 残留 bug 2 处，各 1–2 行（完整 traceback 已取回）：
1. 执行器：`move_order`（约 line 66）`open(src_path)` 拿到 base 目录而非订单文件，`IsADirectoryError: [Errno 21] Is a directory`（main L303 → process_one L236 → move_order L66）；另 latent 点：`move_order` 全程无 return，调用方 `result.get("kind")`（main L308）取到 None 致 `AttributeError`。
2. fillwatch：`detect_new_fills(snapshot, logged)` 只定义 2 参，`main()` 以 3 参 `(snap, logged, base)` 调用（main L237），`TypeError`；另 latent 点：`if new_fills is None` 判静默不可达、输出键名 `orders` 而自测取 `computed_orders`。
- 接口规范已补 9 处（712→837 行）：节点账本与 quota 精确 JSON 字段（§6.4）、成交入账更新公式（§6.5）、交易日虚拟兜底（§5.4）、B 线卖出补挂细节（§7.6）、订单队列命名规则（§1.3）、订单 JSON 字段名（§1.2）、订单状态流转细节（§1.4）、虚拟成交与记账口径（§4.6）、`__main__` 入口 + 真实 CLI 形式（§8.1）。
- 自测命令（盒内实测）：在搭建目录跑 `python3 tests/test_<t>.py --base <virtual 目录>`；四份自测 `tests/test_compliance.py`、`tests/test_executor.py`、`tests/test_fillwatch.py`、`tests/test_gate.py`；通过标准即自测脚本内的断言。
- 对接验证（未做，待补）：A 线卖单 601088 卖 200 @49.58 + B 线买单 600919 @12.98 500 股，经虚拟程序（`virtual/virtual_ops.py`：submit → run → snapshot → 查 trade_log/quota/节点），核实合规、执行、快照、入账、quota 平衡。

### 失败根因：证据与推断的区分

- **证据**：两轮用的都是一次性 LLM 调用（给提示词、拿输出，无工具、无迭代）；提示词里只有 bug 现象 + 失败输出全文 + 相关脚本全文 + 自测脚本全文，没有显式写出调用链与返回值契约；模型输出由机械脚本按函数名原样替换，不跑测试验证；7B 第二轮输出与第一轮逐字节相同，无任何机制发现并纠正重复。
- **推断**（须验证）：模型须凭空从代码里反推调用方与被调方的接口契约，7B 推断失败。这是“提示词缺契约 + 无工具迭代”的问题，不只是模型参数量问题。本预案的模型、提示词、agent 三项正是针对这两点下药；是否药到病除，由第二段实搭建的结果判定，不在本预案里预支结论。

### 笔记本环境（2026-11-13 16:37–16:45 只读核查，宏碁 Nitro 5 madaha-Nitro-AN515-47）

- 硬件：R7 6800H，16 核；内存总量 13Gi（16GB 标称），可用 10Gi；磁盘 / 分区 468G，已用 30G，剩余 415G；独显已坏、核显 680M；Ubuntu 24.04，内核 Linux 7.0.0-42-generic；Python 3.12.3；git 在 `~/.local/bin/git`（v2.43.0，须设 `GIT_EXEC_PATH=~/.local/git-pkg/usr/lib/git-core`）；无 ab- 克隆；`~/ops-build-laptop/` 不存在（搭建时新建）。
- Ollama：系统服务在跑，`OLLAMA_HOST=100.90.180.87:11434`，`OLLAMA_IGPU_ENABLE=1`；**只绑 Tailscale IP，不绑 localhost**（裸 `ollama list` 报错，须 `OLLAMA_HOST=http://100.90.180.87:11434 ollama list`）；模型 `qwen3:8b`、`qwen3:8b-64k`（各 5.2GB，Q4_K_M，8.2B，均支持 completion/tools/thinking）。
- FCC 网关：`0.0.0.0:8082` 在监听，systemd 用户服务 `fcc-server.service`（FCC 6.19.6）active running；base URL `http://127.0.0.1:8082`，OpenAI 兼容 `/v1`；**Proxy Auth 已开启**（无 token 调 `/v1/models` 返回 HTTP 401；token 在笔记本 `~/.fcc/.env` 的 `ANTHROPIC_AUTH_TOKEN`，只在笔记本侧就地使用）；**必须 `stream=true`**（非流式在 Ollama 路径全部 500，FCC 6.19.6 bug，`Decimal is not JSON serializable`）；`/v1/models`（带 token）HTTP 200，共 104 个模型。
- dsh-our-free-model 网关：`127.0.0.1:18900` 在监听，node 进程 PID 23641（nohup 方式，自 11 月 12 日运行，**重启不自动恢复**）；key 为网关自身的 `forwardKey`（存 `~/.our-free-model/settings.json`）；`/v1/models`（带 key）HTTP 200，共 27 个模型；非流式即可。
- hub（美国 VPS，Tailscale 100.125.193.42:3001）：从笔记本 curl `/v1/models`（不带 key）HTTP 401，0.81s，连通；模型清单未验证（需 key），不列入已确认清单。
- pytest：笔记本未装（`No module named pytest`），跑自测前须先装。
- **Claude Code CLI：未安装**（`which claude` 无结果，无 `~/.claude.json`、`~/.claude/`，无 `ANTHROPIC_*` 环境变量）；FCC 自带 `fcc-claude` 启动器，但运行即报 `Could not find Claude Code command: claude`，提示 `npm install -g @anthropic-ai/claude-code`；启动器在、底层 CLI 不在，**后端指向未经实测**（按设计应指向 FCC 代理 127.0.0.1:8082，装好后须验证）。node/npm 在 `~/node-v22/bin`（node v22，含 npm/npx），不在默认 SSH PATH 内，安装须用全路径。另有 `~/.local/bin/pi`、`hermes`、`fcc-aider`、`fcc-codex`、`fcc-opencode` 等现成 CLI。

---

## 1. 模型级别

### 证据

- 3B（qwen2.5:3b）与 7B coder（qwen2.5-coder:7b）都在调试上失败，且失败模式不同：3B 倾向复述原文、输出截断；7B 生成干净、无截断/语法错误，但同样定位不到调用不一致处，第二轮自我重复（输出与第一轮逐字节相同），只做症状级改动（`isdir` 分支，没补 return）。
- 两轮都是在一次性调用、无工具、无迭代的条件下失败的；提示词里没有显式契约。单凭“7B 失败”不能推出“更大就一定行”，也不能推出“更大也没用”——模型级别与提示词、agent 是三个独立变量，本轮只换了模型级别，另两个变量未动。
- 7B 在盒内 CPU 上生成约 9 tok/s（验活），自修单任务 130.9–299.8 秒（提示词约 9K–19K 字符，输出仅约 140/170 token，大部分时间花在提示词处理上）；内存偏紧（加载时 available 约 35Mi），未 OOM。笔记本 16 核 / 可用 10Gi，本地 8B 推理条件优于盒子，但仍是 CPU，无 GPU。

### 结论：首选与备用（均为笔记本上现成可用、免费，不须用户新领 Key）

- **首选：DeepSeek-V4.1-Flash，经 FCC（Coarena `deepseek-v4-1-flash-1017`）**。调用方式：Claude Code 经 FCC 127.0.0.1:8082，模型名 `deepseek-v4-1-flash-1017`，须 `stream=true`，Proxy Auth token 走笔记本 `~/.fcc/.env` 现有配置。实测：最小调用（max_tokens=1，stream=true）HTTP 200，6.33 秒（TTFB 5.20 秒）。
- 选它的理由（三条，均为已验证事实）：①它是笔记本上已验证可用的最强免费模型之一——API 级大模型（DeepSeek V4.1 系列，参数量级远超 7B，以推理与代码见长），不是 7–8B 本地模型；②已实测可用（HTTP 200），不须新领 Key、不须新配网关；③走 FCC（systemd 自启），agent 的后端就是 FCC，模型与 agent 同一路，不另起炉灶。
- **备用 1：nemotron-3.5-lightning-30b-a3b，经 FCC（NVIDIA NIM）**。模型名 `anthropic/nvidia_nim/nvidia/nemotron-3.5-lightning-30b-a3b`。实测：最小调用 HTTP 200，1.74 秒（本次实测最快）。30B 级，推理快；若 DeepSeek 路径失败（超时、限流、输出异常），切此模型重试。
- **备用 2：LongCat-2.5，经 dsh 网关（`longcat-2.5-free`）**。实测：最小调用（max_tokens=1，非流式）HTTP 200，4.33 秒。LongCat-2.5 是辩论与 hub 的主力模型，已在多轮任务中验证可用；dsh 网关为 nohup 运行（重启不自动恢复），使用前须先确认端口 18900 仍在监听。
- **备用 3（另一网关同模型）：DeepSeek-V4.1-Flash，经 dsh 网关（`deepseek-v4.1-flash-free`）**。实测：最小调用 HTTP 200，2.29 秒，非流式即可。若 FCC 路径整体不可用，改走 dsh 调同一模型。
- **明确排除作首选：本地 `qwen3:8b` / `qwen3:8b-64k`**。理由：它是与已失败的 7B coder 同一量级（8.2B）的本地模型，盒内两轮已证明该量级在一次性调用下调不通；把它作首选等于重复已失败的实验。它只在全部 API 路径都不可用时作最后兜底，且届时结论须写明“本地 8B 仍不足”。
- **不作首选、只作未来升级项**：Coarena 清单里的 `claude-sonnet-5-5`、`claude-opus-5-5` 等更大模型——只在清单里出现，未实测可用，不列入本次首选/备用；若 DeepSeek 与 nemotron 两路都失败，再评估是否实测它们。

### 本项结论的边界

- 模型级别只是三个变量之一。首选 DeepSeek-V4.1-Flash 的依据是“已验证可用的最强免费模型 + API 级”，不是“它一定能调通”。能不能调通由第二段实搭建的结果判定；若仍失败，须在报告里写清是模型、提示词、agent 三者中哪一环仍不足，不许把失败笼统归于“模型不够”。

---

## 2. 提示词

### 盒内两轮提示词缺了什么（证据）

- 盒内提示词只含：bug 现象 + 自测失败输出全文 + 相关脚本全文 + 自测脚本全文；要求“只输出改过的完整函数”。缺三样：①调用链与返回值契约没有显式写出，模型须自己从代码里反推接口；②没有“先说根因、再改动”的约束，模型直接跳到改代码；③没有验证要求，模型输出后不跑测试、不知道自己改得对不对（7B 第一轮的 `isdir` 改动把崩溃点从 move_order 推到 main，模型自己完全不知道）。
- 机械套用规则（输出与原文相同或语法不通过时不应用）只能过滤无效输出，不能纠正错误定位；7B 第二轮自我重复（与第一轮逐字节相同）无人发现、无机制纠正。

### 提示词须包含的东西（调试契约，五条，缺一不可）

1. **失败证据全文**：完整 traceback（文件、行号、函数名、错误类型与消息）+ 自测失败输出全文，不截断、不摘要。traceback 是定位的唯一可靠起点。
2. **调用链（显式写出，不让模型反推）**：沿 traceback 逐级列出调用链，例如执行器 `main L303 → process_one L236 → move_order L66`，并对链上每个函数写清：调用方传了什么实参、被调方收到了什么、被调方返回了什么、调用方拿到返回值后做了什么。契约以表格写出，不许只写“请检查调用”。
3. **接口契约表（从自测断言与接口规范抄，不许模型自己编）**：对链上每个函数，写清输入契约（参数名、个数、类型、含义）与输出契约（返回值类型、键名、含义），并注明契约来源（自测脚本哪一行断言、接口规范哪一节）。例如 fillwatch：自测取 `computed_orders` 键，契约表须写明输出字典必须含 `computed_orders` 键；执行器：`move_order` 须返回结果（调用方 `result.get("kind")` 依赖它），契约表须写明返回值不得为 None。
4. **根因先于改动**：模型在改任何代码之前，必须先用一句话写出根因（“根因是 X 调用 Y 时传了 Z，而 Y 期望 W”），并指明根因在哪一方（调用方 / 被调方 / 契约本身）。根因句须与 traceback 的行号对得上；对不上即判定未定位，不许改代码。
5. **最小改动 + 验证闭环**：只改不一致的一方，不重写无关代码；改完必须跑对应的自测（`python3 tests/test_<t>.py --base <virtual 目录>`），报通过数/总数；仍失败则回到第 2 条重做，最多 3 轮；3 轮未过即停，写清差在哪，不许硬编通过。

### 调试用提示词模板（可直接用，`{...}` 为占位符）

```text
你是调试员，任务是修一个已定位到文件的 bug。只改不一致的一方，不重写无关代码。

（全文，不摘要）
自测：{python3 tests/test_<t>.py --base <virtual 目录> 的完整输出}
Traceback：
{完整 traceback，全文}

（沿 traceback 逐级列出）
{main Lx → f Lx → g Lx}：对链上每个函数，写清调用方传了什么实参、被调方收到了什么、被调方返回了什么、调用方拿到返回值后做了什么。

（从自测断言与接口规范抄，不许自己编）
| 函数 | 输入契约（参数名、个数、类型、含义） | 输出契约（返回值类型、键名、含义） | 契约来源（自测哪一行 / 接口规范哪一节） |
| {函数名} | {…} | {…} | {…} |

（按顺序做，不许跳步）
1. 对照契约表与调用链，逐项比对：调用方传的实参与被调方期望的参数是否一致；被调方返回的值与调用方取用的键/属性是否一致。
2. 用一句话写出根因，格式：“根因是 {调用方/被调方} 在 {文件:行号} 处 {传了什么/返回了什么}，而 {另一方} 期望 {什么}。”根因句须与 traceback 的行号对得上；对不上即判定未定位，停下重读契约表，不许改代码。
3. 只改不一致的一方，最小改动；改完跑对应的自测并报通过数/总数。
4. 仍失败则回到第 1 步，最多 3 轮；3 轮未过即停，写清差在哪。


{自测脚本内的断言原文，或“合规 4/4、门控 9/9、执行器 14/14、fillwatch 5/5，合计 32/32；本轮目标合计 ≥26/32”}
```

### 与盒内两轮提示词的区别

| 项 | 盒内两轮 | 本模板 |
|---|---|---|
| 契约 | 无，模型自己从代码里反推 | 显式契约表，从自测断言与接口规范抄 |
| 根因 | 无要求，模型直接改代码 | 根因句先于改动，须与 traceback 行号对上 |
| 工具/验证 | 一次性输出，机械替换，不跑测试 | 改完必须跑对应自测，报通过数，失败即迭代 |
| 重复 | 无机制发现自我重复（fixB2 与 fixB1 逐字节相同无人发现） | 每轮须先报上一轮改动与结果，重复输出即判定未定位 |
| 通过标准 | 自测脚本全文给了，但未要求模型逐项对断言 | 通过标准逐项列出，改完逐项核对 |

---

## 3. AI agent

### 一次性 LLM 调用 vs 带工具可迭代的编码 agent（证据）

- 盒内两轮都是一次性 LLM 调用：给提示词、拿输出，无工具、无迭代。模型不能跑测试验证自己的改动（7B 第一轮的 `isdir` 改动把崩溃点推后，模型自己不知道）；不能读调用方的实际传参（只能凭提示词里的全文代码反推）；不能发现自己的重复（fixB2 与 fixB1 逐字节相同，无机制纠正）；输出截断时（3B 第一轮）整个输出作废。
- 带工具可迭代的 agent（Claude Code 类）与之的根本区别不是“模型更强”，而是**闭环**：读文件 → 跑测试 → 读 traceback → 定位根因 → 改代码 → 重跑测试，直到通过或轮数用完。每一步的输出都是下一轮的输入，错误不会原样重复三轮而不被发现。

### 结论：用 Claude Code（经 FCC），须先装 CLI

- **首选 agent：Claude Code CLI，经 FCC 127.0.0.1:8082 作后端，模型用 DeepSeek-V4.1-Flash（Coarena `deepseek-v4-1-flash-1017`）**。
- 选它的理由：①Claude Code 是带工具循环的编码 agent（读文件、改代码、跑命令、跑测试、迭代），正好补上盒内一次性调用缺的闭环；②FCC 就是为 Claude Code 配的网关（Free Claude Code proxy），已聚合多路免费模型，agent 与模型同一路；③笔记本上 node/npm 现成（`~/node-v22/bin`，node v22），安装只需一条命令。
- **唯一缺口（已验证）：Claude Code CLI 未安装**。安装命令（用全路径，因 node 不在默认 SSH PATH 内）：
```bash
~/node-v22/bin/npm install -g @anthropic-ai/claude-code
```
装好后须验证两件事再开工：①`claude --version` 能出版本号；②后端指向 FCC（`fcc-claude` 启动器按设计应指向 127.0.0.1:8082，装好后以实测为准，不预支结论）。
- 若 `claude --version` 仍不可用，检查 npm 全局 bin 目录是否在 PATH 内（用 `~/node-v22/bin/npm root -g` 查，再把该 bin 目录加进 PATH 或用全路径调 `claude`）。
- **备用 agent（按顺序）**：
1. `fcc-aider` / `fcc-opencode`（笔记本 `~/.local/bin/` 现成）：同为带工具循环的编码 CLI，走 FCC 同一路；若 Claude Code 装不上或跑不起来，改用其中之一，工具清单与迭代循环不变。
2. 沙箱驱动的工具循环（最后兜底）：沙箱侧写驱动脚本，经 FCC/dsh API 调模型，读文件与跑测试经 `laptop_ssh.sh` 在笔记本上做，改代码由驱动按函数名替换后跑测试验证。此路 agent 不在笔记本上，但闭环仍在（跑测试→读 traceback→改→重跑），只是驱动在沙箱；仅当笔记本上所有 agent CLI 都不可用时才用。
- **明确不用的路**：盒内的一次性 LLM 调用（已两轮证伪）；本地 `qwen3:8b` 作 agent 模型（与已失败的 7B 同量级，不作首选，见 §1）。

### Agent 工具清单与迭代循环

- 工具清单（缺一不可）：Read（读文件：文档、脚本、自测、traceback）、Edit（改代码：按函数名或行号最小改动）、Bash（跑命令：`py_compile`、自测、虚拟程序 init/submit/run/snapshot、quota/log 核对）、TodoWrite（可选，记轮次与通过数）。
- 迭代循环（每轮）：
1. 跑对应的自测，取完整失败输出。
2. 读 traceback，沿调用链读调用方与被调方，填 §2 的契约表。
3. 写根因句（须与 traceback 行号对上），否则停下重读，不改代码。
4. 最小改动（只改不一致的一方）。
5. 重跑对应自测，报通过数/总数；通过即进下一步，未通过即回第 1 步。
6. 每 bug 最多 3 轮；3 轮未过即停，写清差在哪，不许硬编通过。
- 纪律（与盒内两轮相同，继续执行）：沙箱侧不代写代码、不给确定性补丁；调试须由笔记本上的 agent 自己用工具迭代完成；每轮产物用轮次后缀区分（`fixC1/`、`fixC2/`…，防覆盖）；agent 的每轮改动、根因句、自测通过数须记入日志。

---

## 4. 搭建流程（笔记本上可复现）

干净目录：笔记本 `~/ops-build-laptop/`（与盒内 `~/ops-build/` 区分；`~` 下无 ab- 克隆，搭建时新建）。全程只读 GitHub 文档写四脚本；虚拟程序只作执行与验证环境；不碰真实 trade_log/台账/总纲、不登录叩富网、不连华为 VPS。

| 步 | 做什么 | 输入 | 输出 | 通过标准 | 失败回退 |
|---|---|---|---|---|---|
| 0. 环境准备 | 克隆 ab- 到 `~/ops-build-laptop/`（git 在 `~/.local/bin/git`，须设 `GIT_EXEC_PATH`）；装 Claude Code CLI（`~/node-v22/bin/npm install -g @anthropic-ai/claude-code`）；装 pytest（`pip install pytest` 或 `pip3 install pytest`）；验证 FCC 监听与模型（`curl 127.0.0.1:8082/v1/models` 带 token，须 200；最小调用 DeepSeek-V4.1-Flash 须 200）；验证虚拟程序能跑（`python3 virtual_ops.py init` + `python3 selftest.py` 须全过，证明环境本身没问题） | GitHub 仓库、npm、pip、FCC token（笔记本现有配置） | 克隆完成的 `~/ops-build-laptop/`、可用的 `claude`、pytest、FCC 模型实测 200、虚拟自测全过 | 全部通过才进下一步 | Claude Code 装不上 → 改用 `fcc-aider`/`fcc-opencode`；FCC 模型不通 → 切备用模型（nemotron / dsh DeepSeek / LongCat）；pytest 装不上 → 用 `python3 -m pytest` 或直接跑自测脚本（自测脚本本身不依赖 pytest 框架，只须 python3） |
| 1. 读文档 | agent 读接口规范（837 行）、总纲 01、P1 四份记录（门控/fillwatch/记账/接口）、虚拟程序 README；只读，不写代码 | GitHub 文档（克隆到本地的 ab-） | agent 对四脚本职责的复述（合规/执行器/门控/fillwatch 各管什么、接口契约要点） | 复述须与接口规范一致（沙箱侧抽查：四脚本职责、订单队列命名、合规清单要点） | 复述不一致 → 让 agent 重读对应章节，不许直接给答案 |
| 2. 写四脚本 | agent 在 `~/ops-build-laptop/` 写 `order_compliance.py`、`order_executor.py`、`gate_local.py`、`fillwatch_rehang.py`（Python，仅标准库）；依据只许是接口规范、总纲 01、P1 记录、虚拟程序 README 与 `virtual/` 内的 `virtual_ops.py`/`nodes.json`（字段名与口径以虚拟程序为准）；**不许抄盒内已写的四脚本**（`docs/实施记录/ops_build_test_20261113_files/` 内的 `order_*.py`、`gate_local.py`、`fillwatch_rehang.py`、`fixA/`、`fixB/` 一律不许作模板，只许在复核时对照自测断言） | 接口规范、总纲 01、P1 记录、虚拟程序 | 四脚本 + `py_compile` 通过 | `py_compile` 4/4 通过；每脚本含 `if __name__ == "__main__"` 入口（盒内初版缺入口致静默退出的教训）；CLI 形式与接口规范 §8.1 一致（位置参数，不许自造 `--order_file`/`--gate_file`/`--fill_file`） | 语法不通过 → agent 自己读报错重写，不许沙箱代写 |
| 3. 跑四项自测（基线） | 在搭建目录跑 `python3 tests/test_<t>.py --base <克隆的 virtual 目录>`（四份自测在 GitHub 的 `docs/实施记录/ops_build_test_20261113_files/tests/` 内，搭建时复制到 `~/ops-build-laptop/tests/`）；记基线通过数 | 四脚本 + 自测脚本 | 基线通过数（合规 x/4、门控 x/9、执行器 x/14、fillwatch x/5，合计 x/32） | 有基线数即可（基线本身不要求达标，盒内初版基线 0 项实质通过亦可接受） | 自测脚本跑不起来（缺模块/路径错）→ 先修环境（PYTHONPATH、--base 路径），不许改自测断言 |
| 4. 调试迭代 | agent 按 §3 迭代循环修 bug，每 bug 最多 3 轮；每轮用 §2 模板（契约表 + 根因句先于改动 + 改完跑自测）；每轮产物用轮次后缀区分（`fixC1/`、`fixC2/`…） | 基线失败输出 + 完整 traceback + 契约表 | 每轮的根因句、改动 diff、自测通过数 | 合计 ≥26/32（80%）即进下一步；每轮须有根因句与自测数，缺一即判定该轮无效 | 3 轮未达 80% → 停，写清差在哪、还缺什么（哪几项失败、根因是否定位、是否自我重复），不许硬编通过；不许沙箱代修 |
| 5. 对接验证 | 达 80% 后做：A 线卖单 601088 卖 200 @49.58 + B 线买单 600919 @12.98 500 股，经虚拟程序（`virtual_ops.py init` → 写订单 JSON → `submit` → `run` → `snapshot` → `quota`/`log` 核对）；核实合规通过、成交入账、快照 status ok 且不 stale、quota 四仓平衡、虚拟 trade_log 有 2 笔带 `///` 标记的成交行、节点股数更新正确 | 达标的四脚本 + 虚拟程序 | 对接验证结果（每项 PASS/FAIL + 证据） | 全部 PASS 才算对接通过 | 任一项 FAIL → 回第 4 步修（若轮数已用完则停，写清差在哪）；未达 80% 按规则跳过对接，记为“未达标，对接未做” |
| 6. 写报告推 GitHub | 更新 `docs/实施记录/ops_build_test_20261113.md`，追加“笔记本搭建”章节（模型、agent、每轮改动、自测最终通过率、对接结果、完整结论能/部分能/不能＋依据）；产物放同名 `_files/`（四脚本 + 自测日志 + 轮次副本，`*.log`/`*.jsonl` 只留沙箱、不进 GitHub）；CHANGELOG.md 2026-11-13 节加一条；推 GitHub | 全部产物 | GitHub commit | 报告须含完整结论与依据；若未达 80%，须写清差在哪、还缺什么，不许谎报通过 | 推送失败 → 先核对本地与远端 HEAD，不强推、不改历史 |

### 风险与已知坑（搭建前须读）

- FCC 非流式 500 bug：调用方一律 `stream=true`（Claude Code 经 FCC 时须确认其流式设置；若 agent 调模型报 500，先查是否走了非流式）。
- Ollama 只绑 Tailscale IP（100.90.180.87:11434），不绑 localhost；agent 若调本地 Ollama 须用该地址。
- dsh 网关为 nohup 运行，重启不自动恢复；使用前确认端口 18900 仍在监听。
- `laptop_ssh.sh '<命令>'` 形式脚本不接受（报 cannot parse host），须用 `laptop_ssh.sh madaha@100.90.180.87 '<命令>'`。
- 笔记本 Chrome 常驻但本次不碰浏览器执行层（`laptop_order.py` 不在验证范围内，只验脚本、不实测下单）。
- 沙箱侧不代写代码、不给确定性补丁；调试须由笔记本上的 agent 自己用工具迭代完成。
- 盒内两轮的教训：段顺序影响名字定义（helpers 段须在 `if __name__` 段之前）；缺 `__main__` 入口致静默退出；datetime 类/模块名冲突；非标准库 import；CLI 参数形式须与真实一致。这些已补进接口规范 §8.1，搭建时须逐项核对。

## 预案结论（四项）

1. **模型**：首选 DeepSeek-V4.1-Flash（FCC Coarena `deepseek-v4-1-flash-1017`，实测 6.33 秒）；备用 nemotron-3.5-lightning-30b-a3b（FCC NVIDIA NIM，实测 1.74 秒）、LongCat-2.5（dsh `longcat-2.5-free`，实测 4.33 秒）、DeepSeek-V4.1-Flash 经 dsh（`deepseek-v4.1-flash-free`，实测 2.29 秒）；本地 `qwen3:8b` 明确不作首选。
2. **提示词**：调试契约五条（失败证据全文、显式调用链、接口契约表、根因先于改动、最小改动 + 验证闭环），附可直接用的模板；与盒内两轮的区别是契约显式化、根因前置、改完必跑测试、重复即判定未定位。
3. **Agent**：首选 Claude Code CLI 经 FCC（须先装 CLI，一条 npm 命令；后端指向装好后实测验证）；备用 `fcc-aider`/`fcc-opencode`，最后兜底沙箱驱动的工具循环。工具清单：Read、Edit、Bash、（可选 TodoWrite）；迭代循环：跑测试 → 读 traceback → 填契约表 → 写根因句 → 最小改动 → 重跑测试。
4. **搭建流程**：六步（环境准备 → 读文档 → 写四脚本 → 跑自测基线 → 调试迭代至 ≥80% → 对接验证 → 写报告推 GitHub），每步有输入/输出/通过标准/失败回退；干净目录为笔记本 `~/ops-build-laptop/`。
