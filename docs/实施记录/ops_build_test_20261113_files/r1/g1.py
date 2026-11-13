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