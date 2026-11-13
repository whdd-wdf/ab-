def check_b(order, base, checks, reasons):
    code = order["code"]
    side = order["side"]
    price = float(order["price"])
    qty = int(order["qty"])
    amount = round(price * qty, 2)
    
    quota = load_json(base + "/virtual_quota.json", {})
    quotes = load_json(base + "/quotes.json", {})
    
    prev_close = order.get("prev_close")
    if prev_close is None:
        prev_close = quotes.get(code, {}).get("prev_close")
    
    def ck(item, passed, detail):
        checks.append({"item": item, "pass": bool(passed), "detail": detail})
        if not passed:
            reasons.append(item + "：" + detail)
    
    if side == "买入":
        # (a)“涨幅<=5%”
        if prev_close is None:
            ck("涨幅<=5%", True, "跳过（前收取不到）")
        else:
            ck("涨幅<=5%", price / prev_close - 1 <= 0.05, "涨幅 " + str(round((price / prev_close - 1) * 100, 2)) + "%")
        
        # (b)“买价≈现价”
        cur = quotes.get(code, {}).get("price")
        if cur is None:
            ck("买价≈现价", True, "跳过（当前价取不到）")
        else:
            ck("买价≈现价", abs(price / cur - 1) <= PRICE_DEV_TOL, "买价 " + str(price) + "，现价 " + str(cur))
        
        # (c)“买价<=P4限价”
        if "limit_price" not in order or order["limit_price"] is None:
            ck("买价<=P4限价", True, "跳过（未传 limit_price）")
        else:
            ck("买价<=P4限价", price <= float(order["limit_price"]), "买价 " + str(price))
        
        # (d)“单只<=5万”
        ck("单只<=5万", amount <= B_SINGLE_LIMIT, "金额 " + str(amount))
        
        # (e)“买入<=B可用”
        av = quota.get("B", {}).get("available")
        if av is None:
            ck("买入<=B可用", False, "quota 取不到")
        else:
            ck("买入<=B可用", amount <= av, "金额 " + str(amount) + "，B 可用 " + str(av))
        
        # (f)“B线<=3只”
        holdings = quota.get("B", {}).get("holdings", {})
        held = holdings.get(code, {}).get("qty", 0)
        if held > 0:
            ck("B线<=3只", True, "加仓既有持仓")
        else:
            held_n = 0
            for v in holdings.values():
                if v.get("qty", 0) > 0:
                    held_n += 1
            ck("B线<=3只", held_n < B_MAX_COUNT, "新开仓，当前持仓 " + str(held_n) + " 只")
        
        # (g)“单笔>=5000”
        ck("单笔>=5000", amount >= MIN_AMOUNT, "金额 " + str(amount))
    
    elif side == "卖出":
        # (h)“卖出<=持仓”
        held = quota.get("B", {}).get("holdings", {}).get(code, {}).get("qty", 0)
        ck("卖出<=持仓", qty <= held, "卖 " + str(qty) + " 股，持仓 " + str(held) + " 股")