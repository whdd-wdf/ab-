import os
import json
import time
import sys
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Shanghai")
except Exception:
    TZ = timezone(timedelta(hours=8))
A_CODES = {"510300": "A1", "601088": "A2", "513650": "A3"}
NAMES = {"510300": "沪深300ETF", "601088": "中国神华", "513650": "标普500ETF南方"}
LINE_NAME = {"A1": "A1", "A2": "A2", "A3": "A3", "B": "B"}
MARK_OF_LINE = {"A1": "\u3010A1\u3011", "A2": "\u3010A2\u3011", "A3": "\u3010A3\u3011", "B": "\u3010B\u3011"}
TICK = {"510300": 0.001, "601088": 0.01, "513650": 0.001}
DEFAULT_TICK = 0.01
def tick_of(code):
    return TICK.get(code, DEFAULT_TICK)

import json
from datetime import datetime, timezone, timedelta
import os
import shutil

def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, obj):
    tmp_path = path + ".tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp_path, path)

def gate_open(base):
    trading_day_path = os.path.join(base, ".trading_day")
    if not os.path.exists(trading_day_path):
        return (False, "门控标志不存在")
    
    trading_day_mtime = os.path.getmtime(trading_day_path)
    trading_day_date = datetime.fromtimestamp(trading_day_mtime, tz=timezone(timedelta(hours=8)))
    today_str = now().strftime("%Y-%m-%d")
    if trading_day_date.strftime("%Y-%m-%d") != today_str:
        return (False, "门控标志非当日")
    
    current_minute = now().hour * 60 + now().minute
    if not (7 * 60 <= current_minute < 17 * 60):
        return (False, "不在 07:30–17:05 窗口内")
    
    return (True, "门开")

def quota_key_of_order(order):
    line = order.get('line', None)
    if line:
        return line
    code = order.get('code', None)
    if code:
        return A_CODES.get(code, 'B')
    return 'B'

def move_order(base, src_name, dest_dir, result):
    src_path = os.path.join(base, 'order_queue', 'pending', src_name)
    dest_path = os.path.join(base, 'order_queue', dest_dir, src_name)
    if os.path.isdir(src_path):
        shutil.move(src_path, dest_path)
    else:
        with open(src_path, 'r', encoding='utf-8') as f:
            order_json = json.load(f)
        order_json['result'] = result
        with open(dest_path, 'w', encoding='utf-8') as f:
            json.dump(order_json, f, ensure_ascii=False)
        os.remove(src_path)

import os
import datetime
from datetime import timezone, timedelta

def gate_open(base):
    flag = base + "/.trading_day"
    if not os.path.exists(flag):
        return None
    mtime = os.path.getmtime(flag)
    TZ = timezone(timedelta(hours=8))
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    d = datetime.fromtimestamp(mtime, tz=TZ).strftime("%Y-%m-%d")
    if d != today:
        return None
    t = datetime.now(TZ)
    if t.hour * 60 + t.minute < 7 * 60 + 30 or t.hour * 60 + t.minute > 17 * 60 + 5:
        return None
    return True

def quota_key_of_order(order):
    A_CODES = {"510300": "A1", "601088": "A2", "513650": "A3"}
    if order.get("line") == "B":
        return "B"
    if order["code"] in A_CODES:
        return A_CODES[order["code"]]
    return None

