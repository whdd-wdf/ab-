# P1-4 华为记账轻量版 — 实施记录（2026-11-13）

## 结论

- **华为记账轻量版已上线（待切 live）**：`huawei_bookings.csv` 已建（华为 `/root/monitor/`，现仅表头）；
唯一写者为华为 `fillwatch_rehang.py` live 模式；合规与额度已改读 trade_log + bookings 两份。
- **干跑验证全过**（真实跑过，见下）：P1-3 回归 10/10；记账 live 夹具（3 笔新成交记账 + 2 笔补挂下发 + 已入账不重记）；
重跑幂等（第 2 次记账 0 行、下单 0 笔）；compare 模式不写账不写队；合并 dry-run → apply → 再 apply（0 行）→ archive 全通；
归档缺失拒绝（RC=1，live 文件未动）。
- **live 状态：未切**。fillwatch-rehang.timer 仍跑 compare 模式（部署后 10:03–10:13 各轮 `no_new_fills` 正常）；
记账只在 `--mode live` 时写，compare 切 live 的前置与 P1-3 相同（真实成交逐笔比对一致后切）。
- **未下真实订单**；未改 `order_executor.py`（mtime 仍为 2026-11-12 16:07）；未写华为 trade_log 副本；
沙箱 trade_log 全程 md5 不变（`cd0743fffddfacedefe3eeaa263a7d8c`）。

## 文件位置

| 文件 | 位置 | 说明 |
|---|---|---|
| 华为记账本 | 华为 `/root/monitor/huawei_bookings.csv` | 新文件，现仅表头；归档目录 `/root/monitor/huawei_bookings_archive/`（已有一份测试归档，见验证） |
| 记账写者（华为运行版） | 华为 `/root/monitor/fillwatch_rehang.py` | md5 `6d6afd254181a1ae127726f3715887a0`；备份 `.bak-20261113-p1book` |
| 记账写者（沙箱源） | `~/workspace/goals/a/hidden_files/monitor_huawei/fillwatch_rehang.py` | 同源，md5 一致 |
| 合规（华为运行版） | 华为 `/root/monitor/order_compliance.py` | md5 `3ddfa289928e0f13c9394d7fc1f5dcd0`；备份 `.bak-20261113-p1book` |
| 合规（沙箱源） | `~/workspace/goals/a/hidden_files/order_compliance.py` | 同源，md5 一致 |
| 额度/落袋（沙箱源，同步至华为） | `~/workspace/goals/a/files/paper-trading/realized_ledger.py` | md5 `1c248facbb42b11123614af20e1c15f9`，两边一致；`quota.py` 未改；备份 `.bak-20261113-p1book` |
| 合并脚本（沙箱） | `~/workspace/goals/a/hidden_files/merge_huawei_bookings.py` | dry-run 默认；`--apply` 合并、`--archive` 归档 |
| 本记录 | `~/workspace/goals/a/hidden_files/p1_bookkeeping_20261113.md` | — |

## 写触发点与去重设计

