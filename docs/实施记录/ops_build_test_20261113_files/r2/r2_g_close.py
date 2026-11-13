def do_close(base, dry_run=False):
    today = today_str()
    flag = base + "/.trading_day"
    
    if dry_run:
        return {"ok": True, "action": "close", "date": today, "dry_run": True}
    
    moved = []
    
    if os.path.exists(flag):
        os.remove(flag)
    
    pending_dir = base + "/order_queue/pending"
    failed_dir = base + "/order_queue/failed"
    
    if os.path.exists(pending_dir):
        os.makedirs(failed_dir, exist_ok=True)
        for fname in sorted(os.listdir(pending_dir)):
            if fname.endswith(".json"):
                src = pending_dir + "/" + fname
                dst = failed_dir + "/" + fname[:-5] + ".dup.json" if os.path.exists(failed_dir + "/" + fname) else failed_dir + "/" + fname
                os.rename(src, dst)
                moved.append(fname)
    
    return {"ok": True, "action": "close", "date": today, "moved": moved}