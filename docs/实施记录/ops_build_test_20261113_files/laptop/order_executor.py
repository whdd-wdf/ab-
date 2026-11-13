#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""order_executor.py — 订单队列执行器（操作侧，虚拟环境搭建版）

依据：docs/操作与管控接口规范.md §1.4（状态流转）、§5.2（门控判定）、§6.5（虚拟成交入账）。
合规调用同目录 order_compliance.py（subprocess，传 --base）；虚拟成交由同目录虚拟程序
virtual_ops.py 的 run / snapshot 完成（口径以 §6.5 为准，不自行复制入账公式）。

用法：
  python3 order_executor.py --base <目录>
  --once        只跑一轮（默认也是只跑一轮，本版无常驻循环，由 watcher/cron 触发）
  --dry-run-all 全部按 dry-run 处理（只合规、不成交）
  不传 --base 时用真实路径 /root/monitor/。

流转（§1.4）：
  pending/*.json
  ├─ 门关（标志缺失/非当日，或不在 07:30–17:05）──→ failed/{result:{status:"gate-closed", reason}}
  ├─ 文件 mtime 非当日 ─────────────────────────→ failed/{result:{status:"stale", reason}}
  ├─ 合规不通过 ───────────────────────────────→ failed/{result:{status:"rejected", reasons, checks}}
  ├─ dry_run=true 且合规通过（或 --dry-run-all）→ done/{result:{status:"dry-run-pass", placed:false}}
  └─ 合规通过 ─────────────────────────────────→ done/{result:{status:"filled", …}}（按限价虚拟成交）

注意：虚拟 run() 一次性处理整个 pending，故先把拒绝/过期单移出 pending，再触发成交，
否则坏单会被虚拟程序自己处理。stdout 只输出一个 JSON 汇总。仅标准库。
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

try:  # 北京时间（与 virtual/virtual_ops.py 同口径）
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Shanghai")
except Exception:  # pragma: no cover - 无 tzdata 时回落固定 +08:00
    TZ = timezone(timedelta(hours=8))

REAL_BASE = "/root/monitor"
GATE_OPEN_MIN = 7 * 60 + 30   # 07:30
GATE_CLOSE_MIN = 17 * 60 + 5  # 17:05


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def now():
    return datetime.now(TZ)


def today_str():
    return now().strftime("%Y-%m-%d")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.rename(tmp, path)


def gate_open(base):
    """§5.2：标志存在且 mtime 日期 == 当日，且当前在 07:30–17:05 内。"""
    flag = os.path.join(base, ".trading_day")
    if not os.path.exists(flag):
        return False, "门控标志不存在"
    mtime = datetime.fromtimestamp(os.path.getmtime(flag), tz=TZ)
    if mtime.strftime("%Y-%m-%d") != today_str():
        return False, "门控标志非当日（mtime %s）" % mtime.strftime("%Y-%m-%d")
    n = now()
    mins = n.hour * 60 + n.minute
    if not (GATE_OPEN_MIN <= mins <= GATE_CLOSE_MIN):
        return False, "不在 07:30–17:05 窗口内（当前 %s）" % n.strftime("%H:%M")
    return True, "门开"


def move_order(src, dest_dir, order):
    """先写目标再删源（与虚拟程序同语义，不覆盖同名文件）。"""
    oid = str(order.get("order_id") or os.path.basename(src)[:-5])
    dest = os.path.join(dest_dir, "%s.json" % oid)
    if os.path.exists(dest):
        dest = os.path.join(dest_dir, "%s.dup-%d.json" % (oid, int(now().timestamp())))
    save_json(dest, order)
    os.remove(src)
    return dest


def drop_state_row(base, order_id):
    """合规拒绝时删除 state.json 中该 order_id 的订单簿条目（§1.4 虚拟流转）。"""
    state_file = os.path.join(base, "state.json")
    state = load_json(state_file, None)
    if not isinstance(state, dict):
        return
    rows = state.get("orders", [])
    kept = [o for o in rows if str(o.get("order_id")) != str(order_id)]
    if len(kept) != len(rows):
        state["orders"] = kept
        save_json(state_file, state)


def run_compliance(base, order):
    """调同目录 order_compliance.py（subprocess，传 --base）。返回 (passed, checks, reasons)。"""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "order_compliance.py")
    cmd = [sys.executable, script, "--base", base,
           "--order", json.dumps(order, ensure_ascii=False)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception as e:
        return False, [], ["合规脚本调用失败：%r" % e]
    try:
        out = json.loads(p.stdout)
    except Exception:
        return False, [], ["合规脚本输出无法解析（rc=%s）：%s %s"
                           % (p.returncode, p.stdout.strip()[:200], p.stderr.strip()[:200])]
    return bool(out.get("passed")), out.get("checks", []), out.get("reasons", [])


def virtual_cmd(base, *args):
    """调同目录虚拟程序（run / snapshot），返回 (rc, stdout)。"""
    script = os.path.join(base, "virtual_ops.py")
    if not os.path.exists(script):
        return 127, "虚拟程序不存在：%s" % script
    try:
        p = subprocess.run([sys.executable, script] + list(args),
                           capture_output=True, text=True, timeout=300)
        return p.returncode, p.stdout
    except Exception as e:
        return 1, "虚拟程序调用失败：%r" % e


# ---------------------------------------------------------------------------
# 执行一轮
# ---------------------------------------------------------------------------
def run_once(base, dry_run_all=False):
    pending_dir = os.path.join(base, "order_queue", "pending")
    done_dir = os.path.join(base, "order_queue", "done")
    failed_dir = os.path.join(base, "order_queue", "failed")
    for d in (pending_dir, done_dir, failed_dir):
        os.makedirs(d, exist_ok=True)

    summary = {"ok": True, "action": "run", "date": today_str(), "base": base,
               "processed": 0, "filled": [], "rejected": [], "gate_closed": [],
               "stale": [], "dry_run_pass": [], "errors": []}

    files = sorted(f for f in os.listdir(pending_dir) if f.endswith(".json"))
    if not files:
        summary["gate"] = "n/a"
        return summary

    ok_gate, gate_detail = gate_open(base)
    summary["gate"] = "open" if ok_gate else "closed"
    summary["gate_reason"] = gate_detail
    if not ok_gate:
        # 门关：整批移入 failed（§5.2），不跑合规
        for fn in files:
            src = os.path.join(pending_dir, fn)
            order = load_json(src, None)
            if not isinstance(order, dict):
                order = {"order_id": fn[:-5]}
            oid = str(order.get("order_id") or fn[:-5])
            order["result"] = {"status": "gate-closed", "reason": gate_detail}
            try:
                move_order(src, failed_dir, order)
            except FileNotFoundError:
                continue
            summary["gate_closed"].append(oid)
            summary["processed"] += 1
        return summary

    accepted = []
    for fn in files:
        src = os.path.join(pending_dir, fn)
        if not os.path.exists(src):
            continue
        order = load_json(src, None)
        if not isinstance(order, dict):
            # 解析失败兜底进 failed（§1.4，不丢弃无记录）
            bad = {"order_id": fn[:-5]}
            bad["result"] = {"status": "rejected", "reasons": ["订单 JSON 解析失败"],
                             "checks": []}
            move_order(src, failed_dir, bad)
            summary["rejected"].append({"order_id": fn[:-5], "status": "rejected"})
            summary["processed"] += 1
            continue
        oid = str(order.get("order_id") or fn[:-5])

        # 订单文件 mtime 非当日 -> stale
        mtime = datetime.fromtimestamp(os.path.getmtime(src), tz=TZ)
        if mtime.strftime("%Y-%m-%d") != today_str():
            order["result"] = {"status": "stale",
                               "reason": "订单非当日（%s），过期" % mtime.strftime("%Y-%m-%d")}
            move_order(src, failed_dir, order)
            summary["stale"].append(oid)
            summary["processed"] += 1
            continue

        passed, checks, reasons = run_compliance(base, order)
        if not passed:
            order["result"] = {"status": "rejected", "reasons": reasons, "checks": checks}
            move_order(src, failed_dir, order)
            drop_state_row(base, oid)
            summary["rejected"].append({"order_id": oid, "status": "rejected",
                                        "reasons": reasons})
            summary["processed"] += 1
            continue

        if dry_run_all or order.get("dry_run") is True:
            # 只合规、不成交（§1.4 dry-run-pass）
            order["result"] = {"status": "dry-run-pass", "placed": False, "checks": checks}
            move_order(src, done_dir, order)
            summary["dry_run_pass"].append(oid)
            summary["processed"] += 1
            continue

        accepted.append({"file": fn, "path": src, "order": order, "order_id": oid,
                         "checks": checks})

    # 拒绝/过期/坏单已全部移出 pending，此时再触发虚拟成交（§6.5）
    if accepted:
        rc, out = virtual_cmd(base, "run")
        if rc != 0:
            summary["errors"].append({"step": "virtual run", "rc": rc,
                                      "detail": out.strip()[:300]})
        for a in accepted:
            summary["processed"] += 1
            done_path = os.path.join(done_dir, "%s.json" % a["order_id"])
            d = load_json(done_path, None)
            if isinstance(d, dict) and d.get("result", {}).get("status") == "filled":
                r = d["result"]
                summary["filled"].append({"order_id": a["order_id"],
                                          "code": a["order"].get("code"),
                                          "side": a["order"].get("side"),
                                          "price": r.get("fill_price"),
                                          "qty": a["order"].get("qty"),
                                          "fill_time": r.get("fill_time")})
            elif os.path.exists(done_path):
                summary["filled"].append({"order_id": a["order_id"],
                                          "code": a["order"].get("code"),
                                          "side": a["order"].get("side"),
                                          "price": a["order"].get("price"),
                                          "qty": a["order"].get("qty")})
            else:
                failed_path = os.path.join(failed_dir, "%s.json" % a["order_id"])
                d = load_json(failed_path, None)
                summary["rejected"].append({"order_id": a["order_id"],
                                            "status": (d or {}).get("result", {}).get("status", "unknown"),
                                            "reasons": (d or {}).get("result", {}).get("reasons", [])})
        # 有成交则写一份快照（fillwatch 成交确认源，§4.2/§4.6）
        if summary["filled"]:
            rc2, out2 = virtual_cmd(base, "snapshot")
            if rc2 != 0:
                summary["errors"].append({"step": "virtual snapshot", "rc": rc2,
                                          "detail": out2.strip()[:300]})

    summary["counts"] = {"filled": len(summary["filled"]),
                         "rejected": len(summary["rejected"]),
                         "gate_closed": len(summary["gate_closed"]),
                         "stale": len(summary["stale"]),
                         "dry_run_pass": len(summary["dry_run_pass"])}
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv):
    ap = argparse.ArgumentParser(description="订单队列执行器（虚拟环境搭建版）")
    ap.add_argument("--base", default=REAL_BASE, help="数据根目录（默认 /root/monitor/）")
    ap.add_argument("--once", action="store_true", help="只跑一轮（默认即只跑一轮）")
    ap.add_argument("--dry-run-all", dest="dry_run_all", action="store_true",
                    help="全部按 dry-run 处理（只合规、不成交）")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    base = os.path.abspath(args.base)
    try:
        summary = run_once(base, dry_run_all=args.dry_run_all)
    except Exception as e:
        summary = {"ok": False, "base": base, "processed": 0, "error": repr(e)}
        print(json.dumps(summary, ensure_ascii=False))
        return 1
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
