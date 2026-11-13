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