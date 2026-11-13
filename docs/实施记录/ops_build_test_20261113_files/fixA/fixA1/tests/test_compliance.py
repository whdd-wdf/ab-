#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""order_compliance.py 最小自测（用虚拟程序数据）。
用法：python3 test_compliance.py --base /workspace/ab-/virtual
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
SCRIPT = os.path.join(OPS_BUILD, "order_compliance.py")
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL") + " " + name + (" | " + detail if detail else ""))


def run_cli(base, order):
    cmd = [sys.executable, SCRIPT, "--base", base, "--order", json.dumps(order, ensure_ascii=False)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    try:
        out = json.loads(p.stdout)
    except Exception:
        out = {"ok": False, "raw": p.stdout, "stderr": p.stderr}
    return p.returncode, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    args = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="vtest_compliance_")
    try:
        vdir = os.path.join(tmp, "virtual")
        shutil.copytree(args.base, vdir, ignore=shutil.ignore_patterns("snapshots", "__pycache__"))
        os.makedirs(os.path.join(vdir, "snapshots"), exist_ok=True)
        subprocess.run([sys.executable, "virtual_ops.py", "init"], cwd=vdir,
                       capture_output=True, text=True, timeout=60, check=True)
        # 1. A 线卖单 601088 卖 200 @49.58 通过
        rc, out = run_cli(vdir, {"order_id": "T-C1", "code": "601088", "side": "卖出",
                                 "price": 49.58, "qty": 200, "line": "A", "prev_close": 49.10})
        check("A卖 601088 200@49.58 通过", rc == 0 and out.get("passed") is True, json.dumps(out, ensure_ascii=False)[:300])
        # 2. A 线买价 48.00 非节点价被拒
        rc, out = run_cli(vdir, {"order_id": "T-C2", "code": "601088", "side": "买入",
                                 "price": 48.00, "qty": 200, "line": "A", "prev_close": 49.10})
        reasons = " ".join(out.get("reasons", []))
        check("A买 48.00 非节点价被拒", rc == 1 and out.get("passed") is False and "节点价" in reasons, reasons[:200])
        # 3. B 线买价偏离现价 >1% 被拒（现价 12.98，买 13.63 偏离约 5%）
        rc, out = run_cli(vdir, {"order_id": "T-C3", "code": "600919", "side": "买入",
                                 "price": 13.63, "qty": 500, "line": "B",
                                 "prev_close": 12.80, "limit_price": 13.18})
        ch = {c["item"]: c for c in out.get("checks", [])}
        dev = ch.get("买价≈现价", {})
        check("B买偏离现价>1%被拒", rc == 1 and out.get("passed") is False
              and dev.get("pass") is False and "现价" in " ".join(out.get("reasons", [])),
              json.dumps(out.get("reasons", []), ensure_ascii=False)[:200])
        # 4. B 线买单 600919 @12.98 500 股通过
        rc, out = run_cli(vdir, {"order_id": "T-C4", "code": "600919", "side": "买入",
                                 "price": 12.98, "qty": 500, "line": "B",
                                 "prev_close": 12.80, "limit_price": 13.18})
        check("B买 600919 500@12.98 通过", rc == 0 and out.get("passed") is True, json.dumps(out, ensure_ascii=False)[:300])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    failed = [r for r in RESULTS if not r[1]]
    print("合计 %d 项，失败 %d 项" % (len(RESULTS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

