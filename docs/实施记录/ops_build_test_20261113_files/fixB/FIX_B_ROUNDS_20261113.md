# 盒内更大模型自修 bug 轮记录（2026-11-13，执行员 B，qwen2.5-coder:7b）

## 基线（本轮盒内重跑，fix2 状态，fixB0）
- 命令：`python3 tests/test_<t>.py --base /workspace/ab-/virtual`（盒内 `~/ops-build/`）
- 合规 4/4，门控 9/9，执行器 9/14，fillwatch 1/5，合计 23/32 = 71.9%。
- 盒内四脚本 md5 与沙箱 fix2 副本一致（executor b7918338、fillwatch 5e0a4cfe、compliance 1527e621、gate b3259598）。
- 完整失败输出已取回：执行器 `IsADirectoryError: [Errno 21] Is a directory: '/tmp/vx/virtual'`
  （main L303 → process_one L236 `move_order(src_path, base, "done", result)` → move_order L66 `open(src_path)`）；
  fillwatch `TypeError: detect_new_fills() takes 2 positional arguments but 3 were given`
  （main L237 `detect_new_fills(snap, logged, base)`）。

## 纪律
- 沙箱侧只给 AI 失败输出与待读代码，不给补丁、不告诉改哪行、怎么改，不直接改盒内脚本。
- 每轮提示词只含：bug 现象 + 自测失败输出全文 + 相关脚本全文 + 自测脚本全文（断言与通过标准）。
  自测脚本作为通过标准交给模型，不含任何改法提示。模型输出的函数由机械脚本
  （fixB1/fixB2 内 `apply_fn.py`）按函数名原样替换进副本，不改内容；输出与原文相同
  或语法不通过时不应用。
- 每轮产物用轮次后缀区分：fixB1/、fixB2/ 为四脚本与自测的副本，原件（`~/ops-build/` 根目录 fix2 脚本）未动。

## 模型与驱动
- 模型：盒内 Ollama `qwen2.5-coder:7b`（4.7GB），temperature 0.2，`num_ctx` 第一轮 16384、第二轮 8192，
  `num_predict` 2048。驱动为新写的 `driver_b.py`（仿 `ops_driver.py`，模型名改为 qwen2.5-coder:7b，
  逐 job 可配 num_ctx/num_predict），nohup 后台跑、短命令轮询。
- 实测速度：提示词约 19K/15K/10K/9K 字符时，单任务 299.8 / 216.8 / 144.4 / 130.9 秒。
  含约 5K token 提示词处理在内，有效生成速度明显低于任务简报称的约 9 tok/s（两轮输出仅约 140/170 token，
  大部分时间花在提示词处理上）。内存偏紧：模型加载时 available 约 35Mi，未 OOM。

## 第一轮（fixB1，全文提示词）
- 交给 AI 的内容：失败输出全文（含执行器完整 traceback）+ 两脚本全文 + 两自测脚本全文；
  要求只输出改过的完整函数定义。提示词 20072 / 15704 字符。
- AI 输出（qwen2.5-coder:7b）：
  - 执行器 FIXB1-X：563 字符，299.8 秒。只改 `move_order`：加 `if os.path.isdir(src_path): shutil.move(...)`
    分支，else 保持原样。**未定位真正原因**：没动调用方（process_one 的传参），也没补返回值。
    机械套用判定 APPLIED（diff 24 行）。
  - fillwatch FIXB1-F：684 字符，216.8 秒。输出的 `detect_new_fills` 与原文逐字相同。
    机械套用判定 NOOP，未应用。
- 是否一次修对：否，两处均未修。
- 重测（fixB1 副本）：合规 4/4，门控 9/9，执行器 9/14，fillwatch 1/5，合计 23/32。
- 执行器失败输出变了（新 traceback 已取回，`executor_traceback_b1.txt`）：
  `AttributeError: 'NoneType' object has no attribute 'get'`（main L308 `result.get("kind")`），
  因 move_order 全程无 return，process_one 返回 None。isdir 分支把崩溃点从 move_order 内推到了 main，
  但 5 项失败数未变。

