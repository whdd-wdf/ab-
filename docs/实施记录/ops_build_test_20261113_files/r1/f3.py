def detect_new_fills(snapshot, booked_keys):
    snapshot_date = snapshot["timestamp"][:10]
    new_fills = []
    for fill in snapshot["fills_today"]:
        if (snapshot_date, fill["code"], fill["side"], fill["qty"], fill["price"]) not in booked_keys:
            new_fills.append({
                "snapshot_date": snapshot_date,
                **fill
            })
    return new_fills

def compute_rehang(fill, base):
    nodes = load_json(base + "/nodes.json", {})
    quotes = load_json(base + "/quotes.json", {})
    
    fill_time = int(fill["time"].replace("-", "").replace(" ", "").replace(":", ""))
    fill_price_str = str(fill["price"]).replace(".", "p")
    
    if fill["side"] == "BUY":
        for node in nodes[fill["code"]]["nodes"]:
            node_price = round_tick(node["price"], quotes[fill["code"]]["tick"])
            if node_price == round_tick(fill["price"], quotes[fill["code"]]["tick"]):
                rehang_order = {
                    "order_id": "FW-" + snapshot_date.replace("-", "").replace("-", "").replace("-", "") + "-" + fill["code"] + "-buy-" + fill_price_str + "-" + str(fill_time),
                    "code": fill["code"],
                    "side": "BUY",
                    "price": round_tick(node["price"] * 1.02, quotes[fill["code"]]["tick"]),
                    "qty": fill["qty"],
                    "line": "A",
                    "note": "由" + fill["side"] + str(fill["qty"]) + "@" + str(fill["price"]) + "补挂",
                    "amount": round(fill["price"] * fill["qty"], 2),
                    "source_fill": {
                        "code": fill["code"],
                        "side": fill["side"],
                        "price": fill["price"],
                        "qty": fill["qty"],
                        "time": fill["time"]
                    }
                }
                return rehang_order
    elif fill["side"] == "SELL":
        for node in nodes[fill["code"]]["nodes"]:
            node_price = round_tick(node["price"] * 1.02, quotes[fill["code"]]["tick"])
            if node_price == round_tick(fill["price"], quotes[fill["code"]]["tick"]):
                rehang_order = {
                    "order_id": "FW-" + snapshot_date.replace("-", "").replace("-", "").replace("-", "") + "-" + fill["code"] + "-sell-" + fill_price_str + "-" + str(fill_time),
                    "code": fill["code"],
                    "side": "SELL",
                    "price": fill["price"],
                    "qty": fill["qty"],
                    "line": "A",
                    "note": "由" + fill["side"] + str(fill["qty"]) + "@" + str(fill["price"]) + "补挂",
                    "amount": round(fill["price"] * fill["qty"], 2),
                    "source_fill": {
                        "code": fill["code"],
                        "side": fill["side"],
                        "price": fill["price"],
                        "qty": fill["qty"],
                        "time": fill["time"]
                    }
                }
                return rehang_order
    return None