import os
import subprocess
import json
from datetime import datetime, timedelta
import time

# 常量定义
GATE_OPEN_MIN = 7 * 60 + 30  # 07:30
GATE_CLOSE_MIN = 17 * 60 + 5  # 17:05
TICK = 0.001  # 510300/513650
A_CODES = {'A1': 'A', 'A2': 'A', 'A3': 'A', 'B': 'B'}

# 辅助函数
def now():
    return datetime.now()

def now_str():
    return now().strftime('%Y-%m-%d %H:%M:%S')

def today_str():
    return now().strftime('%Y-%m-%d')

def load_json(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def save_json(file_path, data):
    with open(file_path + '.tmp', 'w') as f:
        json.dump(data, f)
    os.rename(file_path + '.tmp', file_path)

def gate_open(base):
    trading_day_file = os.path.join(base, '.trading_day')
    if not os.path.exists(trading_day_file):
        return False, '不存在交易日标志文件'
    with open(trading_day_file, 'r') as f:
        trading_day = f.read().strip()
    if trading_day != today_str():
        return False, '交易日标志文件日期不匹配'
    if not (GATE_OPEN_MIN <= now().minute < GATE_CLOSE_MIN):
        return False, '当前时间不在交易时间范围内'
    return True, '交易日标志文件日期匹配且当前时间在交易时间范围内'

def quota_key_of_order(order):
    line = order['line']
    if line in A_CODES:
        return A_CODES[line]
    return line

def move_to_failed(base, order_id, order):
    failed_dir = os.path.join(base, 'failed')
    if not os.path.exists(failed_dir):
        os.makedirs(failed_dir)
    failed_file = os.path.join(failed_dir, f'failed-{order_id}.json')
    result = {'status': 'stale', 'reason': f'订单非当日'}
    save_json(failed_file, result)
    os.remove(os.path.join(base, 'pending', f'{order_id}.json'))

def move_to_done(base, order_id, order):
    done_dir = os.path.join(base, 'done')
    if not os.path.exists(done_dir):
        os.makedirs(done_dir)
    done_file = os.path.join(done_dir, f'done-{order_id}.json')
    result = {'status': 'dry-run-pass', 'placed': False}
    save_json(done_file, result)
    os.remove(os.path.join(base, 'pending', f'{order_id}.json'))

def order_executor(base):
    base_ops = os.path.join(base, 'virtual_ops.py')
    order_queue = os.path.join(base, 'order_queue')
    pending_dir = os.path.join(order_queue, 'pending')
    failed_dir = os.path.join(order_queue, 'failed')
    done_dir = os.path.join(order_queue, 'done')
    if not os.path.exists(pending_dir):
        return {"ok": False, "action": "run", "date": today_str(), "processed": 0, "filled": [], "rejected": [], "gate_closed": [], "dry_run": []}
    if not os.path.exists(failed_dir):
        os.makedirs(failed_dir)
    if not os.path.exists(done_dir):
        os.makedirs(done_dir)
    processed = 0
    filled = []
    rejected = []
    gate_closed = []
    dry