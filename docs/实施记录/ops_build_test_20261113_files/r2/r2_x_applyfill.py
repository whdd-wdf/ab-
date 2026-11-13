def apply_fill(order, base):
    import csv
    import json

    code = order["code"]
    price = float(order["price"])
    qty = int(order["qty"])
    amount = round(price * qty, 2)

    qk = quota_key_of_order(order)
    if qk is None:
        qk = A_CODES.get(code, "B")

    mark = MARK_OF_LINE.get(qk, "\u3010B\u3011")

    quota = load_json(base + "/virtual_quota.json", {})
    nodes = load_json(base + "/nodes.json", {})
    state = load_json(base + "/state.json", {"orders": []})

    q = quota.setdefault(qk, {})
    q.setdefault("holdings", {})[code] = {"qty": 0, "sellable": 0, "avg_cost": 0.0}

    fill_time = now_str()

    if order["side"] == "买入":
        pnl, remark = apply_buy(order, base, quota, nodes, state, q, q[code], fill_time, mark)
    else:
        pnl, remark = apply_sell(order, base, quota, nodes, state, q, q[code], fill_time, mark)

    q["available"] = round(float(q.get("quota", 0.0)) - float(q.get("deployed", 0.0)), 2)
    q["grid_available"] = round(float(q.get("grid_quota", 0.0)) - float(q.get("deployed", 0.0)), 2)

    save_json(base + "/virtual_quota.json", quota)
    save_json(base + "/nodes.json", nodes)
    save_json(base + "/state.json", state)

    row = [today_str(), code, order.get("name", ""), order["side"], price, qty, amount, pnl if order["side"] == "卖出" else 0.0, remark]
    with open(base + "/virtual_trade_log.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)

    state_orders = state.get("orders", [])
    for o in state_orders:
        if o.get("order_id") == order.get("order_id"):
            o["status"] = "已成交"
            o["fill_time"] = fill_time

    save_json(base + "/state.json", state)

    return {"kind": "filled", "order_id": order.get("order_id"), "code": code, "side": order["side"], "price": price, "qty": qty, "amount": amount, "pnl": pnl}
