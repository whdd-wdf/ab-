# 依据接口规范 §5 门控标志
import os
import time
import json
import shutil
import fcntl
from datetime import datetime, timedelta

# 常量
OPEN_MIN = 7 * 60 + 30
CLOSE_MIN = 17 * 60 + 5

# 辅助函数
def now():
    return datetime.now()

def today_str():
    return now().strftime("%Y-%m-%d")

def is_trading_day():
    # 周一至五返回 True，并返回口径说明字符串
    return True, "周一至五"

def flag_state(base):
    # 返回 flag 是否存在、mtime 日期、是否当日
    flag_path = os.path.join(base, ".trading_day")
    if not os.path.exists(flag_path):
        return False, None, None
    mtime = os.path.getmtime(flag_path)
    mtime_date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    return True, mtime_date, mtime_date == today_str()

def in_window():
    # 当前时间是否在 07:30–17:05 内
    return now().time() >= datetime.strptime(f"{today_str()} {datetime.strptime('07:30', '%H:%M').time()}",
                                              "%Y-%m-%d %H:%M").time() and now().time() <= datetime.strptime(f"{today_str()} {datetime.strptime('17:05', '%H:%M').time()}",
                                                                                                             "%Y-%m-%d %H:%M").time()

# 主函数
def main(base):
    lock_path = os.path.join(base, ".gate.lock")
    lock_file = open(lock_path, "w")
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print(json.dumps({"ok": True, "action": "lock busy, skipped"}), end="")
        return 0

    base = os.path.abspath(base)
    base_flags = os.path.join(base, ".trading_day")
    base_pending = os.path.join(base, "order_queue", "pending")
    base_failed = os.path.join(base, "order_queue", "failed")

    if not os.path.exists(base_flags):
        # 开门逻辑
        trading_day, _, _ = flag_state(base)
        if trading_day:
            print(json.dumps({"ok": True, "action": "open", "trading_day": True, "flag": "created"}), end="")
            return 0
        else:
            print(json.dumps({"ok": True, "action": "open", "trading_day": False, "note": "非交易日，只做关闭扫尾"}), end="")
            return 0
    else:
        # 关门逻辑
        for file in os.listdir(base_pending):
            file_path = os.path.join(base_pending, file)
            if not os.path.exists(file_path):
                continue
            if os.path.exists(os.path.join(base_failed, file)):
                continue
            if os.path.exists(os.path.join(base_failed, f"{file}.dup-1")):
                continue
            if in_window():
                shutil.move(file_path, os.path.join(base_failed, file))
            else:
                shutil.move(file_path, os.path.join(base_failed, f"{file}.dup-{int(time.time())}"))
        print(json.dumps({"ok": True, "action": "close", "moved": [], "skipped": []}), end="")
        return 0
```

请注意，此代码仅实现依据接口规范 §5 门控标志的部分，包括文件锁机制和基本的开门和关门逻辑。开门逻辑中，假设交易日为周一至五