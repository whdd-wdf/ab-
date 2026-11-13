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
    with open(src_path, 'r', encoding='utf-8') as f:
        order_json = json.load(f)
    order_json['result'] = result
    with open(dest_path, 'w', encoding='utf-8') as f:
        json.dump(order_json, f, ensure_ascii=False)
    os.remove(src_path)