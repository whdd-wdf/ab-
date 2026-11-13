import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

MIN_AMOUNT = 5000
BANNED_PRICE = {code: 4.316 for code in A_CODES}
STALE_SECS = 1800

def round_tick(price, tick):
    from decimal import Decimal, ROUND_HALF_UP
    return float(Decimal(str(price)).quantize(Decimal(str(tick)), rounding=ROUND_HALF_UP)

def filter_order(order, snapshot, base):
    code = order["code"]
    tick = tick_of(code)
    
    if order["amount"] < MIN_AMOUNT:
        return False, "small_amount"
    
    if round_tick(order["price"], tick) in BANNED_PRICE.get(code, set()):
        return False, "banned_cluster_price"
    
    if (pending := snapshot.get("pending", [])) and any(
        pending_order["code"] == code and pending_order["side"] == order["side"] and pending_order["status"] == "未成交" and round_tick(pending_order["price"], tick) == round_tick(order["price"], tick)
    ):
        if pending_order["side"] == "买入":
            return False, "duplicate_pending_buy"
        elif pending_order["side"] == "卖出":
            return False, "duplicate_pending_sell"
    
    if order["side"] == "卖出":
        prev_close = quotes.get(code, {}).get("prev_close")
        if not prev_close:
            return True, "grid_available 未取到，仅记 note"
        else:
            limit_up = round_tick(prev_close * 1.10, tick)
            if order["price"] > limit_up:
                return False, "above_limit_up"
    
    if order["side"] == "卖出":
        quota_json = json.loads(open(f"{base}/virtual_quota.json").read())
        sellable = quota_json.get("A_CODES", {}).get(code, {}).get("holdings", {}).get("sellable", 0)
        if order["qty"] > sellable:
            return False, "sellable_exceeded"
    
    if order["side"] == "买入":
        quota_json = json.loads(open(f"{base}/virtual_quota.json").read())
        grid_available = quota_json.get("A_CODES", {}).get(code, {}).get("grid_available", 0)
        if not grid_available:
            return True, "grid_available 未取到，仅记 note"
        if order["amount"] > grid_available:
            return False, "grid_available_exceeded"
    
    return True, ""

def main():
    import argparse
    import json
    from os import path
    from time import time
    
    parser = argparse.ArgumentParser(description="Trade Watcher")
    parser.add_argument("--base", default="/workspace/ab-/virtual", help="Base directory for files")
    parser.add_argument("--mode", default="compare", help="Mode to run in")
    parser.add_argument("--snapshot", help="Snapshot file to use")
    
    args = parser.parse_args()
    
    if args.mode not in ["compare"]:
        return {"ok": False, "error": "mode 只支持 compare"}
    
    if not args.snapshot:
        args.snapshot = latest_snapshot(args.base)
    
    if not args.snapshot:
        return {"ok": False, "error": "no_snapshot"}
    
    snapshot = json.loads(open(args.snapshot).read())
    age = time() - snapshot["timestamp"]
    
    if age > STALE_SECS:
        return {"ok": False, "error": "stale_snapshot", "snapshot_time": snapshot["timestamp"], "snapshot_age_secs": age}
    
    trade_log = set()
    for line in open(f"{args.base}/virtual_trade_log.csv"):
        trade_log.add(line.strip())
    
    new_fills