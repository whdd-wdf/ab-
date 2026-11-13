# 第二套独立系统预案（2026-11-13）

> 用户 2026-11-13 18:19 下令：在笔记本上搭建一套与现系统独立的完整另一套系统（浏览器、chief agent、监管系统、执行系统全在笔记本上，不存在通道问题，接口对接由笔记本的 chief agent 完成）；18:21 点选“独立账户，各跑各的”——第二套用另开的叩富模拟账户、独立仓位（从 100 万重新开始），与现系统（股神037_4560 / 小白菜）完全分开，互不干扰。
>
> 用户同日补充 chief agent 要求：chief agent 要有两个对话通道，最好能在一个讨论组里——①一个由 Muse 交流的通道（chief agent 能与沙箱的 Muse 对话）；②一个接飞书（Feishu）的通道（用户用飞书与 chief agent 对话）；③最好两者在一个讨论组里（Muse、用户经飞书、chief agent 三方能在同一个讨论组里一起讨论）。
>
> 本预案只依据已验证事实写结论；凡属推断处明确标注“推断”，不把推断写成结论。预案通过、用户点头后才开工搭建；写预案阶段不装浏览器、不建叩富账户、不写四脚本。
>
> 用户 2026-11-13 晚实测确认：**cofool 现在（随时）可以下单撤单，整个流程可以在非交易时间试跑。** 影响：第 0 步唯一未过项与第 6/7 步的下单撤单验证不再受交易窗口限制，非交易时间即可用真实下单后立即撤单跑通（不留持仓；真实下单仍须用户点头，见文末补充节）。

## 背景与已验证事实

### 现系统（第一套）

- A/B 线交易系统，总纲在 `docs/01-总览与两线分工.md`（docs/01–07），接口规范 `docs/操作与管控接口规范.md`（837 行），虚拟程序 `~/workspace/ab-/virtual/`（管控侧已验证端到端跑通），操作侧四脚本（合规/执行器/门控/fillwatch）已在笔记本上用 Claude Code + DeepSeek-V4.1-Flash 一次搭通（基线 36/36、对接全过，commit 80554f0，搭建执行 skill 见 `docs/搭建执行技能.md`）。
- 现系统执行层：`~/workspace/goals/a/hidden_files/laptop_order.py`（笔记本 `~/laptop_order.py`），经 CDP 驱动现 Chrome 下单；`cofool_driver.py` 第 47 行写死 `CDP_PORT = 9222`（`CDP_HTTP = "http://127.0.0.1:9222"`），第二套须把执行层改成可配端口或另拷一份改端口。
- 现系统分工：华为 VPS（123.60.222.204，Tailscale 100.74.158.35）为合规审核与执行调度，笔记本 Chrome 为下单执行层，沙箱 Muse 为监督与决策；P1 脱离 Muse 正在进行（华为自备门控、fillwatch compare、记账轻量版已落地；B 线 intraday 切换 2026-11-13 15:10 验证未通过，未切换）。

### 笔记本环境（2026-11-13 18:23 只读核查 + 18:24 复核，宏碁 Nitro 5 madaha-Nitro-AN515-47）

- 硬件：R7 6800H，16 核；内存总量 13Gi，可用 10Gi；磁盘 / 分区 468G，已用 30G，剩余 414G；独显已坏、核显 680M；Ubuntu 24.04；Python 3.12.3。
- **Chrome 是便携解压版，不在系统路径**：`which google-chrome chromium chromium-browser brave-browser microsoft-edge` 均无结果；`/opt/google/chrome/chrome` 不存在；实际二进制在 `/home/madaha/chrome-install/extracted/opt/google/chrome/chrome`，版本 `Google Chrome 157.0.8103.50`；同一目录下另有安装包 `google-chrome-stable_current_amd64.deb`（版本待核实，见 §1）。`~/.config` 下有两个 profile 目录：`cofool-chrome`、`google-chrome`。
- **现 Chrome 在跑**：`cofool-chrome.service` 自 2026-11-12 09:08 运行中，Main PID 57941，内存 342.1M，启动命令含 `--headless=new --no-sandbox --disable-gpu --remote-debugging-port=9222 --user-data-dir=/home/madaha/.config/cofool-chrome --window-size=1280,800 about:blank`；CDP 9222 在监听且可通（`/json/version` 返回 `Chrome/157.0.8103.50`、`Protocol-Version: 1.3`）；**9223、9224 均空闲**。
- **apt/snap**：`chromium-browser` 有 apt 候选 `2:1snap1-0ubuntu2`（实为转 snap 的过渡包，源 `cn.archive.ubuntu.com noble/universe`）；`chromium` 无候选；`brave-browser`、`microsoft-edge-stable` 在 apt 源中无包（`/etc/apt/sources.list.d/` 无 brave/microsoft 源）；snap 已装 firefox，无 chromium/brave。
- **Claude Code 已装，但不在默认 PATH**：`which claude` 无结果，`~/.local/bin/claude` 不存在，`~/.local/bin/fcc-claude --version` 在裸 PATH 下报 `Could not find Claude Code command: claude`；实测本体在 `~/node-v22/bin/claude`（符号链接到 `../lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe`），`~/node-v22/bin/` 内含 bun、bunx、claude、corepack、node、npm、npx；`export PATH=$HOME/node-v22/bin:$PATH` 后 `claude --version` 与 `fcc-claude --version` 均返回 `2.1.323 (Claude Code)`。注意：`~/node-v22/bin/npm root -g` 在裸 PATH 下报 `/usr/bin/env: "node": 没有那个文件或目录`（npm 的 shebang 用 `env node`，node 不在 PATH），调 npm 须先把 `~/node-v22/bin` 加进 PATH。`~/.local/bin/fcc-claude` 是符号链接到 `/home/madaha/.local/share/uv/tools/free-claude-code/bin/fcc-claude`。
- **FCC 网关在跑**：`fcc-server.service`（FCC 6.19.6）自 2026-11-12 16:47 运行中，Main PID 71313；`curl 127.0.0.1:8082/v1/models` 不带 token 返回 401（预期表现，服务在跑）；Proxy Auth 已开，模型须用带前缀完整 ID（裸名会回退到默认模型），调用须 `stream=true`（非流式 500）。
- **dsh 网关**：127.0.0.1:18900，nohup 运行，重启不自动恢复（2026-11-12 核查时在监听）。
- **Ollama 在跑**：`ollama.service` 自 2026-11-11 运行中，模型 `qwen3:8b`、`qwen3:8b-64k`；**只监听 100.90.180.87:11434，不监听 127.0.0.1:11434**（`curl 127.0.0.1:11434/api/tags` 不通）。
- **第一套搭建目录仍在**：`~/ops-build-laptop/`（含四脚本、tests、virtual），第二套须另建目录、不得覆盖或混用。
- 连接脚本：沙箱经 `laptop_ssh.sh madaha@100.90.180.87 '<命令>'` 连笔记本（Tailscale SSH，实测可用，单次约 4–5 秒）。

