import json
import datetime
import decimal
import os
import subprocess
import re
from collections import defaultdict

STALE_SECS = 300
MIN_AMOUNT = 5000.0
BANNED_PRICE = [52.06, 4.316, 4.324, 4.325]
TICK = 0.001
A_CODES = [510300, 601088, 513650]

def now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

def today_str():
    return now().strftime('%Y-%m-%d')

def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def round_tick(value):
    return decimal.Decimal(value).quantize(decimal.Decimal(TICK))

def order_price_of(row):
    if row['备注']:
        match = re.search(r'委托价?(\d+\.\d+)', row['备注'])
        if match:
            return match.group(1)
    return row['价格']

def is_fill(row):
    return row['方向'] in ['买入', '卖出'] and '委托中' not in row['备注'] and '已撤销' not in row['备注']

def read_trade_log_fills(path):
    fills = defaultdict(set)
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            row = json.loads(line)
            fill_key = (row['日期'], row['代码'], row['方向'], row['数量'], row['委托价'])
            if fill_key not in fills:
                fills[fill_key].add(row)
    return list(fills.keys()), list(fills.values())

def latest_snapshot(base):
    snapshots = os.listdir(os.path.join(base, 'snapshots'))
    if not snapshots:
        return None
    snapshots.sort(key=lambda x: datetime.datetime.strptime(x.split('.')[0], '%Y-%m-%d_%H%M'))
    latest = snapshots[-1]
    return load_json(os.path.join(base, 'snapshots', latest))

def snapshot_age_secs(snapshot):
    try:
        timestamp = datetime.datetime.strptime(snapshot['timestamp'], '%Y-%m-%d %H:%M')
        return (timestamp - now()).total_seconds()
    except:
        return float('inf')

def main(base):
    verdict = {'stale_snapshot': False, 'reason': None, 'new_fills': []}
    if not os.path.exists(os.path.join(base, 'snapshots')):
        verdict['reason'] = 'snapshots 目录不存在'
        return verdict

    latest_snapshot = latest_snapshot(base)
    if latest_snapshot is None:
        verdict['reason'] = 'latest_snapshot 为空'
        return verdict

    if snapshot_age_secs(latest_snapshot) > STALE_SECS:
        verdict['stale_snapshot'] = True
        verdict['reason'] = 'stale_snapshot'
        return verdict

    snapshot = latest_snapshot
    trade_log = os.path.join(base, 'virtual_trade_log.csv')
    new_fills = []

    if not os.path.exists(trade_log):
        verdict['reason'] = 'trade_log 文件不存在'
        return verdict

    snapshot_fills = set()
    for fill in snapshot['orders']['fills_today']:
        fill_key = (fill['timestamp'].split(' ')[0], fill['code'], fill['side'], fill['qty'], fill['price'])
        snapshot_fills.add(fill_key)

    trade_log_fills, trade_log_fills_data = read_trade_log_fills(trade_log)
    for fill in trade_log_fills_data:
        fill_key = (fill['日期'], fill['代码'], fill['方向'], fill['数量