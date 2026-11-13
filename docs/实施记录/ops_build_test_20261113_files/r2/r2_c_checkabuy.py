def check_a_buy(order, base, checks, reasons):
    code = order["code"]
    price = float(order["price"])
    qty = int(order["qty"])
    amount = round(price * qty, 2)
    
    nodes = load_json(base + "/nodes.json", {})
    quota = load_json(base + "/virtual_quota.json", {})
    quotes = load_json(base + "/quotes.json", {})
    
    prev_close = order.get("prev_close")
    if prev_close is None:
        prev_close = quotes.get(code, {}).get("prev_close")
    
    tick = tick_of(code)
    qk = A_CODES[code]
    q = quota.get(qk, {})
    
    def ck(item, passed, detail):
        checks.append({"item": item, "pass": bool(passed), "detail": detail})
        if not passed:
            reasons.append(item + "：" + detail)
    
    node_prices = [n["node_price"] for n in nodes.get(code, {}).get("nodes", [])]
    ok = round_tick(price, tick) in [round_tick(p, tick) for p in node_prices]
    if not ok and prev_close is not None:
        limit_down = round_tick(prev_close * 0.90, tick)
        if any(round_tick(p, tick) <= limit_down and round_tick(price, tick) == limit_down for p in node_prices):
            ok = True
    
    ck("买价=节点价", ok, "买价 " + str(price))
    
    ga = q.get("grid_available")
    if ga is None:
        ck("买入<=grid_available", False, "quota 取不到")
    else:
        ck("买入<=grid_available", amount <= ga, "金额 " + str(amount) + "，grid_available " + str(ga))
    
    ck("单笔>=5000", amount >= MIN_AMOUNT, "金额 " + str(amount))