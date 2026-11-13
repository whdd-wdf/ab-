# 虚拟程序对接测试：盒内 AI 一轮管控实录

开始时间 2026-11-13 13:42:38 CST

[2026-11-13 13:42:38 CST] 脚本启动。模型=qwen2.5:3b，虚拟目录=/workspace/ab-/virtual，干跑=False（错三元组=False）
[2026-11-13 13:42:38 CST] 门控标志 .trading_day 当日=True，B线可用=490341.72，B线持仓={}
[2026-11-13 13:42:38 CST] check 600176：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "600176", "name": "中国巨石", "prev_close": 10.52, "price": 10.46, "buy_price": 10.46, "change_pct": -0.0057, "deviation_pct": 0.0, "p4_limit": 10.84, "qty_50k": 4700, "amount_50k": 49162.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:42:38 CST] check 002475：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "002475", "name": "立讯精密", "prev_close": 38.2, "price": 38.51, "buy_price": 38.51, "change_pct": 0.0081, "deviation_pct": 0.0, "p4_limit": 39.35, "qty_50k": 1200, "amount_50k": 46212.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:42:38 CST] check 000596：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "000596", "name": "古井贡酒", "prev_close": 86.1, "price": 85.78, "buy_price": 85.78, "change_pct": -0.0037, "deviation_pct": 0.0, "p4_limit": 88.68, "qty_50k": 500, "amount_50k": 42890.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:42:38 CST] check 600919：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "600919", "name": "江苏银行", "prev_close": 12.8, "price": 12.98, "buy_price": 12.98, "change_pct": 0.0141, "deviation_pct": 0.0, "p4_limit": 13.18, "qty_50k": 3800, "amount_50k": 49324.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:42:38 CST] check 600018：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "600018", "name": "上港集团", "prev_close": 6.52, "price": 6.5, "buy_price": 6.5, "change_pct": -0.0031, "deviation_pct": 0.0, "p4_limit": 6.72, "qty_50k": 7600, "amount_50k": 49400.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:42:38 CST] check 603198：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "603198", "name": "迎驾贡酒", "prev_close": 43.6, "price": 44.11, "buy_price": 44.11, "change_pct": 0.0117, "deviation_pct": 0.0, "p4_limit": 44.91, "qty_50k": 1100, "amount_50k": 48521.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:42:38 CST] check 000001：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "000001", "name": "平安银行", "prev_close": 11.48, "price": 11.32, "buy_price": 11.32, "change_pct": -0.0139, "deviation_pct": 0.0, "p4_limit": 11.82, "qty_50k": 4400, "amount_50k": 49808.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:42:39 CST] check 600000：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "600000", "name": "浦发银行", "prev_close": 10.86, "price": 10.74, "buy_price": 10.74, "change_pct": -0.011, "deviation_pct": 0.0, "p4_limit": 11.19, "qty_50k": 4600, "amount_50k": 49404.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:42:39 CST] 程序预计算表已拼好，共 8 只候选
[2026-11-13 13:43:14 CST] 步骤A选股 成功：attempt=1 耗时 35 秒，输出 65 字

## 步骤 A_pick AI 输出原文

复述：代码600176，名称中国巨石，现价10.46。

定稿：代码600176，名称中国巨石，买入价10.46，数量4700股。
[2026-11-13 13:43:14 CST] 警告：挑股理由缺失（正文仅 0 字），记警告、不阻塞
[2026-11-13 13:43:14 CST] 三元组复述与 quotes 一致：代码=600176 名称=中国巨石 现价=10.46
[2026-11-13 13:43:14 CST] 步骤A解析：代码=600176 买入价=10.46 数量=4700 金额=49162.00 前收=10.52 P4=10.84
[2026-11-13 13:43:14 CST] check 600176：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "600176", "name": "中国巨石", "prev_close": 10.52, "price": 10.46, "buy_price": 10.46, "change_pct": -0.0057, "deviation_pct": 0.0, "p4_limit": 10.84, "qty_50k": 4700, "amount_50k": 49162.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:43:23 CST] 步骤B把关 成功：attempt=1 耗时 9 秒，输出 50 字

## 步骤 B_gate AI 输出原文

逐项读数判断：1）通过；2）通过；3）通过；4）通过；5）通过；6）通过；7）通过。
合规结论：通过
[2026-11-13 13:43:23 CST] 步骤B解析：合规结论=通过
[2026-11-13 13:43:24 CST] check 600176：exit=0 耗时 0.1 秒，输出：{"ok": true, "code": "600176", "name": "中国巨石", "prev_close": 10.52, "price": 10.46, "buy_price": 10.46, "change_pct": -0.0057, "deviation_pct": 0.0, "p4_limit": 10.84, "qty_50k": 4700, "amount_50k": 49162.0, "gates": {"rise_ok": true, "p4_ok": true, "deviation_ok": true, "amount_ok": true}, "virtual": true}

[2026-11-13 13:43:24 CST] 辩论前程序复核通过：三元组/涨幅/P4/股数/金额五项一致
[2026-11-13 13:43:30 CST] 步骤C保守方 成功：attempt=1 耗时 7 秒，输出 119 字

## 步骤 C_conservative AI 输出原文

