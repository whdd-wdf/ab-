# 虚拟程序（模拟操作侧）

> **这是一个虚拟程序，不是真实交易系统。** 它模拟操作侧（华为 VPS / 笔记本）
> 的接口行为，供 AI（管控侧）按接口规范对接、演练选股 / 把关 / 讨论等 skill，
> 逻辑跑起来有结果，但**不产生真实资金、不登录叩富网、不连华为 VPS、不碰
> 真实 trade_log / 台账 / 总纲**。
>
> 接口依据：`~/workspace/ab-/docs/操作与管控接口规范.md`（§1 订单队列、§1.5
> 合规清单、§2 trade_log、§4 fillwatch 快照、§5 门控标志、§6 账本与 quota、
> §7 B 线监盘）。格式与该规范一致。

## 文件清单

| 文件 | 作用 |
|---|---|
| `virtual_ops.py` | 唯一入口（Python 标准库，无第三方依赖）。订单队列、合规校验、虚拟执行器、虚拟行情、虚拟 quota、门控标志、fillwatch 快照、节点账本 JSON |
| `selftest.py` | 自测脚本：跑一轮 6 项检查，全部 PASS 才算通过 |
| `README.md` | 本文件 |
| `order_queue/{pending,done,failed}/` | 订单队列（`init` 后生成，§1） |
| `virtual_trade_log.csv` | 虚拟成交总账（`init` 后生成，§2 格式，9 列） |
| `virtual_quota.json` | 虚拟 quota（A1/A2/A3/B 四仓，§6.2 口径） |
| `nodes.json` | A 线节点账本 JSON（从真实账本抄节点价与股数） |
| `quotes.json` | 虚拟行情（A 线三码 + 8 只 B 线候选码） |
| `snapshots/fillwatch_YYYYMMDD_HHMM.json` | fillwatch 快照（§4.2 格式） |
| `.trading_day` | 门控标志（空文件，mtime 日期 = 当日即开门，§5） |
| `state.json` | 虚拟订单簿（当日委托表，供快照用） |

## 怎么跑

```bash
cd ~/workspace/ab-/virtual
python3 virtual_ops.py init # 初始化 / 重置虚拟状态
python3 virtual_ops.py quote 601088 # 查虚拟行情
python3 virtual_ops.py check 600919 # 算数：涨幅/P4/5万量/偏差一次算好（AI 只读数字、不自己算）
python3 virtual_ops.py check 600919 12.87 # 指定买价算一遍
python3 virtual_ops.py quota # 打印虚拟 quota
python3 virtual_ops.py log # 打印虚拟 trade_log 尾部 10 行

# 下单一笔（订单 JSON 见下）
python3 virtual_ops.py submit /tmp/my_order.json
python3 virtual_ops.py run # 执行器处理一轮 pending
python3 virtual_ops.py snapshot # 生成 fillwatch 快照
python3 selftest.py # 自测（全部 PASS 才算通过）
```

**启动 / 停止 / 重置**：本程序无常驻服务，不用启动、不用停止；每次 `init`
即重置全部虚拟状态（队列、账本、quota、行情、快照全回初始值）。想重跑一轮，
直接再跑一次 `init`。

**环境**：Python 3.9+，仅标准库；沙箱 / Simular Box 均可跑（盒内能跑）。

## AI 怎么对接（按接口规范 §9–§10）

管控侧（AI）只读虚拟程序的输出文件、只按规定写订单，与真实系统同一套接口：

| AI 要做的事 | 读 / 写哪个虚拟文件 |
|---|---|
| 查门是否开 | 读 `virtual/.trading_day`（mtime 日期 = 当日即开门，§5） |
| 查行情 / 选股候选 | `python3 virtual_ops.py quote <代码>`，或读 `virtual/quotes.json`（8 只 B 线候选：600176、002475、000596、600919、600018、603198、000001、600000） |
| 算数（买入前核对） | `python3 virtual_ops.py check <代码> [买价]`：涨幅/P4 限价/5 万量/偏差一次算好，AI 只读数字、不自己算（见下节 `check` 算数接口） |
| 查额度 / 持仓 | `python3 virtual_ops.py quota`，或读 `virtual/virtual_quota.json` |
| 查节点价 / 可卖量 | 读 `virtual/nodes.json`（节点价、手数、卖价 = 节点价×1.02） |
| 下单 | 写订单 JSON，`python3 virtual_ops.py submit <订单JSON>` → 进 `order_queue/pending/` |
| 查订单结果 | 读 `order_queue/done/<order_id>.json`（`result.status=filled`）或 `order_queue/failed/<order_id>.json`（`result.status=rejected`，`reasons`/`checks` 列明原因） |
| 查当日成交 | 读 `virtual/virtual_trade_log.csv` 尾部，或 `python3 virtual_ops.py log` |
| 查快照 / 是否 stale | `python3 virtual_ops.py snapshot`；快照 `timestamp` 距现在 > 300 秒即 stale（§4.3） |
| 补挂（卖了补买、买了补卖） | 读最新快照 `fills_today`，按节点价算补挂单再 `submit`（与真实 fillwatch 同逻辑，见 §4.5） |

