import os
import json
import csv
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Shanghai")
except Exception:
    TZ = timezone(timedelta(hours=8))
MIN_AMOUNT = 5000.0
STALE_SECS = 300
BANNED_PRICE = {"510300": {4.316, 4.324, 4.325}, "601088": {52.06}}
A_CODES = {"510300": "A1", "601088": "A2", "513650": "A3"}
TICK = {"510300": 0.001, "601088": 0.01, "513650": 0.001}
DEFAULT_TICK = 0.01
def tick_of(code):
    return TICK.get(code, DEFAULT_TICK)
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default