- **唯一写者：`fillwatch_rehang.py` live 模式**。不在执行器写：执行器 done 的 `placed` 只表示订单进了委托表，
不是成交；成交的唯一确认源是 fillwatch 快照（`fills_today` 中 `status=已成交` 的行）。不另起新脚本：
另起一个检测器会与 fillwatch 抢同一份快照、两路竞写。
- **写时机**：live 模式下，每轮检出新成交后、补挂计算之前记账。记账与补挂结果无关（补挂被 `small_amount` /
`above_limit_up` 等过滤跳过的成交也要记账）；与下单门控无关（记账不是下单，门关闭也不影响记账）。
compare 模式只列 `would_book`、绝不写（已验证：bookings 行数不变、队列 0 文件、不建 state）。
- **记账范围**：快照全部成交行（A 线 + B 线）。B 线成交无补挂计算，但必须记账，否则华为 B 线持仓失真。
执行器队列的 B 线订单、早盘/午盘任务的 A 线订单，成交后都在同一份快照里，故单写者全覆盖。
- **记账行格式**：与 trade_log 同 9 列（日期，代码，名称，方向，价格，数量，金额，盈亏，备注）、同方向栏
（恰“买入”/“卖出”）、同标记口径（备注开头【A1】/【A2】/【A3】/【B线】，B 线取快照 name 字段）；
备注含“委托价X，委托时间YYYY-MM-DD HH:MM:SS，快照<文件名>”，只用全角“，”/“；”、不用 ASCII 逗号
（`b_holdings` 等按逗号切分，ASCII 逗号会错位）。盈亏栏留空（落袋盈亏由 realized_ledger 按移动加权平均法算，
不读盈亏栏）。价格栏取快照价（即委托价——快照只带委托价，见下）。
- **去重键（与 realized_ledger.fill_key 同口径）**：`(日期, 代码, 方向, 数量, 委托价)`，
委托价取备注 `委托价?(\d+\.\d+)`（须带小数点，防把“委托08:27:25”当价格），否则取价格栏。
不含成交价——优价成交时华为记账价（委托价）与沙箱实价不同，键含成交价会对不上；
不含时间——沙箱备注时间格式不统一，22 行成交行无 HH:MM:SS。
计数取 max：两边各一份是同一笔并行记账，只算一次；同一文件内同键多行是真实孪生单，按行数算。
历史 79 行成交中同键 0 重（2026-11-13 核）。
- **三层防重**：① 新成交检出时已读 trade_log + bookings 两份（已在任一份中的不算新）；② 记账后立即重读复核
行已落盘才记 state（`state[fill_key].booked=true`）；③ 合并脚本按同一键再比对（缺失份数才追加）。
state 的 `emitted` 写入改 `setdefault+update`，不覆盖已有的 `booked` 记录。
- **优价差说明**：快照委托表只带委托价，华为记账的“成交价”实为委托价；优价成交时（如委托 50.14、实价 50.20）
与沙箱实价差几分×股数。合并时去重键不含成交价、优先取 trade_log 的行（实价准），差额只影响华为离线期的
账面成本尾差，不影响去重与持仓股数。

## 两份读取实现

- **`realized_ledger.py`（沙箱源，同步至华为）**：`compute()` 改读 `read_fill_rows()`——trade_log 全量 +
`huawei_bookings.csv`（存在才读），候选位置：华为标准位置 `/root/monitor/huawei_bookings.csv` 优先，
账本同目录次之；任一位置无文件时行为与旧版完全一致。去重：同键计数取 max，优先取 trade_log 的行，
多余份数取 bookings 的行；按日期稳定排序（trade_log 在前）。`quota.py` 未改（它调 `ledger_compute()`）。
同步风险已处理：`migration_sync.sh` 每小时同步 `realized_ledger.py` 沙箱→华为，故改动做在沙箱源再同步，
不是只改华为副本（否则一小时内被覆盖）；同步后两边 md5 一致。
- **`order_compliance.py`**：`b_holdings()` 改读两份（同一去重键与 max 计数）；`data_age_min` 取两份中较新的
mtime；`_is_fill_row` 按 `is_fill` 口径对齐（“已撤销”只有紧跟标记后才算撤销行——旧版遇“已撤销”一律跳过，
B 线成交行备注提及另一笔撤销时会漏计；当前数据无此类 B 线行，行为不变）。
`order_compliance.py` 不在 `migration_sync.sh` 同步清单内（华为 `/root/monitor/` 版为独立部署），改沙箱源后
rsync 部署，两边 md5 一致。
- **`fillwatch_rehang.py`**：`read_trade_log_fills()` 改读两份（`--bookings` 参数，默认华为标准位置）；
新增 `read_trade_log_fills(..., codes=None)` 全代码版供 B 线记账检出用；`已撤销` 匹配口径与 quota.py 对齐
（标记后紧跟才算撤销；P1-3 原 blanket 规则会漏配“最高卖单已撤销”类真实成交行，如 2026-10-22 A1 买入行；
case4 的已撤销行是标记后紧跟，对齐后行为不变——回归 10/10 证实）。

## 合并流程（Muse 恢复时做一次）

脚本 `merge_huawei_bookings.py`（沙箱，默认 dry-run，不写任何文件）：