## 第二轮（fixB2，短提示词 + 上轮失败事实）
- 吸取第一轮教训，改短提示词：只给调用链上的相关函数（执行器：move_order、process_one、main；
  fillwatch：detect_new_fills、main），并告知上一轮失败的事实（执行器改了 isdir 分支仍 5 项失败、
  新失败输出为 AttributeError；fillwatch 输出与原文相同），仍不给任何改法与行号。
  提示词 10956 / 9416 字符。
- AI 输出：
  - 执行器 FIXB2-X：563 字符，144.4 秒。与第一轮输出**逐字节相同**（md5 8bb03eed 相同），
    仍是同一个 isdir/shutil 版 move_order。fixB2 副本里该函数已是此版本，机械套用判定 NOOP，未应用。
  - fillwatch FIXB2-F：684 字符，130.9 秒。与第一轮输出**逐字节相同**（md5 9a44f9a6 相同），
    仍是原文 detect_new_fills。机械套用判定 NOOP，未应用。
- 是否一次修对：否，两处均未修。
- 重测（fixB2 副本）：合规 4/4，门控 9/9，执行器 9/14，fillwatch 1/5，合计 23/32。

## 结论：更大模型自修失败
- 两轮上限用完，通过率仍 23/32 = 71.9%，未达 80%（26/32）。不可做对接验证。
- 失败模式（供后续判断参考，非补丁）：
  - 执行器：两轮 AI 都只改了 `move_order` 本身（症状级 isdir 分支），未动调用方；
    第二轮输出与第一轮逐字节相同，属自我重复。另有 latent 点：move_order 全程无 return，
    main 取 `result.get("kind")` 会 AttributeError——该点在两轮里均未被模型提及或修复。
  - fillwatch：两轮输出都是原文 `detect_new_fills` 的逐字复述，未动定义与调用方中的任何一方。
    另有 latent 点：main 以 `if new_fills is None` 判静默（detect 返回空列表时走不到静默分支）、
    输出键名是 `orders` 而自测取 `computed_orders`——该两点在两轮里均未被模型提及或修复。
  - 与 qwen2.5:3b（fixA）相比，qwen2.5-coder:7b 的表现是：不再输出截断/语法不通过的内容，
    但同样倾向复述原文或只做症状级改动，且第二轮自我重复；换更大模型未解决“定位不到调用不一致处”
    这一瓶颈。瓶颈在调试定位，不在生成流畅度。
- 沙箱侧未代修：fixB1/fixB2 副本的四脚本 md5 为 executor e269e16a（仅含模型第一轮的 move_order 改动）、
  fillwatch 5e0a4cfe（与 fix2 相同）、compliance 1527e621、gate b3259598，未谎称 AI 修好。

## 自测最终通过率：23/32 = 71.9%（未变）

| 脚本 | 通过/总数 |
|---|---|
| 合规 | 4/4 ✅ |
| 门控 | 9/9 ✅ |
| 执行器 | 9/14 ❌ |
| fillwatch | 1/5 ❌ |
| 合计 | 23/32 = 71.9% |

## 对接验证：未做（按规则跳过）

通过率 71.9% < 80%，按任务规则跳过对接验证。记为“操作侧脚本未能跑通，对接未做”。
原定对接（A 线卖单 601088 卖 200 @49.58 + B 线买单 600919 @12.98 500 股，核实合规、执行、
快照、入账、quota 平衡）须等两处 bug 修完重测达 80% 后补做。

## 同步清单
- 盒内 `~/ops-build/fixB0/`（基线 4 份自测日志 + 2 份完整 traceback）、`fixB1/`、`fixB2/`
  已整包（tar.gz，md5 fe9830370137a52ae6235d3f352206d1，42977 字节）经 base64 分块传回沙箱，
  解包于 `docs/实施记录/ops_build_test_20261113_files/fixB/`，共 66 个文件 + 本记录；
  解包后 md5 复核一致（executor e269e16a、fillwatch 5e0a4cfe）。同步齐全，无缺失。
  （注：解包时 tar 报 ownership 警告，仅影响文件属主，不影响内容；已用 md5 核对。）
- 盒子状态：任务结束时仍 running，未休眠（协调员统一休眠）。
