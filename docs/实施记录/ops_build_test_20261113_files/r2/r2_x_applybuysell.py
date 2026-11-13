def apply_buy(order, base, quota, nodes, state, q, h, fill_time, mark):
    code = order["code"]
    price = float(order["price"])
    qty = int(order["qty"])
    amount = round(price * qty, 2)
    fee = round(amount * 0.00025, 2)
    if fee < 5.0:
        fee = 5.0
    cost_total = round(amount + fee, 2)
    old_qty = int(h.get("qty", 0))
    old_cost = float(h.get("avg_cost", 0.0))
    new_qty = old_qty + qty
    new_avg = round((old_qty * old_cost + cost_total) / new_qty, 4)
    if new_qty > 0:
        h["qty"] = new_qty
        h["avg_cost"] = new_avg
        h["sellable"] = int(h.get("sellable", 0))
    q["deployed"] = round(float(q.get("deployed", 0.0)) + cost_total, 2)
    for node in nodes.get(code, {}).get("nodes", []):
        if node.get("node_price") == price:
            node["hands"] = int(node.get("hands", 0)) + int(qty / 100)
    remark = mark + " 委托 " + fill_time + " 买入成交 委托价" + str(price)
    return (0.0, remark)


def apply_sell(order, base, quota, nodes, state, q, h, fill_time, mark):
    code = order["code"]
    price = float(order["price"])
    qty = int(order["qty"])
    amount = round(price * qty, 2)
    avg = float(h.get("avg_cost", 0.0))
    fee = round(amount * 0.00075, 2)
    if fee < 5.0:
        fee = 5.0
    pnl = round((price - avg) * qty - fee, 2)
    new_qty = int(h.get("qty", 0)) - qty
    h["qty"] = new_qty
    h["sellable"] = int(h.get("sellable", 0)) - qty
    if new_qty <= 0:
        h["avg_cost"] = 0.0
    q["deployed"] = round(float(q.get("deployed", 0.0)) - avg * qty, 2)
    if q["deployed"] < 0:
        q["deployed"] = 0.0
    q["pnl"] = round(float(q.get("pnl", 0.0)) + pnl, 2)
    for node in nodes.get(code, {}).get("nodes", []):
        if node.get("node_price") == price:
            node["hands"] = int(node.get("hands", 0)) - int(qty / 100)
    remark = mark + " 委托 " + fill_time + " 卖出成交 委托价" + str(price)
    return (pnl, remark)