反对买入的理由：当前股价为10.46元，与前一日收盘价10.52元相比，跌幅为0.57%，表明市场对该股近期表现持观望态度。拟买入价与现价相同，金额为49162.00元，占现有资产的10%。仓位增加可能加大整体投资风险。保守方结论：跳过。
[2026-11-13 13:43:38 CST] 步骤C激进方 成功：attempt=1 耗时 8 秒，输出 136 字

## 步骤 C_aggressive AI 输出原文

支持买入的理由：当前价格为10.46元，与前一日收盘价10.52元相比，跌幅仅为-0.57%，表明市场对该股仍持乐观态度。拟买入价10.46元与当前价格完全一致，表明你认为股价可能进一步下跌的空间有限。拟买入数量4700股，金额49162元，占总资产的1%。激进方结论：买
[2026-11-13 13:43:54 CST] 步骤C评判 成功：attempt=1 耗时 16 秒，输出 251 字

## 步骤 C_judge AI 输出原文

裁决：买，置信度0.85。

综合双方意见，激进方认为当前股价虽有小幅下跌，但市场仍持乐观态度，且拟买入价与现价一致，表明股价可能进一步下跌空间有限。而保守方则指出，当前股价与前一日收盘价相比有小幅下跌，且仓位增加可能加大整体投资风险。激进方的分析更倾向于市场对股价的乐观预期，而保守方则更关注当前股价的波动。考虑到激进方的分析更为积极，且当前股价与拟买入价一致，表明市场可能认为股价有进一步下跌的空间有限，因此综合来看，激进方的意见更具有说服力。置信度定为0.85，表示有85%的置信度认为应该买入。
[2026-11-13 13:43:54 CST] 步骤C解析：裁决=买 置信度=0.85
[2026-11-13 13:43:54 CST] 订单 JSON：{"order_id": "B-20261113-600176-1", "code": "600176", "side": "买入", "price": 10.46, "qty": 4700, "line": "B", "prev_close": 10.52, "limit_price": 10.84}
[2026-11-13 13:43:54 CST] 提交订单：exit=0 耗时 0.1 秒，输出：{"ok": true, "action": "submit", "order_id": "B-20261113-600176-1", "status": "pending", "virtual": true}

[2026-11-13 13:43:54 CST] 执行器 run：exit=0 耗时 0.1 秒，输出：{"ok": true, "action": "run", "date": "2026-11-13", "processed": 1, "filled": [{"order_id": "B-20261113-600176-1", "code": "600176", "side": "买入", "price": 10.46, "qty": 4700, "amount": 49162.0, "fill_time": "2026-11-13 13:43:54", "realized_pnl": 0.0}], "rejected": [], "gate_closed": []}

[2026-11-13 13:43:54 CST] 快照 snapshot：exit=0 耗时 0.1 秒，输出：{"label": "fillwatch", "timestamp": "2026-11-13 13:43:54", "status": "ok", "orders": [{"order_id": "B-20261113-600176-1", "code": "600176", "name": "中国巨石", "side": "买入", "price": 10.46, "qty": 4700, "time": "2026-11-13 13:43:54", "status": "已成交"}], "fills_today": [{"order_id": "B-20261113-600176-1", "code": "600176", "name": "中国巨石", "side": "买入", "price": 10.46, "qty": 4700, "time": "2026-11-13 13:43:54", "status": "已成交"}], "pending": [], "file": "fillwatch_20261113_1343.json", "stale": false, "virtual": true}

[2026-11-13 13:43:54 CST] 提交→快照延时 0 秒
[2026-11-13 13:43:54 CST] 最新快照 fillwatch_20261113_1343.json：status=ok fills_today=[{'order_id': 'B-20261113-600176-1', 'code': '600176', 'name': '中国巨石', 'side': '买入', 'price': 10.46, 'qty': 4700, 'time': '2026-11-13 13:43:54', 'status': '已成交'}]
[2026-11-13 13:43:54 CST] trade_log 尾部：exit=0 耗时 0.1 秒，输出：虚拟 trade_log：共 2 行（含表头），尾部 2 行：
日期,代码,名称,方向,价格,数量,金额,盈亏,备注
2026-11-13,600176,中国巨石,买入,10.46,4700,49162.00,,【B线】买入成交（委托10.46；委托10.46，2026-11-13 13:43:54成交；订单B-20261113-600176-1；虚拟成交）

[2026-11-13 13:43:54 CST] 程序按订单号 B-20261113-600176-1 在虚拟 trade_log 里找到成交行：2026-11-13,600176,中国巨石,买入,10.46,4700,49162.00,,【B线】买入成交（委托10.46；委托10.46，2026-11-13 13:43:54成交；订单B-20261113-600176-1；虚拟成交）
[2026-11-13 13:44:16 CST] 步骤D成交确认 成功：attempt=1 耗时 21 秒，输出 209 字

## 步骤 D_confirm AI 输出原文

成交确认行原文：2026-11-13,600176,中国巨石,买入,10.46,4700,49162.00,,【B线】买入成交（委托10.46；委托10.46，2026-11-13 13:43:54成交；订单B-20261113-600176-1；虚拟成交）

快照里这笔买单成交，代码：600176，价格：10.46，数量：4700。

延时计算：13:43:54 - 13:43:54 = 0秒

成交确认：已确认
[2026-11-13 13:44:16 CST] 步骤D解析：程序已找到成交行，ai_confirmed=True（程序为准），AI 自述=已确认，抄出行=是
[2026-11-13 13:44:16 CST] 脚本结束