### 订单 JSON 格式（§1.2）

必填：`order_id`、`code`、`side`（恰为 `买入`/`卖出`）、`price`（限价）、`qty`（股数）。
可选：`limit_price`（B 线 P4 限价）、`prev_close`（前收）、`line`（`A`/`B`）、`note`。

`order_id` 命名与 §1.3 一致：A 线补挂 `FW-<YYYYMMDD>-<代码>-buy/sell-<价，.→p>-<委托时间>`，
B 线触发 `SELL-<YYYYMMDD>-<代码>-<档位>-<序号>`，其余调用方自定、须唯一。

示例（A 线卖单）：

```json
{"order_id": "FW-20261113-601088-sell-49p58-20261113120600",
 "code": "601088", "side": "卖出", "price": 49.58, "qty": 200,
 "line": "A", "prev_close": 49.10}
```

示例（B 线买单）：

```json
{"order_id": "B-20261113-600919-1", "code": "600919", "side": "买入",
 "price": 12.87, "qty": 500, "line": "B", "prev_close": 12.80,
 "limit_price": 13.18}
```

### check 算数接口（AI 只读数字、不自己算）

用法：`python3 virtual_ops.py check <代码> [买价]`（买价不传则取当前价；只读、不下单）。
用途：B 线买入前核对数字——AI 直接读输出的算好值，不自己算涨幅、P4 限价、可买量和偏差（防串价：上一轮对接测试里 AI 算错导致选股串价成交）。

输出 JSON 字段：

| 字段 | 含义 |
|---|---|
| `code` / `name` | 代码 / 名称 |
| `prev_close` | 前收 |
| `price` | 当前价 |
| `buy_price` | 买价（未传则等于当前价） |
| `change_pct` | 买价相对前收的涨幅（小数形式，与 quote 的 `change_pct` 同口径） |
| `deviation_pct` | 买价相对当前价的偏差 |
| `p4_limit` | P4 限价 = 前收×1.03（保留 2 位小数） |
| `qty_50k` | 按 5 万上限、100 股倍数向下取整的可买量（买价过高致不足 100 股则为 0） |
| `amount_50k` | `buy_price × qty_50k` 的金额 |
| `gates` | 四项门染：`rise_ok`（涨幅≤5%）、`p4_ok`（买价≤P4 限价）、`deviation_ok`（偏差绝对值≤1%）、`amount_ok`（5000≤金额≤50000） |

未知代码时报错，格式与 quote 一致。

### 合规校验清单（§1.5，执行器逐项校验，`result.checks` 列逐项结果）

- **A 线买入**：买价 = 节点价（节点价低于跌停时按跌停价挂亦可）；金额 ≤ grid_available；单笔 ≥ 5000。
- **A 线卖出**：卖价 = 节点价×1.02（tick 取整）；数量 ≤ 可卖量；卖价 ≤ 涨停（前收×1.10）；不与在挂卖价重复；非禁挂集群价（510300：4.316/4.324/4.325；601088：52.06）；单笔 ≥ 5000。
- **B 线买入**：涨幅 ≤ 5%；买价 ≤ P4 限价（传入时校验）；买价≈现价（偏差≤1%，超了拒绝；当前价取不到则跳过）；单只 ≤ 5 万；金额 ≤ B 可用；新开仓时 B 线 ≤ 3 只；单笔 ≥ 5000。
- **B 线卖出**：唯一校验——数量 ≤ 持仓。
- 不通过进 `failed/`，`result.reasons` 列明每条失败原因，`result.checks` 列逐项结果。

### 虚拟成交与记账口径

- 合规通过即**虚拟成交**（按限价成交；真实系统里 `placed` 只表示进委托表、
成交唯一确认源是 fillwatch 快照——虚拟程序为简化起见，执行器直接成交，
快照 `fills_today` 即为成交确认源）。
- 成交写 `virtual_trade_log.csv` 行（9 列，方向栏恰为 `买入`/`卖出`，备注开头
带 `///` 标记，含 `委托<价>` 与订单号，与 §2.3 同口径）。
- quota 按移动加权平均口径更新：买入 deployed += 金额；卖出 deployed -= 均价×股数，
落袋 pnl +=（卖价 − 均价）×股数，quota = 初始额度 + pnl，grid_quota = quota×0.85。
- 节点账本同步更新：卖出核减该节点股数，买入加回该节点股数（A3 为 T+0，
当日买入当日可卖；A1/A2 为 T+1，当日买入不计可卖）。

