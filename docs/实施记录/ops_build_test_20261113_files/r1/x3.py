import json
import subprocess
import os
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

def round_tick(price, tick):
    return float(Decimal(str(price)).quantize(Decimal(str(tick)), rounding=ROUND_HALF_UP)

def run_compliance(order, base, compliance_script):
    try:
        result = subprocess.run([sys.executable, compliance_script, "--base", base, "--order", json.dumps(order, ensure_ascii=False)], timeout=300, check=True, stdout=subprocess.PIPE)
        stdout = result.stdout.decode('utf-8')
        passed, checks, reasons = json.loads(stdout)
        return passed, checks, reasons
    except subprocess.TimeoutExpired:
        return False, [], ["合规调用失败：超时"]
    except subprocess.CalledProcessError as e:
        return False, [], [f"合规调用失败：{e.stderr.decode('utf-8')}"]
    except Exception as e:
        return False, [], [f"合规调用失败：原因：{str(e)}"]

def apply_fill(order, base):
    code = order['code']
    side = order['side']
    price = order['price']
    qty = order['qty']
    amount = round(price * qty, 2)
    
    qk = quota_key_of_order(order)
    quota = load_json(base / 'virtual_quota.json')
    nodes = load_json(base / 'nodes.json')
    state = load_json(base / 'state.json', {"orders": []})
    
    q = quota[qk]
    holdings = q.setdefault("holdings", {})
    h = holdings.setdefault(code, {"qty": 0, "sellable": 0, "avg_cost": 0.0})
    
    line = qk if qk in ('A1', 'A2', 'A3') else 'B'
    mark = MARK_OF_LINE[line]
    
    fill_time = now_str()
    
    if side == '买入':
        new_qty = h["qty"] + qty
        h["avg_cost"] = round((q["deployed"] + amount) / new_qty, 4)
        h["qty"] = new_qty
        if code == '513650':
            h["sellable"] += qty
        q["deployed"] = round(q["deployed"] + amount, 2)
        if line in ('A1', 'A2', 'A3'):
            for node in nodes[code]["nodes"]:
                if round_tick(node["price"], nodes[code]["tick"]) == round_tick(price, nodes[code]["tick"]):
                    hands += qty // 100
                    sell_price = round_tick(node["price"] * 1.02, nodes[code]["tick"])
        else:
            sell_price = None
        if side == '买入':
            hands += qty // 100
            if sell_price is None:
                sell_price = None
            else:
                hands -= qty // 100
            q["deployed"] = round(q["deployed"] - round(h["avg_cost"] * qty, 2), 2)
            h["avg_cost"] = round(q["deployed"] / h["qty"], 4) if h["qty"] > 0 else 0.0
            q["pnl"] = round(q["pnl"] + round((price - h["avg_cost"]) * qty, 2), 2)
            q["quota"] = round(166666.67 + q["pnl"], 2) if line in ('A1', 'A2', 'A3') else round(500000.0 + q["pnl"], 2)
            if side == '买入':
                hands -= qty