#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fillwatch_rehang.py 最小自测（用虚拟程序数据）。
用法：python3 test_fillwatch.py --base /workspace/ab-/virtual
在 /tmp 建一份虚拟目录副本跑，不碰原目录。全部 PASS 才 exit 0。"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OPS_BUILD = os.path.dirname(HERE)
SCRIPT = os.path.join(OPS_BUILD, "fillwatch_rehang.py")
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL") + " " + name + (" | " + detail if detail else ""))


def run_cli(base, extra=None):
    cmd = [sys.executable, SCRIPT, "--base", base, "--mode", "compare"] + (extra or [])
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    try:
        out = json.loads(p.stdout)
    except Exception:
        out = {"ok": False, "raw": p.stdout, "stderr": p.stderr}
    return p.returncode, out


def fresh_copy(base, tmp, name):
    vdir = os.path.join(tmp, name)
    shutil.copytree(base, vdir, ignore=shutil.ignore_patterns("snapshots", "__pycache__"))
    os.makedirs(os.path.join(vdir, "snapshots"), exist_ok=True)
    subprocess.run([sys.executable, "virtual_ops.py", "init"], cwd=vdir,
                   capture_output=True, text=True, timeout=60, check=True)
    return vdir


def submit_and_fill(vdir, tmp, order):
    of = os.path.join(tmp, order["order_id"] + ".json")
    with open(of, "w", encoding="utf-8") as f:
        json.dump(order, f, ensure_ascii=False)
    p = subprocess.run([sys.executable, "virtual_ops.py", "submit", of], cwd=vdir,
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stdout + p.stderr
    p = subprocess.run([sys.executable, "virtual_ops.py", "run"], cwd=vdir,
                       capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr
    p = subprocess.run([sys.executable, "virtual_ops.py", "snapshot"], cwd=vdir,
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stdout + p.stderr
    return json.loads(p.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    args = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="vtest_fillwatch_")
    try:
        # 场景 1：快照有新成交、trade_log 未入账 → 检出并算出补买 200@48.61
        vdir = fresh_copy(args.base, tmp, "v1")
        snap = submit_and_fill(vdir, tmp, {"order_id": "T-F1", "code": "601088", "side": "卖出",
                                            "price": 49.58, "qty": 200, "line": "A",
                                            "prev_close": 49.10})
        # 把 trade_log 截回仅表头，模拟“成交未入账”
        with open(os.path.join(vdir, "virtual_trade_log.csv"), encoding="utf-8") as f:
            header = f.readline()
        with open(os.path.join(vdir, "virtual_trade_log.csv"), "w", encoding="utf-8") as f:
            f.write(header)
        rc, out = run_cli(vdir)
        check("新成交检出 1 笔", rc == 0 and len(out.get("new_fills", [])) == 1,
              json.dumps(out, ensure_ascii=False)[:400])
        comp = out.get("computed_orders", [])
        check("算出补挂单 1 笔", len(comp) == 1, json.dumps(comp, ensure_ascii=False)[:400])
        if comp:
            o = comp[0]
            check("补挂是买入 200@48.61", o.get("side") == "买入" and o.get("code") == "601088"
                  and float(o.get("price", 0)) == 48.61 and int(o.get("qty", 0)) == 200,
                  json.dumps(o, ensure_ascii=False)[:300])
            check("补挂 order_id 格式 FW-...-buy-48p61-...",
                  str(o.get("order_id", "")).startswith("FW-20261113-601088-buy-48p61-"),
                  str(o.get("order_id")))
        check("verdict=computed", out.get("verdict") == "computed",
              "verdict=%s" % out.get("verdict"))
        # 场景 2：trade_log 已有该成交 → 静默 no_new_fills
        vdir2 = fresh_copy(args.base, tmp, "v2")
        submit_and_fill(vdir2, tmp, {"order_id": "T-F2", "code": "601088", "side": "卖出",
                                      "price": 49.58, "qty": 200, "line": "A",
                                      "prev_close": 49.10})
        rc, out = run_cli(vdir2)
        check("已入账成交静默", rc == 0 and out.get("verdict") == "silent"
              and out.get("reason") == "no_new_fills" and out.get("new_fills") == [],
              json.dumps(out, ensure_ascii=False)[:300])
        # 场景 3：快照过期 → stale_snapshot 静默
        snaps = sorted(os.listdir(os.path.join(vdir2, "snapshots")))
        sp = os.path.join(vdir2, "snapshots", snaps[-1])
        with open(sp, encoding="utf-8") as f:
            s = json.load(f)
        s["timestamp"] = "2026-11-13 08:00:00"
        with open(sp, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False)
        rc, out = run_cli(vdir2)
        check("过期快照 stale 静默", rc == 0 and out.get("verdict") == "silent"
              and out.get("reason") == "stale_snapshot",
              json.dumps(out, ensure_ascii=False)[:300])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    failed = [r for r in RESULTS if not r[1]]
    print("合计 %d 项，失败 %d 项" % (len(RESULTS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

