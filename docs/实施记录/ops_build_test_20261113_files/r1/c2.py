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