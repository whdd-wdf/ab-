import argparse
import json
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default="/workspace/ab-/virtual")
    parser.add_argument('--action', default="status")
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    base = args.base
    action = args.action
    dry_run = args.dry_run

    if action == "open":
        result = do_open(base, dry_run=dry_run)
    elif action == "close":
        result = do_close(base, dry_run=dry_run)
    else:  # status
        exists, flag_date, is_today = flag_state(base)
        result = {
            "ok": True,
            "action": "status",
            "date": today_str(),
            "trading_day": is_trading_day(today_str()),
            "gate_open": exists and is_today and in_window(),
            "flag_exists": exists,
            "flag_date": flag_date
        }

    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
