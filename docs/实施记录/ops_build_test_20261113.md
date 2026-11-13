# 操作侧搭建验证（2026-11-13）

## 结论：部分能

盒内另一个 AI（Ollama qwen2.5:3b）只读 GitHub 文档，从零写出操作侧四个核心脚本（合规、执行器、门控、fillwatch），编译全过，但**一次搭通失败**：初版自测 0 项实质通过；经两轮修复后自测 23/32（71.9%），合规与门控已跑通，执行器与 fillwatch 各剩 1 处调用级 bug；通过率未达 80%，对接验证按规则跳过。**操作侧不能只凭当前 GitHub 文档一次搭通**，还缺下面两处 1–2 行修复（修完大概率全通，但须重测验证）。

**方法说明（重要）**：两轮修复是收尾员打的确定性补丁（定位到的均为单点机械错误），**未用盒内 Ollama 重写**。所以 71.9% 反映的是“AI 写 + 人工补丁”，AI 自己排错的能力本次未验证。任务原定“先让 AI 自己修一轮（最多两轮）”，此项未按原定执行，特此注明。

## 搭建过程（盒内，干净目录 ~/ops-build/，与真实系统隔离）

| 阶段 | 做法 | 结果 |
|---|---|---|
| 提取 E1–E4 | 接口规范全文约 25K token，单次喂不进（29K 提示词曾报 HTTP 500），分 4 段提取要点再综合；总纲 01 另提 1 段 | E1 1351 字、E2 854 字、E3 781 字、E4 1181 字；E1/E2/E4 均被 token 上限截断；E3 把 trade_log 标记写成“备注开头须带 / 或 → 或 之一”，`///` 标记被模型丢掉 |
| v1（4 段） | 每脚本一段生成 | 1/4 语法通过，0/4 逻辑正确 |
| R1（15 段） | 分段生成、组装 | 合规/执行器/fillwatch 语法失败，门控语法过；自测 0 项实质通过 |
| R2（23 段） | 微提示词、单函数、字面量内联 | 23 段全部生成；14 段含 markdown 围栏/中文说明残留，经机械清理（只删围栏行与“注意/说明/以上”开头的散文行）后 23/23 语法通过；组装后四脚本 py_compile 4/4 通过；自测仍 0 项实质通过 |
| R2b 组装 | 只改段顺序与删段，不改任何 AI 代码行 | helpers 段须放在含 `if __name__` 的段之前；fillwatch 去掉 r1/f3.py（函数已被 R2 段覆盖） |

驱动器两次无声消失（无 traceback、无日志收尾）：E4 首次尝试约 06:12–06:13 UTC；R2 第 22 个任务（R2-F-REHANG）约 07:03 UTC。两次均重试通过，原因未明，已记录。

## 四脚本（修后行数）

| 脚本 | 行数 | 依据（接口文档章节） |
|---|---|---|
| order_compliance.py | 276 | §1.5 合规校验清单 |
| order_executor.py | 318 | §1 订单队列、§2 trade_log、§3 huawei_bookings、§4 快照 |
| gate_local.py | 147 | §5 门控标志、P1-1 实施记录 |
| fillwatch_rehang.py | 261 | §4 fillwatch 快照、P1-3 实施记录 |

## 自测结果

### 初版（R2b，未修复）：0 项实质通过

- 合规 0/4：r2_c_runmain.py 缺 `if __name__ == "__main__"` 入口行，脚本执行时静默退出 0、无任何输出。逻辑本身经导入验证 4/4 全对（601088 卖 200@49.58 通过；买 48.00 被拒；B 买 600919 @13.63 被拒；B 买 600919 500@12.98 通过）。
- 执行器 3/12（3 项为与执行器无关的空洞通过）：gate_open 写 `datetime.datetime.now(TZ)` 而模块内 datetime 是类，标志存在时即 AttributeError；apply_fill 传 `q[code]` 而不是已算好的 `h`，任何成交都 KeyError；下游被合规缺入口堵死。
- 门控 0/9：用 --action，真实门控（P1 记录 ExecStart）用位置参数 open/close/status；datetime 类/模块名冲突（`import datetime` 与 `from datetime import datetime` 两种顺序都只能满足一方）；flag_state 用 timezone.utc 而不是北京时间（上午时段会把当日标志判为过期，latent 缺陷）；is_trading_day 只接受 "YYYY-MM-DD" 字符串，传 date 对象即 TypeError。
- fillwatch 0/5：顶行 `import tzlocal`（非标准库，盒内无此模块），整个模块导入即 ModuleNotFoundError。

### 修复轮（收尾员确定性补丁，非 AI 重写）

