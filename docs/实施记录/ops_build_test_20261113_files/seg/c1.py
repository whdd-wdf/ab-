import sys
import json
import datetime
import decimal
from decimal import Decimal
import subprocess
import os
import subprocess
from datetime import datetime
from subprocess import check_output

MIN_AMOUNT = 5000.0
BANNED_PRICE = 10000.0
TICK = Decimal('0.001')
PRICE_DEV_TOL = Decimal('0.01')
B_SINGLE_LIMIT = Decimal('50000.0')
B_MAX_COUNT = 3
A_CODES = [510300, 601088, 513650]
STALE_SECS = 300

def round_tick(decimal_value):
    return decimal_value.quantize(TICK)

def load_json(file_path, default=None):
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            return json.load(file)
    return default

def latest_snapshot(base):
    snapshot_path = os.path.join(base, 'snapshots', f'fillwatch_{datetime.now().strftime("%Y%m%d_%H%M")}.json')
    if os.path.exists(snapshot_path):
        return load_json(snapshot_path)
    return None

def find_node_for_sell(order_price, nodes):
    for node in nodes:
        if node['price'] * 1.02 == round_tick(order_price):
            return node
    return None

def line_of_order(order):
    if 'line' in order:
        return order['line']
    return next((code for code in A_CODES if code in order['code']), None)

def run_compliance(order_json, order_file=None, stdin=sys.stdin):
    if order_file:
        with open(order_file, 'r') as file:
            order_json = json.load(file)
    elif stdin is not None:
        order_json = json.load(stdin)

    if not order_json or not isinstance(order_json, dict) or 'order_id' not in order_json or not isinstance(order_json['order_id'], str):
        return {"ok": False, "passed": False, "checks": [], "reasons": ["Invalid JSON format"]}

    order_id = order_json['order_id']
    order = order_json

    # Load quota and quotes
    quota = load_json(os.path.join(os.environ['BASE'], 'virtual_quota.json'))
    quotes = load_json(os.path.join(os.environ['BASE'], 'quotes.json'))

    # Load latest snapshot
    snapshot = latest_snapshot(os.environ['BASE'])

    # Load nodes
    nodes = load_json(os.path.join(os.environ['BASE'], 'nodes.json'))

    # Check if order is stale
    if order_id in quota and (datetime.now() - datetime.fromtimestamp(quota[order_id]['mtime'])).seconds > STALE_SECS:
        return {"ok": False, "passed": False, "checks": [], "reasons": ["Order is stale"]}

    # Check if order is banned
    if order['code'] in BANNED_PRICE:
        return {"ok": False, "passed": False, "checks": [], "reasons": ["Order is banned"]}

    # Check if order is within single limit
    if order['qty'] > B_SINGLE_LIMIT:
        return {"ok": False, "passed": False, "checks": [], "reasons": ["Order quantity exceeds single limit"]}

    # Check if order is within 5000 limit
    if order['price'] * order['qty'] > B_SINGLE_LIMIT:
        return {"ok": False, "passed": False, "checks": [], "reasons": ["Order amount exceeds 5000 limit"]}

    # Check if order is within 50000 limit
    if order['price'] * order['qty'] > B_SINGLE_LIMIT