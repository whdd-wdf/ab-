import os
import time
import shutil
import datetime
from zoneinfo import ZoneInfo
from datetime import timezone, timedelta

TZ = ZoneInfo("Asia/Shanghai")

def now():
    return datetime.now(TZ)

def today_str():
    return now().strftime("%Y-%m-%d")

def now_str():
    return now().strftime("%Y-%m-%d %H:%M:%S")

def is_trading_day(base):
    flag_file = os.path.join(base, "monitor/.trading_day")
    if not os.path.exists(flag_file):
        return False
    flag_mtime = os.path.getmtime(flag_file)
    flag_date = datetime.datetime.fromtimestamp(flag_mtime, TZ)
    return flag_date.weekday() < 5 and flag_date.date() == datetime.date.today()

def do_open(base, dry_run):
    if not is_trading_day(base):
        if not dry_run:
            os.remove(os.path.join(base, "monitor/.trading_day"))
            return {"ok": True, "action": "open", "trading_day": False, "note": "非交易日，只做关闭扫尾"}
        return {"ok": True, "action": "open", "trading_day": False, "flag": "would_create"}
    if is_trading_day(base):
        is_today, flag_date, _ = flag_state(base)
        if is_today:
            return {"ok": True, "action": "open", "trading_day": True, "flag": "already_open"}
    if not dry_run:
        os.utime(os.path.join(base, "monitor/.trading_day"), times=(flag_mtime, flag_mtime))
        return {"ok": True, "action": "open", "trading_day": True, "flag": "created"}
    return {"ok": True, "action": "open", "trading_day": True, "flag": "would_create"}

def do_close(base, dry_run):
    moved = []
    skipped = []
    if not dry_run and os.path.exists(os.path.join(base, "order_queue")):
        pending = os.listdir(os.path.join(base, "order_queue/pending"))
        pending.sort()
        for file in pending:
            if not dry_run:
                try:
                    shutil.move(os.path.join(base, "order_queue/pending", file),
                                os.path.join(base, "order_queue/failed", file))
                    moved.append(file)
                except FileNotFoundError:
                    skipped.append(file)
            else:
                moved.append(file)
    return {"ok": True, "action": "close", "moved": moved, "skipped": skipped, "dry_run": dry_run}