### 飞书通道的事实（2026-11-13 网页查证，OpenClaw/Qwen Code 飞书频道文档与飞书开放平台说明）

- **应用机器人（App bot，全功能，双向）**：在飞书开放平台（open.feishu.cn）创建企业自建应用，开启“机器人”能力；事件订阅选“使用长连接”（WebSocket），订阅 `im.message.receive_v1`（接收消息）；**无需公网 URL、无需 SSL 证书**，长连接由笔记本主动向飞书服务器发起出站连接，NAT/防火墙后可正常工作。所需权限：`im:message`（读发消息）、`im:message:send_as_bot`（以机器人身份发消息），群聊另需群消息读取权限（`im:message.group_msg` 或 `im:message.group_at_msg:readonly`）；改权限/事件后须创建新版本并发布（可能须企业管理员审核通过才生效）。
- **群聊**：机器人可进私聊与群聊；加进群后默认须 @提及才响应（`requireMention: true`）；一个群最多可添加 99 个机器人；机器人默认不能进外部群，须在应用设置里允许“对外共享 / 外部群可用”，且群须允许添加外部机器人。
- **同一应用只能有一个长连接消费者**：新服务器跑起来后，务必停掉其它机器上的旧转发器，否则事件会被两边分摊（漏收）。
- **自定义机器人（webhook，仅单向推送）**：在群内“设置 → 群机器人 → 添加自定义机器人”创建，得 webhook 地址 `https://open.feishu.cn/open-apis/bot/v2/hook/{id}`；外部系统 POST 即可以机器人身份在群里发消息（文本、富文本、卡片、图片）；**只能发、不能收**；限流单租户单机器人 100 次/分钟、5 次/秒，请求体 ≤20KB。本预案的 chief agent 须双向对话，自定义机器人不够用，只能作备用推送手段。

### Muse 通道的事实

- 沙箱→笔记本方向已通：`laptop_ssh.sh madaha@100.90.180.87 '<命令>'`（Tailscale SSH，2026-11-13 多次实测可用，单次约 4–5 秒）。
- 笔记本→沙箱方向未建立：沙箱 VM 的 Tailscale 地址与 SSH 服务是否对笔记本开放，未核实；华为 VPS 反向连不上沙箱（已验证），笔记本反向连沙箱须在搭建时实测，不能默认可用。
- 结论：Muse 与 chief agent 之间没有现成的实时对话协议；可行的是**文件式异步消息通道**（见 §2），不是实时聊天。

### 两轮盒内验证的教训（本预案的依据）

- 盒内 qwen2.5:3b 与 qwen2.5-coder:7b 两轮均“部分能”（自测 23/32 = 71.9%，AI 自修两轮均零有效改动）；笔记本 Claude Code + DeepSeek-V4.1-Flash 一轮“能”（基线 36/36、对接全过、调试 0 轮）。胜在三点：带工具闭环（读文件、跑测试、迭代）+ 显式契约提示词（调用链与返回值契约表、根因句先于改动）+ API 级模型。本预案的模型、提示词、agent 三项沿用同一结论（详见 `docs/搭建执行技能.md`）。

---

## 1. 浏览器

### 候选与证据

| 候选 | 证据（2026-11-13 18:23 实测） | 结论 |
|---|---|---|
| 第二份便携版 Google Chrome 157.0.8103.50 | 与现 Chrome 同一版本、二进制已在笔记本上（`~/chrome-install/extracted/`）；安装包 `google-chrome-stable_current_amd64.deb` 也在同一目录（版本待核实，见下） | **首选** |
| Chromium（apt） | `chromium-browser` 有 apt 候选 `2:1snap1-0ubuntu2`，实为转 snap 的过渡包；须经 snap 商店下载安装 | 备用 |
| Brave / Edge | apt 源中无包，`apt-cache search` 无结果；须先加第三方源才能装 | 不作首选 |
| 第二个 Chrome profile（同一份 Chrome） | 现 Chrome 以 `--user-data-dir=/home/madaha/.config/cofool-chrome` 独占 profile 运行；同一份二进制可用不同 `--user-data-dir` 再起一个进程 | 可行但不推荐作首选（见下） |

### 结论：首选与备用

- **首选：第二份便携版 Google Chrome，与现 Chrome 同版本（157.0.8103.50）**。做法：用 `~/chrome-install/` 下已有的安装包再解压一份（或复制现 `extracted/` 目录）到独立路径（如 `~/sys2/chrome/`），独立 profile（如 `/home/madaha/.config/sys2-chrome`），独立 systemd 服务（如 `sys2-chrome.service`，`Restart=always`），CDP 端口 **9223**（已核实空闲）。选它的理由（三条，均为已验证事实）：①与现执行层已验证过的 Chrome 同版本，`laptop_order.py`/`cofool_driver.py` 的 CDP  primitives 不用重新验证浏览器兼容性；②二进制与安装包都已在笔记本上，不须下载、不须加源、不依赖 snap 商店；③与现 Chrome 进程、profile、端口完全隔离，互不干扰。
- **备用 1：同一份 Chrome 二进制 + 独立 profile 与端口**。做法：不新装浏览器，用现 `extracted/` 的 chrome 二进制另起一个进程，`--user-data-dir=/home/madaha/.config/sys2-chrome --remote-debugging-port=9223`。优点是零安装；缺点是两套系统共用一份二进制文件（升级/损坏会同时影响两边），隔离性不如首选。仅当首选的解压/复制出问题时用。
- **备用 2：Chromium（apt 转 snap）**。做法：`apt install chromium-browser`（实际走 snap 安装）。缺点：须 snap 商店联网下载；版本与 Chrome 157 可能不同，执行层须重新验证 CDP 兼容性；snap 版 Chromium 的沙箱/权限行为与 .deb 版 Chrome 有差异。仅当便携版 Chrome 路径不可用时用。
- **明确不用**：Brave/Edge（apt 无源，须加第三方源，未验证；且与现执行层验证过的 Chrome 157 不是同一版本，兼容性须重验）。

### 待核实（搭建第 1 步时做，不在本预案里预支结论）

- `~/chrome-install/google-chrome-stable_current_amd64.deb` 的版本号（`dpkg-deb -I` 或解压后跑 `--version`），是否与现 Chrome 157.0.8103.50 一致；不一致时仍可用，但须在搭建验证里跑一遍执行层 smoke test。
- 第二份 Chrome 的 CDP 9223 实测可通（`/json/version` 返回版本号与协议版本）。

### 与现 Chrome 的隔离方案

| 项 | 现系统 | 第二套系统 | 隔离方式 |
|---|---|---|---|
| 二进制 | `~/chrome-install/extracted/opt/google/chrome/chrome` | `~/sys2/chrome/` 下独立一份（首选） | 不同目录 |
| profile | `/home/madaha/.config/cofool-chrome` | `/home/madaha/.config/sys2-chrome` | 不同 `--user-data-dir` |
| CDP 端口 | 9222 | 9223 | 不同 `--remote-debugging-port` |
| systemd 服务 | `cofool-chrome.service` | `sys2-chrome.service`（新建，`Restart=always`） | 不同服务单元 |
| 登录态 | 现叩富账户（股神037_4560 / 小白菜） | 新叩富账户（见 §5） | 不同 profile，登录态天然隔离 |

