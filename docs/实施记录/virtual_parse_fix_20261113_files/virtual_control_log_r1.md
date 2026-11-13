# 虚拟程序对接测试：盒内 AI 一轮管控实录

开始时间 2026-11-13 13:21:11 CST

[2026-11-13 13:21:11 CST] 脚本启动。模型=qwen2.5:3b，虚拟目录=/workspace/ab-/virtual，干跑=False（错三元组=False）
[2026-11-13 13:21:11 CST] 门控标志 .trading_day 当日=True，B线可用=490341.72，B线持仓={}
[2026-11-13 13:21:11 CST] check 600176：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "600176", "name": "中国巨石", "prev_close": 10.52, "price": 10.46, "buy_price": 10.46, "change_pct": -0.0057, "deviation_pct": 0.0, "p4_limit": 10.84, "qty_50k": 4700, "amount_50k": 49162.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:21:11 CST] check 002475：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "002475", "name": "立讯精密", "prev_close": 38.2, "price": 38.51, "buy_price": 38.51, "change_pct": 0.0081, "deviation_pct": 0.0, "p4_limit": 39.35, "qty_50k": 1200, "amount_50k": 46212.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:21:11 CST] check 000596：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "000596", "name": "古井贡酒", "prev_close": 86.1, "price": 85.78, "buy_price": 85.78, "change_pct": -0.0037, "deviation_pct": 0.0, "p4_limit": 88.68, "qty_50k": 500, "amount_50k": 42890.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:21:11 CST] check 600919：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "600919", "name": "江苏银行", "prev_close": 12.8, "price": 12.98, "buy_price": 12.98, "change_pct": 0.0141, "deviation_pct": 0.0, "p4_limit": 13.18, "qty_50k": 3800, "amount_50k": 49324.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:21:11 CST] check 600018：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "600018", "name": "上港集团", "prev_close": 6.52, "price": 6.5, "buy_price": 6.5, "change_pct": -0.0031, "deviation_pct": 0.0, "p4_limit": 6.72, "qty_50k": 7600, "amount_50k": 49400.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:21:12 CST] check 603198：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "603198", "name": "迎驾贡酒", "prev_close": 43.6, "price": 44.11, "buy_price": 44.11, "change_pct": 0.0117, "deviation_pct": 0.0, "p4_limit": 44.91, "qty_50k": 1100, "amount_50k": 48521.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:21:12 CST] check 000001：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "000001", "name": "平安银行", "prev_close": 11.48, "price": 11.32, "buy_price": 11.32, "change_pct": -0.0139, "deviation_pct": 0.0, "p4_limit": 11.82, "qty_50k": 4400, "amount_50k": 49808.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:21:12 CST] check 600000：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "600000", "name": "浦发银行", "prev_close": 10.86, "price": 10.74, "buy_price": 10.74, "change_pct": -0.011, "deviation_pct": 0.0, "p4_limit": 11.19, "qty_50k": 4600, "amount_50k": 49404.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:21:12 CST] 程序预计算表已拼好，共 8 只候选
[2026-11-13 13:22:37 CST] 步骤A选股 成功：attempt=1 耗时 86 秒，输出 927 字

## 步骤 A_pick AI 输出原文

正例：600176 中国巨石，P4 10.84，现价 10.46，涨幅 -0.57%，符合买入条件。现价 10.46，P4 10.84，单笔金额 49162.00，符合单笔金额条件。买入后持仓为 1 只，符合持仓条件。定稿：代码600176，买入价10.46，数量4700股。复述：代码600176，名称中国巨石，现价10.46。

正例：002475 立讯精密，P4 39.35，现价 38.51，涨幅 0.81%，符合买入条件。现价 38.51，P4 39.35，单笔金额 46212.00，符合单笔金额条件。买入后持仓为 1 只，符合持仓条件。定稿：代码002475，买入价38.51，数量1200股。复述：代码002475，名称立讯精密，现价38.51。