1. `--dry-run`：从华为取 bookings（`hw_ssh.sh cat` 到 `/tmp/huawei_bookings_staging.csv`），
与沙箱 trade_log 按去重键比对，预览缺失行；先校验 bookings 成交行备注开头标记齐全，否则拒绝。
2. `--apply`：追加缺失行进沙箱 trade_log.csv（脚本 csv 追加，保标记）；追加后复核：再比对缺失须为 0，
全量标记 grep 复核通过。重复跑追加 0 行（幂等）。
3. `--archive`：复核缺失为 0 后，把华为 bookings 移入
`/root/monitor/huawei_bookings_archive/huawei_bookings_YYYYMMDD_HHMMSS.csv`（md5 校验一致），
再把 live 文件截为仅表头并复核只剩 1 行。缺失 > 0 时拒绝归档（RC=1，live 文件未动）；
空 bookings 文件不归档。归档文件名时间戳取华为主机 `date`（UTC）。
4. 归档后跑沙箱 `quota.py` 一次：数字应与合并前（trade_log + bookings 两份读）一致，
因去重口径保证合并前后同一笔只算一次。
5. 本脚本只读华为 bookings（cat），只追加沙箱 trade_log，归档只动华为 bookings 文件；绝不写华为 trade_log 副本。

## 干跑验证（真实跑过，2026-11-13 10:03–10:15）

### V1 P1-3 回归（新代码，华为真实跑）

`python3 /tmp/fw_rehang_test/run_fw_tests.py`：**10/10 PASS**（修复 `booking_row_for` 取价键名 bug 后；
中间一次 1/10：`exception: 'price'`——`booking_row_for` 用 `fill["price"]`，而 `new_bookings` 键名是
`order_price`；已改兼容两键并重跑全过）。`queue_pending_after_compare=[]`。

### V2 记账 live 夹具（华为 `/tmp/bk_test/`，全部夹具路径，不碰真实队列/账本）

夹具快照 `bk_test_bk1.json`（4 笔成交：新 A 卖 601088 100@52.62、新 A 买 510300 1300@4.122、
新 B 买 600919 1000@12.50、已入账 A 卖 601088 200@49.58；trade_log 用真实副本）：

| 轮次 | 模式 | 结果 |
|---|---|---|
| 1 | live | `live_emitted_2`；记账 3 行（A2 卖 100@52.62 金额 5262.00、A1 买 1300@4.122 金额 5358.60、B线 买 1000@12.50 金额 12500.00，标记【A2】/【A1】/【B线】、委托时间齐全）；补挂 2 笔下发到夹具队列（买 100@51.59、卖 1300@4.204）；已入账的 200@49.58 未重记；state 同存 `booked` 与 `emitted` |
| 2 | live（同快照重跑） | `no_new_fills`；bookings 行数不变（4 行，md5 不变）、队列仍 2 文件——幂等 |
| 3 | compare（夹具重置后） | `computed_compare_only`；`would_book` 列 3 行；bookings 仍 1 行（仅表头）、队列 0 文件、不建 state——compare 不写 |

### V3 合规/额度读两份（沙箱 fakehome + 华为实测）

- 额度（fakehome，`HOME=/tmp/bk_test/fakehome`）：基线 A2 deployed 59046.64 / grid_available 83441.73、B deployed 0；
加入 bookings（新 A2 买 200@48.61 + 今日已入账 A2 卖 200@49.58 的重复份 + 新 B 买 1000@12.50）后：
A2 deployed **68773.74（+9727.10 = 9722 + 佣金 5.00 + 过户费 0.10）**、grid_available **73714.63（−9727.10）**、
A2 pnl 不变 966.71（重复卖单正确去重）；B deployed **12505.13**、grid_available 404285.33；A1/A3/A 不变。
- 孪生单：bookings 同键新买单 2 份 → A2 持仓 1200→1600 股、deployed 78500.84（+2×9727.10）、pnl 不变。
- B 持仓（合规函数 monkeypatch）：基线 `{}`（B 空仓）；bookings（B 买 1000 + B 卖 400 + 10-27 买入重复份）→ `{'600919': 600}`。
- 华为合规实测（真实文件、仅表头 bookings）：A1 买 100@4.999 → reject（非节点价，grid_available 12056.30 读数正确）；
B 卖 600919 100@13.00 → reject（卖出 100 超 B线持仓 0）；均 RC=1、无 LLM 调用。