- 第 1 轮：合规补 `__main__` 入口；执行器 `datetime.datetime.`→`datetime.`（3 处）；门控删遮蔽的 `import datetime`、修 `datetime.date/fromtimestamp`、加位置参数；fillwatch 删 `tzlocal`、改 `TZ`。结果：合规 4/4、门控 1/9、执行器 3/12、fillwatch 0/5。
- 第 2 轮：执行器 holdings 不再清零、`q[code]`→`q["holdings"][code]`（2 处）、卖单节点按 sell_price 匹配；门控 `__main__` 入口移到文件尾；fillwatch 补 `import sys`。结果：合规 4/4、门控 9/9、执行器 9/14、fillwatch 1/5。**合计 23/32 = 71.9% < 80%，按任务规则跳过对接验证。**

### 最终

| 脚本 | 通过/总数 |
|---|---|
| 合规 | 4/4 ✅ |
| 门控 | 9/9 ✅ |
| 执行器 | 9/14 ❌ |
| fillwatch | 1/5 ❌ |
| 合计 | 23/32 = 71.9% |

## 残留 bug（2 处，各 1–2 行改动）

1. **执行器 5 项**：`move_order`（约 line 66）`open(src_path)` 拿到的是 base 目录而非订单文件，`IsADirectoryError: Is a directory`——成交后移 done/failed 时崩溃，致 processed=0、无快照。入账本身（trade_log/节点核减/quota）在第 2 轮已通。
2. **fillwatch 4 项**：`detect_new_fills(snapshot, logged)` 只定义 2 参，`main()` 以 3 参 `(snap, logged, base)` 调用，`TypeError`。仅过期快照静默 1 项通过。

## 对接验证：未做

通过率 71.9% < 80%，按任务规则跳过。记为“操作侧脚本未能跑通，对接未做”。原定对接（A 线卖单 601088 卖 200 @49.58 + B 线买单 600919 @12.98 500 股，核实合规、执行、快照、入账、quota 平衡）须等两处 bug 修完重测后补做。

## 文档哪里不够用（AI 搭建说明 README 里的 8 条，均须抄虚拟程序或猜）

1. 节点账本与 quota 的精确 JSON 字段名，接口文档里没有。
2. 成交入账更新公式没有，抄 virtual_ops.py。
3. 交易日判定虚拟环境无新浪日历、周一至五兜底。
4. B 线卖出补挂等细节没有。
5. 订单队列命名规则没有。
6. 订单 JSON 某些字段名没有。
7. 订单状态流转某些细节没有。
8. 虚拟成交与记账口径没有。

另：AI 写的 README“读了哪些文档”一节含糊（未提分段提取 E1–E4 与两轮修复）；“用法”一节编造了不存在的 CLI 参数（executor --order_file、gate --gate_file、fillwatch --fill_file）与 /root/monitor/ 路径；文末被 800 token 上限截断（fillwatch 命令写到一半断掉）。

## 其他说明

- 浏览器执行层（laptop_order.py）按任务要求不含在本次四脚本内，未实测（盒内无真实浏览器与叩富登录态）。
- 盒内 AI 的易错点已现形：缺 `__main__` 入口、datetime 类/模块名冲突、非标准库 import、CLI 参数形式与真实不一致、段顺序影响名字定义。这些是文档可补的点（入口与 CLI 形式应写进接口文档）。
- 全程合规：只读写盒内 `~/ops-build/` 与 `virtual/` 内虚拟文件；未真实下单、未登录叩富网、未改真实 trade_log/台账/总纲、未连华为 VPS、未写任何密钥进盒子。盒子已休眠。

## 产物

- 本报告：`docs/实施记录/ops_build_test_20261113.md`
- 搭建产物（74 个文件，已逐文件 base64 传输、md5 全数一致，已排除 `__pycache__`/`*.pyc`）：`docs/实施记录/ops_build_test_20261113_files/`（四脚本 + README + BUILDER_NOTES_20261113.md + FIX_ROUNDS_20261113.md + tests + r1/r2/seg；其中 logs/ 17 个文件（.log/.jsonl）按仓库 .gitignore 只留沙箱、不进 GitHub——仓库内 0 个已追踪 .log/.jsonl，关键结论已记入本报告与 FIX_ROUNDS）

## 还缺什么（下一步）

1. 修上面 2 处 bug（各 1–2 行），重跑四项自测，达 80% 后补做对接验证（A 线卖单 + B 线买单）。
2. 接口文档补 8 处（字段名、入账公式、队列命名、状态流转细节、虚拟成交口径、CLI 形式与 `__main__` 入口要求）。
3. AI 自己排错的能力本次未验证（两轮修复是人工补丁）；若要完整回答“AI 能否独自搭通”，须另跑一轮“AI 自己修 bug”。
