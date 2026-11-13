#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fillwatch_rehang.py — A 线成交监视与补挂计算（操作侧，虚拟环境搭建版）

依据：docs/操作与管控接口规范.md §4.2（快照格式）、§4.3（stale 判定）、
§4.4（新成交检出口径）、§4.5（输出与补挂计算）、§7.6（B 线卖出无补挂）。

用法：
  python3 fillwatch_rehang.py --base <目录> --mode compare
  --mode compare|live（默认 compare）；另支持 --date、--snapshot、--trade-log、
  --bookings、--ledger、--state、--queue-dir、--log、--out-dir、--prev-close。
  不传 --base 时用真实路径 /root/monitor/。

口径：
  新成交 = 快照 fills_today 中 A 线三码（510300/601088/513650）的成交行，
           其匹配键 (代码, 方向, 数量, 委托价) 不在 trade_log / bookings 已入账行中。
  trade_log 行：方向须恰为 买入/卖出；备注含“委托中”不算成交；备注在标记后紧跟
           “已撤销”不算成交；委托价按正则 委托价?(\\d+\\.\\d+) 提取（须带小数点），
           取不到则取价格栏。
  stale：快照 timestamp 距现在 > 300 秒 → verdict=silent、reason=stale_snapshot。
  补挂：卖出成交 → 按节点价补买单（节点由卖价反推 round_tick(节点×1.02)=卖价）；
        买入成交 → 按节点价×1.02 补卖单。
  过滤：单笔 <5000（small_amount）、禁挂集群价（banned_cluster_price）、
        补挂价已在挂（duplicate_pending_sell/buy）、卖价高于涨停（above_limit_up）、
        节点反推不到（node_not_found）。

compare 模式不写队列、不写 state、不写 bookings；stdout 只输出一个 JSON。
仅标准库。
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

try:  # 北京时间（与 virtual/virtual_ops.py 同口径）
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Shanghai")
except Exception:  # pragma: no cover - 无 tzdata 时回落固定 +08:00
    TZ = timezone(timedelta(hours=8))

REAL_BASE = "/root/monitor"
STALE_SECS = 300
MIN_AMOUNT = 5000.0
BANNED_PRICE = {"510300": {4.316, 4.324, 4.325}, "601088": {52.06}}
TICK = {"510300": 0.001, "513650": 0.001}
A_CODES = {"510300": "A1", "601088": "A2", "513650": "A3"}
MARK_OF_LINE = {"A1": "【A1】", "A2": "【A2】", "A3": "【A3】", "B": "【B线】"}
ORDER_PRICE_RE = re.compile(r"委托价?(\d+\.\d+)")


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def now():
    return datetime.now(TZ)


def today_str():
    return now().strftime("%Y-%m-%d")


def now_str():
    return now().strftime("%Y-%m-%d %H:%M:%S")


def tick_of(code):
    return TICK.get(code, 0.01)


def round_tick(price, tick):
    q = Decimal(str(tick))
    return float(Decimal(str(price)).quantize(q, rounding=ROUND_HALF_UP))


def r2(x):
    return round(float(x) + 1e-9, 2)


def load_json(path, default):
    if not path or not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.rename(tmp, path)


def price_slug(price):
    s = ("%.4f" % float(price)).rstrip("0").rstrip(".")
    return s.replace(".", "p")


def is_cancelled(remark):
    """备注在第一个 】 之后、去空格后以“已撤销”开头，才算撤销行（§2.3）。"""
    if "】" not in remark:
        return False
    tail = remark.split("】", 1)[1].strip()
    return tail.startswith("已撤销")


def order_price_of(row):
    """委托价提取：备注 委托价?(\\d+\\.\\d+)（须带小数点），否则取价格栏。"""
    m = ORDER_PRICE_RE.search(row.get("备注", "") or "")
    if m:
        try:
            return float(m.group(1))
        except Exception:
            pass
    try:
        return float(row.get("价格"))
    except Exception:
        return None


def fill_key(date, code, side, qty, order_price):
    return (date, str(code), side, int(qty), order_price)


