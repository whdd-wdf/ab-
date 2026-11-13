#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
虚拟操作侧程序 virtual_ops.py（模拟操作侧，只读真实系统）

模拟对象（按 ~/workspace/ab-/docs/操作与管控接口规范.md）：
  §1  订单队列 virtual/order_queue/{pending,done,failed}/（订单 JSON 格式与 §1.2 一致）
  §1.5 合规校验（逐项 checks + reasons，reject 进 failed）
  §2  虚拟 trade_log：virtual/virtual_trade_log.csv（9 列，与 §2.2 同格式）
  §4  fillwatch 快照：virtual/snapshots/fillwatch_YYYYMMDD_HHMM.json（§4.2 格式）
  §5  门控标志：virtual/.trading_day（mtime 日期 = 当日即开门）
  §6  节点账本 JSON：virtual/nodes.json（从真实 A 线节点账本抄节点价与股数）
  §6.2 虚拟 quota：virtual/virtual_quota.json（A1/A2/A3/B 四仓）
  §7  B 线候选：虚拟行情含 8 只 B 线候选码（真实 A 股代码，种子随机游走价）

虚拟成交不产生真实资金、不登录叩富网、不连华为 VPS、不碰真实文件。
全部虚拟状态都在本文件所在 virtual/ 目录内，与真实文件不同名不同路径。

用法（北京时间）：
  python3 virtual_ops.py init                    # 初始化 / 重置虚拟状态
  python3 virtual_ops.py quote <代码>            # 查虚拟行情
  python3 virtual_ops.py check <代码> [买价]  # 算数：涨幅/P4/5万量/偏差一次算好（AI 只读数字、不自己算）
  python3 virtual_ops.py submit <订单JSON文件>   # 写 pending
  python3 virtual_ops.py run                     # 执行器处理一轮 pending
  python3 virtual_ops.py snapshot                # 生成 fillwatch 快照
  python3 virtual_ops.py quota                   # 打印虚拟 quota
  python3 virtual_ops.py log [N]                 # 打印虚拟 trade_log 尾部 N 行（默认 10）