---

## 2. chief agent

### chief agent 到底是什么（先说清，再设计）

- **Claude Code 不是 chief agent 本身**。Claude Code CLI 2.1.323 是带工具循环的编码 agent（读文件、改代码、跑命令、跑测试、迭代），按任务调用、跑完即退，不是常驻监督。把它直接当 chief agent，会缺三样：①没人按交易日时间表驱动它（谁在 08:00 叫它出表、10:00 叫它 trade-check）；②没人常驻收飞书消息（Claude Code 没有飞书长连接）；③没人把 Muse 的消息接进来（Claude Code 不监听沙箱）。
- **chief agent 是一个角色，由三件东西合起来担任**：
  1. **Agent 核心：Claude Code CLI 2.1.323**（经 FCC 调 DeepSeek-V4.1-Flash，完整模型 ID 见 `docs/搭建执行技能.md` §1）。它是“脑子”——读文档、做决策、写代码、跑验证。调用方式与第一套搭建相同：`~/.local/bin/fcc-claude` 启动器，`-p` 非交互模式，stdin 传提示词，nohup 后台跑、短命令轮询；**调用前必须把 `~/node-v22/bin` 加进 PATH**（裸 PATH 下 `fcc-claude` 报 `Could not find Claude Code command: claude`，已实测）。
  2. **驱动器：笔记本本地 systemd 定时器 + 调度脚本**。它是“闹钟与手脚”——按交易日时间表（接口规范 §10 的每日工作流，见 §3）在 08:00、09:20、10:00、13:05、14:30、15:05、16:53 等时点调用 agent 核心执行对应任务；同时轮询消息通道文件，把 Muse 与飞书的消息交给 agent 核心处理。
  3. **飞书监听器：常驻服务（systemd user 服务）**。它是“耳朵与嘴”——持有飞书 WebSocket 长连接，收群消息、发群消息；收到须 chief agent 处理的消息时，调用 agent 核心（或写入任务队列），把结果发回群里。
- **推断**（须在搭建时验证）：上述三件套是能拼起来的最小可行 chief agent；是否够用，由搭建验证（§7 第 7 步）判定，不在本预案里预支结论。

### 两个对话通道（用户补充要求）

#### 通道 1：Muse ↔ chief agent（沙箱 ↔ 笔记本）

- **技术实现：文件式异步消息通道，经现有 Tailscale SSH**。沙箱→笔记本方向已通（`laptop_ssh.sh`，单次约 4–5 秒）；笔记本→沙箱方向未建立，不依赖它。做法：
  - 笔记本上建消息目录（如 `~/sys2/inbox/`），两个追加式 JSONL 文件：`muse_to_chief.jsonl`（Muse 写给 chief agent 的指令/问题/复核意见）与 `chief_to_muse.jsonl`（chief agent 写给 Muse 的汇报/请示/报警）。
  - Muse 写消息：沙箱经 `laptop_ssh.sh` 在笔记本上追加一行（`echo '...' >> ~/sys2/inbox/muse_to_chief.jsonl`）；读 chief agent 的回复：沙箱经 `laptop_ssh.sh` 读 `chief_to_muse.jsonl` 尾部。
  - chief agent 读 Muse 的消息：驱动器轮询 `muse_to_chief.jsonl`（如每 60 秒），有新行即调用 agent 核心处理；写回复：追加到 `chief_to_muse.jsonl`。
  - 每条消息带字段：`time`、`from`、`to`、`kind`（指令/汇报/请示/报警/复核）、`body`、`need_reply`（是否须回复）。去重与顺序以文件行号为准，不另建队列。
- **延迟**：单向约 5 秒（SSH）+ 轮询间隔（60 秒）≈ 1 分钟级，不是实时聊天。**推断**：该延迟对监督、复核、日汇总够用，对盘中紧急决策不够用——盘中紧急决策 chief agent 按规则自行定、事后汇报，不等 Muse 回复（与现系统“规则内决定自行定”的总则一致）。
- **备用**：若搭建时实测笔记本能直连沙箱 Tailscale 地址并调沙箱的 HTTP/SSH 服务，可把文件通道升级为直连 API；未实测前不采用，文件通道是保底方案。

#### 通道 2：用户 ↔ chief agent（经飞书）

- **技术实现：飞书应用机器人 + WebSocket 长连接**（依据见“背景与已验证事实”飞书一节）。做法：
  - 在飞书开放平台创建企业自建应用，开启“机器人”能力；事件订阅选“使用长连接”，订阅 `im.message.receive_v1`；权限开 `im:message`、`im:message:send_as_bot` 与群消息读取权限；创建新版本并发布（可能须企业管理员审核）。
  - 笔记本上跑飞书监听器常驻服务（systemd user 服务，`Restart=always`），持 WebSocket 长连接收消息；收到消息后按规则处理（见下“通道与职责的配合”），须 agent 核心判断的调用 Claude Code，结果经长连接发回群里。
  - App ID 与 App Secret 只存笔记本（如 `~/sys2/config/feishu.env`，600 权限），**绝不进 GitHub、绝不打印、绝不经聊天发送**（与现系统 Key/密码纪律一致）。
  - **不采用自定义机器人 webhook**：它只能发、不能收，chief agent 须双向对话，不够用；可作备用推送手段（见下）。
- **延迟**：长连接近实时（秒级），用户在飞书里的消息 chief agent 秒级收到；须 agent 核心判断的，另加一次 Claude Code 调用的时间（DeepSeek-V4.1-Flash 实测最小调用约 6 秒，长提示词更长）。

#### “一个讨论组”如何落地

- **组建在飞书里**：建一个飞书群，成员为用户 + chief agent 机器人（应用机器人加进群）。群里默认须 @机器人 才响应；为让 chief agent 能主动汇报，须在应用权限里开群消息读取权限（`im:message.group_msg` 或 `im:message.group_at_msg:readonly`，二选一按需开），并把群策略设为允许机器人收全群消息或至少收 @消息。
- **Muse 进不了飞书群**：Muse 没有飞书账号/机器人身份，无法直接成为群成员。**Muse 在群里的存在方式是经 chief agent 中转**：
  - Muse → 群：Muse 经通道 1 把消息写到笔记本（`muse_to_chief.jsonl`，`kind` 标为“转群”）；chief agent 收到后以机器人身份发进群，**正文前加 `[Muse]` 前缀**标明发言人（如 `[Muse] 复核意见：……`），用户在群里看到的就是 Muse 的话。
  - 群 → Muse：群里用户 @chief agent 并点名 Muse（如“@机器人 问 Muse ……”），或 chief agent 判断某条群消息须 Muse 复核时，chief agent 把该消息原文写进 `chief_to_muse.jsonl`（`kind` 标为“转 Muse”）；Muse 经通道 1 读到后回复，chief agent 再把回复以 `[Muse]` 前缀发进群。
  - 用户在群里直接与 chief agent 对话时，不经过 Muse，chief agent 直接回（规则内的事自己定）。
