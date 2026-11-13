import re
from datetime import datetime, timezone

def order_price_of(row):
    match = re.search(r"委托价?(\d+\.\d+)", row["备注"] or "")
    return float(match.group(1)) if match else float(row["价格"] or 0)

def is_fill(row):
    return row["方向"] in ["买入", "卖出"] and "委托中" not in row["备注"] and (row["备注"] or "").strip().startswith("】") and not (row["备注"] or "").strip().startswith("已撤销")

def read_trade_log_fills(path):
    with open(path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        return {k: v for row in reader for k, v in row.items() if is_fill(row)}

def latest_snapshot(base):
    snapshots = [f for f in os.listdir(base) if f.startswith("fillwatch_") and f.endswith(".json")]
    if not snapshots:
        return None
    snapshots.sort()
    return json.load(open(os.path.join(base, snapshots[-1]), 'r'))

def snapshot_age_secs(snapshot):
    try:
        timestamp = datetime.strptime(snapshot["timestamp"], "%Y-%m-%d %H:%M:%S")
        return (now() - timestamp).total_seconds()
    except ValueError:
        return 10**9