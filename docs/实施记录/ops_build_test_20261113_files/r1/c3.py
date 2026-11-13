def check_a(order, base, checks, reasons):
    code = order['code']
    side = order['side']
    price = float(order['price'])
    qty = int(order['qty'])
    amount = round(price * qty, 2)
    
    nodes = load_json(base / 'nodes.json', {})
    quota = load_json(base / 'virtual_quota.json', {})
    quotes = load_json(base / 'quotes.json', {})
    
    prev_close = order.get('prev_close', quotes.get(code, {}).get('prev_close', None))
    tick = tick_of(code)
    qk = A_CODES[code]
    q = quota.get(qk, {})
    
    def ck(item, passed, detail):
        checks.append({"item": item, "pass": bool(passed), "detail": detail})
        if not passed:
            reasons.append(item + "：" + detail)
    
    # 买入分支
    if side == "买入":
        buy_price = None
        if nodes[code]["nodes"]:
            node_prices = [round_tick(node_price, tick) for node_price in nodes[code]["nodes"]]
            buy_price = next((price for price in node_prices if round_tick(price, tick) <= round_tick(prev_close * 0.90, tick)), None)
            if buy_price is None:
                buy_price = round_tick(prev_close * 0.90, tick)
            if buy_price is not None:
                buy_price = round_tick(buy_price, tick)
        if buy_price is None:
            ck("buy_price", False, "节点价列表无符合条件的节点价")
        elif buy_price <= q["grid_available"]:
            ck("buy_price", False, "buy_price <= grid_available")
        elif amount <= q["grid_available"]:
            ck("amount", True, None)
        else:
            ck("amount", False, "amount >= 5000")
    # 卖出分支
    else:
        sell_price = round_tick(price * 1.02, tick)
        if find_node_for_sell(code, sell_price, nodes[code]["nodes"]):
            ck("sell_price", True, None)
        else:
            ck("sell_price", False, "find_node_for_sell failed")
        if q["holdings"][code]["sellable"] >= qty:
            ck("qty", True, None)
        else:
            ck("qty", False, "qty <= holdings[code]['sellable']")
        if prev_close is None:
            ck("prev_close", True, None)
        else:
            if prev_close * 1.10 >= round_tick(prev_close, tick):
                ck("prev_close", True, None)
            else:
                ck("prev_close", False, "prev_close * 1.10 >= round_tick(prev_close, tick)")
        if latest_snapshot(base) is None:
            ck("latest_snapshot", True, None)
        else:
            if latest_snapshot(base).get('pending', {}).get((code, side, sell_price), {}).get('status') == '未成交':
                ck("latest_snapshot", False, "同 code、同 side 卖出、status 为 未成交")
            else:
                ck("latest_snapshot", False, "round_tick(其 price, tick) 等于 round_tick(sell_price, tick)")
        if code in BANNED_PRICE and sell_price in BANNED_PRICE[code]:
            ck("sell_price", False, "round_tick(sell_price, tick) 在 BANNED_PRICE.get(code, {}) 里")
        else:
            ck("sell_price", True, None)
        if amount >= 5000:
            ck("amount", True, None)
        else:
            ck("amount", False, "amount >= 5000")