- **延迟**：用户 ↔ chief agent 是秒级；Muse 经中转的一来一回约 1–2 分钟（SSH + 轮询）。三方在同一个群里讨论时，Muse 的发言会有 1–2 分钟滞后——须在群规里写明（chief agent 盘中按规则先定、Muse 事后复核，不等 Muse 到场才动手）。
- **备用推送手段（可选）**：另在群里加一个自定义机器人 webhook（仅发），chief agent 遇飞书长连接中断时，经 webhook 把报警推到群里（单向保底）；长连接恢复后切回主通道。是否加，由搭建时决定，不强制。

#### 通道与 chief agent 职责的配合

| 场景 | 谁先动 | 走哪个通道 | chief agent 做什么 | Muse 做什么 |
|---|---|---|---|---|
| 日常汇报（早盘出表、成交补挂、收盘小结） | chief agent 定时任务完成后 | 飞书群（机器人发）+ 写 `chief_to_muse.jsonl` 一份 | 按接口规范 §10 的时间表执行并汇报 | 读汇报，异常才介入 |
| 异常报警（快照 stale、quota 不平衡、登录态失效） | chief agent 检出时 | 飞书群立即发 + 写 `chief_to_muse.jsonl`（`kind=报警`） | 立即报警，按规则先处置（如停手、不下单），事后补原因 | 复核处置是否合规，必要时在群里以 `[Muse]` 前缀给指示 |
| 用户在群里下指令 | 用户在群里发消息 | 飞书群 | 规则内的事直接办并回群里；涉及规则原则变更的，转 Muse（通道 1）请示，用户是最终拍板人 | 接到转达后给意见，chief agent 转回群里 |
| Muse 要复核/定夺 | Muse 在沙箱发起 | 通道 1（文件）→ chief agent 转进飞书群（`[Muse]` 前缀） | 把 Muse 的消息原文转进群，不改写、不摘要 | 在沙箱写复核意见，chief agent 只负责转达 |
| chief agent 拿不准、须 Muse 定 | chief agent 检出时 | 通道 1（`kind=请示`）+ 飞书群里先说一声“已请示 Muse，待回复” | 把问题与证据写进 `chief_to_muse.jsonl`，按规则先做保底处置（如暂停相关操作），不等回复不硬闯 | 尽快回复，chief agent 把回复转进群 |

- **决策权**：chief agent 在规则内自行决定（与现系统“规则执行总则”一致）；Muse 复核与定夺；用户只在规则原则变更时拍板。三方分工与现系统 Muse/用户的分工一致，chief agent 是把 Muse 的执行与监督职责搬到笔记本上，不是另立一套规则。

#### 须用户配合的步骤（飞书侧，chief agent 与 Muse 都替不了用户）

1. 在飞书开放平台（open.feishu.cn）创建企业自建应用（须用用户的飞书账号；若用户所在企业须管理员审批，由用户找管理员）。
2. 在应用里开启“机器人”能力；事件订阅选“使用长连接”，订阅 `im.message.receive_v1`；开权限 `im:message`、`im:message:send_as_bot` 与群消息读取权限；创建新版本并发布。
3. 在飞书里建讨论群，把 chief agent 机器人加进群（若群是外部群，须先在应用设置里允许“对外共享 / 外部群可用”）。
4. 把应用的 App ID 与 App Secret 填进笔记本的 `~/sys2/config/feishu.env`（600 权限）——由用户在笔记本上亲自填，或把值给 chief agent 由它写进文件；**绝不经聊天发送、绝不进 GitHub**。
5. （可选）若要加自定义机器人 webhook 作报警保底，由用户在群里“设置 → 群机器人 → 添加自定义机器人”，把 webhook 地址给 chief agent。

### 首选与备用（chief agent）

- **首选：Claude Code（agent 核心）+ 本地 systemd 定时器/驱动器 + 飞书监听器常驻服务**（即本节设计）。理由：agent 核心与模型已在笔记本上验证可用（第一套搭建 36/36）；飞书长连接无需公网地址，笔记本 NAT 后可直接用；驱动器与监听器都是小脚本，chief agent 的“常驻”部分不需要另装重型框架。
- **备用 1：OpenClaw（开源 agent 框架，本地跑）**。它原生支持飞书频道（WebSocket 长连接）、定时任务与多通道，chief agent 的常驻部分可由它承担，Claude Code 只作编码/搭建工具。须在搭建时先评估（未在笔记本上验证过安装与飞书通道），若首选的自研驱动器+监听器搭不通，再试 OpenClaw。
- **备用 2：沙箱驱动的工具循环**（`docs/搭建执行技能.md` §3 的兜底路）：沙箱侧写驱动脚本，经 FCC/dsh API 调模型，笔记本侧只跑执行与监听；chief agent 的“脑子”仍在沙箱，笔记本只剩手脚。此路违背“第二套独立于 Muse”的目标（沙箱/Muse 一停 chief agent 即停），仅当笔记本上 Claude Code 完全不可用时才用。
- **明确不用**：盒内一次性 LLM 调用（已两轮证伪）；本地 `qwen3:8b` 作 chief agent 的主力模型（与已失败的 7B 同量级，不作首选，见 `docs/搭建执行技能.md` §1）。

---

## 3. 监管系统（管控侧）

### 搭什么

- 管控侧的职责（接口规范第二部分 §9–§16）：每日工作流（§10，见下表，改为笔记本本地执行）、决策规则引用（§11，总纲 02/03/04）、硬约束（§12，14 条）、不能碰的操作侧东西（§13）、管控侧可以写的文件（§14）、出错时怎么办（§15）、交接检查清单（§16）。
- 每日工作流（交易日，北京时间；接口规范 §10 原表，执行位置改为笔记本本地）：

