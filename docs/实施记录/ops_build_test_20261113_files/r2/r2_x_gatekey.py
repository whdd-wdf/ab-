import os
import datetime
from datetime import timezone, timedelta

def gate_open(base):
    flag = base + "/.trading_day"
    if not os.path.exists(flag):
        return None
    mtime = os.path.getmtime(flag)
    TZ = timezone(timedelta(hours=8))
    today = datetime.datetime.now(TZ).strftime("%Y-%m-%d")
    d = datetime.datetime.fromtimestamp(mtime, tz=TZ).strftime("%Y-%m-%d")
    if d != today:
        return None
    t = datetime.datetime.now(TZ)
    if t.hour * 60 + t.minute < 7 * 60 + 30 or t.hour * 60 + t.minute > 17 * 60 + 5:
        return None
    return True

def quota_key_of_order(order):
    A_CODES = {"510300": "A1", "601088": "A2", "513650": "A3"}
    if order.get("line") == "B":
        return "B"
    if order["code"] in A_CODES:
        return A_CODES[order["code"]]
    return None