正例：000596 古井贡酒，P4 88.68，现价 85.78，涨幅 -0.37%，符合买入条件。现价 85.78，P4 88.68，单笔金额 42890.00，符合单笔金额条件。买入后持仓为 1 只，符合持仓条件。定稿：代码000596，买入价85.78，数量500股。复述：代码000596，名称古井贡酒，现价85.78。

正例：600919 江苏银行，P4 13.18，现价 12.98，涨幅 1.41%，符合买入条件。现价 12.98，P4 13.18，单笔金额 49324.00，符合单笔金额条件。买入后持仓为 1 只，符合持仓条件。定稿：代码600919，买入价12.98，数量3800股。复述：代码600919，名称江苏银行，现价12.98。

正例：600018 上港集团，P4 6.72，现价 6.50，涨幅 -0.31%，符合买入条件。现价 6.50，P4 6.72，单笔金额 49400.00，符合单笔金额条件。买入后持仓为 1 只，符合持仓条件。定稿：代码600018，买入价6.50，数量7600股。复述：代码600018，名称上港集团，现价6.50。

正例：603198 迎驾贡酒，P4 44.91，现价 44.11，涨幅 1.17%，符合买入条件。现价 44.11，P4 44.91，单笔金额 48521.00，符合单笔金额条件。买入后持仓为 1 只，
[2026-11-13 13:22:37 CST] 三元组复述与 quotes 一致：代码=600176 名称=中国巨石 现价=10.46
[2026-11-13 13:22:37 CST] 步骤A解析：代码=600176 买入价=10.46 数量=4700 金额=49162.00 前收=10.52 P4=10.84
[2026-11-13 13:22:37 CST] check 600176：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "600176", "name": "中国巨石", "prev_close": 10.52, "price": 10.46, "buy_price": 10.46, "change_pct": -0.0057, "deviation_pct": 0.0, "p4_limit": 10.84, "qty_50k": 4700, "amount_50k": 49162.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:22:47 CST] 步骤B把关 成功：attempt=1 耗时 10 秒，输出 50 字

## 步骤 B_gate AI 输出原文

逐项读数判断：1）通过；2）通过；3）通过；4）通过；5）通过；6）通过；7）通过。
合规结论：通过
[2026-11-13 13:22:47 CST] 步骤B解析：合规结论=通过
[2026-11-13 13:22:47 CST] check 600176：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "600176", "name": "中国巨石", "prev_close": 10.52, "price": 10.46, "buy_price": 10.46, "change_pct": -0.0057, "deviation_pct": 0.0, "p4_limit": 10.84, "qty_50k": 4700, "amount_50k": 49162.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:22:47 CST] 辩论前程序复核通过：三元组/涨幅/P4/股数/金额五项一致
[2026-11-13 13:22:54 CST] 步骤C保守方 成功：attempt=1 耗时 6 秒，输出 107 字

## 步骤 C_conservative AI 输出原文

反对买入的理由包括：当前股价与前收盘价相比有微小跌幅，表明市场可能对该公司近期表现持观望态度；拟买入数量较大，占现有持仓比例较高，可能导致仓位过重；金额达到49162.00元，对资金管理构成压力。保守方结论：跳过。
[2026-11-13 13:23:02 CST] 步骤C激进方 成功：attempt=1 耗时 9 秒，输出 157 字

## 步骤 C_aggressive AI 输出原文

支持买入的理由：当前价格为10.46元，与前一日收盘价10.52元相比，跌幅仅为-0.57%，表明市场对该股仍持正面态度。拟买入价10.46元与当前价格完全一致，意味着可以以当前市价买入，避免因市场波动导致的额外成本。拟买入数量4700股，金额49162元，占总仓位的10%，保持了投资组合的分散性。激进方结论：买
[2026-11-13 13:23:15 CST] 步骤C评判 成功：attempt=1 耗时 13 秒，输出 180 字

