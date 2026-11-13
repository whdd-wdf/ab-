# P1-3 A 线 fillwatch 上华为 — 实施记录（2026-11-13）

## 结论

- **compare 模式已上线并行跑**：华为 `fillwatch_rehang.py` + `fillwatch-rehang.timer`（每 2 分钟，09:30–15:05 窗口内）已启用，与沙箱 hook 并行比对中。
- **干跑验证 10/10 全过**（真实跑过，见下）。
- **live 状态：待比对，未切**。今日截至 09:32 A 线真实成交 0 笔，无逐笔比对样本；按任务要求不强行切 live。切 live 的前置条件：出现真实 A 线成交，且华为算出的补挂单与沙箱 hook 唤醒后主代理实际补挂的单逐笔一致；切前再确认 `claims/` 与 `order_queue/pending` 为空。

## 文件位置

| 文件 | 位置 | 说明 |
|---|---|---|
| 比对+补挂脚本（华为运行版） | 华为 `/root/monitor/fillwatch_rehang.py` | 新文件，未改 `cofool_fillwatch.py` / `order_executor.py` / `order_compliance.py` |
| 沙箱留存副本（同源） | `~/workspace/goals/a/hidden_files/monitor_huawei/fillwatch_rehang.py` | md5 与华为版一致 `4e04c26944d21b0602d040a8a8c4d0f6` |
| systemd 服务/计时器 | 华为 `/etc/systemd/system/fillwatch-rehang.service`、`.timer` | `OnCalendar=Mon-Fri *:01/2`（2026-11-13 09:39 竞态修正，见下节；原 `:00/2` 已废止，备份见 `.bak-20261113`）；服务 `--mode compare` |
| 运行日志 | 华为 `/root/monitor/fillwatch_rehang.log`、`/root/monitor/fillwatch_rehang_20261113.jsonl` | 每轮一行 JSON verdict |
| 干跑夹具与断言脚本 | 华为 `/tmp/fw_rehang_test/`（`case*.json/csv`、`ledger_case8.md`、`run_fw_tests.py`）；沙箱生成器 `/tmp/gen_fw_test.py` | 仅测试用，不在正式路径 |
| 本记录 | `~/workspace/goals/a/hidden_files/p1_fillwatch_20261113.md` | — |

备份说明：脚本为新文件，华为上无同名旧文件可覆盖（部署前已确认不存在）；沙箱副本即备份源。未改动 MEMORY.md、总纲 docs、GOAL.md。

## 规则实现（fillwatch_rehang.py）

- **数据源（华为本地）**：最新快照 `/root/monitor/snapshots/fillwatch_YYYYMMDD_*.json`；trade_log 副本 `/root/workspace/goals/a/files/paper-trading/trade_log.csv`（已核：md5 `eecf8d0d363014fe857983bfddaea2ab` 与沙箱一致；账本 md5 `e0d5a97d01885730c684603914e95181` 两边一致）；节点账本同目录 `A线网格节点账本.md`（解析口径与 `order_compliance.py` 的 `parse_ledger` 一致）；行情 `quotes.py` 取 `prev_close`。
- **新成交检出口径（与沙箱 fillwatch_compare.py / quota.py 一致）**：匹配键 `(代码, 方向, 数量, 委托价)`；trade_log 委托价取备注 `委托价?(\d+\.\d+)`（兼容“委托价/委托”两种写法，须带小数点）；备注含“委托中”/“已撤销”的行不算已入账成交；方向栏须恰为“买入”/“卖出”；只比 A 线三码。
- **补挂计算**：卖出成交 → 按节点价补买单（节点由卖价反推：满足 `round_tick(节点×1.02)=卖价` 的账本节点）；买入成交 → 按节点价×1.02（tick 取整：510300/513650 为 0.001，601088 为 0.01）补卖单，数量与成交量相同；A3（513650）买入成交当日可卖（`tplus0: true`，T+0 口径）；A1/A2 买入成交后挂的卖单卖老股（以账本可卖量校验）。
- **过滤（任一不过即跳过并记 reason）**：单笔金额 <5000（`small_amount`）；补挂价为禁挂集群价 A1 4.316/4.324/4.325、A2 52.06（`banned_cluster_price`）；补挂价已在在挂单中（`duplicate_pending_sell/buy`，**以快照 `orders` 中“未成交”为准，不用 laptop_order.py orders 读数**——其多页读数会漏页）；卖价高于当日涨停（`above_limit_up`，涨停=前收×1.10 tick 取整；今日实测前收 A1 4.114 / A2 48.96 / A3 1.99，涨停 4.525 / 53.86 / 2.189）；卖出量超账本可卖量；买入金额超 `grid_available`（quota.py 本地跑，取不到时只记 note、不拦截，live 时合规再拦）。节点反推不到（`node_not_found`，如跌停价买入无法反推节点）时跳过、不猜单。
- **去重**：已下发（live  emitted）的成交以 fill key（代码|方向|委托价|数量|委托时间）记入 `/root/monitor/fillwatch_rehang_state.json`，不再重复算；跳过的成交每轮重算（在挂重复解除后可恢复）。compare 模式不写 state、不写队列。
- **窗口与快照保护**：窗口 09:30–15:05（与 fillwatch_compare 对齐）；快照 status 非 ok 或超 5 分钟过期不计算，只记 verdict；compare 模式下过期/错误快照不唤醒（告警仍由沙箱 hook 负责）。
- **live 模式（已实现，未启用）**：写单前校验交易日标志 `/root/monitor/.trading_day` 为当日且 07:30–17:05、华为 `b_intraday/claims/` 为空；订单 JSON（`order_id/order_id FW-YYYYMMDD-代码-buy/sell-价-委托时间`、`code/side/price/qty/line/prev_close/note`）写入 `order_queue/pending/`（原子 tmp+rename，写后复核存在再记 state）；执行器合规+笔记本下单仍由 `order_executor.py` / `order-watcher.path` 负责，本脚本不直接下单、不写 trade_log。