| 时间 | 做什么 | 执行方 | 接口 |
|---|---|---|---|
| 07:30 前后 | 核对门已开：笔记本门控标志 mtime 为当日、执行单元 active；未开先查 gate 日志、交易日判定，不要直接下单 | chief agent（定时器） | 门控标志（笔记本本地路径，见 §6） |
| 08:00 | 早盘出表挂单：先查账本（有持股节点跳过买单，卖单从有持股最低档起挂），按总纲 02 现算（铺开、留高节点、覆盖 ≥1.21、lattice 校验），写订单队列；挂完立即查当日委托比对，重复/错单撤单修正、缺单补挂 | chief agent（agent 核心 + 执行系统） | 订单队列、账本 |
| 09:20–09:25 | 早盘挂单复核（只读）：复核只读、写 run-0920 记录，不补挂不撤单；无法复核必须明说 | chief agent | trade_log、快照 |
| 09:35–15:00 | 监盘：A 线成交由 fillwatch 检出，检出后立即补挂（卖了补买、买了补卖），补挂后终核、入账、通知，**每次补挂报延时（目标 4–6 分钟）**；B 线触发由监盘检出，触发才执行 | chief agent（fillwatch + B 线监盘常驻） | 快照、监盘 |
| 10:00 / 11:25 / 14:00 | trade-check：只在异常时报警，无事静默；检查项含 fillwatch 快照（10 分钟内且 status ok）与 B 监盘心跳（10 分钟内）+ 取数失败轮数 | chief agent | 快照、心跳 |
| 13:05 | 午盘网格执行与核对：按总纲 02 与午盘任务体；核对当日委托 | chief agent | 订单队列、账本 |
| 14:30 | B 线尾盘选股 + 买入辩论：UZI 通过的候选逐只跑买入辩论，买入须评判批准且置信度 ≥0.7 并过 P4/≥5000/单只上限/B 线≤3 只等闸门；辩论失败、超时、置信度不足一律跳过；硬截止 14:55，UZI 结束已过 14:50 则直接空仓 | chief agent（agent 核心 + 辩论 LLM） | 合规闸门 |
| 15:05 | 收盘核对：查当日成交补漏、跑 `quota.py` 核对平衡、写收盘小结（有新增 A 线成交时才写） | chief agent | trade_log、quota |
| 17:05 前后 | 核对门已关：标志已删、执行单元 disabled、pending 已移入 failed | chief agent | 门控标志 |
| 16:53 | 独立评审（常设）：只读核查当日执行与规则一致性，只提意见不改系统；属实缺口当晚补进总纲/任务体/skill 并复核 | chief agent（或 Muse 经通道 1 复核） | 总纲 |

### 复用还是重写

- **复用为主**：管控侧的虚拟程序（`~/workspace/ab-/virtual/`，管控端到端已验证跑通）与接口规范（837 行）直接复用——第二套的监管系统就是虚拟程序 + 接口规范的本地实例化，不重写管控逻辑。
- **须适配的三处**（搭建时做）：①虚拟程序的 base 路径与状态文件改到第二套目录（`~/sys2/` 下独立一份，不与第一套的 `~/workspace/ab-/virtual/` 共用状态）；②每日工作流的执行位置由“沙箱 Muse + 华为”改为“笔记本 chief agent”（定时器、hook、文件路径全改成本地）；③辩论 LLM 的调用方由沙箱 `debate_run.py` 改为笔记本本地调用（经 FCC/dsh，与第一套搭建同一路；Modal 辩论 LLM 是否共用，见 §6 未决事项）。
- **chief agent 在其中的角色**：它是管控侧的执行者与决策者——按 §10 的时间表驱动每日工作流，按 §11 的规则做决策，按 §12 的硬约束停手与上报；Muse 经通道 1 复核与定夺，用户经飞书群拍板规则原则变更。

---

## 4. 执行系统（操作侧）

### 搭什么

- 操作侧四脚本（合规 `order_compliance.py`、执行器 `order_executor.py`、门控 `gate_local.py`、成交监视 `fillwatch_rehang.py`），与第一套相同的职责与接口（接口规范 §1–§8），但全部跑在笔记本本地、全部用第二套的目录与账户。
- **搭建方法：复用 `docs/搭建执行技能.md` 的流程**。该 skill 已在笔记本上一次验证通过（基线 36/36、对接全过、调试 0 轮），第二套照同一流程再跑一遍：Claude Code 读文档 → 写四脚本 → 跑自测基线 → 调试迭代至 ≥80% → 对接验证 → 写报告推 GitHub。**推断**：同一流程、同一模型、同一 agent，第二次应能复现通过；是否复现，由搭建验证判定，不在本预案里预支结论。

### 针对新浏览器的执行层改动

- **CDP 端口参数化**：现 `cofool_driver.py` 第 47 行写死 `CDP_PORT = 9222`；第二套的执行层须把端口改成可配（如环境变量 `SYS2_CDP_PORT=9223` 或命令行参数），指向新浏览器的 9223，不得写死 9222（否则会连到第一套的 Chrome、误操作现系统账户）。
- **新浏览器 profile 与登录态**：第二套的执行层只连新浏览器的 profile（`~/.config/sys2-chrome`），绝不连 `~/.config/cofool-chrome`。新浏览器的叩富登录态初始为空，须在搭建时登录一次新账户（见 §5）；登录态失效时执行器停止（与现系统硬约束 §12 第 9 条一致：不得用浏览器重登、不得绕过登录态下单）。
- **执行层脚本位置**：第二套的 `laptop_order.py` / `cofool_driver.py` 另拷一份到 `~/sys2/` 下改端口与 profile，不改第一套的 `~/laptop_order.py`（第一套仍在跑，动它会断现系统）。
- **B 线监盘**：第二套的 B 线 5 分钟监盘跑在笔记本本地（systemd 定时器），行情源与第一套相同（新浪单源，华为路径不可用时东财直连也不通的教训见 P1-2 记录）；取数失败不触发（宁可漏判、不可误判）。

---

## 5. 独立账户

### 另开叩富模拟账户

- **第二套用另开的叩富模拟账户、独立仓位，从 100 万重新开始**（用户 2026-11-13 18:21 点选“独立账户，各跑各的”）。
- **注册流程（未核实，须在搭建时确认）**：现账户“股神037_4560 / 小白菜”当初如何注册（是否须手机号验证、是否一个手机号只能开一个模拟账户），本预案未核实。暂定两条路，搭建时按实测定：①用户亲自在新浏览器里注册第二个模拟账户（最稳，身份验证由用户自己过）；②用户授权后由 chief agent 在新浏览器里代办注册（须用户在场配合验证步骤）。**不默认 agent 能独立注册**，注册涉及用户身份信息，须用户配合或明确授权。
- **登录**：新账户的登录态只存在新浏览器的 profile（`~/.config/sys2-chrome`）里；登录操作由用户在笔记本上亲自做一次（或在用户监督下由 chief agent 做），登录后 profile 常驻（新浏览器 systemd 服务 `Restart=always`，与现 Chrome 相同）。密码与现系统一样走 Secure Vault 纪律（只用一次、不复述、不写记忆与普通文件、不进 GitHub）。
- **初始资金**：叩富模拟账户初始 100 万（与现系统相同）；第二套的 A 线三仓与 B 线额度划分沿用总纲口径（A1/A2/A3 各 166,666.67、B 线 50 万硬上限），但数字是第二套自己的，与现系统互不影响。

### 账本与 trade_log 隔离

