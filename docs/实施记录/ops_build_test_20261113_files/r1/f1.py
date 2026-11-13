import argparse
import csv
import json
import os
import re
import sys
import datetime
import json

# 常量
STALE_SECS = 300
MIN_AMOUNT = 5000.0
BANNED_PRICE = {"510300": {4.316, 4.324, 4.325}, "601088": {52.06}}
TICK = {"510300": 0.001, "513650": 0.001}
A_CODES = {"510300": "A1", "601088": "A2", "513650": "A3"}

# 函数
def tick_of(code):
    return TICK.get(code, 0.01)

def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)