import datetime
import os
import time
from datetime import timezone

def is_trading_day(d=None):
    if d is None:
        d = today_str()
    y, m, dd = int(d[0:4]), int(d[5:7]), int(d[8:10])
    return datetime.date(y, m, dd).weekday() < 5

def flag_state(base):
    flag = base + "/.trading_day"
    if not os.path.exists(flag):
        return (False, None, False)
    mtime = os.path.getmtime(flag)
    d = datetime.datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
    return (True, d, d == today_str())

def in_window():
    t = now()
    return (t.hour * 60 + t.minute >= 7 * 60 + 30) and (t.hour * 60 + t.minute <= 17 * 60 + 5)