def state_key(fill):
    """live 去重键（与 §4.5 同口径）：代码|方向|委托价|数量|委托时间。"""
    try:
        price = float(fill.get("price"))
    except Exception:
        price = fill.get("price")
    return "%s|%s|%s|%s|%s" % (fill.get("code"), fill.get("side"), price,
                               fill.get("qty"), fill.get("time", ""))


# ---------------------------------------------------------------------------
# 读取已入账成交（trade_log + bookings，两份）
# ---------------------------------------------------------------------------
def read_booked(paths):
    """返回 (keys:set, rows:list)。只认方向恰为买入/卖出、且非委托中/非撤销的行。"""
    keys = set()
    rows = []
    for path in paths:
        if not path or not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    side = (row.get("方向") or "").strip()
                    if side not in ("买入", "卖出"):
                        continue
                    remark = row.get("备注") or ""
                    if "委托中" in remark:
                        continue
                    if is_cancelled(remark):
                        continue
                    op = order_price_of(row)
                    try:
                        qty = int(float(row.get("数量")))
                    except Exception:
                        continue
                    if op is None:
                        continue
                    keys.add(fill_key((row.get("日期") or "").strip(), row.get("代码"),
                                      side, qty, round(op, 4)))
                    rows.append(row)
        except Exception:
            continue
    return keys, rows


# ---------------------------------------------------------------------------
# 节点账本
# ---------------------------------------------------------------------------
def load_nodes(path):
    data = load_json(path, None)
    if isinstance(data, dict):
        return data
    return {}


def parse_ledger_md(path):
    """从 A 线网格节点账本.md 解析节点表（列序 节点价|节点持仓价|手数|卖价|标记）。"""
    out = {}
    if not path or not os.path.exists(path):
        return out
    code = None
    title_re = re.compile(r"^##\s*(A[123])（(\d{6})）")
    row_re = re.compile(r"^\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*(\d+)\s*\|")
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                m = title_re.match(line.strip())
                if m:
                    code = m.group(2)
                    out.setdefault(code, {"nodes": []})
                    continue
                if code is None:
                    continue
                m = row_re.match(line.strip())
                if m:
                    out[code]["nodes"].append({"node_price": float(m.group(1)),
                                               "cost_price": float(m.group(2)),
                                               "hands": int(m.group(3))})
    except Exception:
        return {}
    return out


def find_node_for_sell(nodes, code, sell_price):
    tick = tick_of(code)
    for n in nodes.get(code, {}).get("nodes", []):
        if round_tick(n["node_price"] * 1.02, tick) == round_tick(sell_price, tick):
            return float(n["node_price"])
    return None


def find_node_for_buy(nodes, code, buy_price):
    tick = tick_of(code)
    for n in nodes.get(code, {}).get("nodes", []):
        if round_tick(n["node_price"], tick) == round_tick(buy_price, tick):
            return float(n["node_price"])
    return None


# ---------------------------------------------------------------------------
# 快照
# ---------------------------------------------------------------------------
def latest_snapshot_path(snap_dir):
    if not os.path.isdir(snap_dir):
        return None
    files = sorted(f for f in os.listdir(snap_dir)
                   if f.startswith("fillwatch_") and f.endswith(".json"))
    if not files:
        return None
    return os.path.join(snap_dir, files[-1])


