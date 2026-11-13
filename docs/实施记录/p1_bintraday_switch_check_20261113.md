# P1-2 B 线 intraday 移华为 — 切换前在轨确认（2026-11-13 09:17–09:20 CST）

确认员：只确认、不重做、不改任何东西、不下单。确认时点 2026-11-13 09:17–09:20 CST。
并行比对窗口 09:35–15:00 尚未开始，本记录只确认“进行中无异常 + 切换条件当前状态”，不判定最终切换结果。
最终切换由 runonce b-intraday-switch-1113 于今日 15:10 自行执行并上报，主代理另行确认。

## 1. runonce b-intraday-switch-1113 — 在轨 ✅

- 存在、enabled=true，runonce，at 2026-11-13T15:10:00，timezone Asia/Shanghai，owner goal:a。
- 任务体与方案文档（b_intraday_huawei_plan_20261113.md §5.1/§5.3）一致：
  验证并行比对（66 轮 status 一致、无 error、华为 kline_source 全 sina、无触发；不一致/error/kline_source 非 sina 超 3 轮即不过）
  → 验证 claims/ 为空 → 通过则停沙箱 cron b-intraday-monitor（disable 不删除）、华为 timer compare→live、更新方案文档/GOAL.md/MEMORY.md、报主聊天
  → 不过则不切、不动任何 cron/timer、报具体项等主代理定夺。
- 硬约束齐全：验证不过绝不硬切、不下真实单、不改交易规则口径、key/凭证绝不进聊天日志。

## 2. 并行比对当前状态 — 进行中无异常 ✅（窗口未开，0 轮盘中比对）

华为侧（经 hw_ssh.sh，华为时间 09:17:40 CST）：
- `/root/monitor/b_intraday_run.log`：mtime 2026-11-13 09:15:01（距确认时约 2.5 分钟，10 分钟内 ✅），共 7 行，
  08:45–09:15 每 5 分钟一行，全部 `{"mode": "compare", "status": "skip", "note": "out_of_window_or_gate_closed"}`。
- error 数：0（grep -i error 无命中）。
- 华为 timer `b-intraday-monitor.timer`：enabled + active，下次触发 09:20:00，上次 09:15:01。
- 模式文件 `/root/monitor/b_intraday_mode` 内容为 `compare`；触发器 `/root/monitor/b_intraday_trigger.py` 含 compare/dryrun/live 三档逻辑，缺省 compare。
- 华为 `claims/`：空 ✅。沙箱 `claims/`：亦空。
- 华为 `/root/workspace/.../b_intraday/run_20261113.jsonl`：尚不存在——属预期（窗口 09:35 未开，触发器只写 skip 行、不跑检测脚本）。
- 华为 `atr_cache.json` / `regime.json` 仍为 2026-11-12 09:21 旧缓存——属预期，按方案 §3.2/§4.1 由 09:35 首轮刷新为当日、source 应为 sina；15:10 验证时须核对。

沙箱侧：
- cron `b-intraday-monitor`：enabled=true，interval@5m，Asia/Shanghai，仍在跑（compare 期它仍是唯一执行方 ✅）。
- 沙箱 `run_20261113.jsonl`：22 行，mtime 09:14，末 5 行（08:54–09:14）全部 `out_of_window`、trigger null ✅。

kline_source：窗口未开，尚无盘中轮次可核对（华为与沙箱均未取数），15:10 验证时须按方案核对全日 66 轮。

## 3. claims 状态 — 空 ✅

- 华为 claims/ 空，沙箱 claims/ 空，无残留认领，无双单风险（compare 模式本就不写 pending）。

## 4. Hook 状态 — 均启用、无异常 ✅

- `b-intraday-done`：enabled=true，poll 60s，脚本 `~/hooks/scripts/b_intraday_huawei.sh`。近 5 次调用全部 silent，
  payload `{"date": "20261113", "new": [], "seen_count": 0, "total": 0, "note": "no_files_or_ssh_failed rc=2 err="}`——
  无 done/failed 文件，属 compare 期预期静默（rc=2 为无匹配文件时的 ls 返回码，非故障）。
- `trade-log-sync`：enabled=true，poll 60s。近 5 次调用全部 silent，09:14 左右一次 `trade_log synced`
  （mtime 1794532450，md5 eecf8d0d363014fe857983bfddaea2ab），其余 `trade_log unchanged`，同步链路正常。
- 旧 hook `b-intraday` 仍为 disabled（已废弃，未复用）✅；`fillwatch` 启用中，不受影响。

## 5. 是否具备 15:10 切换条件 — 当前状态：具备待验证 ⏳

- 切换前置（runonce 存在且任务体正确、华为 compare 在跑、claims 为空、hook 启用）当前全部就绪，无阻塞项。
- 但切换判定条件（66 轮一致、无 error、kline_source 全 sina、无触发）须等 09:35–15:00 并行比对跑完才能判定，
  现在无法、也不应断言通过或不通过。
- 15:10 runonce 须核对的待验证点：① 全日 66 轮 status 一致性；② 华为 kline_source 全 sina；
  ③ 华为 atr_cache.json/regime.json 已刷新为当日且 source=sina；④ claims/ 切换前仍为空；⑤ 无 error/取数失败超 3 轮。

## 6. 异常 — 无

- 本次确认未发现异常。唯一需说明的非异常现象：b-intraday-done hook 日志 note 含 `rc=2`（无匹配文件所致，静默正确），
  以及华为当日 run jsonl 尚未生成（窗口未开所致），均非故障。
