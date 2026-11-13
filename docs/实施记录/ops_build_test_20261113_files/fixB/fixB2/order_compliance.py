import argparse
import json
import os
import sys
import datetime
from datetime import datetime, timezone, timedelta

# 常量定义
MIN_AMOUNT = 5000.0
BANNED_PRICE = {"510300": {4.316, 4.324, 4.325}, "601088": {52.06}}
TICK = {"510300": 0.001, "513650": 0.001}
PRICE_DEV_TOL = 0.01
B_SINGLE_LIMIT = 50000.0
B_MAX_COUNT = 3
A_CODES = {"510300": "A1", "601088": "A2", "513650": "A3"}
STALE_SECS = 300

# 辅助函数
def tick_of(code):
    return TICK.get(code, 0.01)

import json
import os
from datetime import datetime, timezone, timedelta

def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, 'r') as f:
        return json.load(f)

def latest_snapshot(base):
    snapshots_path = os.path.join(base, 'snapshots')
    files = os.listdir(snapshots_path)
    files = [f for f in files if f.startswith('fillwatch_') and f.endswith('.json')]
    if not files:
        return None
    files.sort()
    return load_json(os.path.join(snapshots_path, files[-1]), None)

def find_node_for_sell(code, sell_price, nodes):
    tick = load_json(os.path.join(base, 'quotes.json'), {}).get('tick')
    for node in nodes.get(code, []):
        node_price = node.get('node_price')
        if round_tick(node_price * 1.02, tick) == round_tick(sell_price, tick):
            return node_price
    return None

def line_of_order(order):
    line = order.get('line')
    if line:
        return line
    code = order.get('code')
    if code in A_CODES:
        return 'A'
    return 'B'

def find_node_for_sell(code, sell_price, nodes):
    tick = tick_of(code)
    for node in nodes:
        node_price = node["node_price"]
        if round_tick(node_price * 1.02, tick) == round_tick(sell_price, tick):
            return node_price
    return None

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

def run_compliance(order, base):
    checks = []
    reasons = []
    line = line_of_order(order)
    if line == "A" and order.get("code") in A_CODES:
        check_a(order, base, checks, reasons)
    else:
        check_b(order, base, checks, reasons)
    return (len(reasons) == 0, checks, reasons)


def main():
    import argparse, json, sys
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="/workspace/ab-/virtual")
    parser.add_argument("--order")
    parser.add_argument("--order-file")
    args = parser.parse_args()
    base = args.base
    try:
        if args.order:
            order = json.loads(args.order)
        elif args.order_file:
            with open(args.order_file, 'r') as f:
                order = json.load(f)
        else:
            order = json.loads(sys.stdin.read())
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)
    passed, checks, reasons = run_compliance(order, base)
    print(json.dumps({"ok": True, "passed": passed, "checks": checks, "reasons": reasons}, ensure_ascii=False))
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    sys.exit(main())
