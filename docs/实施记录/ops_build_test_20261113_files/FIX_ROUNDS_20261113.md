# 操作侧四脚本修复轮记录（2026-11-13 收尾员）

方法：未用盒内 Ollama 重写（定位到的均为单点机械错误，直接打补丁更稳）；两轮上限已用完，停。

## 第一轮（fix1）
- order_compliance.py：补 `if __name__ == "__main__": sys.exit(main())`（原文件缺入口，静默退出 rc=0）。
- order_executor.py：`datetime.datetime.` -> `datetime.`（3 处；import datetime 遮蔽类）。
- gate_local.py：删遮蔽的 `import datetime`；`datetime.date(` -> `datetime(`；`datetime.datetime.fromtimestamp` -> `datetime.fromtimestamp`；加位置参数 action_pos。
- fillwatch_rehang.py：删 `import tzlocal`；`datetime.datetime.strptime` -> `datetime.strptime`；`tzlocal.get_localzone()` -> `TZ`。
- 结果：合规 4/4，门控 1/9，执行器 3/12，fillwatch 0/5。

## 第二轮（fix2）
- order_executor.py：holdings 不再清零（setdefault）；`q[code]` -> `q["holdings"][code]`（2 处）；卖单节点按 sell_price/节点价×1.02 匹配。
- gate_local.py：`__main__` 入口移到文件尾（原在 helpers 定义之前，today_str/TZ 未定义）。
- fillwatch_rehang.py：补 `import sys`。
- 结果：合规 4/4，门控 9/9，执行器 9/14，fillwatch 1/5。合计 23/32 = 71.9% < 80%，按任务跳过对接验证。

## 残留 FAIL（未修，两轮已用完）
- 执行器 5 项：`move_order`（约 line 66）`open(src_path)` 拿到的是 base 目录而非订单文件，`IsADirectoryError: Is a directory`，成交后移 done/failed 时崩溃，致 processed=0、无快照。
- fillwatch 4 项：`detect_new_fills(snapshot, logged)` 只定义 2 参，main() 以 3 参 `(snap, logged, base)` 调用，TypeError。
- 其余：执行器 trade_log/节点核减/快照 5 项在 fix2 已通过（9/14 中的 9 项含这些）。

## 行数（修后）
- order_compliance.py 276，order_executor.py 318，gate_local.py 147，fillwatch_rehang.py 261。
