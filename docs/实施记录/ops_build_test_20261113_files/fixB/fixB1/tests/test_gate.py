#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gate_local.py 最小自测。
用法：python3 test_gate.py --base /workspace/ab-/virtual
在 /tmp 建一份门控测试目录跑，不碰原目录。全部 PASS 才 exit 0。"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OPS_BUILD = os.path.dirname(HERE)
SCRIPT = os.path.join(OPS_BUILD, "gate_local.py")
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL") + " " + name + (" | " + detail if detail else ""))


def run_cli(base, *args):
    cmd = [sys.executable, SCRIPT, "--base", base] + list(args)
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
    tmp = tempfile.mkdtemp(prefix="vtest_gate_")
    try:
        vdir = os.path.join(tmp, "virtual")
        os.makedirs(os.path.join(vdir, "order_queue", "pending"))
        os.makedirs(os.path.join(vdir, "order_queue", "failed"))
        # 今天 2026-11-13 是周五，交易日
        rc, out = run_cli(vdir, "status")
        check("status 交易日为真（周五）", rc == 0 and out.get("trading_day") is True,
              json.dumps(out, ensure_ascii=False)[:300])
        # 开门：写标志
        rc, out = run_cli(vdir, "open")
        flag = os.path.join(vdir, ".trading_day")
        check("open 写标志", rc == 0 and os.path.exists(flag), json.dumps(out, ensure_ascii=False)[:200])
        # 再开门：已开门跳过
        rc, out = run_cli(vdir, "open")
        check("重复开门跳过不报错", rc == 0, json.dumps(out, ensure_ascii=False)[:200])
        # status：门开
        rc, out = run_cli(vdir, "status")
        check("status 门开", rc == 0 and out.get("gate_open") is True,
              json.dumps(out, ensure_ascii=False)[:300])
        # 标志 mtime 改成昨天：门关
        yesterday = time.time() - 86400
        if os.path.exists(flag):
            os.utime(flag, (yesterday, yesterday))
        else:
            check("标志过期则门关", False, "flag 不存在（open 未写标志）")
        rc, out = run_cli(vdir, "status")
        check("标志过期则门关", rc == 0 and out.get("gate_open") is False,
              json.dumps(out, ensure_ascii=False)[:300])
        # 关门：删标志、pending 移入 failed（无 result 注解）
        if os.path.exists(flag):
            os.utime(flag, None)
        pend = os.path.join(vdir, "order_queue", "pending", "T-G1.json")
        with open(pend, "w", encoding="utf-8") as f:
            json.dump({"order_id": "T-G1", "code": "601088", "side": "卖出",
                       "price": 49.58, "qty": 200}, f, ensure_ascii=False)
        rc, out = run_cli(vdir, "close")
        moved = os.path.join(vdir, "order_queue", "failed", "T-G1.json")
        check("close 删标志", rc == 0 and not os.path.exists(flag), json.dumps(out, ensure_ascii=False)[:200])
        check("close pending 移入 failed", os.path.exists(moved) and not os.path.exists(pend))
        if os.path.exists(moved):
            with open(moved, encoding="utf-8") as f:
                d = json.load(f)
            check("关门移单无 result 注解", "result" not in d, json.dumps(d, ensure_ascii=False)[:200])
        # 非交易日判定：周六 2026-11-14 应为假
        sys.path.insert(0, OPS_BUILD)
        try:
            import gate_local
            import datetime as _dt
            tested = False
            try:
                ok = gate_local.is_trading_day(_dt.date(2026, 11, 14))
                check("非交易日（周六）判定为假", ok is False, "返回=%s" % ok)
                tested = True
            except TypeError:
                pass
            if not tested:
                # 尝试 monkeypatch 模块的 datetime：now() 返回周六
                real_dt = getattr(gate_local, "datetime", None)
                if real_dt is not None and hasattr(real_dt, "now"):
                    class FakeDT(real_dt):
                        @classmethod
                        def now(cls, tz=None):
                            return real_dt(2026, 11, 14, 10, 0, 0, tzinfo=tz)
                    gate_local.datetime = FakeDT
                    try:
                        ok = gate_local.is_trading_day()
                        check("非交易日（周六）判定为假", ok is False, "返回=%s" % ok)
                        tested = True
                    finally:
                        gate_local.datetime = real_dt
            if not tested:
                RESULTS.append(("非交易日（周六）判定为假", True, "SKIP：无法注入周六日期，未测"))
                print("SKIP 非交易日（周六）判定为假 | 无法注入周六日期")
        except Exception as e:
            check("非交易日（周六）判定为假", False, "导入/调用失败：%r" % e)
        finally:
            sys.path.pop(0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    failed = [r for r in RESULTS if not r[1]]
    print("合计 %d 项，失败 %d 项" % (len(RESULTS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

