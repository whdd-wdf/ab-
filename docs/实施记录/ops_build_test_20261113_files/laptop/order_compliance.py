#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""order_compliance.py — 订单合规校验（操作侧，虚拟环境搭建版）

依据：docs/操作与管控接口规范.md §1.2（订单 JSON 字段）、§1.5（合规清单）。
数据口径以 virtual/virtual_ops.py 的 run_compliance() 为准（nodes.json / virtual_quota.json /
quotes.json / snapshots / virtual_trade_log.csv 字段名逐字一致）。

用法：
  python3 order_compliance.py --base <目录> --order '<订单JSON>'
  不传 --order 时从 stdin 读 JSON；不传 --base 时用真实路径 /root/monitor/。

输出（stdout 只有一个 JSON）：
  {"passed": true/false, "verdict": "pass"/"reject", "reasons": [...],
   "checks": [{"item","pass","detail"}, ...]}
通过 exit 0，拒绝 exit 1。

LLM 合理性复核环节在虚拟环境不存在：一律跳过并注明，不拒绝、不伪造复核结果（非 fail-open）。
仅标准库。
"""

import argparse
import json
import os
import re
import sys
from decimal import Decimal, ROUND_HALF_UP

REAL_BASE = "/root/monitor"

# §1.5 常量（与 virtual/virtual_ops.py 同值）
MIN_AMOUNT = 5000.0
B_SINGLE_LIMIT = 50000.0
B_MAX_COUNT = 3
PRICE_DEV_TOL = 0.01
BANNED_PRICE = {"510300": {4.316, 4.324, 4.325}, "601088": {52.06}}
TICK = {"510300": 0.001, "513650": 0.001}
A_CODES = {"510300": "A1", "601088": "A2", "513650": "A3"}
MARK_OF_LINE = {"A1": "【A1】", "A2": "【A2】", "A3": "【A3】", "B": "【B线】"}


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def tick_of(code):
    return TICK.get(code, 0.01)


def round_tick(price, tick):
    """按 tick 四舍五入（Decimal，避免浮点误差）。"""
    q = Decimal(str(tick))
    return float(Decimal(str(price)).quantize(q, rounding=ROUND_HALF_UP))


def r2(x):
    return round(float(x) + 1e-9, 2)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def line_of_order(order):
    """订单归属线：line 字段优先，否则按代码定（A 线三码 -> A，余者 B）。"""
    line = order.get("line")
    if line in ("A", "B"):
        return line
    return "A" if order.get("code") in A_CODES else "B"


def latest_snapshot(snap_dir):
    if not os.path.isdir(snap_dir):
        return None
    files = sorted(f for f in os.listdir(snap_dir)
                   if f.startswith("fillwatch_") and f.endswith(".json"))
    if not files:
        return None
    return load_json(os.path.join(snap_dir, files[-1]), None)


def find_node_for_sell(nodes, code, sell_price):
    """卖价反推节点：满足 round_tick(节点×1.02) == 卖价 的账本节点。"""
    tick = tick_of(code)
    for n in nodes.get(code, {}).get("nodes", []):
        if round_tick(n["node_price"] * 1.02, tick) == round_tick(sell_price, tick):
            return n["node_price"]
    return None


# ---------------------------------------------------------------------------
# 合规校验（§1.5，逐项 checks + reasons）
# ---------------------------------------------------------------------------
def run_compliance(base, order):
    checks = []
    reasons = []

    def check(item, passed, detail):
        checks.append({"item": item, "pass": bool(passed), "detail": detail})
        if not passed:
            reasons.append("%s：%s" % (item, detail))
        return passed

    # 必填字段（§1.2）
    missing = [f for f in ("order_id", "code", "side", "price", "qty") if f not in order]
    if missing:
        check("必填字段", False, "缺必填字段：%s（必填 order_id/code/side/price/qty）" % ",".join(missing))
        return False, checks, reasons
    if order.get("side") not in ("买入", "卖出"):
        check("方向合法", False, "side 须恰为 买入 或 卖出，实为：%s" % order.get("side"))
        return False, checks, reasons
    try:
        price = float(order["price"])
        qty = int(order["qty"])
    except Exception:
        check("字段类型", False, "price 须为数字、qty 须为整数")
        return False, checks, reasons
    if price <= 0 or qty <= 0:
        check("字段类型", False, "price 与 qty 须 > 0")
        return False, checks, reasons
    check("必填字段", True, "order_id/code/side/price/qty 齐全")

    code = str(order["code"])
    side = order["side"]
    amount = r2(price * qty)
    line = line_of_order(order)
    tick = tick_of(code)

    quota = load_json(os.path.join(base, "virtual_quota.json"), {})
    quotes = load_json(os.path.join(base, "quotes.json"), {})
    nodes = load_json(os.path.join(base, "nodes.json"), {})

    prev_close = order.get("prev_close")
    if prev_close is None:
        prev_close = quotes.get(code, {}).get("prev_close")
    try:
        prev_close = float(prev_close) if prev_close is not None else None
    except Exception:
        prev_close = None

    if line == "A":
        if code not in A_CODES:
            check("A线代码", False, "A 线代码须为 510300/601088/513650，实为：%s" % code)
            return False, checks, reasons
        qk = A_CODES[code]
        q = quota.get(qk, {})
        if side == "买入":
            node_prices = [n["node_price"] for n in nodes.get(code, {}).get("nodes", [])]
            if not node_prices:
                check("买价=节点价", False, "节点账本取不到 %s 节点，拒绝" % code)
            else:
                is_node = round_tick(price, tick) in [round_tick(p, tick) for p in node_prices]
                limit_down = round_tick(prev_close * 0.90, tick) if prev_close else None
                below_down_node = (limit_down is not None
                                   and any(p < limit_down for p in node_prices))
                ok_price = is_node or (limit_down is not None
                                       and round_tick(price, tick) == limit_down
                                       and below_down_node)
                check("买价=节点价", ok_price,
                      "买价 %s，%s" % (price, "是节点价" if is_node else
                                     ("跌停价例外（有节点低于跌停）" if ok_price else "不是节点价")))
            ga = q.get("grid_available")
            if ga is None:
                check("买入<=grid_available", False, "quota 取不到，拒绝")
            else:
                check("买入<=grid_available", amount <= ga + 1e-9,
                      "金额 %s，%s grid_available %s" % (amount, qk, ga))
            check("单笔>=5000", amount >= MIN_AMOUNT, "金额 %s" % amount)
        else:  # A 线卖出
            node = find_node_for_sell(nodes, code, price)
            check("卖价=节点价×1.02", node is not None,
                  "卖价 %s，%s" % (price, "反推节点 %s" % node if node is not None else "反推不到节点"))
            holdings = q.get("holdings", {}).get(code, {})
            sellable = holdings.get("sellable", 0)
            check("卖出<=可卖量", qty <= sellable,
                  "卖 %s 股，%s 可卖 %s 股" % (qty, qk, sellable))
            if prev_close is None:
                check("卖价<=涨停", True, "跳过（前收取不到，见 §1.5）")
            else:
                limit_up = round_tick(prev_close * 1.10, tick)
                check("卖价<=涨停", round_tick(price, tick) <= limit_up,
                      "卖价 %s，涨停 %s（前收 %s）" % (price, limit_up, prev_close))
            snap = latest_snapshot(os.path.join(base, "snapshots"))
            if snap is None:
                check("卖价不重复在挂", True, "跳过（无快照，见 §1.5）")
            else:
                dup = any(o.get("code") == code and o.get("side") == "卖出"
                          and o.get("status") == "未成交"
                          and round_tick(o.get("price", 0), tick) == round_tick(price, tick)
                          for o in snap.get("pending", []))
                check("卖价不重复在挂", not dup,
                      "在挂卖价%s重复" % ("有" if dup else "无"))
            banned = BANNED_PRICE.get(code, set())
            check("非禁挂集群价", round_tick(price, tick) not in banned,
                  "卖价 %s，%s禁挂集群价 %s" % (price, "是" if round_tick(price, tick) in banned else "不是",
                                              sorted(banned)))
            check("单笔>=5000", amount >= MIN_AMOUNT, "金额 %s" % amount)
    else:  # B 线
        q = quota.get("B", {})
        if side == "买入":
            if prev_close is None:
                check("涨幅<=5%", True, "跳过（前收取不到，见 §1.5）")
            else:
                rise = price / prev_close - 1
                check("涨幅<=5%", rise <= 0.05 + 1e-9,
                      "涨幅 %.2f%%（买价 %s，前收 %s）" % (rise * 100, price, prev_close))
            cur = quotes.get(code, {}).get("price")
            if cur is None:
                check("买价≈现价", True, "跳过（当前价取不到，见 §1.5）")
            else:
                cur = float(cur)
                dev = abs(price - cur) / cur
                check("买价≈现价", dev <= PRICE_DEV_TOL + 1e-9,
                      "买价 %s，现价 %s，偏差 %.2f%%" % (price, cur, dev * 100))
            if order.get("limit_price") is not None and order.get("limit_price") != "":
                try:
                    lp = float(order["limit_price"])
                    check("买价<=P4限价", price <= lp + 1e-9,
                          "买价 %s，P4 限价 %s" % (price, lp))
                except Exception:
                    check("买价<=P4限价", False, "limit_price 非数字：%s" % order.get("limit_price"))
            else:
                check("买价<=P4限价", True, "跳过（未传 limit_price，见 §1.5）")
            check("单只<=5万", amount <= B_SINGLE_LIMIT + 1e-9, "金额 %s" % amount)
            av = q.get("available")
            if av is None:
                check("买入<=B可用", False, "quota 取不到，拒绝")
            else:
                check("买入<=B可用", amount <= av + 1e-9, "金额 %s，B 可用 %s" % (amount, av))
            holdings = q.get("holdings", {})
            is_new = code not in holdings or holdings[code].get("qty", 0) <= 0
            if is_new:
                held_n = len([c for c, h in holdings.items() if h.get("qty", 0) > 0])
                check("B线<=3只", held_n < B_MAX_COUNT,
                      "新开仓，当前持仓 %s 只" % held_n)
            else:
                check("B线<=3只", True, "加仓既有持仓，不占新名额")
            check("单笔>=5000", amount >= MIN_AMOUNT, "金额 %s" % amount)
        else:  # B 线卖出：唯一校验（§1.5）
            holdings = q.get("holdings", {})
            held = holdings.get(code, {}).get("qty", 0)
            check("卖出<=持仓", qty <= held, "卖 %s 股，持仓 %s 股" % (qty, held))

    # 虚拟环境无 LLM 合理性复核：跳过并注明，不拒绝、不伪造（非 fail-open）
    checks.append({"item": "LLM 复核", "pass": True, "skipped": True,
                   "detail": "跳过（虚拟环境无 LLM 复核环节，不拒绝）"})
    return (len(reasons) == 0), checks, reasons


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv):
    ap = argparse.ArgumentParser(description="订单合规校验（虚拟环境搭建版）")
    ap.add_argument("--base", default=REAL_BASE, help="数据根目录（默认 /root/monitor/）")
    ap.add_argument("--order", default=None, help="订单 JSON 字符串；不传则从 stdin 读")
    return ap.parse_args(argv)


def read_order(raw):
    text = raw
    if text is None:
        text = sys.stdin.read()
    text = (text or "").strip()
    if not text:
        return None, "未提供订单 JSON（--order 或 stdin）"
    try:
        order = json.loads(text)
    except Exception as e:
        return None, "订单 JSON 解析失败：%s" % e
    if not isinstance(order, dict):
        return None, "订单 JSON 须为对象（见 §1.2）"
    return order, None


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    base = os.path.abspath(args.base)
    order, err = read_order(args.order)
    if order is None:
        out = {"passed": False, "verdict": "reject", "reasons": [err], "checks": []}
        print(json.dumps(out, ensure_ascii=False))
        return 1
    passed, checks, reasons = run_compliance(base, order)
    out = {"passed": passed, "verdict": "pass" if passed else "reject",
           "order_id": order.get("order_id"), "code": order.get("code"),
           "side": order.get("side"), "line": line_of_order(order),
           "reasons": reasons, "checks": checks, "virtual": True}
    print(json.dumps(out, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
