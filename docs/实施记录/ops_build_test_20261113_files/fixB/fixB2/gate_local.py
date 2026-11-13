import argparse
import fcntl
import json
import os
import sys
import time
from datetime import datetime, timedelta

# 文件头注释
# 依据接口规范 §5、交易日判定为周一至五兜底并注明真实系统用新浪日历脚本

OPEN_MIN = 7 * 60 + 30
CLOSE_MIN = 17 * 60 + 5

# 常量
OPEN_MIN = 450  # 7 * 60 + 30
CLOSE_MIN = 2550  # 17 * 60 + 5

def is_trading_day():
    return now().weekday() < 5

def flag_state(base):
    flag_path = os.path.join(base, ".trading_day")
    if not os.path.exists(flag_path):
        return (False, None, False)
    with open(flag_path, 'r') as f:
        date_str = f.read().strip()
    date_str = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
    return (True, date_str, date_str == today_str())

def in_window():
    now_min = now().hour * 60 + now().minute
    return OPEN_MIN <= now_min <= CLOSE_MIN

import os
import time
from datetime import timezone

def is_trading_day(d=None):
    if d is None:
        d = today_str()
    y, m, dd = int(d[0:4]), int(d[5:7]), int(d[8:10])
    return datetime(y, m, dd).weekday() < 5

def flag_state(base):
    flag = base + "/.trading_day"
    if not os.path.exists(flag):
        return (False, None, False)
    mtime = os.path.getmtime(flag)
    d = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
    return (True, d, d == today_str())

def in_window():
    t = now()
    return (t.hour * 60 + t.minute >= 7 * 60 + 30) and (t.hour * 60 + t.minute <= 17 * 60 + 5)

def do_open(base, dry_run=False):
    today = today_str()
    if not is_trading_day(today):
        return {"ok": False, "action": "open", "date": today, "skipped": True, "reason": "非交易日"}
    exists, flag_date, is_today = flag_state(base)
    if exists and is_today:
        return {"ok": True, "action": "open", "date": today, "skipped": True, "reason": "门已开"}
    if dry_run:
        return {"ok": True, "action": "open", "date": today, "dry_run": True}
    with open(base + "/.trading_day", "w") as f:
        pass
    return {"ok": True, "action": "open", "date": today}

def do_close(base, dry_run=False):
    today = today_str()
    flag = base + "/.trading_day"
    
    if dry_run:
        return {"ok": True, "action": "close", "date": today, "dry_run": True}
    
    moved = []
    
    if os.path.exists(flag):
        os.remove(flag)
    
    pending_dir = base + "/order_queue/pending"
    failed_dir = base + "/order_queue/failed"
    
    if os.path.exists(pending_dir):
        os.makedirs(failed_dir, exist_ok=True)
        for fname in sorted(os.listdir(pending_dir)):
            if fname.endswith(".json"):
                src = pending_dir + "/" + fname
                dst = failed_dir + "/" + fname[:-5] + ".dup.json" if os.path.exists(failed_dir + "/" + fname) else failed_dir + "/" + fname
                os.rename(src, dst)
                moved.append(fname)
    
    return {"ok": True, "action": "close", "date": today, "moved": moved}

import argparse
import json
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default="/workspace/ab-/virtual")
    parser.add_argument('--action', default="status")
    parser.add_argument('action_pos', nargs='?', default=None)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    base = args.base
    action = args.action_pos or args.action
    dry_run = args.dry_run

    if action == "open":
        result = do_open(base, dry_run=dry_run)
    elif action == "close":
        result = do_close(base, dry_run=dry_run)
    else:  # status
        exists, flag_date, is_today = flag_state(base)
        result = {
            "ok": True,
            "action": "status",
            "date": today_str(),
            "trading_day": is_trading_day(today_str()),
            "gate_open": exists and is_today and in_window(),
            "flag_exists": exists,
            "flag_date": flag_date
        }

    print(json.dumps(result, ensure_ascii=False))
    return 0

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

if __name__ == "__main__":
    sys.exit(main())
