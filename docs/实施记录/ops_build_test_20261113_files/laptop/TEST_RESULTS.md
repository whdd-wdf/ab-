# 笔记本搭建（操作侧四脚本）测试结果 — 2026-11-13

产物目录：`docs/实施记录/ops_build_test_20261113_files/laptop/`（四脚本为原文件复制，md5 与笔记本工作目录一致；本文件为测试结果摘要）。
完整报告见 `docs/实施记录/ops_build_test_20261113.md` 的“笔记本搭建（2026-11-13）”章节。

## 一、环境

- 模型：DeepSeek-V4.1-Flash，经 FCC（Coarena）；完整模型 ID `anthropic/custom_11c1cd762ab64b7abf5df581d358f2fb/deepseek-v4-1-flash-1017`。
- 核实方法：FCC 服务日志 `~/.fcc/logs/server.log` 的 `request.completed` 记录显示 provider 为 `custom_11c1cd762ab64b7abf5df581d358f2fb`、model 为 `deepseek-v4-1-flash-1017`。
- Agent：Claude Code CLI 2.1.323，经 `~/.local/bin/fcc-claude` 启动器（注入 FCC 代理环境）启动，`-p` 非交互模式，stdin 传提示词，nohup 后台跑、短命令轮询。

## 二、时间口径说明（如实记录）

自测与对接在真实时间 17:18 之后跑，当时已过 07:30–17:05 门控窗口。真实时间跑基线为 21/31，失败全系窗口已过（执行器 gate-closed、虚拟 run 不成交），非脚本 bug。

真基线与对接改用 `PYTHONTZPATH=/tmp/faketz/zone`（`ZoneInfo('Asia/Shanghai')` 被替换为 UTC0 的假时区文件，假本地时间约 09:18–09:19，与真实日期同一天）；脚本本身未改。窗口逻辑本身被门控自测的过期标志等项覆盖。

## 三、编译

`python3 -m py_compile order_compliance.py order_executor.py gate_local.py fillwatch_rehang.py` → **4/4 通过**。

## 四、基线自测（真基线，假时区）

| 脚本 | 通过/总数 | 失败 |
|---|---|---|
| order_compliance | 4/4 | 0 |
| order_executor | 16/16 | 0 |
| gate_local | 9/9 | 0 |
| fillwatch_rehang | 7/7 | 0 |
| **合计** | **36/36 = 100%** | 0 |

分母说明：预案写 32（执行器 14、fillwatch 5）是按盒内跑通时的计分（条件检查跳过时分母变小）；克隆内自测文件全通过时共 36 项（执行器 16、fillwatch 7），36/36 = 100%，超过 80% 门槛（26/32）。

各脚本自测通过项（输出要点，逐项 PASS）：

- 合规（4 项）：A卖 601088 200@49.58 通过；A买 48.00 非节点价被拒；B买偏离现价>1%被拒；B买 600919 500@12.98 通过。输出“合计 4 项，失败 0 项”。
- 执行器（16 项）：虚拟 submit 成功；虚拟 submit 坏单成功；执行器 exit 0；执行器处理 2 笔；合规单进 done；成交单 result=filled；不合规单进 failed；拒绝单 result=rejected；trade_log 有 1 笔成交行；成交行带【A2】标记；成交行是卖出 200@49.58；A2 deployed 减少约 9841；A2 quota 平衡 available=quota-deployed；节点 48.61 hands 2→0；state 行变 已成交；执行器写了快照。输出“合计 16 项，失败 0 项”。
- 门控（9 项）：status 交易日为真（周五）；open 写标志；重复开门跳过不报错；status 门开；标志过期则门关；close 删标志；close pending 移入 failed；关门移单无 result 注解；非交易日（周六）判定为假。输出“合计 9 项，失败 0 项”。
- fillwatch（7 项）：新成交检出 1 笔；算出补挂单 1 笔；补挂是买入 200@48.61；补挂 order_id 格式 FW-…-buy-48p61-…；verdict=computed；已入账成交静默；过期快照 stale 静默。输出“合计 7 项，失败 0 项”。

调试迭代：0 轮（基线已全绿，无 bug 可修，无 fixC 轮次副本）。

## 五、对接验证（全部 PASS）

A 线卖单 601088 卖 200 @49.58 与 B 线买单 600919 @12.98 500 股，逐项结果：

| 检查项 | 结果 |
|---|---|
| 合规两单 | 均通过 |
| 执行器 | processed 2、filled 2、rejected 0 |
| 快照 | status ok、timestamp 2026-11-13 09:19:23、age 约 12 秒、不 stale |
| quota 四仓平衡 | A1/A2/A3/B 的 available=quota-deployed、grid_available=grid_quota-deployed 均成立 |
| A2 数值 | deployed 49205.53、quota 167708.27、pnl 1041.60 |
| B 数值 | deployed 6490.00、持 600919 500 股 |
| 虚拟 trade_log | 2 笔成交行：【A2】卖出 601088 200@49.58、盈亏 74.89；【B线】买入 600919 500@12.98 |
| 节点 | 48.61 hands 2→0、sell_price null |
| fillwatch（已入账状态下） | silent/no_new_fills |
| fillwatch（trade_log 截回表头后） | 检出新成交 1 笔，算出补买单 FW-20261113-601088-buy-48p61-20261113091923（买入 200@48.61） |

## 六、产物与仓库规则

- 四脚本：`order_compliance.py`、`order_executor.py`、`gate_local.py`、`fillwatch_rehang.py`（仅标准库，均有 `__main__` 入口）。
- 本目录不放任何 `.log` / `.jsonl`（按仓库 `.gitignore` 只留沙箱，不进 GitHub）。
- 四脚本 md5 与盒内原版不同，非复制。