每个命令输出 JSON 或清晰文本，成功 exit 0，失败 exit 1。
仅标准库，无第三方依赖。
"""

import csv
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Shanghai")
except Exception:  # pragma: no cover - 无 tzdata 时回落固定 +08:00
    TZ = timezone(timedelta(hours=8))

BASE = os.path.dirname(os.path.abspath(__file__))
QUEUE_DIR = os.path.join(BASE, "order_queue")
PENDING_DIR = os.path.join(QUEUE_DIR, "pending")
DONE_DIR = os.path.join(QUEUE_DIR, "done")
FAILED_DIR = os.path.join(QUEUE_DIR, "failed")
SNAP_DIR = os.path.join(BASE, "snapshots")
TRADE_LOG = os.path.join(BASE, "virtual_trade_log.csv")
QUOTA_FILE = os.path.join(BASE, "virtual_quota.json")
NODES_FILE = os.path.join(BASE, "nodes.json")
QUOTES_FILE = os.path.join(BASE, "quotes.json")
STATE_FILE = os.path.join(BASE, "state.json")
GATE_FLAG = os.path.join(BASE, ".trading_day")

TRADE_LOG_HEADER = ["日期", "代码", "名称", "方向", "价格", "数量", "金额", "盈亏", "备注"]
MIN_AMOUNT = 5000.0
PRICE_DEV_TOL = 0.01  # §1.5：B 线买入买价相对现价的允许偏差（1%）
B_SINGLE_LIMIT = 50000.0
B_MAX_COUNT = 3
STALE_SECS = 300  # §4.3：快照 timestamp 距现在 > 300 秒即 stale
GATE_OPEN_MIN = 7 * 60 + 30   # 07:30
GATE_CLOSE_MIN = 17 * 60 + 5  # 17:05

# §1.5 禁挂集群价
BANNED_PRICE = {"510300": {4.316, 4.324, 4.325}, "601088": {52.06}}
# tick：510300/513650 为 0.001，601088 与全部 B 线股票为 0.01
TICK = {"510300": 0.001, "513650": 0.001}
A_CODES = {"510300": "A1", "601088": "A2", "513650": "A3"}

NAMES = {
    "510300": "300ETF", "601088": "中国神华", "513650": "标普ETF",
    "600176": "中国巨石", "002475": "立讯精密", "000596": "古井贡酒",
    "600919": "江苏银行", "600018": "上港集团", "603198": "迎驾贡酒",
    "000001": "平安银行", "600000": "浦发银行",
}
LINE_OF_CODE = {"510300": "A1", "601088": "A2", "513650": "A3"}
MARK_OF_LINE = {"A1": "【A1】", "A2": "【A2】", "A3": "【A3】", "B": "【B线】"}

# ---------------------------------------------------------------------------
# 节点账本（从真实 A 线网格节点账本.md 抄：节点价 -> 手数）
# A1 39 档（锚 4.122）、A2 39 档（锚 51.59）、A3 47 档（锚 1.51）。
# A2 按任务给定的虚拟初始值持 1200 股（12 手），故最高两档 59.26/60.45 置 0，
# 使节点股数之和 = 持仓股数（真实账本当时为 1400 股/14 手，节点价本身未动）。
# 节点持仓价全档 = 平台买入成本价（A1 4.200、A2 49.20、A3 1.985）。
# ---------------------------------------------------------------------------
NODES_SEED = {
    "510300": {
        "cost": 4.200, "nodes": [
            (3.004, 0), (3.064, 0), (3.125, 0), (3.187, 0), (3.251, 0),
            (3.316, 0), (3.382, 0), (3.450, 0), (3.519, 0), (3.589, 0),
            (3.661, 0), (3.733, 0), (3.808, 0), (3.884, 0), (3.962, 0),
            (4.041, 0), (4.122, 18), (4.204, 18), (4.288, 17), (4.374, 17),
            (4.461, 16), (4.550, 16), (4.641, 16), (4.734, 15), (4.829, 15),
            (4.926, 14), (5.025, 14), (5.126, 14), (5.229, 13), (5.334, 13),
            (5.441, 12), (5.550, 12), (5.661, 11), (5.774, 11), (5.889, 11),
            (6.007, 10), (6.127, 9), (6.250, 8), (6.375, 8),
        ],
    },
    "601088": {
        "cost": 49.20, "nodes": [
            (28.48, 0), (29.05, 0), (29.63, 0), (30.22, 0), (30.83, 0),
            (31.45, 0), (32.07, 0), (32.72, 0), (33.37, 0), (34.04, 0),
            (34.72, 0), (35.41, 0), (36.12, 0), (36.84, 0), (37.58, 0),
            (38.33, 0), (39.10, 0), (39.88, 0), (40.68, 0), (41.49, 0),
            (42.32, 0), (43.17, 0), (44.03, 0), (44.91, 0), (45.81, 0),
            (46.73, 0), (47.66, 0), (48.61, 2), (49.59, 2), (50.58, 1),
            (51.59, 1), (52.62, 1), (53.67, 1), (54.74, 1), (55.84, 1),
            (56.96, 1), (58.10, 1), (59.26, 0), (60.45, 0),
        ],
    },
    "513650": {
        "cost": 1.985, "nodes": [
            (0.977, 0), (0.997, 0), (1.017, 0), (1.037, 0), (1.058, 0),
            (1.079, 0), (1.101, 0), (1.123, 0), (1.145, 0), (1.168, 0),
            (1.191, 0), (1.215, 0), (1.239, 0), (1.264, 0), (1.289, 0),
            (1.315, 0), (1.341, 0), (1.368, 0), (1.395, 0), (1.423, 0),
            (1.451, 0), (1.480, 0), (1.510, 0), (1.540, 0), (1.571, 0),
            (1.602, 0), (1.634, 0), (1.667, 0), (1.700, 0), (1.734, 0),
            (1.769, 0), (1.804, 0), (1.840, 0), (1.877, 0), (1.915, 0),
            (1.953, 0), (1.992, 30), (2.032, 30), (2.073, 30), (2.114, 30),
            (2.156, 30), (2.199, 30), (2.243, 30), (2.288, 30), (2.334, 30),
            (2.381, 30), (2.429, 30),
        ],
    },
}

# 虚拟 quota 初始值（任务给定的真实系统参考值，仅作初始值）
QUOTA_SEED = {
    "A1": {"code": "510300", "quota": 166400.49, "deployed": 129384.11,
           "pnl": -266.18, "available": 37016.38, "grid_quota": 141440.42,
           "grid_available": 12056.30,
           "holdings": {"510300": {"qty": 30800, "sellable": 22200, "avg_cost": 4.2008}}},
    "A2": {"code": "601088", "quota": 167633.38, "deployed": 59046.64,
           "pnl": 966.71, "available": 108586.74, "grid_quota": 142488.37,
           "grid_available": 83441.73,
           "holdings": {"601088": {"qty": 1200, "sellable": 700, "avg_cost": 49.2055}}},
    "A3": {"code": "513650", "quota": 166666.67, "deployed": 65522.04,
           "pnl": 0.0, "available": 101144.63, "grid_quota": 141666.67,
           "grid_available": 76144.63,
           "holdings": {"513650": {"qty": 33000, "sellable": 33000, "avg_cost": 1.9855}}},
    "B": {"code": None, "quota": 490341.72, "deployed": 0.0,
          "pnl": -9658.28, "available": 490341.72, "grid_quota": 416790.46,
          "grid_available": 416790.46, "holdings": {}},
}

# 虚拟行情种子：前收（真实价附近）；当前价由 _gen_quotes() 种子随机游走生成
QUOTES_SEED = {
    "510300": {"name": "300ETF", "prev_close": 4.13},
    "601088": {"name": "中国神华", "prev_close": 49.10},
    "513650": {"name": "标普ETF", "prev_close": 1.99},
    "600176": {"name": "中国巨石", "prev_close": 10.52},
    "002475": {"name": "立讯精密", "prev_close": 38.20},
    "000596": {"name": "古井贡酒", "prev_close": 86.10},
    "600919": {"name": "江苏银行", "prev_close": 12.80},
    "600018": {"name": "上港集团", "prev_close": 6.52},
    "603198": {"name": "迎驾贡酒", "prev_close": 43.60},
    "000001": {"name": "平安银行", "prev_close": 11.48},
    "600000": {"name": "浦发银行", "prev_close": 10.86},
}


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
    """按 tick 四舍五入（Decimal，避免浮点误差）。"""
    from decimal import Decimal, ROUND_HALF_UP
    q = Decimal(str(tick))
    return float(Decimal(str(price)).quantize(q, rounding=ROUND_HALF_UP))


def r2(x):
    return round(float(x) + 1e-9, 2)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.rename(tmp, path)


def fail(msg, code=1):
    print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def line_of_order(order):
    """订单归属线：line 字段优先，否则按代码定（A 线三码 -> A，余者 B）。"""
    line = order.get("line")
    if line in ("A", "B"):
        return line
    return "A" if order.get("code") in A_CODES else "B"


def quota_key_of_order(order):
    if line_of_order(order) == "B":
        return "B"
    return A_CODES[order["code"]]


# ---------------------------------------------------------------------------
# init：初始化 / 重置虚拟状态
# ---------------------------------------------------------------------------
def _gen_quotes():
    """种子随机游走：以前收为起点走 12 步（每步 ±0.4%），累计钳制在 ±3% 内，
    tick 取整。当日种子固定，同一天内 init 结果可复现。"""
    seed = int(now().strftime("%Y%m%d"))
    rng = random.Random(seed)
    out = {}
    for code, q in QUOTES_SEED.items():
        prev = q["prev_close"]
        price = prev
        for _ in range(12):
            price *= 1.0 + rng.uniform(-0.004, 0.004)
            price = min(max(price, prev * 0.97), prev * 1.03)
        price = round_tick(price, tick_of(code))
        out[code] = {"name": q["name"], "prev_close": prev, "price": price,
                     "change_pct": r2(price / prev - 1)}
    return out


def cmd_init(_args):
    for d in (PENDING_DIR, DONE_DIR, FAILED_DIR, SNAP_DIR):
        os.makedirs(d, exist_ok=True)
        for fn in os.listdir(d):
            p = os.path.join(d, fn)
            if os.path.isfile(p):
                os.remove(p)
    # 节点账本 JSON
    nodes = {}
    for code, v in NODES_SEED.items():
        nodes[code] = {
            "line": LINE_OF_CODE[code], "name": NAMES[code],
            "cost": v["cost"],  # 节点持仓价全档 = 平台买入成本价
            "nodes": [{"node_price": p, "cost_price": v["cost"],
                       "hands": h, "sell_price": (round_tick(p * 1.02, tick_of(code))
                                                  if h > 0 else None)}
                      for p, h in v["nodes"]],
        }
    save_json(NODES_FILE, nodes)
    # 虚拟 quota（任务给定初始值 verbatim）
    save_json(QUOTA_FILE, json.loads(json.dumps(QUOTA_SEED)))
    # 虚拟行情
    save_json(QUOTES_FILE, _gen_quotes())
    # 状态（订单簿）
    save_json(STATE_FILE, {"seed": int(now().strftime("%Y%m%d")), "step": 0, "orders": []})
    # 虚拟 trade_log（仅表头）
    with open(TRADE_LOG, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(TRADE_LOG_HEADER)
    # 门控标志：空文件，mtime 日期 = 当日即开门（§5.1）
    open(GATE_FLAG, "a").close()
    os.utime(GATE_FLAG, None)
    print(json.dumps({"ok": True, "action": "init", "date": today_str(),
                      "gate": "open", "virtual": True,
                      "note": "虚拟状态已重置；未碰真实系统"}, ensure_ascii=False))
    return 0


def _require_init():
    for p in (QUOTA_FILE, NODES_FILE, QUOTES_FILE, STATE_FILE):
        if not os.path.exists(p):
            fail("虚拟状态未初始化，请先跑：python3 virtual_ops.py init")


# ---------------------------------------------------------------------------
# quote：查虚拟行情
# ---------------------------------------------------------------------------
def cmd_quote(args):
    if len(args) != 1:
        fail("用法：python3 virtual_ops.py quote <代码>")
    _require_init()
    code = args[0]
    quotes = load_json(QUOTES_FILE, {})
    if code not in quotes:
        fail("未知代码：%s（虚拟行情覆盖：%s）" % (code, ",".join(sorted(quotes))))
    q = quotes[code]
    print(json.dumps({"ok": True, "code": code, "name": q["name"],
                      "price": q["price"], "prev_close": q["prev_close"],
                      "change_pct": q["change_pct"], "virtual": True},
                     ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# check：算数接口（只读、不下单；AI 只读输出的数字、不自己算）
# 用法：python3 virtual_ops.py check <代码> [买价]（买价不传则取当前价）
# ---------------------------------------------------------------------------
def cmd_check(args):
    if len(args) not in (1, 2):
        fail("用法：python3 virtual_ops.py check <代码> [买价]")
    _require_init()
    code = args[0]
    quotes = load_json(QUOTES_FILE, {})
    if code not in quotes:
        fail("未知代码：%s（虚拟行情覆盖：%s）" % (code, ",".join(sorted(quotes))))
    q = quotes[code]
    prev_close = q["prev_close"]
    price = q["price"]
    if len(args) == 2:
        try:
            buy_price = float(args[1])
        except Exception:
            fail("买价须为数字，实为：%s" % args[1])
        if buy_price <= 0:
            fail("买价须 > 0")
    else:
        buy_price = price
    change = r2(buy_price / prev_close - 1)
    deviation = r2(buy_price / price - 1)
    p4_limit = round(prev_close * 1.03, 2)
    qty_50k = int(50000 // (buy_price * 100)) * 100
    amount_50k = r2(buy_price * qty_50k)
    print(json.dumps({"ok": True, "code": code, "name": q["name"],
                      "prev_close": prev_close, "price": price,
                      "buy_price": buy_price, "change_pct": change,
                      "deviation_pct": deviation, "p4_limit": p4_limit,
                      "qty_50k": qty_50k, "amount_50k": amount_50k,
                      "gates": {"rise_ok": buy_price / prev_close - 1 <= 0.05 + 1e-9,
                                "p4_ok": buy_price <= p4_limit + 1e-9,
                                "deviation_ok": abs(buy_price / price - 1) <= PRICE_DEV_TOL + 1e-9,
                                "amount_ok": MIN_AMOUNT <= amount_50k <= B_SINGLE_LIMIT + 1e-9},
                      "virtual": True}, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# submit：写 pending
# ---------------------------------------------------------------------------
def cmd_submit(args):
    if len(args) != 1:
        fail("用法：python3 virtual_ops.py submit <订单JSON文件>")
    _require_init()
    path = args[0]
    if not os.path.exists(path):
        fail("订单文件不存在：%s" % path)
    with open(path, "r", encoding="utf-8") as f:
        try:
            order = json.load(f)
        except Exception as e:
            fail("订单 JSON 解析失败：%s" % e)
    for field in ("order_id", "code", "side", "price", "qty"):
        if field not in order:
            fail("订单缺必填字段：%s（必填 order_id/code/side/price/qty，见接口规范 §1.2）" % field)
    if order["side"] not in ("买入", "卖出"):
        fail("side 须恰为 买入 或 卖出，实为：%s" % order["side"])
    if not isinstance(order["qty"], int) or order["qty"] <= 0:
        fail("qty 须为正整数，实为：%s" % order["qty"])
    try:
        order["price"] = float(order["price"])
    except Exception:
        fail("price 须为数字，实为：%s" % order["price"])
    if order["price"] <= 0:
        fail("price 须 > 0")
    oid = str(order["order_id"])
    for d in (PENDING_DIR, DONE_DIR, FAILED_DIR):
        if os.path.exists(os.path.join(d, oid + ".json")):
            fail("order_id 已存在（%s），不覆盖；重提请换 order_id（见接口规范附录 A4）" % oid)
    dest = os.path.join(PENDING_DIR, oid + ".json")
    save_json(dest, order)
    state = load_json(STATE_FILE, {"orders": []})
    state.setdefault("orders", []).append({
        "order_id": oid, "code": order["code"], "name": NAMES.get(order["code"], ""),
        "side": order["side"], "price": order["price"], "qty": order["qty"],
        "time": now_str(), "status": "未成交"})
    save_json(STATE_FILE, state)
    print(json.dumps({"ok": True, "action": "submit", "order_id": oid,
                      "status": "pending", "virtual": True}, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# 合规校验（接口规范 §1.5 逐项）
# ---------------------------------------------------------------------------
def _latest_snapshot():
    if not os.path.isdir(SNAP_DIR):
        return None
    files = sorted(f for f in os.listdir(SNAP_DIR)
                   if f.startswith("fillwatch_") and f.endswith(".json"))
    if not files:
        return None
    return load_json(os.path.join(SNAP_DIR, files[-1]), None)


def _find_node_for_sell(code, sell_price):
    """卖价反推节点：满足 round_tick(节点×1.02) == 卖价 的账本节点。"""
    nodes = load_json(NODES_FILE, {})
    tick = tick_of(code)
    for n in nodes.get(code, {}).get("nodes", []):
        if round_tick(n["node_price"] * 1.02, tick) == round_tick(sell_price, tick):
            return n["node_price"]
    return None


def run_compliance(order):
    """返回 (passed: bool, checks: list, reasons: list)。
    checks 每项：{"item": 名称, "pass": bool, "detail": 说明}。"""
    code = order["code"]
    side = order["side"]
    price = float(order["price"])
    qty = int(order["qty"])
    amount = r2(price * qty)
    checks = []
    reasons = []
    line = line_of_order(order)
    quota = load_json(QUOTA_FILE, {})
    quotes = load_json(QUOTES_FILE, {})
    nodes = load_json(NODES_FILE, {})

    def check(item, passed, detail):
        checks.append({"item": item, "pass": bool(passed), "detail": detail})
        if not passed:
            reasons.append("%s：%s" % (item, detail))
        return passed

    prev_close = order.get("prev_close")
    if prev_close is None:
        prev_close = quotes.get(code, {}).get("prev_close")
    tick = tick_of(code)

    if line == "A" and code in A_CODES:
        qk = A_CODES[code]
        q = quota.get(qk, {})
        if side == "买入":
            node_prices = [n["node_price"] for n in nodes.get(code, {}).get("nodes", [])]
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
        else:  # 卖出
            node = _find_node_for_sell(code, price)
            check("卖价=节点价×1.02", node is not None,
                  "卖价 %s，%s" % (price, "反推节点 %s" % node if node else "反推不到节点"))
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
            snap = _latest_snapshot()
            if snap is None:
                check("卖价不重复在挂", True, "跳过（无快照，见 §1.5）")
            else:
                dup = any(o["code"] == code and o["side"] == "卖出"
                          and o["status"] == "未成交"
                          and round_tick(o["price"], tick) == round_tick(price, tick)
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
                dev = abs(price - cur) / cur
                check("买价≈现价", dev <= PRICE_DEV_TOL + 1e-9,
                      "买价 %s，现价 %s，偏差 %.2f%%" % (price, cur, dev * 100))
            if "limit_price" in order and order.get("limit_price") is not None:
                check("买价<=P4限价", price <= float(order["limit_price"]) + 1e-9,
                      "买价 %s，P4 限价 %s" % (price, order["limit_price"]))
            else:
                check("买价<=P4限价", True, "跳过（未传 limit_price，见 §1.5）")
            check("单只<=5万", amount <= B_SINGLE_LIMIT + 1e-9,
                  "金额 %s" % amount)
            av = q.get("available")
            if av is None:
                check("买入<=B可用", False, "quota 取不到，拒绝")
            else:
                check("买入<=B可用", amount <= av + 1e-9,
                      "金额 %s，B 可用 %s" % (amount, av))
            holdings = q.get("holdings", {})
            is_new = code not in holdings or holdings[code]["qty"] <= 0
            if is_new:
                held_n = len([c for c, h in holdings.items() if h["qty"] > 0])
                check("B线<=3只", held_n < B_MAX_COUNT,
                      "新开仓，当前持仓 %s 只" % held_n)
            else:
                check("B线<=3只", True, "加仓既有持仓，不占新名额")
            check("单笔>=5000", amount >= MIN_AMOUNT, "金额 %s" % amount)
        else:  # B 线卖出：唯一校验（§1.5）
            holdings = q.get("holdings", {})
            held = holdings.get(code, {}).get("qty", 0)
            check("卖出<=持仓", qty <= held,
                  "卖 %s 股，持仓 %s 股" % (qty, held))
    return (len(reasons) == 0), checks, reasons


# ---------------------------------------------------------------------------
# 执行器 run：处理一轮 pending（合规通过即虚拟成交，按限价成交）
# ---------------------------------------------------------------------------
def gate_open():
    """§5.2：标志存在且 mtime 日期 == 当日，且当前在 07:30–17:05 内。"""
    if not os.path.exists(GATE_FLAG):
        return False, "门控标志不存在"
    mtime = datetime.fromtimestamp(os.path.getmtime(GATE_FLAG), tz=TZ)
    if mtime.strftime("%Y-%m-%d") != today_str():
        return False, "门控标志非当日（mtime %s）" % mtime.strftime("%Y-%m-%d")
    mins = now().hour * 60 + now().minute
    if not (GATE_OPEN_MIN <= mins <= GATE_CLOSE_MIN):
        return False, "不在 07:30–17:05 窗口内（当前 %s）" % now().strftime("%H:%M")
    return True, "门开"


def _append_trade_log(row):
    with open(TRADE_LOG, "a", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(row)


def _recompute_quota(q):
    q["available"] = r2(q["quota"] - q["deployed"])
    q["grid_quota"] = r2(q["quota"] * 0.85)
    q["grid_available"] = r2(q["grid_quota"] - q["deployed"])


def _apply_fill(order, fill_time):
    """虚拟成交入账：写 trade_log 行 + 更新 quota/持仓/节点账本。返回成交明细。"""
    code = order["code"]
    side = order["side"]
    price = float(order["price"])
    qty = int(order["qty"])
    amount = r2(price * qty)
    qk = quota_key_of_order(order)
    quota = load_json(QUOTA_FILE, {})
    nodes = load_json(NODES_FILE, {})
    q = quota[qk]
    holdings = q.setdefault("holdings", {})
    h = holdings.setdefault(code, {"qty": 0, "sellable": 0, "avg_cost": 0.0})
    line = qk if qk in ("A1", "A2", "A3") else "B"
    mark = MARK_OF_LINE[line]
    pnl_realized = ""
    if side == "买入":
        dep_before = q["deployed"]
        new_qty = h["qty"] + qty
        # 均价 = 持仓成本 / 股数（含买入费用，realized_ledger 移动加权口径）
        h["avg_cost"] = round((dep_before + amount) / new_qty, 4)
        h["qty"] = new_qty
        # A3 是 T+0，当日买入当日可卖；A1/A2 为 T+1，当日买入不计可卖
        if code == "513650":
            h["sellable"] += qty
        q["deployed"] = r2(q["deployed"] + amount)
        if code in A_CODES:
            node = round_tick(price, tick_of(code))
            found = False
            for n in nodes[code]["nodes"]:
                if round_tick(n["node_price"], tick_of(code)) == node:
                    n["hands"] += qty // 100
                    n["sell_price"] = round_tick(n["node_price"] * 1.02, tick_of(code))
                    found = True
                    break
            if not found:
                nodes[code]["nodes"].append(
                    {"node_price": node, "cost_price": nodes[code]["cost"],
                     "hands": qty // 100,
                     "sell_price": round_tick(node * 1.02, tick_of(code))})
                nodes[code]["nodes"].sort(key=lambda x: x["node_price"])
            remark_node = "节点%s×%s" % (node, qty)
        else:
            remark_node = "委托%s" % price
        remark = "%s买入成交（%s；委托%s，%s成交；订单%s；虚拟成交）" % (
            mark, remark_node, price, fill_time, order["order_id"])
    else:  # 卖出
        # 均价 = 持仓成本 / 股数（含买入费用，realized_ledger 移动加权口径，全精度）
        avg_before = q["deployed"] / h["qty"] if h["qty"] > 0 else price
        pnl_realized = r2((price - avg_before) * qty)
        h["qty"] -= qty
        h["sellable"] -= qty
        q["deployed"] = r2(q["deployed"] - r2(avg_before * qty))
        h["avg_cost"] = round(q["deployed"] / h["qty"], 4) if h["qty"] > 0 else 0.0
        q["pnl"] = r2(q["pnl"] + pnl_realized)
        if qk in ("A1", "A2", "A3"):
            q["quota"] = r2(166666.67 + q["pnl"])
        else:
            q["quota"] = r2(500000.0 + q["pnl"])
        if code in A_CODES:
            node = _find_node_for_sell(code, price)
            if node is not None:
                for n in nodes[code]["nodes"]:
                    if round_tick(n["node_price"], tick_of(code)) == round_tick(node, tick_of(code)):
                        n["hands"] = max(0, n["hands"] - qty // 100)
                        if n["hands"] == 0:
                            n["sell_price"] = None
                        break
            remark_node = "节点%s×%s" % (node, qty)
        else:
            remark_node = "委托%s" % price
        remark = "%s卖出成交（%s；委托%s，%s成交；订单%s；虚拟成交）" % (
            mark, remark_node, price, fill_time, order["order_id"])
    _recompute_quota(q)
    save_json(QUOTA_FILE, quota)
    save_json(NODES_FILE, nodes)
    _append_trade_log([today_str(), code, NAMES.get(code, ""), side, price, qty,
                       "%.2f" % amount,
                       ("%.2f" % pnl_realized) if pnl_realized != "" else "",
                       remark])
    state = load_json(STATE_FILE, {"orders": []})
    for o in state.get("orders", []):
        if o["order_id"] == order["order_id"]:
            o["status"] = "已成交"
            o["time"] = fill_time
    save_json(STATE_FILE, state)
    return {"code": code, "side": side, "price": price, "qty": qty,
            "amount": amount, "fill_time": fill_time,
            "realized_pnl": pnl_realized if pnl_realized != "" else 0.0}


def cmd_run(_args):
    _require_init()
    files = sorted(f for f in os.listdir(PENDING_DIR) if f.endswith(".json"))
    summary = {"ok": True, "action": "run", "date": today_str(),
               "processed": 0, "filled": [], "rejected": [], "gate_closed": []}
    if not files:
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    ok_gate, gate_detail = gate_open()
    if not ok_gate:
        for fn in files:
            src = os.path.join(PENDING_DIR, fn)
            with open(src, "r", encoding="utf-8") as f:
                order = json.load(f)
            order["result"] = {"status": "gate-closed", "reason": gate_detail}
            save_json(os.path.join(FAILED_DIR, fn), order)
            os.remove(src)
            summary["gate_closed"].append(order["order_id"])
            summary["processed"] += 1
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    for fn in files:
        src = os.path.join(PENDING_DIR, fn)
        with open(src, "r", encoding="utf-8") as f:
            order = json.load(f)
        oid = order.get("order_id", fn[:-5])
        # 订单文件 mtime 非当日 -> stale（§1.4）
        mtime = datetime.fromtimestamp(os.path.getmtime(src), tz=TZ)
        if mtime.strftime("%Y-%m-%d") != today_str():
            order["result"] = {"status": "stale",
                               "reason": "订单非当日（%s），过期" % mtime.strftime("%Y-%m-%d")}
            save_json(os.path.join(FAILED_DIR, fn), order)
            os.remove(src)
            summary["rejected"].append({"order_id": oid, "status": "stale"})
            summary["processed"] += 1
            continue
        passed, checks, reasons = run_compliance(order)
        if not passed:
            order["result"] = {"status": "rejected", "reasons": reasons, "checks": checks}
            save_json(os.path.join(FAILED_DIR, fn), order)
            os.remove(src)
            state = load_json(STATE_FILE, {"orders": []})
            state["orders"] = [o for o in state.get("orders", []) if o["order_id"] != oid]
            save_json(STATE_FILE, state)
            summary["rejected"].append({"order_id": oid, "status": "rejected",
                                        "reasons": reasons})
            summary["processed"] += 1
            continue
        fill = _apply_fill(order, now_str())
        order["result"] = {"status": "filled", "fill_price": fill["price"],
                           "fill_time": fill["fill_time"], "checks": checks,
                           "virtual": True}
        save_json(os.path.join(DONE_DIR, fn), order)
        os.remove(src)
        summary["filled"].append({"order_id": oid, **fill})
        summary["processed"] += 1
    print(json.dumps(summary, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# snapshot：生成 fillwatch 快照（§4.2 格式）
# ---------------------------------------------------------------------------
def cmd_snapshot(_args):
    _require_init()
    state = load_json(STATE_FILE, {"orders": []})
    today_orders = [o for o in state.get("orders", [])
                    if o.get("time", "").startswith(today_str())]
    fills = [o for o in today_orders if o["status"] == "已成交"]
    pending = [o for o in today_orders if o["status"] == "未成交"]
    snap = {"label": "fillwatch", "timestamp": now_str(), "status": "ok",
            "orders": today_orders, "fills_today": fills, "pending": pending}
    fname = "fillwatch_%s.json" % now().strftime("%Y%m%d_%H%M")
    save_json(os.path.join(SNAP_DIR, fname), snap)
    out = dict(snap)
    out["file"] = fname
    out["stale"] = False
    out["virtual"] = True
    print(json.dumps(out, ensure_ascii=False))
    return 0


def snapshot_is_stale(snap):
    try:
        ts = datetime.strptime(snap["timestamp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)
    except Exception:
        return True
    return (now() - ts).total_seconds() > STALE_SECS


# ---------------------------------------------------------------------------
# quota / log：只读打印
# ---------------------------------------------------------------------------
def cmd_quota(_args):
    _require_init()
    quota = load_json(QUOTA_FILE, {})
    print(json.dumps({"ok": True, "date": today_str(), "quota": quota,
                      "virtual": True}, ensure_ascii=False, indent=2))
    return 0


def cmd_log(args):
    _require_init()
    n = 10
    if args:
        try:
            n = int(args[0])
        except ValueError:
            fail("log 参数须为整数行数")
    if not os.path.exists(TRADE_LOG):
        print("(虚拟 trade_log 为空)")
        return 0
    with open(TRADE_LOG, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    print("虚拟 trade_log：共 %d 行（含表头），尾部 %d 行：" % (len(lines), min(n, len(lines))))
    for ln in lines[-n:]:
        print(ln)
    return 0


USAGE = ("用法：python3 virtual_ops.py "
         "{init|quote <代码>|check <代码> [买价]|submit <订单JSON文件>|run|snapshot|quota|log [N]}")


def main(argv):
    if len(argv) < 2:
        print(USAGE, file=sys.stderr)
        return 1
    cmd, args = argv[1], argv[2:]
    handlers = {"init": cmd_init, "quote": cmd_quote, "check": cmd_check, "submit": cmd_submit,
                "run": cmd_run, "snapshot": cmd_snapshot, "quota": cmd_quota,
                "log": cmd_log}
    if cmd not in handlers:
        print(USAGE, file=sys.stderr)
        return 1
    try:
        return handlers[cmd](args)
    except SystemExit as e:
        return int(e.code or 0)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
