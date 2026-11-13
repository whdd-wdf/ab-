import argparse
import json
import os
import sys
import datetime
from datetime import datetime, timezone, timedelta

# 常量定义
MIN_AMOUNT = 5000.0
BANNED_PRICE = {"510300": {4.316, 4.324, 4.325}, "601088": {52.06}}
TICK = {"510300": 0.001, "513650": 0.001}
PRICE_DEV_TOL = 0.01
B_SINGLE_LIMIT = 50000.0
B_MAX_COUNT = 3
A_CODES = {"510300": "A1", "601088": "A2", "513650": "A3"}
STALE_SECS = 300

# 辅助函数
def tick_of(code):
    return TICK.get(code, 0.01)