- **完全隔离，不许共用**：第二套的 trade_log、quota、节点账本、落袋收益登记、picks-log 等全部另建在 `~/sys2/` 下（如 `~/sys2/ledger/trade_log.csv`、`~/sys2/ledger/quota.py`、`~/sys2/ledger/A线网格节点账本.md`），**绝不与现系统的 `~/workspace/goals/a/files/paper-trading/` 共用文件**；第二套的 quota.py、realized_ledger.py 另拷一份改路径，不改现系统的版本。
- **节点账本**：第二套的 A 线节点账本按 `local-a-ledger` skill 重新建账（同一建账方法、同一 lattice 口径，但持仓从 0 开始、按新账户的 100 万初始资金配）；现系统的账本不动。
- **同步**：第二套不设沙箱↔华为同步（全在笔记本上，无通道）；第二套的 ledger 只在笔记本本地，Muse 经 `laptop_ssh.sh` 只读核查，不写。

---

## 6. 接口对接（chief agent 按接口规范对接）

### chief agent 的接口清单（接口规范章节号，第二套的本地化路径）

| 接口 | 接口规范 | 现系统（第一套） | 第二套（笔记本本地） |
|---|---|---|---|
| 订单队列 | §1 | 华为 `/root/monitor/order_queue/`（pending/done/failed） | 笔记本 `~/sys2/monitor/order_queue/`（pending/done/failed，同一目录结构与 JSON 格式） |
| trade_log | §2 | 沙箱 `~/workspace/goals/a/files/paper-trading/trade_log.csv` | 笔记本 `~/sys2/ledger/trade_log.csv`（同一列格式与标记口径） |
| 记账本 | §3 | 华为 `huawei_bookings.csv`（P1-4，未切 live） | 笔记本 `~/sys2/ledger/sys2_bookings.csv`（第二套 live 模式由 fillwatch 写，同一去重键） |
| fillwatch 快照 | §4 | 华为 `/root/monitor/` 快照 + 沙箱 hook 比对 | 笔记本 `~/sys2/monitor/snapshots/`（同一 JSON 格式与 stale 判定） |
| 门控标志 | §5 | 华为 `/root/monitor/.trading_day` + 沙箱 gate | 笔记本 `~/sys2/monitor/.trading_day`（同一判定：标志为当日 + 07:30–17:05 窗口） |
| 账本与 quota | §6 | 沙箱节点账本 + `quota.py` + `realized_ledger.py` | 笔记本 `~/sys2/ledger/` 下独立一份（同一口径，见 §5） |
| B 线监盘 | §7 | 华为 compare / 沙箱执行 | 笔记本本地 systemd 定时器（同一检测脚本与认领/attempts 口径） |
| 每日工作流 | §10 | 沙箱 Muse + 华为 | 笔记本 chief agent（定时器驱动，见 §3） |
| 硬约束 | §12 | 14 条（Muse 遵守） | 14 条（chief agent 遵守，逐条照搬；其中“绝不反向覆盖华为执行器”等涉华为条目改为对应的笔记本本地条目） |

### 第二套与现系统的隔离边界

| 项 | 共用还是隔离 | 说明 |
|---|---|---|
| 总纲（docs/01–07）与接口规范 | **共用** | 第二套沿用同一套交易规则与接口定义；规则变更仍先改总纲、再改任务/skill、最后记 CHANGELOG（硬约束 §12 第 14 条） |
| 叩富账户与仓位 | **隔离** | 各跑各的账户（§5），仓位与盈亏互不影响 |
| trade_log、quota、节点账本、落袋登记 | **隔离** | 各自独立文件与目录（§5），绝不共用、绝不互相读取 |
| 订单队列、快照、门控标志 | **隔离** | 各自独立目录与端口，chief agent 只读/写第二套的 |
| 浏览器与 CDP 端口 | **隔离** | 现 Chrome 9222 / 新浏览器 9223，不同进程、不同 profile |
| Claude Code、FCC、dsh、Ollama | **共用（基础设施）** | 笔记本上已有的 agent 与模型网关，两套系统共用；但 chief agent 的配置与工作目录独立 |
| GitHub 仓库 ab- | **共用** | 两套系统的文档与记录都在同一仓库（见未决事项第 3 条）；第二套的文档另起目录，不覆盖第一套的记录 |
| 飞书应用机器人 | **隔离** | 第二套的 chief agent 用自己新建的飞书应用与机器人，不复用现系统可能有的任何飞书配置 |
| Muse 通道 | **隔离** | 第二套的消息文件在 `~/sys2/inbox/`，与现系统的 hook/seen 文件分开 |

---

## 7. 搭建流程

干净目录：笔记本 `~/sys2/`（与第一套的 `~/ops-build-laptop/` 与 `~/workspace/goals/a/` 区分）。全程只读 GitHub 文档；不碰现系统任何运行中的文件（现 Chrome、现 trade_log、现台账、华为 `/root/monitor/`）；不登录现叩富账户。

