# 盒内 AI 自修 bug 轮记录（2026-11-13，执行员 A）

## 基线（本轮重跑，fix2 状态）
- 命令：python3 tests/test_<t>.py --base /workspace/ab-/virtual
- 合规 4/4，门控 9/9，执行器 9/14，fillwatch 1/5，合计 23/32 = 71.9%。
- 残留：执行器 5 项、fillwatch 4 项（见下）。

## 两处残留 bug（只向 AI 提供现象与失败输出）
1. 执行器：move_order（约 line 66）open(src_path) 拿到 base 目录而非订单文件，
   IsADirectoryError: Is a directory。失败项：执行器 exit 0、处理 2 笔、合规单进 done、
   不合规单进 failed、执行器写了快照。入账本身（trade_log/节点核减/quota）在 fix2 已通。
2. fillwatch：detect_new_fills(snapshot, logged) 只定义 2 参，main() 第 237 行以 3 参
   (snap, logged, base) 调用，TypeError: detect_new_fills()。失败项：新成交检出 1 笔、
   算出补挂单 1 笔、verdict=computed、已入账成交静默。

## 纪律
- 沙箱侧只给 AI 失败输出与待读代码，不给补丁、不告诉改哪行、怎么改，不直接改盒内脚本。
- AI 输出的函数由机械脚本（/tmp/apply_fn.py）按函数名原样替换进副本，不改内容；
  输出与原文相同、或语法不通过时不应用。
- 每轮产物用轮次后缀区分：fixA1/、fixA2/ 为四脚本与自测的副本，原件未动。

## 第一轮（fixA1）
- 交给 AI 的内容：失败输出全文（含执行器完整 traceback）+ 两脚本全文；要求只输出
  改过的完整函数定义（代码块形式），不输出解释与未修改内容。提示词约 13.9K/10.2K 字符。
- AI 输出（驱动 /workspace/ops_driver.py，qwen2.5:3b，temperature 0.2，num_ctx 8192，
  num_predict 800）：
  - 执行器 FIXA1-X：2364 字符，174.8 秒。复述了文件片段（helpers、gate_open、move_order
    等 7 个 def），最后一个函数 def gate_open(base): 被截断，全文语法不通过（ast 解析失败）。
    其中 move_order 与原文相同。未应用。
  - fillwatch FIXA1-F：670 字符，69.8 秒。输出的 detect_new_fills 与原文逐字相同，
    等于没改。未应用。
- 是否一次修对：否，两处均未修。
- 重测（fixA1 副本）：合规 4/4，门控 9/9，执行器 9/14，fillwatch 1/5，合计 23/32。

## 第二轮（fixA2）
- 吸取第一轮教训（整文件提示词诱发复述、输出被截断），改短提示词：只给调用链上的
  相关函数（执行器：move_order、process_one、main；fillwatch：detect_new_fills、main），
  并告知上一轮失败的事实（执行器输出截断语法不通过；fillwatch 输出与原文相同）。
  未告知任何改法与行号。提示词约 5.6K/3.9K 字符。
- AI 输出：
  - 执行器 FIXA2-X：441 字符，39.8 秒。只输出一个函数 move_order，与原文逐字相同。
    机械套用判定 NOOP，未应用。
  - fillwatch FIXA2-F：670 字符，29.9 秒。与第一轮输出逐字相同，仍是原文
    detect_new_fills，未改。机械套用判定 NOOP，未应用。
- 是否一次修对：否，两处均未修。
- 重测（fixA2 副本）：合规 4/4，门控 9/9，执行器 9/14，fillwatch 1/5，合计 23/32。

## 结论：AI 自修失败
- 两轮上限用完，通过率仍 23/32 = 71.9%，未达 80%（26/32）。不可做对接验证。
- 失败模式（供后续判断参考，非补丁）：
  - 执行器：两轮 AI 都只复述 move_order 本身，未动调用方；第二轮输出的 move_order
    与原文完全相同。
  - fillwatch：两轮输出都是原文 detect_new_fills 的逐字复述，未动定义与调用方中的任何一方。
  - 小模型（qwen2.5:3b）在“只输出改过的函数”指令下仍倾向复述原文；短提示词后输出变短变干净，
    但内容仍是原样照抄。
- 沙箱侧未代修：fixA1/fixA2 副本与 fix2 状态的四脚本内容一致（md5 见同步清单），
  未谎称 AI 修好。
