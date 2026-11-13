def compute_rehang(fill, base):
    code = fill["code"]
    side = fill["side"]
    price = float(fill["price"])
    qty = int(fill["qty"])
    nodes = load_json(base + "/nodes.json", {})
    tick = tick_of(code)
    
    if side == "卖出":
        node_price = None
        for node in nodes.get(code, {}).get("nodes", []):
            if round_tick(node["node_price"] * 1.02, tick) == round_tick(price, tick):
                node_price = node["node_price"]
                break
        if node_price is None:
            return None
        new_side = "买入"
        new_price = round_tick(node_price, tick)
    
    else:  # side == "买入"
        node_price = None
        for node in nodes.get(code, {}).get("nodes", []):
            if round_tick(node["node_price"], tick) == round_tick(price, tick):
                node_price = node["node_price"]
                break
        if node_price is None:
            return None
        new_side = "卖出"
        new_price = round_tick(node_price * 1.02, tick)
    
    amount = round(new_price * qty, 2)
    dstr = str(fill.get("snapshot_date", ""))
    if "-" in dstr:
        dstr = dstr.replace("-", "")
    pstr = str(new_price).replace(".", "p")
    order_id = "FW-" + dstr + "-" + code + "-" + ("buy" if new_side == "买入" else "sell") + "-" + pstr + "-" + now_str()[0:10].replace("-", "") + now_str()[11:13] + now_str()[14:16] + now_str()[17:19]
    return {"order_id": order_id, "code": code, "side": new_side, "price": new_price, "qty": qty, "amount": amount, "node_price": node_price, "fill_code": code, "fill_side": side, "fill_price": price}