| 步 | 做什么 | 输入 | 输出 | 通过标准 | 失败回退 |
|---|---|---|---|---|---|
| 0. 环境准备 | 建 `~/sys2/` 目录结构（`monitor/`、`control/`、`ledger/`、`inbox/`、`browser/`、`config/`）；克隆 ab- 到 `~/sys2/build/`；验证 Claude Code（`export PATH=$HOME/node-v22/bin:$PATH; claude --version` 须出 2.1.323）与 FCC（`curl 127.0.0.1:8082/v1/models` 不带 token 须 401）；验证虚拟程序能跑（`python3 virtual_ops.py init` + `python3 selftest.py` 全过） | GitHub 仓库、FCC token（笔记本现有配置） | `~/sys2/` 目录、克隆、可用的 `claude`、FCC 实测、虚拟自测全过 | 全部通过才进下一步 | Claude Code 不可用 → 按 `docs/搭建执行技能.md` §3 的备用 agent（`fcc-aider`/`fcc-opencode`）；FCC 不通 → 切 dsh 备用模型；虚拟自测因门控窗口未过 → 可用假时区重跑，或按 2026-11-13 晚补充在非交易时间用真实下单+撤单跑通 |
| 1. 浏览器 | 第二份便携版 Chrome 解压到 `~/sys2/chrome/`（或复制现 `extracted/`），独立 profile `~/.config/sys2-chrome`，新建 `sys2-chrome.service`（`Restart=always`，CDP 9223），验证 `/json/version` 可通 | `~/chrome-install/` 下的安装包 | 可用的新浏览器（CDP 9223 通、profile 独立） | CDP 9223 返回版本号与协议版本；`ss` 确认 9222 与 9223 各自监听、互不干扰 | 解压失败 → 改用备用 1（同一份二进制 + 独立 profile）；仍失败 → 备用 2（apt Chromium，走 snap） |
| 2. chief agent | 写驱动器（systemd 定时器 + 调度脚本，按 §3 的每日工作流）与飞书监听器（常驻服务，持 WebSocket 长连接）；建消息通道文件（`~/sys2/inbox/muse_to_chief.jsonl`、`chief_to_muse.jsonl`）；**用户配合**：建飞书应用、开机器人与长连接、建讨论群并加机器人、把 App ID/Secret 填进 `~/sys2/config/feishu.env`（600 权限）；验证两通道（Muse 通道：沙箱经 `laptop_ssh.sh` 写一行、chief agent 读到并回复；飞书通道：群里 @机器人有回复） | Claude Code、FCC、飞书应用（用户建） | 驱动器、监听器、两通道可通 | 两通道各跑通一次往返；飞书群里 @机器人有回复；Muse 的消息能经 chief agent 以 `[Muse]` 前缀发进群 | 飞书应用建不了/发布须审批 → 等用户走完审批再继续；长连接不通 → 查权限与事件订阅，仍不通改 webhook 备用推送 |
| 3. 监管系统 | 复制虚拟程序到 `~/sys2/control/virtual/`（独立状态），适配 base 路径与每日工作流执行位置（改为笔记本 chief agent 定时器驱动）；辩论 LLM 改为笔记本本地调用（经 FCC/dsh）；干跑一轮虚拟管控（选股→把关→辩论→提交→成交→快照→入账→quota） | 虚拟程序、接口规范、总纲 | 可跑的监管系统（虚拟） | 虚拟管控端到端跑通（参照第一套管控验证的通过标准：零 500、把关全对、ai_confirmed=true） | 虚拟跑不通 → 按 `docs/搭建执行技能.md` §2 的调试契约修（根因句先于改动、改完跑自测、最多 3 轮） |
| 4. 执行系统 | 按 `docs/搭建执行技能.md` 六步流程再跑一遍：Claude Code 读文档 → 写四脚本（`~/sys2/monitor/`）→ 跑自测基线 → 调试迭代至 ≥80% → 对接验证（A 线卖 601088 200@49.58 + B 线买 600919 500@12.98，经第二套的虚拟程序）→ 写报告；执行层 CDP 端口改为 9223、profile 改为 `~/.config/sys2-chrome` | 接口规范、总纲 01、虚拟程序、搭建执行 skill | 四脚本 + 自测通过数 + 对接结果 | 基线 ≥80% 且对接全部 PASS（与第一套同一标准） | 未达 80% → 按 skill 的调试契约修，最多 3 轮；3 轮未过即停，写清差在哪 |
| 5. 独立账户 | **用户配合**：注册第二个叩富模拟账户（流程见 §5，未核实，搭建时确认）；在新浏览器里登录一次新账户（用户亲自做或在监督下由 chief agent 做），验证登录态（执行层 `status` 命令 `logged_in` 为 true）；按 `local-a-ledger` skill 建第二套的 A 线节点账本（持仓从 0 开始、100 万初始资金） | 新叩富账户（用户注册） | 登录态可用的新浏览器、第二套的节点账本与 trade_log（空表头） | `status` 顯示 logged_in 为 true；账本平衡恒等式成立 | 注册须手机号验证且用户不在场 → 停，等用户配合；登录态失效 → 停，不绕过登录态下单 |
| 6. 接口对接 | chief agent 按 §6 的接口清单接线：订单队列、快照、账本、trade_log、门控标志、 B 线监盘全部指向 `~/sys2/` 下路径；跑一轮端到端（写单 → 合规 → 执行器 → 快照 → fillwatch 补挂 → 入账 → quota 平衡），核实隔离边界（第二套的操作绝不写现系统的文件、绝不连 9222） | 四脚本、监管系统、新浏览器 | 接通的第二套系统 | 端到端跑通且隔离核查通过（grep 第二套的日志与文件，确认无现系统路径、无 9222）；2026-11-13 晚补充：端到端验证不必等交易日，非交易时间可用真实下单后立即撤单跑（不留持仓，真实下单须用户点头） | 隔离核查不过 → 停，查哪一步写错了路径/端口，修好重验 |
| 7. 验证 | 影子验证：第二套在影子模式跑 1–2 个交易日（只决策、不下单，或虚拟成交），核对每日工作流、补挂延时、quota 平衡；通过后再切 live（真实下单须用户点头，与现系统“下单前必报”的纪律一致）；2026-11-13 晚补充：下单撤单端到端验证不必等交易日，可提前在非交易时间跑（下单后立即撤单、不留持仓） | 接通的第二套系统 | 验证报告 | 影子 1–2 日无异常（无错单、无重复下单、quota 平衡、补挂延时在目标内）；2026-11-13 晚补充：下单撤单端到端部分不必等交易日，可提前在非交易时间跑；每日工作流影子观察仍须 1–2 个交易日（下周一 2026-11-16 起） | 影子发现问题 → 修好重跑影子，不强行切 live |
| 8. 写报告推 GitHub | 更新 `docs/实施记录/second_system_plan_20261113.md`（追加搭建记录）或另写搭建报告；产物放 `docs/实施记录/second_system_20261113_files/`；CHANGELOG.md 加一条；推 GitHub | 全部产物 | GitHub commit | 报告须含完整结论与依据；未达标须写清差在哪，不许谎报通过 | 推送失败 → 先核对本地与远端 HEAD，不强推、不改历史 |

### 风险与已知坑（搭建前须读）

- Claude Code 不在默认 PATH：调 `claude` 与 `fcc-claude` 前必须 `export PATH=$HOME/node-v22/bin:$PATH`，否则报 `Could not find Claude Code command: claude`；npm 同理（shebang 用 `env node`）。
- FCC 非流式 500 bug：调用方一律 `stream=true`；模型须用带前缀完整 ID（裸名会回退到默认模型）。
- 飞书同一应用只能有一个长连接消费者：调试时不要同时跑两个监听器，否则事件分摊漏收；改权限/事件后须创建新版本并发布（可能须管理员审核）。
- 飞书群默认须 @机器人 才响应；chief agent 要主动汇报，须开群消息读取权限并设好群策略。
- Muse 通道是文件式异步（约 1 分钟级延迟），不是实时聊天；盘中紧急决策 chief agent 按规则先定、事后汇报，不等 Muse 回复。
- 新浏览器的叩富登录须用户配合（注册与首次登录）；登录态失效时执行器停止，不得用浏览器重登、不得绕过登录态下单。
- 第二套的 trade_log/quota/账本与现系统完全隔离；写错路径会污染现系统账本，搭建第 6 步须做隔离核查（grep 日志与文件，确认无现系统路径、无 9222）。
- 笔记本是单点：全在笔记本上，没有通道问题，但笔记本一停第二套全停（现系统至少操作侧在华为上还能跑）；笔记本 Chrome 常驻服务崩溃自启须验证（`Restart=always`）。
- Chromium 经 apt 是转 snap 的过渡包，须 snap 商店联网下载；便携版 Chrome 的 .deb 版本待核实（见 §1）。
- 沙箱侧不代写代码、不给确定性补丁；调试须由笔记本上的 agent 自己用工具迭代完成（与第一套搭建同一纪律）。
- cofool 非交易时间可下单撤单（用户 2026-11-13 晚实测确认）：第 0/6/7 步的下单撤单验证不必等交易窗口；试跑只下单后立即撤单、不留持仓，真实下单须用户点头。

---

## 预案结论（七项）

