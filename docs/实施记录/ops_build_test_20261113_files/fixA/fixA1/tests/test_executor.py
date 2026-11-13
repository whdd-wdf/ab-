#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""order_executor.py 最小自测（用虚拟程序数据）。
用法：python3 test_executor.py --base /workspace/ab-/virtual
在 /tmp 建一份虚拟目录副本跑，不碰原目录。全部 PASS 才 exit 0。"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OPS_BUILD = os.path.dirname(HERE)
SCRIPT = os.path.join(OPS_BUILD, "order_executor.py")
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL") + " " + name + (" | " + detail if detail else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    args = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="vtest_executor_")
    try:
        vdir = os.path.join(tmp, "virtual")
        shutil.copytree(args.base, vdir, ignore=shutil.ignore_patterns("snapshots", "__pycache__"))
        os.makedirs(os.path.join(vdir, "snapshots"), exist_ok=True)
        subprocess.run([sys.executable, "virtual_ops.py", "init"], cwd=vdir,
                       capture_output=True, text=True, timeout=60, check=True)
        # 提交一笔合规 A 线卖单（经虚拟 submit，同时写 state 行）
        order = {"order_id": "T-X1", "code": "601088", "side": "卖出", "price": 49.58,
                 "qty": 200, "line": "A", "prev_close": 49.10}
        of = os.path.join(tmp, "order1.json")
        with open(of, "w", encoding="utf-8") as f:
            json.dump(order, f, ensure_ascii=False)
        p = subprocess.run([sys.executable, "virtual_ops.py", "submit", of], cwd=vdir,
                           capture_output=True, text=True, timeout=60)
        check("虚拟 submit 成功", p.returncode == 0, p.stdout.strip()[:200])
        # 提交一笔不合规 A 线买单（48.00 非节点价）
        bad = {"order_id": "T-X2", "code": "601088", "side": "买入", "price": 48.00,
               "qty": 200, "line": "A", "prev_close": 49.10}
        bf = os.path.join(tmp, "order2.json")
        with open(bf, "w", encoding="utf-8") as f:
            json.dump(bad, f, ensure_ascii=False)
        p = subprocess.run([sys.executable, "virtual_ops.py", "submit", bf], cwd=vdir,
                           capture_output=True, text=True, timeout=60)
        check("虚拟 submit 坏单成功", p.returncode == 0, p.stdout.strip()[:200])
        # 跑 AI 执行器
        p = subprocess.run([sys.executable, SCRIPT, "--base", vdir],
                           capture_output=True, text=True, timeout=300)
        try:
            summ = json.loads(p.stdout)
        except Exception:
            summ = {}
        check("执行器 exit 0", p.returncode == 0, p.stdout.strip()[:300] + p.stderr.strip()[:200])
        check("执行器处理 2 笔", summ.get("processed") == 2, json.dumps(summ, ensure_ascii=False)[:300])
        # done/ 里有成交单
        done1 = os.path.join(vdir, "order_queue", "done", "T-X1.json")
        check("合规单进 done", os.path.exists(done1))
        if os.path.exists(done1):
            with open(done1, encoding="utf-8") as f:
                d = json.load(f)
            check("成交单 result=filled", d.get("result", {}).get("status") == "filled",
                  json.dumps(d.get("result", {}), ensure_ascii=False)[:200])
        # failed/ 里有拒绝单
        fail2 = os.path.join(vdir, "order_queue", "failed", "T-X2.json")
        check("不合规单进 failed", os.path.exists(fail2))
        if os.path.exists(fail2):
            with open(fail2, encoding="utf-8") as f:
                d = json.load(f)
            check("拒绝单 result=rejected", d.get("result", {}).get("status") == "rejected",
                  json.dumps(d.get("result", {}), ensure_ascii=False)[:200])
        # trade_log 有 1 笔带 【A2】 标记的成交行
        with open(os.path.join(vdir, "virtual_trade_log.csv"), encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        fills = [r for r in rows if r["方向"] in ("买入", "卖出")]
        check("trade_log 有 1 笔成交行", len(fills) == 1, "行数=%d" % len(fills))
        if fills:
            check("成交行带 【A2】 标记", fills[0]["备注"].startswith("【A2】"), fills[0]["备注"][:80])
            check("成交行是卖出 200@49.58", fills[0]["方向"] == "卖出" and fills[0]["代码"] == "601088"
                  and float(fills[0]["价格"]) == 49.58 and int(fills[0]["数量"]) == 200,
                  str(fills[0])[:200])
        # quota A2 deployed 减少（卖出均价约 49.2055×200）
        with open(os.path.join(vdir, "virtual_quota.json"), encoding="utf-8") as f:
            quota = json.load(f)
        a2 = quota["A2"]
        check("A2 deployed 减少约 9841", abs(a2["deployed"] - (59046.64 - 9841.10)) < 2.0,
              "deployed=%s" % a2["deployed"])
        check("A2 quota 平衡 available=quota-deployed",
              abs(a2["available"] - (a2["quota"] - a2["deployed"])) < 0.02,
              "available=%s quota=%s deployed=%s" % (a2["available"], a2["quota"], a2["deployed"]))
        # 节点 48.61 hands 由 2 变 0
        with open(os.path.join(vdir, "nodes.json"), encoding="utf-8") as f:
            nodes = json.load(f)
        n4861 = [n for n in nodes["601088"]["nodes"] if abs(n["node_price"] - 48.61) < 1e-9]
        check("节点 48.61 hands 2→0", len(n4861) == 1 and n4861[0]["hands"] == 0,
              json.dumps(n4861, ensure_ascii=False)[:200])
        # state.json 订单行变 已成交
        with open(os.path.join(vdir, "state.json"), encoding="utf-8") as f:
            state = json.load(f)
        st1 = [o for o in state.get("orders", []) if o["order_id"] == "T-X1"]
        check("state 行变 已成交", len(st1) == 1 and st1[0]["status"] == "已成交",
              json.dumps(st1, ensure_ascii=False)[:200])
        # 执行器写了快照
        snaps = sorted(os.listdir(os.path.join(vdir, "snapshots")))
        check("执行器写了快照", len(snaps) >= 1, str(snaps))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    failed = [r for r in RESULTS if not r[1]]
    print("合计 %d 项，失败 %d 项" % (len(RESULTS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

