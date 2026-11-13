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

import os
import datetime
from datetime import timezone, timedelta

def gate_open(base):