1. **浏览器**：首选第二份便携版 Google Chrome 157.0.8103.50（安装包已在笔记本上），独立 profile `~/.config/sys2-chrome`，CDP **9223**，独立 systemd 服务；备用为同一份二进制 + 独立 profile、再备用为 apt Chromium（转 snap）。
2. **chief agent**：**待评估后定（用户 2026-11-13 18:40：选择性很大，挑合适的，不一定局限于现有的）**。本预案原首选为 Claude Code（agent 核心）+ 本地 systemd 定时器/驱动器 + 飞书监听器常驻服务，现改为候选之一；搭建时须广泛评估（Claude Code、OpenClaw 及其他 agent 框架），挑最合适的。两个通道不变——Muse 通道用文件式异步消息经 Tailscale SSH（约 1 分钟级延迟），飞书通道用应用机器人 + WebSocket 长连接（无需公网地址）；“一个讨论组”落在飞书群里，Muse 经 chief agent 以 `[Muse]` 前缀中转进群；再备用为沙箱驱动工具循环（违背独立目标，仅兜底）。
3. **监管系统**：复用虚拟程序与接口规范（本地实例化），chief agent 按接口规范 §10 的每日工作流驱动，辩论 LLM 改笔记本本地调用。
4. **执行系统**：复用 `docs/搭建执行技能.md` 六步流程再跑一遍；执行层 CDP 端口改为 9223、profile 改为新浏览器，脚本另拷一份到 `~/sys2/`，不动第一套的 `~/laptop_order.py`。
5. **独立账户**：另开叩富模拟账户（注册流程未核实，须用户配合或授权），100 万重新开始；账本与 trade_log 在 `~/sys2/ledger/` 下完全隔离，绝不共用现系统文件。
6. **接口对接**：chief agent 按接口规范 §1–§8、§10、§12 的清单接线，路径全部本地化到 `~/sys2/`；隔离边界见 §6 的表（总纲/接口规范/基础设施共用，账户/账本/队列/快照/浏览器/飞书应用隔离）。
7. **搭建流程**：九步（环境→浏览器→chief agent→监管→执行→独立账户→接口对接→影子验证→写报告推 GitHub），每步有输入/输出/通过标准/失败回退；影子 1–2 日通过后再切 live（真实下单须用户点头）。（2026-11-13 晚补充：第 6/7 步的下单撤单验证不必等交易日，见补充节。）

---

## 补充：非交易时间可用真实下单撤单试跑（2026-11-13 晚，用户实测确认）

**结论**：cofool 现在（随时）可以下单撤单，整个流程可以在非交易时间试跑（用户 2026-11-13 晚实测确认，非推断）。

**影响**：

- **第 0 步**：唯一未过项（虚拟程序自测须在交易窗口内重跑）不再受交易窗口限制——可在非交易时间用真实下单+撤单跑通，或仍用假时区重跑，二者任选，以实测为准。
- **第 6 步（接口对接）**：端到端验证不必等交易日，非交易时间即可做（下单后立即撤单、不留持仓）；排期可提前到本周末（2026-11-14 周六）非交易时间。
- **第 7 步（影子验证）**：下单撤单端到端部分不必等交易日，可提前在非交易时间跑；每日工作流影子观察（08:00 出表、09:20 复核、盘中补挂延时等）仍须 1–2 个交易日真实行情观察，从下周一 2026-11-16 起。

**纪律不变**：试跑只下单后立即撤单、不留持仓；真实下单仍按既定规矩——须用户点头的才算数，影子验证本身不持仓；切 live 仍须用户点头，影子通过也不许擅自切 live。其他步骤与权限一律不变。

---

## 未决事项（用户 2026-11-13 18:40 已定四项，余一项未定）

1. **第二套叩富模拟账户的注册流程**：~~是否须手机号验证、一个手机号能否开两个模拟账户、agent 能否代办注册——均未核实。搭建第 5 步时确认；默认由用户亲自注册。~~ **已定（用户 2026-11-13 18:40）：由用户亲自注册新账户**，并负责提供飞书 ID、key。
2. **chief agent 的首选设计是否采用**：~~本预案首选 Claude Code + 定时器/驱动器 + 飞书监听器；备用 OpenClaw 未在笔记本上验证过。若用户倾向直接用 OpenClaw 这类现成框架，须先评估再定。~~ **已定（用户 2026-11-13 18:40）：选择性很大，挑合适的，不一定局限于现有的**——搭建时须广泛评估（Claude Code、OpenClaw 及其他 agent 框架），挑最合适的，不许只因现成而默认 Claude Code。预案 §2 的首选设计改为“待评估后定”。
3. **第二套系统的文档放哪里**：~~本预案推荐与第一套共用同一 GitHub 仓库 ab-（另起目录，如 `docs/第二套系统/` 或 `docs/实施记录/second_system_*`），总纲与接口规范共用；若用户想另建仓库，搭建时再分。~~ **已定（用户 2026-11-13 18:40）：GitHub 另开分支记录笔记本**——第二套的文档与记录放在 ab- 仓库的 `laptop` 分支，不定期完善后合并进 main 作为新版本号。主分支 main 上的预案原文（commit 594dc7d）保持不动；本节定夺记在 `laptop` 分支的预案副本上。
4. **Modal 辩论 LLM 是否共用**：第二套的买入辩论是否走现系统的 Modal 端点（`b-debate-llm`，笔记本 `~/modal_vllm.py`），还是另起一套；本预案暂定共用（同一端点、同一模型），搭建时确认。**用户 2026-11-13 18:40 定笔记本基础设施共用（包括 llmhub），Modal 作为辩论 LLM 基础设施按共用处理，搭建时再确认。**
5. **Muse 通道的轮询间隔**：本预案暂定 60 秒（单向约 1 分钟级延迟）；若用户要更快，改为 30 秒（SSH 调用更频繁）或升级为直连 API（须实测笔记本→沙箱方向）。**未定，仍暂定 60 秒。**

---

## 用户定夺（2026-11-13 18:40，四项）

1. **笔记本基础设施共用，包括 llmhub**：第二套与第一套共用笔记本基础设施（Claude Code、FCC、dsh、Ollama、llmhub 等）；隔离边界见 §6 的表（基础设施共用，账户/账本/队列/快照/浏览器/飞书应用/Muse 通道隔离）。
2. **用户负责 cofool 新账号、飞书 ID、key**：另开叩富模拟账户由用户亲自注册；飞书应用的创建与 App ID、App Secret 由用户提供（填进 `~/sys2/config/feishu.env`，600 权限，绝不经聊天发送、不进 GitHub）。
3. **chief agent 选择性很大，挑合适的，不一定局限于现有的**：不限于 Claude Code；搭建时须广泛评估（Claude Code、OpenClaw 及其他 agent 框架），挑最合适的，不许只因现成而默认 Claude Code。
4. **GitHub 另开分支记录笔记本**：第二套的文档与记录放在 ab- 仓库的 `laptop` 分支，不定期完善后合并进 main 作为新版本号。