def run_compliance(order, base, compliance_script):
    import subprocess, json

    cmd = [sys.executable, compliance_script, "--base", base, "--order", json.dumps(order, ensure_ascii=False)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            return (False, [], ["合规脚本退出码 " + str(proc.returncode)])
        try:
            out = json.loads(proc.stdout)
            if not out:
                return (False, [], ["合规输出解析失败"])
            return (bool(out.get("passed", False)), out.get("checks", []), out.get("reasons", []))
        except json.JSONDecodeError:
            return (False, [], ["合规输出解析失败"])
    except subprocess.TimeoutExpired:
        return (False, [], ["合规调用超时"])
    except Exception as e:
        return (False, [], ["合规调用失败： " + str(e)])

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
        if node.get("sell_price") == price or round(float(node.get("node_price", 0)) * 1.02, 2) == round(price, 2):
            node["hands"] = int(node.get("hands", 0)) - int(qty / 100)
    remark = mark + " 委托 " + fill_time + " 卖出成交 委托价" + str(price)
    return (pnl, remark)

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
    q.setdefault("holdings", {}).setdefault(code, {"qty": 0, "sellable": 0, "avg_cost": 0.0})

    fill_time = now_str()

    if order["side"] == "买入":
        pnl, remark = apply_buy(order, base, quota, nodes, state, q, q["holdings"][code], fill_time, mark)
    else:
        pnl, remark = apply_sell(order, base, quota, nodes, state, q, q["holdings"][code], fill_time, mark)

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

def process_one(src_path, base, compliance_script):
    order = load_json(src_path, None)
    if order is None:
        return {"kind": "rejected", "order_id": os.path.basename(src_path), "reasons": ["订单文件解析失败"]}
    
    if "order_id" not in order:
        order["order_id"] = os.path.splitext(os.path.basename(src_path))[0]
    
    if "time" not in order:
        order["time"] = now_str()
    
    passed, checks, reasons = run_compliance(order, base, compliance_script)
    
    if passed:
        result = apply_fill(order, base)
        return move_order(src_path, base, "done", result)
    else:
        result = {
            "kind": "rejected",
            "order_id": order["order_id"],
            "code": order.get("code"),
            "side": order.get("side"),
            "price": order.get("price"),
            "qty": order.get("qty"),
            "checks": checks,
            "reasons": reasons
        }
        return move_order(src_path, base, "failed", result)

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

def write_snapshot(base):
    state = load_json(base + "/state.json", {"orders": []})
    orders = state.get("orders", [])
    today = today_str()
    fills_today = [o for o in orders if o.get("status") == "已成交" and str(o.get("time", ""))[:10] == today]
    pending = [o for o in orders if o.get("status") == "未成交"]
    fname = "fillwatch_" + today.replace("-", "") + "_" + now_str()[11:13] + now_str()[14:16] + ".json"
    snap = {"label": "fillwatch", "timestamp": now_str(), "status": "ok", "orders": orders, "fills_today": fills_today, "pending": pending}
    os.makedirs(base + "/snapshots", exist_ok=True)
    with open(base + "/snapshots/" + fname, 'w', encoding='utf-8') as f:
        json.dump(snap, f, ensure_ascii=False)


def main():
    import argparse, json, sys
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default="/workspace/ab-/virtual", help='Base directory for snapshots')
    parser.add_argument('--compliance', default='', help='Compliance script path')
    args = parser.parse_args()
    base = args.base
    compliance_script = args.compliance if args.compliance else os.path.join(os.path.dirname(os.path.abspath(__file__)), "order_compliance.py")
    
    if not gate_open(base):
        print(json.dumps({"ok": False, "error": "gate_closed", "processed": 0, "filled": [], "rejected": [], "gate_closed": [], "dry_run": []}, ensure_ascii=False))
        return 0
    
    pending_dir = base + "/order_queue/pending"
    if not os.path.exists(pending_dir):
        print(json.dumps({"ok": False, "error": "no_pending_dir", "processed": 0, "filled": [], "rejected": [], "gate_closed": [], "dry_run": []}, ensure_ascii=False))
        return 0
    
    filled = []
    rejected = []
    processed = 0
    for fname in sorted(os.listdir(pending_dir)):
        if fname.endswith(".json"):
            src = pending_dir + "/" + fname
            result = process_one(src, base, compliance_script)
            processed += 1
            if result.get("kind") == "filled":
                filled.append(result)
            elif result.get("kind") == "rejected":
                rejected.append(result)
    
    if filled:
        write_snapshot(base)
    
    print(json.dumps({"ok": True, "action": "run", "date": today_str(), "processed": processed, "filled": filled, "rejected": rejected, "gate_closed": [], "dry_run": []}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())

