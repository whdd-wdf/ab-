import os
import datetime
import tzlocal

def latest_snapshot(base):
    sdir = base + "/snapshots"
    if not os.path.isdir(sdir):
        return None
    names = sorted([n for n in os.listdir(sdir) if n.startswith("fillwatch_") and n.endswith(".json")])
    if not names:
        return None
    fname = names[-1]
    data = load_json(sdir + "/" + fname, None)
    if data is None:
        return None
    data["_file"] = fname
    return data

def snapshot_age_secs(snapshot):
    ts = snapshot.get("timestamp", "")
    if isinstance(ts, (int, float)):
        return now().timestamp() - float(ts)
    try:
        dt = datetime.datetime.strptime(str(ts), "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=tzlocal.get_localzone())
        return (now() - dt).total_seconds()
    except ValueError:
        return 10**9
