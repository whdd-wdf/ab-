def filter_order(order, snapshot, base):
    code = order["code"]
    side = order["side"]
    price = float(order["price"])
    qty = int(order["qty"])
    amount = round(price * qty, 2)
    
    tick = tick_of(code)
    
    if amount < MIN_AMOUNT:
        return (False, "small_amount")
    
    if round_tick(price, tick) in BANNED_PRICE.get(code, set()):
        return (False, "banned_cluster_price")
    
    dup = False
    dup_side = ""
    for o in snapshot.get("pending", []):
        if o.get("code") == code and o.get("side") == side and o.get("status") == "未成交" and round_tick(float(o.get("price", 0)), tick) == round_tick(price, tick):
            dup = True
            dup_side = side
            break
    
    if side == "卖出":
        quotes = load_json(base + "/quotes.json", {})
        prev_close = quotes.get(code, {}).get("prev_close")
        if prev_close is not None:
            limit_up = round_tick(prev_close * 1.10, tick)
        if round_tick(price, tick) > limit_up:
            return (False, "above_limit_up")
    
    quota = load_json(base + "/virtual_quota.json", {})
    qk = A_CODES.get(code, "B")
    q = quota.get(qk, {})
    
    if side == "卖出":
        sellable = q.get("holdings", {}).get(code, {}).get("sellable", 0)
        if qty > sellable:
            return (False, "sellable_exceeded")
    
    if side == "买入":
        ga = q.get("grid_available")
        if ga is None:
            return (True, "note:grid_available 未取到")
        if amount > ga:
            return (False, "grid_available_exceeded")
    
    return (True, "")

def main():
    import argparse, json, sys
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="/workspace/ab-/virtual")
    parser.add_argument("--snapshot")
    parser.add_argument("--mode", default="compare")
    args = parser.parse_args()
    base = args.base
    
    if args.mode != "compare":
        print(json.dumps({"ok": False, "verdict": "error", "error": "mode 只支持 compare"}, ensure_ascii=False))
        return 1
    
    if args.snapshot is not None:
        snap = load_json(args.snapshot, None)
    else:
        snap = latest_snapshot(base)
    
    if snap is None:
        print(json.dumps({"ok": False, "verdict": "error", "error": "no_snapshot"}, ensure_ascii=False))
        return 1
    
    age = snapshot_age_secs(snap)
    if age > STALE_SECS:
        print(json.dumps({"ok": True, "verdict": "silent", "reason": "stale_snapshot", "snapshot_time": snap.get("timestamp"), "snapshot_age_secs": age}, ensure_ascii=False))
        return 0
    
    logged = read_trade_log_fills(base)
    new_fills = detect_new_fills(snap, logged, base)
    
    if new_fills is None:
        print(json.dumps({"ok": True, "verdict": "silent", "reason": "no_new_fills", "snapshot_time": snap.get("timestamp")}, ensure_ascii=False))
        return 0
    
    orders = []
    filtered = []
    for fill in new_fills:
        re = compute_rehang(fill, base)
        if re is None:
            filtered.append({"fill": fill, "reason": "node_not_found"})
            continue
        ok, reason = filter_order(re, snap, base)
        if ok:
            orders.append(re)
        else:
            filtered.append({"fill": fill, "reason": reason})
    
    print(json.dumps({"ok": True, "verdict": "computed", "new_fills": new_fills, "orders": orders, "filtered": filtered, "snapshot_time": snap.get("timestamp")}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