## 与真实系统的区别

| 项 | 虚拟程序 | 真实系统 |
|---|---|---|
| 成交 | 执行器合规通过即按限价虚拟成交 | 订单进委托表（`placed`），成交须等 fillwatch 快照确认 |
| 资金 | 无真实资金，quota 数字只在 `virtual_quota.json` 里变 | 叩富网模拟盘资金（昵称「小白菜」） |
| 登录 / 下单 | 不登录叩富网，不调笔记本 Chrome | 经华为合规 → 笔记本 `laptop_order.py` 下单 |
| 行情 | 种子随机游走（当日种子固定，可复现），从前收出发 | 新浪 / 东财实时行情 |
| 通道 | 无网络调用，全本地文件 | 沙箱 ↔ 华为（`hw_ssh.sh` 三通道）、华为 ↔ 笔记本 SSH |
| 写者 | 全部虚拟文件只在 `virtual/` 目录内 | trade_log 唯一写者是沙箱 worker；华为只写 bookings/快照 |
| 门控 | `virtual/.trading_day`，`init` 即写当日 | 沙箱 gate + 华为 `gate_local.py` 双写，07:30 开 / 17:05 关 |

**防混淆**：虚拟 trade_log 叫 `virtual_trade_log.csv`、虚拟 quota 叫
`virtual_quota.json`，与真实 `trade_log.csv` / `quota.py` 不同名不同路径；
虚拟文件一律不写出 `virtual/` 目录。

## 初始值（任务给定的真实系统参考值，仅作初始值）

- A1 510300：持 30800 股、可卖 22200，成本 4.200，quota 166,400.49，deployed 129,384.11，grid_available 12,056.30
- A2 601088：持 1200 股（节点股数之和与之对齐：最高两档 59.26/60.45 置 0，节点价未动）、可卖 700，成本锚 49.20，quota 167,633.38，deployed 59,046.64，grid_available 83,441.73
- A3 513650：持 33000 股、可卖 33000（T+0），成本 1.985，quota 166,666.67，deployed 65,522.04，grid_available 76,144.63
- B 线空仓：quota/available 490,341.72，deployed 0
- 节点锚：A1 4.122（39 档）、A2 51.59（39 档）、A3 1.51（47 档）；卖价 = 节点价×1.02；tick：510300/513650 为 0.001，601088 为 0.01。

## 自测（`selftest.py`）

跑一轮 6 项，全部 PASS 才 exit 0：

1. A 线卖单 601088 卖 200 @49.58：合规通过、成交入账，quota/持仓/可卖/节点股数更新正确。
2. B 线买单 600919（按虚拟行情现价）：过涨幅/P4/单只/B 线≤3 只闸门，成交入账。
3. 错单 A 线买价 48.00（非节点价）：合规拒绝进 failed，`reasons` 指明买价非节点价，`checks` 逐项齐全。
4. 跑后 quota 四仓平衡、快照 status ok 且不 stale、虚拟 trade_log 有 2 笔带标记的成交行。
5. 错价单 600919 买价 = 现价×1.05（偏离现价 5%）：合规拒绝进 failed，`checks` 里“买价≈现价”项不通过，`reasons` 含“现价”。
6. check 接口：`check 600919`（默认/显式买价=现价）输出的涨幅、P4 限价、5 万量、金额、偏差与手工重算一致；`check 600919 <现价×1.05>` 时 `deviation_ok` 为 False。

```bash
python3 selftest.py # 全部 PASS 才算通过
```

## 已知简化（与真实系统有意的差别）

- 虚拟执行器直接成交，不模拟“挂单未成交”状态（真实系统须等快照确认成交）。虚拟执行器“合规即成交”，错价单若合规放行会直接成交，故买价≈现价是防串价的关键闸门。
- 无 LLM 合理性复核环节（真实合规通过后走 LLM 复核，超时/失败 fail-open）。
- 无 B 线监盘触发器（5 分钟 K 穿线检测）：B 线买单由 AI / 自测直接提交；监盘逻辑待第二步（AI 侧 skill）在虚拟行情上实现。
- 虚拟行情为当日固定种子游走价，`init` 后不变；不模拟盘中逐笔波动。
- 无 `trade_log` 同步、认领（claims）、attempts 等跨机协同件：单机虚拟，不跨机。