## 步骤 C_judge AI 输出原文

裁决：买，置信度0.85。

综合考虑，激进方的意见更为全面，从价格、市场态度以及资金管理的角度都提供了有力的支持。尽管保守方指出了一些风险点，但激进方通过分析认为这些风险点并不足以改变当前的买入决策。激进方强调了当前价格与前收盘价的接近，以及拟买入数量和金额对投资组合的影响，这些因素都支持了激进方的结论。因此，综合来看，激进方的意见更具有说服力，建议买入。
[2026-11-13 13:23:15 CST] 步骤C解析：裁决=买 置信度=0.85
[2026-11-13 13:23:15 CST] 订单 JSON：{"order_id": "B-20261113-600176-1", "code": "600176", "side": "买入", "price": 10.46, "qty": 4700, "line": "B", "prev_close": 10.52, "limit_price": 10.84}
[2026-11-13 13:23:15 CST] 提交订单：exit=0 耗时 0.1 秒，输出：{"ok": true, "action": "submit", "order_id": "B-20261113-600176-1", "status": "pending", "virtual": true}

[2026-11-13 13:23:15 CST] 执行器 run：exit=0 耗时 0.1 秒，输出：{"ok": true, "action": "run", "date": "2026-11-13", "processed": 1, "filled": [{"order_id": "B-20261113-600176-1", "code": "600176", "side": "买入", "price": 10.46, "qty": 4700, "amount": 49162.0, "fill_time": "2026-11-13 13:23:15", "realized_pnl": 0.0}], "rejected": [], "gate_closed": []}

[2026-11-13 13:23:15 CST] 快照 snapshot：exit=0 耗时 0.1 秒，输出：{"label": "fillwatch", "timestamp": "2026-11-13 13:23:15", "status": "ok", "orders": [{"order_id": "B-20261113-600176-1", "code": "600176", "name": "中国巨石", "side": "买入", "price": 10.46, "qty": 4700, "time": "2026-11-13 13:23:15", "status": "已成交"}], "fills_today": [{"order_id": "B-20261113-600176-1", "code": "600176", "name": "中国巨石", "side": "买入", "price": 10.46, "qty": 4700, "time": "2026-11-13 13:23:15", "status": "已成交"}], "pending": [], "file": "fillwatch_20261113_1323.json", "stale": false, "virtual": true}

[2026-11-13 13:23:15 CST] 提交→快照延时 0 秒
[2026-11-13 13:23:15 CST] 最新快照 fillwatch_20261113_1323.json：status=ok fills_today=[{'order_id': 'B-20261113-600176-1', 'code': '600176', 'name': '中国巨石', 'side': '买入', 'price': 10.46, 'qty': 4700, 'time': '2026-11-13 13:23:15', 'status': '已成交'}]
[2026-11-13 13:23:15 CST] trade_log 尾部：exit=0 耗时 0.1 秒，输出：虚拟 trade_log：共 2 行（含表头），尾部 2 行：
日期,代码,名称,方向,价格,数量,金额,盈亏,备注
2026-11-13,600176,中国巨石,买入,10.46,4700,49162.00,,【B线】买入成交（委托10.46；委托10.46，2026-11-13 13:23:15成交；订单B-20261113-600176-1；虚拟成交）

[2026-11-13 13:23:29 CST] 步骤D成交确认 成功：attempt=1 耗时 14 秒，输出 145 字

## 步骤 D_confirm AI 输出原文

1）这笔买单成交，成交信息为：订单ID B-20261113-600176-1，代码600176，中国巨石，方向买入，价格10.46，数量4700。
2）延时计算公式：13:23:15 - 13:23:15 = 0秒。
3）在虚拟 trade_log 中未找到这笔成交行。
成交确认：未确认
[2026-11-13 13:23:29 CST] 步骤D解析：未确认/未明
[2026-11-13 13:23:29 CST] 脚本结束
