def do_open(base, dry_run=False):
    today = today_str()
    if not is_trading_day(today):
        return {"ok": False, "action": "open", "date": today, "skipped": True, "reason": "非交易日"}
    exists, flag_date, is_today = flag_state(base)
    if exists and is_today:
        return {"ok": True, "action": "open", "date": today, "skipped": True, "reason": "门已开"}
    if dry_run:
        return {"ok": True, "action": "open", "date": today, "dry_run": True}
    with open(base + "/.trading_day", "w") as f:
        pass
    return {"ok": True, "action": "open", "date": today}
