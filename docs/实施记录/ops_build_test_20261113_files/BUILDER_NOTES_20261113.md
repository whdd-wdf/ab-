# 搭建员记录 BUILDER_NOTES_20261113.md（非 AI 产物，是搭建员的核查记录）

时间：2026-11-13，盒内 UTC 06:44-07:20（北京时间 14:44-15:20）。驱动盒内 AI：Ollama qwen2.5:3b。
任务：验证别的 AI 能否只凭 GitHub 文档独立搭操作侧（四脚本 + README）。

## 轮次总览

- 提取 E1-E4：4 项完成（E1 1351 字、E2 854 字、E3 781 字、E4 1181 字）。E3 把 trade_log 标记写成“备注开头须带 / 或 → 或 之一”，
  `///` 标记被模型丢掉；E1/E2/E4 均被 token 上限截断。
- v1（4 段）：1/4 语法通过，0/4 逻辑正确。
- R1（15 段）：组装后合规/执行器/fillwatch 语法失败，门控语法过；自测 0 项实质通过。
- R2（23 段，微提示词、单函数、字面量内联）：23 段全部生成；14 段含 markdown 围栏/中文说明残留，
  经机械清理（只删围栏行与 注意/说明/以上 开头的散文行，见 CLEANUP_R2.log）后 23/23 语法通过；
  组装后四脚本 py_compile 4/4 通过；自测仍 0 项实质通过（见下）。

## R2 自测结果（最终版 R2b 组装，日志见 logs/test_r2b_*.log）

- test_compliance：0/4。原因：r2_c_runmain.py 缺 `if __name__ == "__main__"` 入口行（模型漏写），
  脚本执行时静默退出 0、无任何输出。逻辑本身经导入验证 4/4 全对：
  601088 卖 200@49.58 通过（6 项全 pass）；买 48.00 被拒（理由“买价=节点价”）；
  B 买 600919 @13.63 被拒（理由“涨幅 6.48%”“买价≈现价”）；B 买 600919 500@12.98 通过。
- test_executor：3/12（3 项为与执行器无关的空洞通过：两次虚拟 submit 成功、未动数据的 quota 平衡）。
  原因有三：① r2_x_gatekey.py 的 gate_open 写 `datetime.datetime.now(TZ)`，而模块内 datetime 是类，
  标志存在时即 AttributeError；② r2_x_applyfill.py 的 apply_fill 传 `q[code]` 而不是已算好的 `h`，
  任何成交都 KeyError: '601088'；③ 下游被合规缺入口堵死（子进程调用合规无输出、解析失败）。
- test_gate：0/9。原因：① r2_g_main.py 用 --action，真实门控（P1 记录 ExecStart）用位置参数 open/close/status；
  ② datetime 类/模块名冲突：r2_g_helpers.py 用 `import datetime`（模块，datetime.date / datetime.datetime），
  而 helpers 段用 `from datetime import datetime`（类，datetime.now），两种顺序都只能满足一方，
  实测 is_trading_day("2026-11-13") 报 TypeError（descriptor 'date' ...），flag_state 报 AttributeError；
  ③ flag_state 用 timezone.utc 而不是北京时间（上午时段会把当日标志判为过期， latent 缺陷）；
  ④ is_trading_day 只接受 "YYYY-MM-DD" 字符串，传 date 对象即 TypeError。
- test_fillwatch：0/5。原因：r2_f_snap.py 顶行 `import tzlocal`（非标准库，盒内无此模块），
  整个模块导入即 ModuleNotFoundError；唯一的快照龄期实现因此不可用。
  （注：R2 组装时曾误判 tzlocal 来自 r1/f3.py 并去掉 f3，后核实 tzlocal 在 r2_f_snap.py 第 3/25 行。）

## 对接测试（任务 3c）：未跑通，被堵死

A 线卖单 601088 卖 200 @49.58 + B 线买单 600919 @12.98 500 股的端到端（合规→执行→快照→入账→quota）
无法执行：合规 CLI 无输出、执行器 gate_open 崩溃、fillwatch 无法导入。三处均为上述缺陷所致，
搭建员未手写代码替补（那样会 falsify 验证）。

## 组装决策（只改段顺序与删段，不改任何 AI 代码行）

- helpers 段须放在含 `if __name__` 的段之前，否则 main() 触发时 now()/today_str()/round_tick 未定义
  （R2 初版执行器即因此报 today_str NameError）。
- fillwatch 去掉 r1/f3.py：其两个函数已被 R2 段覆盖（且 f3 另有问题）。
- 合规 helpers 移到 runmain 之前（仍缺入口行，无济于事，仅保证导入后函数可用）。
- 门控保持 helpers 在最后：两种顺序都解不开 datetime 名冲突，helpers 在最后时至少 now()/in_window 可用。

## 驱动器两次无声消失（无 traceback、无日志收尾）

- E4 首次尝试约 06:12-06:13 UTC；R2 第 22 个任务（R2-F-REHANG）约 07:03 UTC。两次均重试通过。
  原因未明，已记录。

## README.md（AI 自己写，1640 字，133.9 秒）

- “文档不够用”8 条是有效证据：节点/quota 精确 JSON 字段名、入账更新公式、交易日周一至五兜底、
  B 线卖出补挂细节、队列命名、订单 JSON 字段名、状态流转细节、虚拟成交与记账口径均须抄虚拟程序。
- “读了哪些文档”一节含糊（未提分段提取 E1-E4 与两轮修复）；“用法”一节编造了不存在的 CLI 参数
  （executor --order_file、gate --gate_file、fillwatch --fill_file）与 /root/monitor/ 路径；
  文末被 800 token 上限截断（fillwatch 命令写到一半断掉）。

## 产物清单（~/ops-build/）

- order_compliance.py 273 行、order_executor.py 318 行、gate_local.py 148 行、fillwatch_rehang.py 261 行
  （R2b 组装；四脚本 py_compile 全过，但自测 0 项实质通过，见上）。
- README.md（AI 写，见上）、tests/（4 个自测）、r1/（15 段）、r2/（23 段）、
  ASSEMBLY_R1/R2/R2b.log、CLEANUP_R2.log、logs/（提取/R1/R2/README 日志 + R2b 四项自测日志原文）。
- 浏览器执行层（laptop_order.py）按任务要求不含在本次四脚本内，未实测。

