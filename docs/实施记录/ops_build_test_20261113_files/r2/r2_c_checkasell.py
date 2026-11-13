def round_tick(price, tick):
    return round(price / tick) * tick

def check_a_sell(order, base, checks, reasons):
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
    if prev_close is None:
        ck("卖价=节点价×1.02", True, "跳过（前收取不到）")
    else:
        limit_up = round_tick(prev_close * 1.10, tick)
        ck("卖价=节点价×1.02", nodes[code]["nodes"] is not None, "卖价 " + str(price))
    sellable = q.get("holdings", {}).get(code, {}).get("sellable", 0)
    ck("卖出<=可卖量", qty <= sellable, "卖 " + str(qty) + " 股，可卖 " + str(sellable) + " 股")
    if prev_close is None:
        ck("卖价<=涨停", True, "跳过（前收取不到）")
    else:
        ck("卖价<=涨停", round_tick(price, tick) <= limit_up, "卖价 " + str(price) + "，涨停 " + str(limit_up))
    snap = latest_snapshot(base)
    if snap is None:
        ck("卖价不重复在挂", True, "跳过（无快照）")
    else:
        dup = False
        for o in snap.get("pending", []):
            if o.get("code") == code and o.get("side") == "卖出" and o.get("status") == "未成交" and round_tick(o.get("price", 0), tick) == round_tick(price, tick):
                dup = True
        ck("卖价不重复在挂", not dup, "在挂卖价有重复" if dup else "在挂卖价无重复")
    banned = BANNED_PRICE.get(code, set())
    ck("非禁挂集群价", round_tick(price, tick) not in banned, "卖价 " + str(price))
    ck("单笔>=5000", amount >= MIN_AMOUNT, "金额 " + str(amount))

def check_a(order, base, checks, reasons):
    if order["side"] == "买入":
        check_a_buy(order, base, checks, reasons)
    else:
        check_a_sell(order, base, checks, reasons)
