def write_snapshot(base):
    state = load_json(base + "/state.json", {"orders": []})
    orders = state.get("orders", [])
    today = today_str()
    fills_today = [o for o in orders if o.get("status") == "已成交" and str(o.get("time", ""))[:10] == today]
    pending = [o for o in orders if o.get("status") == "未成交"]
    fname = "fillwatch_" + today.replace("-", "") + "_" + now_str()[11:13] + now_str()[14:16] + ".json"
    snap = {"label": "fillwatch", "timestamp": now_str(), "status": "ok", "orders": orders, "fills_today": fills_today, "pending": pending}
    os.makedirs(base + "/snapshots", exist_ok=True)
    with open(base + "/snapshots/" + fname, 'w', encoding='utf-8') as f:
        json.dump(snap, f, ensure_ascii=False)


def main():
    import argparse, json, sys
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default="/workspace/ab-/virtual", help='Base directory for snapshots')
    parser.add_argument('--compliance', default='', help='Compliance script path')
    args = parser.parse_args()
    base = args.base
    compliance_script = args.compliance if args.compliance else os.path.join(os.path.dirname(os.path.abspath(__file__)), "order_compliance.py")
    
    if not gate_open(base):
        print(json.dumps({"ok": False, "error": "gate_closed", "processed": 0, "filled": [], "rejected": [], "gate_closed": [], "dry_run": []}, ensure_ascii=False))
        return 0
    
    pending_dir = base + "/order_queue/pending"
    if not os.path.exists(pending_dir):
        print(json.dumps({"ok": False, "error": "no_pending_dir", "processed": 0, "filled": [], "rejected": [], "gate_closed": [], "dry_run": []}, ensure_ascii=False))
        return 0
    
    filled = []
    rejected = []
    processed = 0
    for fname in sorted(os.listdir(pending_dir)):
        if fname.endswith(".json"):
            src = pending_dir + "/" + fname
            result = process_one(src, base, compliance_script)
            processed += 1
            if result.get("kind") == "filled":
                filled.append(result)
            elif result.get("kind") == "rejected":
                rejected.append(result)
    
    if filled:
        write_snapshot(base)
    
    print(json.dumps({"ok": True, "action": "run", "date": today_str(), "processed": processed, "filled": filled, "rejected": rejected, "gate_closed": [], "dry_run": []}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