### V4 合并脚本端到端（沙箱，trade_log 用副本；live bookings 用 1 笔模拟行）

模拟行（B 买 600919 100@12.50，快照 TEST——B 线现无在途订单，不会与真实成交撞键）：

| 步 | 命令 | 结果 |
|---|---|---|
| dry-run | `merge_huawei_bookings.py --dry-run --trade-log tl_copy.csv` | bookings 1 行、trade_log 77 行、缺失 1 行；未写文件 |
| apply #1 | `--apply --trade-log tl_copy.csv` | 追加 1 行；复核缺失 0 行；真实 trade_log md5 不变 |
| apply #2 | 同上再跑 | 追加 0 行，幂等；复核通过 |
| archive | `--archive --trade-log tl_copy.csv` | 归档 `/root/monitor/huawei_bookings_archive/huawei_bookings_20261113_021318.csv` md5 `0264ee11b4f1b73ceab3159fa2f28295`；live 文件截为仅表头 |
| 拒绝归档 | 模拟行未合并时 `--archive --trade-log tl_copy_orig.csv` | 拒绝，RC=1，live 文件未动（md5 不变） |

中间修过一个 bug：合并后标记复核报“2 行成交行缺标记”——是 2026-10-16/19 两行遗留【A线】单仓行，
`MARKERS` 未含【A线】；已补进复核白名单（华为记账本身只产生 A1/A2/A3/B线）。
最终状态：live bookings 仅表头（md5 `b1267c5794ca154aae604377c7dd7ea1`）、真实 trade_log md5 不变、
华为 quota A2 与沙箱一致（deployed 59046.64 / grid_available 83441.73）。

### V5 运行态复核

- fillwatch-rehang.timer（compare）在新代码部署后 10:03–10:13 各轮均为 `no_new_fills`、无异常。
- 真实队列：pending 空、failed 空、done 仅 `B-REALTEST-1113.json`（既有）。
- `order_executor.py` 未动（mtime 2026-11-12 16:07；与沙箱副本 md5 不同是 P1-1 门控改动遗留的既有差异，非本次）。

## 遗留风险 / 待办

1. **切 live 待真实成交比对**：记账与 P1-3 补挂共用 `--mode live` 开关；切 live 前须有真实 A 线成交，
逐笔核对华为记账行与沙箱 worker 入账行（键、金额、标记）一致。切 live 前再确认 `order_queue/pending|done|failed`
与 `claims/` 状态（P1-3 清单）。
2. **优价差**：华为记账价 = 委托价；优价成交时与沙箱实价差几分×股数，合并时以 trade_log 实价为准。
若日后要华为记账价也取实价，须另接成交明细页（不在轻量版内）。
3. **同日买卖跨文件均价尾差**：`read_fill_rows` 按日期稳定排序（trade_log 在前、bookings 行排同日之后）；
同日同股买卖拆在两文件时均价有分级尾差（数元级），不会撞上卖超持仓（A1/A2 卖老股、A3 持仓 33000 股远大于单笔）。
4. **孪生单跨文件分拆**：同键孪生单恰好拆在两文件时，max 计数会少算 1 笔（须同键同日同量同价的两次独立成交，
历史 0 例）。合并日志逐键报数，可审计。
5. **同步覆盖面**：`realized_ledger.py` 靠沙箱源 + 每小时同步保真；`order_compliance.py` 与
`fillwatch_rehang.py` 不在同步清单内，改动须沙箱源与华为运行版双份同步并核 md5（本次已做到）。
6. **账本可卖量仍读节点账本文件**：合规 A 线卖量校验用账本“可卖”行，不读 trade_log；华为记账后账本文件本身
仍靠沙箱同步更新（账本重算不在 P1-4 内），Muse 停机期间账本可卖量会滞后——合规卖量校验可能偏保守，
属已知边界（P2 再议）。
7. **GitHub 归档**：用户 2026-11-13 定文档须推送 GitHub（仓库 whdd-wdf/ab-）——本记录目前只在沙箱 hidden_files，
推送不属 P1-4 任务体，留待主代理按新规则办理。
