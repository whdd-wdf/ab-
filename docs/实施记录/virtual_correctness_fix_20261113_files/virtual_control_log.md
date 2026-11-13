# 虚拟程序对接测试：盒内 AI 一轮管控实录

开始时间 2026-11-13 12:34:38 CST

[2026-11-13 12:34:38 CST] 脚本启动。模型=qwen2.5:3b，虚拟目录=/workspace/ab-/virtual，干跑=False（错三元组=False）
[2026-11-13 12:34:38 CST] 门控标志 .trading_day 当日=True，B线可用=490341.72，B线持仓={}
[2026-11-13 12:34:38 CST] check 600176：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "600176", "name": "中国巨石", "prev_close": 10.52, "price": 10.46, "buy_price": 10.46, "change_pct": -0.01, "deviation_pct": 0.0, "p4_limit": 10.84, "qty_50k": 4700, "amount_50k": 49162.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 12:34:38 CST] check 002475：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "002475", "name": "立讯精密", "prev_close": 38.2, "price": 38.51, "buy_price": 38.51, "change_pct": 0.01, "deviation_pct": 0.0, "p4_limit": 39.35, "qty_50k": 1200, "amount_50k": 46212.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 12:34:38 CST] check 000596：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "000596", "name": "古井贡酒", "prev_close": 86.1, "price": 85.78, "buy_price": 85.78, "change_pct": -0.0, "deviation_pct": 0.0, "p4_limit": 88.68, "qty_50k": 500, "amount_50k": 42890.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 12:34:38 CST] check 600919：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "600919", "name": "江苏银行", "prev_close": 12.8, "price": 12.98, "buy_price": 12.98, "change_pct": 0.01, "deviation_pct": 0.0, "p4_limit": 13.18, "qty_50k": 3800, "amount_50k": 49324.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 12:34:38 CST] check 600018：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "600018", "name": "上港集团", "prev_close": 6.52, "price": 6.5, "buy_price": 6.5, "change_pct": -0.0, "deviation_pct": 0.0, "p4_limit": 6.72, "qty_50k": 7600, "amount_50k": 49400.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 12:34:39 CST] check 603198：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "603198", "name": "迎驾贡酒", "prev_close": 43.6, "price": 44.11, "buy_price": 44.11, "change_pct": 0.01, "deviation_pct": 0.0, "p4_limit": 44.91, "qty_50k": 1100, "amount_50k": 48521.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 12:34:39 CST] check 000001：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "000001", "name": "平安银行", "prev_close": 11.48, "price": 11.32, "buy_price": 11.32, "change_pct": -0.01, "deviation_pct": 0.0, "p4_limit": 11.82, "qty_50k": 4400, "amount_50k": 49808.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 12:34:39 CST] check 600000：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "600000", "name": "浦发银行", "prev_close": 10.86, "price": 10.74, "buy_price": 10.74, "change_pct": -0.01, "deviation_pct": 0.0, "p4_limit": 11.19, "qty_50k": 4600, "amount_50k": 49404.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 12:34:39 CST] 程序预计算表已拼好，共 8 只候选
[2026-11-13 12:34:43 CST] 步骤A选股 成功：attempt=1 耗时 4 秒，输出 73 字

## 步骤 A_pick AI 输出原文

复述：代码600176，名称中国巨石，现价10.46。

定稿：代码600176，名称中国巨石，现价10.46，买入价10.46，数量4700股。
[2026-11-13 12:34:43 CST] 步骤A未按格式给定稿行（正则未命中），停止，不替 AI 猜数字