## 干跑验证（华为真实跑过，2026-11-13 09:21，10/10）

断言脚本 `/tmp/fw_rehang_test/run_fw_tests.py`，每例独立快照+trade_log+state，前收用 `--prev-close 510300:4.114,601088:48.96,513650:1.99`：

| 例 | 场景 | 期望 | 结果 |
|---|---|---|---|
| case1 | 卖出 601088 200@49.58 | 补买 200@48.61（节点价） | PASS |
| case2 | 买入 510300 1800@4.122 | 补卖 1800@4.204（节点×1.02） | PASS |
| case3 | case1 的成交已入账（trade_log 有委托价 49.58 的卖出行） | 无新成交、不重复算 | PASS |
| case4 | trade_log 里只有该成交的“委托中”行 + 一笔已撤销行 | 仍算新成交、补买 200@48.61 | PASS |
| case5 | 买入 601088 200@48.61，但卖 49.58 已在挂 | `duplicate_pending_sell` 跳过 | PASS |
| case6 | 买入 513650 3000@2.156 → 卖 2.199 | 高于涨停 2.189，`above_limit_up` 跳过 | PASS |
| case7 | 卖出 601088 100@50.58 → 补买 100@49.59=4959 | <5000，`small_amount` 跳过 | PASS |
| case8 | 买入 510300 1300@4.231（定制账本含节点 4.231）→ 卖 4.316 | 禁挂集群价，`banned_cluster_price` 跳过 | PASS |
| case9 | 买入 513650 3000@1.992（当日买） | 补卖 3000@2.032，`tplus0: true` | PASS |
| case10 | 卖出 510300 1800@4.999（无对应节点） | `node_not_found` 跳过 | PASS |

附加验证：

- 干跑后 `order_queue/pending` 仍为空（`queue_pending_after_compare=[]`），compare 模式未创建 state 文件（`state_created_in_compare=False`，timer 的 compare 轮次同样未创建 `/root/monitor/fillwatch_rehang_state.json`）。
- 实时行情路径验证（2026-11-13 09:32，不带 `--prev-close`，case1 夹具）：`prev_close: 48.96, limit_up: 53.86`，算出买入 200@48.61，与用覆盖值的结果一致；`order_id: FW-20261113-601088-buy-48p61-20261113094733`。

## 并行比对（华为 compare vs 沙箱 hook，2026-11-13 上午）

| 时间 | 华为 fillwatch_rehang（compare） | 沙箱 hook fillwatch_compare | 一致？ |
|---|---|---|---|
| 09:22 手动 smoke | `outside_window` | —（窗口外） | — |
| 09:26 / 09:28 timer | `outside_window` | — | — |
| 09:30 | `stale_snapshot`，快照 09:06:22，age 1418s | 09:30:22 `wake / stale_snapshot`，同份快照 age 1440s | ✓ 同一份过期快照、同一结论（华为不计算、沙箱按既有规则唤醒告警） |
| 09:32 | `no_new_fills`，快照 09:30:00，age 120s | 09:31:22 `no_new_fills`，快照 09:30:00，age 82s | ✓ |
| 09:30 快照实况 | `status ok, fills=0, pending=23` | — | A 线当日成交 0 笔 |

