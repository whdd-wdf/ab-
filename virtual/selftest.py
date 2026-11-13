#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
虚拟程序自测 selftest.py（沙箱跑，不碰真实系统）

跑一轮，逐项 PASS/FAIL，全部 PASS 才 exit 0：
  ① A 线卖单：601088 卖 200 @49.58，须合规通过并成交入账
     （验算：49.58 = 节点 48.61×1.02 tick 取整；金额 9916 ≥ 5000；
      quota/持仓/可卖/节点股数按移动加权平均口径更新）
  ② B 线买单：从虚拟候选里挑 600919，按虚拟行情现价买入，
     须过涨幅≤5% / P4 限价 / 单只≤5万 / B 线≤3只闸门，成交入账
  ③ 错单：A 线买价 48.00（非节点价），须合规拒绝进 failed 并写 reasons
  ④ 跑后 quota 更新正确、快照 status ok、虚拟 trade_log 有成交行
  ⑤ 错价单：600919 买价 = 现价×1.05（偏离现价 5%），须因“买价≈现价”被拒绝进 failed
  ⑥ check 接口：check 600919（默认/显式买价=现价）数字与手工重算一致；
     check 600919 <现价×1.05> 时 deviation_ok 为 False

用法：python3 selftest.py
"""
import json
import math
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
OPS = os.path.join(BASE, "virtual_ops.py")
TMP = "/tmp/virtual_selftest"
os.makedirs(TMP, exist_ok=True)

RESULTS = []


def run_ops(*args, expect_ok=True):
    p = subprocess.run([sys.executable, OPS, *args], capture_output=True,
                       text=True, timeout=120)
    if expect_ok and p.returncode != 0:
        raise RuntimeError("virtual_ops.py %s 失败 rc=%d：%s%s"
                           % (" ".join(args), p.returncode, p.stdout, p.stderr))
    return p


def run_ops_json(*args, **kw):
    p = run_ops(*args, **kw)
    try:
        return json.loads(p.stdout)
    except Exception:
        raise RuntimeError("virtual_ops.py %s 输出非 JSON：%s%s"
                           % (" ".join(args), p.stdout, p.stderr))


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print("%s %s%s" % ("PASS" if cond else "FAIL", name,
                       (" — " + detail) if detail else ""))


def write_order(order):
    path = os.path.join(TMP, order["order_id"] + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(order, f, ensure_ascii=False)
    return path


def main():
    print("== 虚拟程序自测（沙箱，全部虚拟文件在 virtual/ 内）==")
    # 0. 初始化
    init = run_ops_json("init")
    check("init 初始化成功", init.get("ok") is True and init.get("gate") == "open",
          "date=%s" % init.get("date"))

    # ① A 线卖单：601088 卖 200 @49.58（节点 48.61×1.02 = 49.5822 -> 49.58）
    q_before = run_ops_json("quota")["quota"]
    a2_before = q_before["A2"]
    avg_before = a2_before["deployed"] / a2_before["holdings"]["601088"]["qty"]
    sell_order = {"order_id": "FW-20261113-601088-sell-49p58-20261113120600",
                  "code": "601088", "side": "卖出", "price": 49.58, "qty": 200,
                  "line": "A", "prev_close": 49.10,
                  "note": "自测 A 线卖单（节点 48.61×1.02）"}
    run_ops_json("submit", write_order(sell_order))
    run1 = run_ops_json("run")
    filled_ids = [f["order_id"] for f in run1.get("filled", [])]
    check("① A 线卖单合规通过并成交",
          sell_order["order_id"] in filled_ids,
          "filled=%s rejected=%s" % (filled_ids, run1.get("rejected")))
    done_path = os.path.join(BASE, "order_queue", "done", sell_order["order_id"] + ".json")
    done = json.load(open(done_path, encoding="utf-8")) if os.path.exists(done_path) else {}
    check("① done 结果为 filled",
          done.get("result", {}).get("status") == "filled",
          "result=%s" % done.get("result", {}).get("status"))
    q_after = run_ops_json("quota")["quota"]
    a2_after = q_after["A2"]
    exp_deployed = round(a2_before["deployed"] - round(avg_before * 200, 2), 2)
    exp_pnl = round(a2_before["pnl"] + round((49.58 - avg_before) * 200, 2), 2)
    check("① A2 quota 更新正确",
          abs(a2_after["deployed"] - exp_deployed) < 0.05
          and abs(a2_after["pnl"] - exp_pnl) < 0.05,
          "deployed %s->%s（预期 %s），pnl %s->%s（预期 %s）"
          % (a2_before["deployed"], a2_after["deployed"], exp_deployed,
             a2_before["pnl"], a2_after["pnl"], exp_pnl))
    h_after = a2_after["holdings"]["601088"]
    check("① A2 持仓/可卖更新正确",
          h_after["qty"] == 1000 and h_after["sellable"] == 500,
          "qty=%s sellable=%s" % (h_after["qty"], h_after["sellable"]))
    nodes = json.load(open(os.path.join(BASE, "nodes.json"), encoding="utf-8"))
    node_4861 = [n for n in nodes["601088"]["nodes"]
                 if abs(n["node_price"] - 48.61) < 1e-9][0]
    check("① 48.61 节点股数核减为 0 手",
          node_4861["hands"] == 0, "hands=%s" % node_4861["hands"])

    # ② B 线买单：600919 按虚拟行情现价买入
    quote = run_ops_json("quote", "600919")
    price = quote["price"]
    prev_close = quote["prev_close"]
    qty = int(math.ceil(6000 / price / 100.0)) * 100
    amount = round(price * qty, 2)
    limit_price = round(prev_close * 1.03, 2)  # P4 限价 = min(14:30 实时价, 开盘×1.03)
    buy_order = {"order_id": "B-20261113-600919-1", "code": "600919",
                 "side": "买入", "price": price, "qty": qty, "line": "B",
                 "prev_close": prev_close, "limit_price": limit_price,
                 "note": "自测 B 线买单"}
    gate_ok = (price / prev_close - 1 <= 0.05 and price <= limit_price
               and 5000 <= amount <= 50000)
    check("② B 线买单参数本身过闸门（涨幅/P4/单只）",
          gate_ok,
          "price=%s prev=%s 涨幅=%.2f%% limit=%s qty=%s amount=%s"
          % (price, prev_close, (price / prev_close - 1) * 100, limit_price, qty, amount))
    run_ops_json("submit", write_order(buy_order))
    run2 = run_ops_json("run")
    filled2 = [f["order_id"] for f in run2.get("filled", [])]
    check("② B 线买单合规通过并成交",
          buy_order["order_id"] in filled2,
          "filled=%s rejected=%s" % (filled2, run2.get("rejected")))
    q_b = run_ops_json("quota")["quota"]["B"]
    b_pos = q_b["holdings"].get("600919", {})
    check("② B 线持仓/额度更新正确",
          b_pos.get("qty") == qty and abs(q_b["deployed"] - amount) < 0.05,
          "600919 qty=%s deployed=%s（预期 %s）" % (b_pos.get("qty"), q_b["deployed"], amount))
    check("② B 线持仓 1 只（≤3 只）",
          len([c for c, h in q_b["holdings"].items() if h["qty"] > 0]) == 1,
          "count=%s" % len([c for c, h in q_b["holdings"].items() if h["qty"] > 0]))

    # ③ 错单：A 线买价 48.00，非节点价 -> 拒绝进 failed
    bad_order = {"order_id": "FW-20261113-601088-buy-48p00-20261113120600",
                 "code": "601088", "side": "买入", "price": 48.00, "qty": 200,
                 "line": "A", "prev_close": 49.10, "note": "自测错单（非节点价）"}
    run_ops_json("submit", write_order(bad_order))
    run3 = run_ops_json("run")
    rej = [r for r in run3.get("rejected", []) if r["order_id"] == bad_order["order_id"]]
    check("③ 错单被拒绝（未成交）",
          len(rej) == 1 and rej[0].get("status") == "rejected",
          "rejected=%s" % run3.get("rejected"))
    failed_path = os.path.join(BASE, "order_queue", "failed",
                               bad_order["order_id"] + ".json")
    failed = json.load(open(failed_path, encoding="utf-8")) if os.path.exists(failed_path) else {}
    res = failed.get("result", {})
    reasons_txt = " ".join(res.get("reasons", []))
    check("③ failed 写 reasons 且指明买价非节点价",
          res.get("status") == "rejected" and "节点价" in reasons_txt,
          "reasons=%s" % res.get("reasons"))
    check("③ failed 写逐项 checks",
          isinstance(res.get("checks"), list) and len(res["checks"]) >= 3,
          "checks=%d 项" % len(res.get("checks", [])))

    # ④ 跑后状态：quota 平衡、快照 ok、trade_log 有成交行
    q_final = run_ops_json("quota")["quota"]
    bal_ok = True
    for k, v in q_final.items():
        if abs(v["quota"] - v["deployed"] - v["available"]) > 0.02:
            bal_ok = False
        if abs(v["grid_quota"] - v["deployed"] - v["grid_available"]) > 0.02:
            bal_ok = False
    check("④ quota 四仓平衡（quota-deployed=available，grid 同理）",
          bal_ok,
          "A1/A2/A3/B available=%s"
          % [q_final[k]["available"] for k in ("A1", "A2", "A3", "B")])
    snap = run_ops_json("snapshot")
    check("④ 快照 status ok 且不 stale",
          snap.get("status") == "ok" and snap.get("stale") is False,
          "status=%s stale=%s fills=%d pending=%d"
          % (snap.get("status"), snap.get("stale"),
             len(snap.get("fills_today", [])), len(snap.get("pending", []))))
    check("④ 快照 fills_today 含 2 笔成交（A2 卖 + B 买）",
          len(snap.get("fills_today", [])) == 2,
          "fills=%s" % [(f["code"], f["side"], f["qty"]) for f in snap.get("fills_today", [])])
    log_text = open(os.path.join(BASE, "virtual_trade_log.csv"),
                    encoding="utf-8").read()
    lines = [ln for ln in log_text.splitlines() if ln]
    fills = [ln for ln in lines[1:] if ",卖出," in ln or ",买入," in ln]
    has_a2_sell = any(ln.startswith("2026-11-13,601088,中国神华,卖出,49.58,200,")
                      and "【A2】" in ln for ln in lines)
    has_b_buy = any(",600919,江苏银行,买入," in ln and "【B线】" in ln for ln in lines)
    check("④ 虚拟 trade_log 有 2 笔成交行且带仓位标记",
          len(fills) == 2 and has_a2_sell and has_b_buy,
          "成交行 %d 行；A2 卖行 %s，B 买行 %s" % (len(fills), has_a2_sell, has_b_buy))

    # ⑤ 错价单：600919 买价 = 现价×1.05（偏离现价 5%），须因“买价≈现价”被拒绝
    quote5 = run_ops_json("quote", "600919")
    cur5 = quote5["price"]
    prev5 = quote5["prev_close"]
    wrong_price = round(cur5 * 1.05, 2)
    qty5 = int(math.ceil(6000 / cur5 / 100.0)) * 100
    wrong_order = {"order_id": "B-20261113-600919-wrongprice-1", "code": "600919",
                   "side": "买入", "price": wrong_price, "qty": qty5, "line": "B",
                   "prev_close": prev5, "limit_price": round(prev5 * 1.03, 2),
                   "note": "自测错价单（买价偏离现价 5%）"}
    run_ops_json("submit", write_order(wrong_order))
    run5 = run_ops_json("run")
    rej5 = [r for r in run5.get("rejected", []) if r["order_id"] == wrong_order["order_id"]]
    failed5_path = os.path.join(BASE, "order_queue", "failed",
                                wrong_order["order_id"] + ".json")
    failed5 = json.load(open(failed5_path, encoding="utf-8")) if os.path.exists(failed5_path) else {}
    res5 = failed5.get("result", {})
    checks5 = res5.get("checks", [])
    dev_item = [c for c in checks5 if c.get("item") == "买价≈现价"]
    reasons5_txt = " ".join(res5.get("reasons", []))
    check("⑤ 错价单被拒绝且“买价≈现价”项不通过、reasons 含现价",
          len(rej5) == 1 and rej5[0].get("status") == "rejected"
          and len(dev_item) == 1 and dev_item[0].get("pass") is False
          and "现价" in reasons5_txt,
          "price=%s cur=%s rejected=%s dev_item=%s reasons=%s"
          % (wrong_price, cur5, rej5, dev_item, res5.get("reasons")))

    # ⑥ check 接口：默认/显式买价=现价时数字与手工重算一致；买价=现价×1.05 时 deviation_ok 为 False
    def r2_local(x):
        return round(float(x) + 1e-9, 2)

    def r4_local(x):
        return round(float(x) + 1e-9, 4)

    def expect_check(buy):
        qty50 = int(50000 // (buy * 100)) * 100
        return {"change_pct": r4_local(buy / prev5 - 1),
                "deviation_pct": r4_local(buy / cur5 - 1),
                "p4_limit": round(prev5 * 1.03, 2),
                "qty_50k": qty50, "amount_50k": r2_local(buy * qty50)}

    def close(a, b):
        return abs(a - b) <= 0.01

    chk_default = run_ops_json("check", "600919")
    chk_explicit = run_ops_json("check", "600919", str(cur5))
    exp_cur = expect_check(cur5)
    ok6 = all(
        chk.get("buy_price") == cur5
        and close(chk.get("change_pct", 1e9), exp_cur["change_pct"])
        and close(chk.get("p4_limit", 1e9), exp_cur["p4_limit"])
        and chk.get("qty_50k") == exp_cur["qty_50k"]
        and close(chk.get("amount_50k", 1e9), exp_cur["amount_50k"])
        and close(chk.get("deviation_pct", 1e9), exp_cur["deviation_pct"])
        for chk in (chk_default, chk_explicit))
    check("⑥ check 接口数字与手工重算一致（默认/显式买价=现价）",
          ok6, "default=%s explicit=%s expected=%s" % (chk_default, chk_explicit, exp_cur))
    chk_wrong = run_ops_json("check", "600919", str(wrong_price))
    check("⑥ check 接口买价偏离现价 5% 时 deviation_ok 为 False",
          chk_wrong.get("gates", {}).get("deviation_ok") is False,
          "buy_price=%s deviation_pct=%s gates=%s"
          % (chk_wrong.get("buy_price"), chk_wrong.get("deviation_pct"), chk_wrong.get("gates")))

    # ⑦ check 涨幅显示精度：change_pct 与手工重算一致到 0.01%（百分点）
    raw_change = (cur5 / prev5 - 1) * 100
    shown_change = chk_default.get("change_pct", 1e9) * 100
    check("⑦ check 涨幅显示与手工重算一致到 0.01%",
          abs(shown_change - raw_change) <= 0.01,
          "shown=%.4f%% raw=%.4f%%" % (shown_change, raw_change))

    print("== 自测结果：%d 项，PASS %d，FAIL %d ==" % (
        len(RESULTS), sum(1 for _, ok, _ in RESULTS if ok),
        sum(1 for _, ok, _ in RESULTS if not ok)))
    failed = [n for n, ok, _ in RESULTS if not ok]
    if failed:
        print("未通过项：%s" % failed)
        return 1
    print("全部 PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
