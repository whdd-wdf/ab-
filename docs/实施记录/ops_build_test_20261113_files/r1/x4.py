import json
from datetime import datetime, timezone, timedelta
import os
import argparse
import shutil
import json
from collections import defaultdict

def process_one(src_path, base, compliance_script):
    with open(src_path, 'r') as file:
        order_json = json.load(file)
    order_id = os.path.splitext(os.path.basename(src_path))[0]
    order_mtime = datetime.fromtimestamp(os.path.getmtime(src_path), tz=timezone(timedelta(hours=8)))

    if order_mtime.date() != datetime.now().date():
        return {"kind": "stale", "order_id": order_id}

    result = run_compliance(order_json, compliance_script)
    if result:
        return result

    return {"kind": "rejected", "order_id": order_id}

def write_snapshot(base):
    state_path = os.path.join(base, 'state.json')
    with open(state_path, 'r') as state_file:
        state = json.load(state_file)

    fills_today = [order for order in state.values() if order['status'] == 'filled']
    pending = [order for order in state.values() if order['status'] == 'pending']

    snapshot_path = os.path.join(base, 'snapshots', f'fillwatch_{today_str()}.json')
    with open(snapshot_path, 'w') as snapshot_file:
        json.dump({
            "label": "fillwatch",
            "timestamp": now_str(),
            "status": "ok",
            "orders": list(state.values()),
            "fills_today": fills_today,
            "pending": pending
        }, snapshot_file)

def main():
    parser = argparse.ArgumentParser(description='Process order queue and write snapshot.')
    parser.add_argument('--base', default='/workspace/ab-/virtual', help='Base directory for virtual program')
    parser.add_argument('--compliance', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "order_compliance.py"), help='Compliance script path')
    args = parser.parse_args()

    base = args.base
    compliance_script = args.compliance

    result = gate_open(base)
    if result:
        return result

    processed = 0
    filled = []
    rejected = []
    dry_run = []

    for file in sorted(os.listdir(os.path.join(base, 'pending'))):
        if file.endswith('.json'):
            src_path = os.path.join(base, 'pending', file)
            result = process_one(src_path, base, compliance_script)
            if result['kind'] == "filled":
                filled.append(result)
                processed += 1
            elif result['kind'] == "rejected":
                rejected.append(result)
                processed += 1
            elif result['kind'] == "dry_run":
                dry_run.append(result)
                processed += 1

    if filled:
        write_snapshot(base)

    result = {
        "ok": True,
        "action": "run",
        "date": today_str(),
        "processed": processed,
        "filled": filled,
        "rejected": rejected,
        "gate_closed": [],
        "dry_run": dry_run
    }

    result_str = json.dumps(result, ensure_ascii=False)
    print(result_str)
    return 0

def run_compliance(order_json, compliance_script):
    # Placeholder for compliance logic
    return True

def gate_open(base):
    trading_day_path = os.path.join(base, '.trading_day')
    if not os.path.exists(trading_day_path):
        return {"status": "gate-closed", "reason": "No trading day file found"}

    with open(trading_day_path, 'r') as file:
        trading_day = json.load(file)

    if trading_day['mtime'].date() != datetime.now().date():
        return {"status": "gate-closed", "reason": "Trading day file is stale"}

    return