说明：09:30 出现 stale 是因为 fillwatch 写端窗口 09:30 起写、首份盘中快照即 09:30，09:30 整点那轮读到的仍是 09:06 的盘前快照——为写端既有行为，非本脚本问题；两边结论一致。

## Live 状态：待比对（未切）

- 切 live 前置未满足：今日截至 09:32 无真实 A 线成交可逐笔比对（B 线空仓，A 线成交可能很少）。
- 切 live 前复核清单（届时逐项打勾）：① 有真实成交且华为补挂单 vs 沙箱主代理实际补挂单逐笔一致；② 华为 `b_intraday/claims/` 为空（2026-11-13 09:24 查为空）；③ `order_queue/pending|done|failed` 为空（同日查为空）；④ `.trading_day` 为当日（2026-11-13 07:25 已立）；⑤ 脚本改 `--mode live` 的方式：改 `fillwatch-rehang.service` 的 `ExecStart` 为 `--mode live` 后 `daemon-reload`，不动 timer。
- compare timer 将持续并行跑（每 2 分钟），直至真实成交比对一致后再切。

## 遗留风险 / 待办

1. **无真实成交样本**：live 切换待真实成交比对；若多日无成交，并行期相应延长，不赶工。
2. **跌停价买入无法反推节点**：买入成交价为跌停价（节点价低于跌停、按跌停价挂）时，脚本 `node_not_found` 跳过，需人工/主代理处理；属安全跳过（宁可漏补、不错补），待后续规则明确。
3. **trade_log 同步延迟**：华为 trade_log 副本靠沙箱同步（约 5 分钟级）；若入账延迟，华为会把已成交未入账的单算成新成交——live 时 state + 队列去重可防重复下单，但入账后沙箱 hook 仍会唤醒一次（P1-4 入账走沙箱 worker 后，华为 state 与沙箱台账的衔接需再核）。
4. **09:30 首轮 stale（已修正，见下节“竞态修正”）**：旧相位 `:00/2` 下 09:30 整点轮次固定 stale 一次；修正后首轮为 09:31，读刚落盘的 09:30 快照，不再 stale。
5. **GitHub 归档**：用户 2026-11-13 新定“GitHub 为唯一可查源，文档与记录须提交并推送到 GitHub（仓库 whdd-wdf/ab-）”——本记录目前只在沙箱 hidden_files，推送 GitHub 不属 P1-3 任务体，留待主代理按新规则办理。

## 竞态修正（2026-11-13 09:39，P1-3 本项）

### 相位差实测

- 写端 `cofool-fillwatch.timer` 与比对端 `fillwatch-rehang.timer` 原先同为 `OnCalendar=Mon-Fri *:00/2`，**相位差 0 秒**，同秒触发（`systemctl list-timers` 09:36 实测：两 timer NEXT 均为 09:38:00，LAST 均为 09:36:00）。
- 写端落盘实测（快照 mtime）：09:30:30.73、09:32:29.25、09:34:29.45、09:36:29.25、09:38:28.97、09:40:29.08——即触发后约 **29–31 秒**才落盘。
- 旧相位下比对端每轮读到的都是上一周期快照（`snapshot_age_secs` 恒 120s）；09:30 首轮读到的是 09:06:22 盘前快照，age 1418s > 300s 阈值 → `stale_snapshot`，首轮浪费，且新成交要晚一轮（2 分钟）才被看到。沙箱 hook 同日 09:30:22 对同一份过期快照误唤一次（沙箱侧行为，不属本项）。
- 09:02–09:28 写端每 2 分钟退出码 3 是窗口外主动 return 3 的设计行为（窗口 09:30–15:05），不是故障，未动、未报。

### 选的方案：(a) 计时器相位错开（主方案）；(b) 只作注释，未实施

- `fillwatch-rehang.timer` 改为 `OnCalendar=Mon-Fri *:01/2`（奇数分钟触发：09:31、09:33、…、15:05）。写端 :00 触发、:00:30 落盘，比对端 :01 触发，读到刚落盘约 30 秒的快照。
- 窗口核算：`in_window` 为分钟粒度 09:30–15:05，首轮 09:31 在窗内、末轮 15:05（奇数分）在窗内，轮次总数不变（168 轮/日，与旧相位相同）。
- (b) 脚本内快照新鲜度门**未加**：timer 相位已保证新鲜读数，再加一道跳过门只会多一条可掩盖 timer 漂移的静默路径；理由已写入 timer 文件注释。脚本 `fillwatch_rehang.py` 一行未改（md5 不变），compare/live 逻辑、退出码 3 行为均未动。