def snapshot_age_secs(snap):
    try:
        ts = datetime.strptime(snap["timestamp"], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None
    return (now().replace(tzinfo=None) - ts).total_seconds()


# ---------------------------------------------------------------------------
# 补挂计算（§4.5）
# ---------------------------------------------------------------------------
def compute_order(fill, nodes, snap, prev_close_map):
    """返回 (order_dict 或 None, skip_reason 或 None)。"""
    code = str(fill.get("code"))
    side = fill.get("side")
    try:
        price = float(fill.get("price"))
        qty = int(fill.get("qty"))
    except Exception:
        return None, "bad_fill_fields"
    tick = tick_of(code)
    fill_time = fill.get("time") or now_str()

    if side == "卖出":
        node = find_node_for_sell(nodes, code, price)
        if node is None:
            return None, "node_not_found"
        target_side = "买入"
        target_price = round_tick(node, tick)
    elif side == "买入":
        node = find_node_for_buy(nodes, code, price)
        if node is None:
            return None, "node_not_found"
        target_side = "卖出"
        target_price = round_tick(node * 1.02, tick)
    else:
        return None, "bad_side"

    amount = r2(target_price * qty)
    if amount < MIN_AMOUNT:
        return None, "small_amount"
    if round_tick(target_price, tick) in BANNED_PRICE.get(code, set()):
        return None, "banned_cluster_price"
    if target_side == "卖出":
        pc = prev_close_map.get(code)
        if pc is not None:
            limit_up = round_tick(pc * 1.10, tick)
            if round_tick(target_price, tick) > limit_up:
                return None, "above_limit_up"
        dup_reason = "duplicate_pending_sell"
    else:
        dup_reason = "duplicate_pending_buy"
    for o in (snap or {}).get("orders", []):
        if o.get("code") == code and o.get("side") == target_side \
                and o.get("status") == "未成交" \
                and round_tick(o.get("price", 0), tick) == round_tick(target_price, tick):
            return None, dup_reason

    try:
        t = datetime.strptime(fill_time, "%Y-%m-%d %H:%M:%S")
        tslug = t.strftime("%Y%m%d%H%M%S")
        date_slug = t.strftime("%Y%m%d")
    except Exception:
        tslug = now().strftime("%Y%m%d%H%M%S")
        date_slug = now().strftime("%Y%m%d")

    oid = "FW-%s-%s-%s-%s-%s" % (date_slug, code,
                                 "buy" if target_side == "买入" else "sell",
                                 price_slug(target_price), tslug)
    order = {"order_id": oid, "code": code, "side": target_side,
             "price": target_price, "qty": qty,
             "line": "A", "prev_close": prev_close_map.get(code),
             "note": "fillwatch 补挂（%s成交 %s@%s → 补%s %s 股 @%s，节点 %s）"
                     % (side, code, price, target_side, qty, target_price, node)}
    return order, None


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def parse_prev_close(text):
    out = {}
    if not text:
        return out
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            k, v = part.split(":", 1)
        elif "=" in part:
            k, v = part.split("=", 1)
        else:
            continue
        try:
            out[k.strip()] = float(v)
        except Exception:
            continue
    return out


def compare(base, args):
    snap_path = args.snapshot or latest_snapshot_path(
        os.path.join(base, "snapshots"))
    trade_log = args.trade_log or os.path.join(base, "virtual_trade_log.csv")
    bookings = args.bookings or os.path.join(base, "huawei_bookings.csv")
    nodes_path = os.path.join(base, "nodes.json")
    state_path = args.state or os.path.join(base, "fillwatch_rehang_state.json")
    queue_dir = args.queue_dir or os.path.join(base, "order_queue")

    out = {"date": args.date or today_str(), "checked_at": now_str(),
           "mode": args.mode, "verdict": "silent", "reason": "no_new_fills",
           "snapshot_time": None, "snapshot_age_secs": None,
           "new_fills": [], "new_bookings": [], "booked": [], "would_book": [],
           "computed_orders": [], "skipped": [], "emitted_order_ids": []}

    snap = load_json(snap_path, None) if snap_path else None
    if not isinstance(snap, dict):
        out["reason"] = "no_snapshot"
        return out
    out["snapshot_time"] = snap.get("timestamp")
    age = snapshot_age_secs(snap)
    out["snapshot_age_secs"] = int(age) if age is not None else None
    if snap.get("status") not in (None, "ok"):
        out["reason"] = "snapshot_%s" % snap.get("status")
        return out
    if age is None or age > STALE_SECS:
        out["reason"] = "stale_snapshot"
        return out

    # 已入账成交（trade_log + bookings 两份，§4.4）
    booked_keys, _ = read_booked([trade_log, bookings])
    # 已下发过的成交（live state 去重，§4.5）
    state = load_json(state_path, {}) if args.mode == "live" else {}
    emitted = state.get("emitted", {}) if isinstance(state, dict) else {}

    snap_date = (snap.get("timestamp") or "")[:10] or (args.date or today_str())
    fills = [f for f in (snap.get("fills_today") or [])
             if str(f.get("code")) in A_CODES and f.get("status", "已成交") == "已成交"]

    new_fills = []
    for f in fills:
        try:
            qty = int(f.get("qty"))
            price = float(f.get("price"))
        except Exception:
            continue
        key = fill_key(snap_date, f.get("code"), f.get("side"), qty, round(price, 4))
        if key in booked_keys:
            continue
        if state_key(f) in emitted:
            continue
        new_fills.append(f)

    out["new_fills"] = new_fills
    if not new_fills:
        out["reason"] = "no_new_fills"
        return out

    # 补挂计算
    nodes = load_nodes(nodes_path)
    if not nodes and args.ledger:
        nodes = parse_ledger_md(args.ledger)
    prev_close_map = parse_prev_close(args.prev_close)
    if not prev_close_map:
        quotes = load_json(os.path.join(base, "quotes.json"), {})
        prev_close_map = {c: v.get("prev_close") for c, v in quotes.items()
                          if isinstance(v, dict) and v.get("prev_close") is not None}

    computed = []
    pairs = []  # (成交, 补挂单) 一一对应；跳过的成交不配单、每轮重算
    skipped = []
    for f in new_fills:
        order, reason = compute_order(f, nodes, snap, prev_close_map)
        if order is None:
            skipped.append({"fill": f, "reason": reason})
        else:
            computed.append(order)
            pairs.append((f, order))
    out["computed_orders"] = computed
    out["skipped"] = skipped

    if args.mode == "live":
        emitted_ids = emit_orders(queue_dir, pairs, state, state_path)
        out["emitted_order_ids"] = emitted_ids
        out["verdict"] = "emitted" if emitted_ids else "blocked"
        if emitted_ids:
            out["reason"] = "live_emitted_%d" % len(emitted_ids)
        else:
            out["reason"] = "no_orders_computed" if not computed \
                else "all_orders_already_emitted"
    else:
        out["verdict"] = "computed"
        out["reason"] = "computed_compare_only"
    return out


def emit_orders(queue_dir, pairs, state, state_path):
    """live：成交以 fill key（代码|方向|委托价|数量|委托时间）记入 state（§4.5）。
    订单原子写入 pending（tmp+rename），写后复核存在再记 state；已下发的不重复算。"""
    pending_dir = os.path.join(queue_dir, "pending")
    os.makedirs(pending_dir, exist_ok=True)
    emitted_ids = []
    emitted = state.setdefault("emitted", {})
    # pairs = [(成交, 补挂单), …] 一一对应（compute_order 对每笔成交至多算一单）
    for fill, o in pairs:
        kstr = state_key(fill)
        if kstr in emitted:
            continue
        dest = os.path.join(pending_dir, "%s.json" % o["order_id"])
        if not os.path.exists(dest):
            tmp = dest + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(o, f, ensure_ascii=False, indent=2)
            os.replace(tmp, dest)
        if os.path.exists(dest):
            emitted_ids.append(o["order_id"])
            emitted[kstr] = {"emitted_at": now_str(), "order_id": o["order_id"]}
    if emitted_ids:
        save_json(state_path, state)
    return emitted_ids


def append_log(args, out):
    if not args.log:
        return
    try:
        os.makedirs(os.path.dirname(args.log) or ".", exist_ok=True)
        with open(args.log, "a", encoding="utf-8") as f:
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv):
    ap = argparse.ArgumentParser(description="fillwatch 补挂计算（虚拟环境搭建版）")
    ap.add_argument("--base", default=REAL_BASE, help="数据根目录（默认 /root/monitor/）")
    ap.add_argument("--mode", default="compare", choices=["compare", "live"])
    ap.add_argument("--date", default=None)
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--trade-log", dest="trade_log", default=None)
    ap.add_argument("--bookings", default=None)
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--state", default=None)
    ap.add_argument("--queue-dir", dest="queue_dir", default=None)
    ap.add_argument("--log", default=None)
    ap.add_argument("--out-dir", dest="out_dir", default=None)
    ap.add_argument("--prev-close", dest="prev_close", default=None)
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    base = os.path.abspath(args.base)
    try:
        out = compare(base, args)
    except Exception as e:
        out = {"date": args.date or today_str(), "checked_at": now_str(),
               "mode": args.mode, "verdict": "error", "reason": "exception: %r" % e,
               "new_fills": [], "computed_orders": [], "skipped": []}
        append_log(args, out)
        print(json.dumps(out, ensure_ascii=False))
        return 1
    append_log(args, out)
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
