import json
import os
import datetime
from decimal import Decimal, ROUND_HALF_UP

def round_tick(price, tick):
    return float(Decimal(str(price)).quantize(Decimal(str(tick)), rounding=ROUND_HALF_UP))

def now():
    return datetime.datetime.now(TZ)

def today_str():
    return now().strftime("%Y-%m-%d")

def now_str():
    return now().strftime("%Y-%m-%d %H:%M:%S")

def check_b(order, base, checks, reasons):
    code = order['code']
    side = order['side']
    price = order['price']
    qty = order['qty']
    amount = price * qty
    line = order['line']
    prev_close = order.get('prev_close', None)
    limit_price = order.get('limit_price', None)
    note = order.get('note', None)
    available = base['available'][line][code]
    holdings = base['holdings'][line][code]

    if prev_close is None:
        reasons.append("prev_close not available")
        return False

    if side == '买入':
        if prev_close is None:
            reasons.append("prev_close not available")
            return False

        if price / prev_close - 1 <= 0.05:
            checks.append("涨幅<=5%")
        else:
            reasons.append("涨幅>5%")
            return False

        if prev_close is None:
            reasons.append("prev_close not available")
            return False

        if abs(price / prev_close - 1) <= 0.01:
            reasons.append("买价≈现价")
        else:
            reasons.append("买价≠现价")
            return False

        if limit_price is None:
            checks.append("limit_price not available")
            return False

        if price <= float(limit_price):
            checks.append("买价<=P4限价")
        else:
            reasons.append("买价>P4限价")
            return False

        if amount > 50000:
            reasons.append("单只>5万")
            return False

        if amount > available:
            reasons.append("单笔>B可用")
            return False

        if holdings > 2:
            reasons.append("B线>3只")
            return False

        if qty > holdings[code]:
            reasons.append("单笔>B持仓")
            return False

    elif side == '卖出':
        if holdings[code] > 0:
            checks.append("卖出<=持仓")
        else:
            reasons.append("卖出>持仓")
            return False

    return True

def run_compliance(order, base):
    checks = []
    reasons = []

    if order['line'] == 'A':
        return check_a(order, base, checks, reasons)
    else:
        return check_b(order, base, checks, reasons)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Order Compliance Checker')
    parser.add_argument('--base', default='/workspace/ab-/virtual', type=str, help='Base directory for virtual data')
    parser.add_argument('--order', type=str, help='Order JSON string')
    parser.add_argument('--order-file', type=str, help='Path to order JSON file')
    args = parser.parse_args()

    if args.order_file:
        with open(args.order_file, 'r') as f:
            order = json.load(f)
    elif args.order:
        order = json.loads(args.order)
    else:
        order = json.loads(input("Enter order JSON: "))

    if not order:
        print({"ok": False, "error": "Invalid order JSON"})
        return 1

    base = {
        'available': {
            'A': {'600919': 100000, '601