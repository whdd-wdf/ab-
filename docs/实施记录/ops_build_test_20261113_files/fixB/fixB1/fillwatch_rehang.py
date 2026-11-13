import os
import sys
import json
import csv
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Shanghai")
except Exception:
    TZ = timezone(timedelta(hours=8))
MIN_AMOUNT = 5000.0
STALE_SECS = 300
BANNED_PRICE = {"510300": {4.316, 4.324, 4.325}, "601088": {52.06}}
A_CODES = {"510300": "A1", "601088": "A2", "513650": "A3"}
TICK = {"510300": 0.001, "601088": 0.01, "513650": 0.001}
DEFAULT_TICK = 0.01
def tick_of(code):
    return TICK.get(code, DEFAULT_TICK)
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

import csv
import re

def is_fill(row):
    remark = str(row.get("备注", ""))
    if "委托中" in remark:
        return False
    idx = remark.find("\u3011")
    if idx < 0:
        return True
    after = remark[idx + 1:].strip()
    if after.startswith("已撤销"):
        return False
    return True

def read_trade_log_fills(base):
    fills = set()
    try:
        with open(base + "/virtual_trade_log.csv", mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get("方向") not in ["买入", "卖出"]:
                    continue
                if not is_fill(row):
                    continue
                remark = str(row.get("备注", ""))
                m = re.search(r"委托价?(\d+\.\d+)", remark)
                if m:
                    price = float(m.group(1))
                else:
                    price = float(row.get("价格", 0))
                key = (str(row.get("日期", "")), str(row.get("代码", "")), str(row.get("方向", "")), int(float(row.get("数量", 0))), price)
                fills.add(key)
    except FileNotFoundError:
        return set()
    return fills

import os
import datetime

def latest_snapshot(base):
    sdir = base + "/snapshots"
    if not os.path.isdir(sdir):
        return None
    names = sorted([n for n in os.listdir(sdir) if n.startswith("fillwatch_") and n.endswith(".json")])
    if not names:
        return None
    fname = names[-1]
    data = load_json(sdir + "/" + fname, None)
    if data is None:
        return None
    data["_file"] = fname
    return data

def snapshot_age_secs(snapshot):
    ts = snapshot.get("timestamp", "")
    if isinstance(ts, (int, float)):
        return now().timestamp() - float(ts)
    try:
        dt = datetime.strptime(str(ts), "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=TZ)
        return (now() - dt).total_seconds()
    except ValueError:
        return 10**9

def detect_new_fills(snapshot, logged):
    new = []
    snap_date = str(snapshot.get("timestamp", ""))[:10]
    for fill in snapshot.get("fills_today", []):
        if fill.get("status") != "已成交":
            continue
        if fill.get("code") not in A_CODES:
            continue
        qty = int(fill.get("qty", 0))
        price = float(fill.get("price", 0))
        key = (snap_date, str(fill.get("code", "")), str(fill.get("side", "")), qty, price)
        if key not in logged:
            new.append({"code": fill.get("code"), "side": fill.get("side"), "price": price, "qty": qty, "fill_time": fill.get("time", ""), "snapshot_date": snap_date})
    return new

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

from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Shanghai")
except Exception:
    TZ = timezone(timedelta(hours=8))
def now():
    return datetime.now(TZ)
def today_str():
    return now().strftime("%Y-%m-%d")
def now_str():
    return now().strftime("%Y-%m-%d %H:%M:%S")
def round_tick(price, tick):
    from decimal import Decimal, ROUND_HALF_UP
    return float(Decimal(str(price)).quantize(Decimal(str(tick)), rounding=ROUND_HALF_UP))

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