### 验证（真实跑过）

| 时间 | 轮次 | 读到的快照 | age | 结论 |
|---|---|---|---|---|
| 09:38:00（改前最后一轮旧相位） | 定时 | 09:36:00 | 120s | 旧行为：读上一周期快照 |
| 09:39:19（改 timer 后 `systemctl restart` 触发的一轮） | 重启触发 | 09:38:00（09:38:28.97 落盘） | 79s | 读到刚落盘的快照，`no_new_fills`——与新相位首轮几何相同（触发在落盘后约 50 秒） |
| 09:41:01（新相位首个定时轮次） | 定时 | 09:40:00（09:40:29.08 落盘） | 61s | `no_new_fills`；09:40:00 无旧相位轮次 fired，偶数分轮次已停 |
| 09:41:32 | 手动 | 09:40:00 | 92s | `no_new_fills`，rc=0 |

- `list-timers` 改后：写端 NEXT 09:42:00、比对端 NEXT 09:43:00，两端稳定错开 60 秒。
- 09:30 首轮场景模拟：无法倒回 09:30 实测，但 09:39:19 与 09:41:01 两轮已证明新相位几何——比对端在写端落盘后约 30–60 秒运行，读到刚落盘的快照；按此几何，下一个交易日 09:31 首轮将读 09:30:30 落盘的 09:30 快照（age 约 30–60s），不再 stale、不再浪费首轮。stale 判定逻辑本身未改（阈值仍 300s），若写端某轮落盘异常延迟仍会照常记 `stale_snapshot`。
- 干跑复核（改后重跑 `/tmp/fw_rehang_test/run_fw_tests.py`）：**10/10 PASS**（case1–case10 与改前一致）；`order_queue/pending` 仍为空，compare 未创建 state 文件。脚本未改，复核仅证明 timer 改动未波及检测能力。

### 备份与同步

- 华为备份（2026-11-13 09:38，改前）：`/etc/systemd/system/fillwatch-rehang.timer.bak-20261113`（旧 md5 `93cf74ff72d8edac808ad636fad12896`）、`.service.bak-20261113`、`/root/monitor/fillwatch_rehang.py.bak-20261113`。
- 新 timer md5：`154ced7383eaf49eead38b8cbdcdfcfc`；`daemon-reload` + `restart fillwatch-rehang.timer` 已执行。
- 脚本未改：华为与沙箱副本 md5 仍一致 `4e04c26944d21b0602d040a8a8c4d0f6`，无需同步拷贝。
- 未改：`cofool_fillwatch.py` / `order_executor.py` / `order_compliance.py` / 沙箱 hook / MEMORY.md / 总纲 / GOAL.md；无真实订单（全程 compare）。

### 遗留风险

1. 写端落盘耗时若某天超过 60 秒（目前 29–31 秒，余量约 30 秒），:01 轮次会读到上一周期快照（age 约 120s，仍在 300s 阈值内可算，仅延迟一轮），不会误算；若连续多轮落盘延迟才可能 stale，届时只记日志、不误唤（华为侧本就不唤醒）。
2. 沙箱 hook 仍在 :22 秒取快照，其 09:30 首轮 stale 误唤不在本项范围内（沙箱侧逻辑），华为侧修正不改变沙箱行为；待沙箱侧另行处理。
3. 下一个交易日 09:31 首轮为第一次真实“新相位首轮”观测，建议届时核对该轮 `snapshot_age_secs` 约为 60s 且非 stale。

### 真实成交验证（2026-11-13 09:43，新相位首个实战样本）

- 09:42 快照中 601088 卖出 200@49.58（委托时间 08:36:19）状态由未成交变为已成交（09:40 快照仍为未成交）——真实成交，成交窗口在 09:40:29–09:42:29 之间。
- 新相位 09:43:01 轮次即从刚落盘的 09:42 快照（age 61s）检出该成交，`verdict: computed`，算出补挂买入 200@48.61（`order_id: FW-20261113-601088-buy-48p61-20261113083619`，金额 9722.00，节点价 48.61）；旧相位要到 09:44:00 才看到，**新相位提前一轮（2 分钟）检出**。
- compare 模式：`emitted_order_ids: []`，`order_queue/pending` 仍为空，未创建 state 文件，未下单。09:45:01 轮次重复算出同一单（compare 不写 state、每轮重算，属预期行为；live 时 state 去重）。
- 此为 P1-3 等待的真实 A 线成交比对样本：华为算单为买入 601088 200@48.61，可与沙箱 hook 唤醒后主代理实际补挂单逐笔比对（比对本身不属本项，交主代理）。
