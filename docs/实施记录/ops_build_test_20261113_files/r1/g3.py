import argparse
import os
import stat
import fcntl
import datetime
import json

def do_open(base, dry_run):
    # 模拟打开操作
    pass

def do_close(base, dry_run):
    # 模拟关闭操作
    pass

def is_trading_day():
    # 模拟判断是否交易日
    return True

def main():
    parser = argparse.ArgumentParser(description="E2 fillwatch gate control")
    parser.add_argument('--base', default='/workspace/ab-/virtual', help='Base directory for operations')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    parser.add_argument('action', choices=['open', 'close', 'status'], help='Action to perform')
    args = parser.parse_args()

    lock_file = os.path.join(args.base, '.gate.lock')
    lock_fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(json.dumps({"ok": True, "action": args.action, "note": "lock busy, skipped"}))
        return 0

    if args.action == 'open':
        do_open(args.base, args.dry_run)
    elif args.action == 'close':
        do_close(args.base, args.dry_run)
    elif args.action == 'status':
        flag_state = os.path.join(args.base, '.gate')
        flag_exists = os.path.exists(flag_state)
        flag_date = datetime.datetime.fromtimestamp(os.path.getmtime(flag_state)).strftime("%Y-%m-%d")
        flag_today = datetime.datetime.now().strftime("%Y-%m-%d") == flag_date
        in_window = is_trading_day()
        gate_open = flag_today and in_window
        print(json.dumps({"ok": True, "action": "status", "trading_day": is_trading_day(), "flag_exists": flag_exists, "flag_date": flag_date, "flag_today": flag_today, "in_window": in_window, "gate_open": gate_open}))
        return 0

    sys.exit(main())