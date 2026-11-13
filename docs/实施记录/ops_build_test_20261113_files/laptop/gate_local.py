#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gate_local.py — 本机门控（操作侧，虚拟环境搭建版）

依据：docs/操作与管控接口规范.md §5.1（标志语义）、§5.2（执行器判定）、
§5.3（关门 pending 处理与并行安全）、§5.4（交易日判定）、§8.1（CLI 形式）。

用法：
  python3 gate_local.py --base <目录> open|close|status
  open / close / status 是位置参数；另支持 --date YYYY-MM-DD、--root <测试根目录>
  （--root 与 --base 同义，--base 优先）、--dry-run、--no-systemd。
  不传 --base / --root 时用真实路径 /root/monitor/。

语义（§5.1）：
  .trading_day 空文件，mtime 的日期就是全部含义：
  mtime 日期 = 当日 ⇔ 今日交易日已开门；文件不存在或 mtime 非当日 ⇔ 门关。

  open   交易日才写标志；标志已存在且为当日则跳过、不回写（幂等，mtime 分毫不差）。
         非交易日只做关闭扫尾（rm -f 标志，不移 pending）。
  close  不判交易日：rm -f 标志 + pending/*.json 逐文件 plain mv 进 failed/
         （无 result 注解，与沙箱 gate-close 同口径）。
  status 输出 {"trading_day": bool, "gate_open": bool, …}。

交易日判定：虚拟环境无新浪日历/节假日日历，按周一至周五兜底（§5.4 兜底口径，
不编造节假日）；is_trading_day(date=None) 可 import 直接调用。
仅标准库。
"""

import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

try:  # 北京时间（与 virtual/virtual_ops.py 同口径）
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Shanghai")
except Exception:  # pragma: no cover - 无 tzdata 时回落固定 +08:00
    TZ = timezone(timedelta(hours=8))

REAL_BASE = "/root/monitor"
GATE_FLAG_NAME = ".trading_day"
GATE_LOCK_NAME = ".gate.lock"
# §5.1 受控 4 单元（两边同一清单），拼写逐字照接口规范
UNITS = ["order-watcher.path", "cofool-fillwatch.timer",
         "cofool-monitor-closecheck.timer", "cofool-monitor-fillcheck.timer"]


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def now():
    return datetime.now(TZ)


def today_str():
    return now().strftime("%Y-%m-%d")


def parse_date(text):
    """YYYY-MM-DD -> datetime.date；解析失败返回 None。"""
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except Exception:
        return None


def is_trading_day(date_arg=None):
    """交易日判定：周一至周五为交易日，周六日为非交易日。
    虚拟环境无节假日日历（§5.4：不编造），节假日不特殊处理。
    date_arg 可为 datetime.date / datetime.datetime / None（None 取今天）。"""
    if date_arg is None:
        d = now().date()
    elif isinstance(date_arg, datetime):
        d = date_arg.date()
    else:
        d = date_arg
    return d.weekday() < 5


def flag_state(base):
    """返回 (exists, mtime_date_str, mtime_epoch)。"""
    flag = os.path.join(base, GATE_FLAG_NAME)
    if not os.path.exists(flag):
        return False, None, None
    mtime = datetime.fromtimestamp(os.path.getmtime(flag), tz=TZ)
    return True, mtime.strftime("%Y-%m-%d"), os.path.getmtime(flag)


def gate_open(base, date_text=None):
    """§5.1 标志语义：文件存在且 mtime 日期 == 当日 ⇔ 门开。
    （07:30–17:05 时间窗是执行器 gate_open() 的附加判定，见 §5.2，本函数不折叠。）"""
    target = date_text or today_str()
    exists, mdate, _ = flag_state(base)
    return bool(exists and mdate == target)


def run_systemctl(action, units, dry_run=False):
    """systemctl enable/disable --now；失败不抛异常，返回 (ok, detail)。"""
    cmd = ["systemctl", action, "--now"] + list(units)
    if dry_run:
        return True, "dry-run: %s" % " ".join(cmd)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if p.returncode == 0:
            return True, "ok"
        return False, (p.stderr or p.stdout).strip()[:300]
    except Exception as e:
        return False, repr(e)


def _lock(base):
    """flock（.gate.lock，非阻塞）。抢不到返回 None。"""
    path = os.path.join(base, GATE_LOCK_NAME)
    try:
        fh = open(path, "a+")
    except Exception:
        return None
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except Exception:
        fh.close()
        return None


def _unlock(fh):
    if fh is None:
        return
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()
    except Exception:
        pass


def move_pending_to_failed(base):
    """关门：pending/*.json plain mv 进 failed/（无 result 注解，§5.3）。
    逐文件 os.rename；对端已移走 -> skip；failed 已有同名 -> <name>.dup-<epoch>.json。"""
    pending_dir = os.path.join(base, "order_queue", "pending")
    failed_dir = os.path.join(base, "order_queue", "failed")
    os.makedirs(failed_dir, exist_ok=True)
    moved, skipped, duped = [], [], []
    if not os.path.isdir(pending_dir):
        return moved, skipped, duped
    for fn in sorted(f for f in os.listdir(pending_dir) if f.endswith(".json")):
        src = os.path.join(pending_dir, fn)
        dest = os.path.join(failed_dir, fn)
        try:
            if os.path.exists(dest):
                dest = os.path.join(failed_dir, "%s.dup-%d.json" % (fn[:-5], int(now().timestamp())))
                duped.append(os.path.basename(dest))
            os.rename(src, dest)
            moved.append(fn)
        except FileNotFoundError:
            skipped.append(fn)
        except Exception as e:
            skipped.append("%s(%r)" % (fn, e))
    return moved, skipped, duped


# ---------------------------------------------------------------------------
# 三个动作
# ---------------------------------------------------------------------------
def do_open(base, date_text, dry_run, use_systemd):
    target = date_text or today_str()
    trading = is_trading_day(parse_date(target) if date_text else None)
    out = {"ok": True, "action": "open", "base": base, "date": target,
           "trading_day": trading, "dry_run": dry_run}
    flag = os.path.join(base, GATE_FLAG_NAME)
    exists, mdate, _ = flag_state(base)
    if not trading:
        # 非交易日：只做关闭扫尾（disable --now + rm -f 标志），不移 pending（§5.3）
        out["action"] = "open-noop-nontrading"
        unit_ok, unit_detail = True, "skipped (non-trading day)"
        if use_systemd:
            unit_ok, unit_detail = run_systemctl("disable", UNITS, dry_run)
        out["units"] = {"ok": unit_ok, "detail": unit_detail}
        if exists and not dry_run:
            os.remove(flag)
            out["flag"] = "removed (non-trading day)"
        else:
            out["flag"] = "already absent" if not exists else "dry-run: would remove"
        out["pending"] = "untouched (non-trading day)"
        return out, 0
    if exists and mdate == target:
        out["action"] = "open-skip"
        out["flag"] = "already dated %s, no touch" % target
        out["units"] = {"ok": True, "detail": "skipped (flag already dated)"}
        return out, 0
    unit_ok, unit_detail = True, "skipped"
    if use_systemd:
        unit_ok, unit_detail = run_systemctl("enable", UNITS, dry_run)
        if not unit_ok:  # 保留一次重试；两次失败才返回 1 且不写标志（fail-closed）
            unit_ok, unit_detail2 = run_systemctl("enable", UNITS, dry_run)
            unit_detail = "1st: %s | 2nd: %s" % (unit_detail, unit_detail2)
    out["units"] = {"ok": unit_ok, "detail": unit_detail}
    if use_systemd and not unit_ok:
        out["ok"] = False
        out["flag"] = "not written (enable failed, fail-closed)"
        return out, 1
    if dry_run:
        out["flag"] = "dry-run: would write, dated %s" % target
        return out, 0
    os.makedirs(base, exist_ok=True)
    with open(flag, "a", encoding="utf-8"):
        pass
    os.utime(flag, None)
    out["flag"] = "written, dated %s" % target
    return out, 0


def do_close(base, date_text, dry_run, use_systemd):
    out = {"ok": True, "action": "close", "base": base, "date": date_text or today_str(),
           "dry_run": dry_run}
    flag = os.path.join(base, GATE_FLAG_NAME)
    unit_ok, unit_detail = True, "skipped"
    if use_systemd:
        unit_ok, unit_detail = run_systemctl("disable", UNITS, dry_run)
    out["units"] = {"ok": unit_ok, "detail": unit_detail}
    exists, _, _ = flag_state(base)
    if exists and not dry_run:
        os.remove(flag)
    out["flag"] = ("dry-run: would remove" if (exists and dry_run)
                   else ("removed" if exists else "already absent"))
    moved, skipped, duped = move_pending_to_failed(base) if not dry_run else ([], [], [])
    out["pending"] = {"moved": moved, "skipped": skipped, "dup": duped,
                      "dry_run": dry_run}
    return out, 0


def do_status(base, date_text, use_systemd, dry_run=False):
    target = date_text or today_str()
    trading = is_trading_day(parse_date(target) if date_text else None)
    exists, mdate, mepoch = flag_state(base)
    opened = gate_open(base, target)
    n = now()
    mins = n.hour * 60 + n.minute
    in_window = 7 * 60 + 30 <= mins <= 17 * 60 + 5
    out = {"ok": True, "action": "status", "base": base, "date": target,
           "trading_day": trading, "gate_open": opened,
           "flag": {"exists": exists, "mtime_date": mdate, "mtime_epoch": mepoch,
                    "path": os.path.join(base, GATE_FLAG_NAME)},
           "window": {"now": n.strftime("%Y-%m-%d %H:%M:%S"),
                      "in_0730_1705": in_window},
           "executor_gate_open": bool(opened and in_window)}
    return out, 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv):
    ap = argparse.ArgumentParser(description="本机门控（虚拟环境搭建版）")
    ap.add_argument("action", nargs="?", choices=["open", "close", "status"],
                    help="open | close | status")
    ap.add_argument("--base", default=None, help="数据根目录（默认 /root/monitor/）")
    ap.add_argument("--root", default=None, help="同 --base（测试根目录）")
    ap.add_argument("--date", default=None, help="模拟当日，YYYY-MM-DD")
    ap.add_argument("--dry-run", dest="dry_run", action="store_true",
                    help="只打印、不改状态、不写日志")
    ap.add_argument("--no-systemd", dest="no_systemd", action="store_true",
                    help="跳过 systemctl")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.action:
        print(json.dumps({"ok": False, "error": "缺位置参数：open|close|status"},
                         ensure_ascii=False))
        return 1
    base = os.path.abspath(args.base or args.root or REAL_BASE)
    date_text = args.date
    if date_text is not None and parse_date(date_text) is None:
        print(json.dumps({"ok": False, "error": "日期须为 YYYY-MM-DD：%s" % date_text},
                         ensure_ascii=False))
        return 1
    # systemd 只在真实根目录执行；测试根目录一律跳过，避免误动本机单元
    use_systemd = (not args.no_systemd) and (base == os.path.abspath(REAL_BASE))
    lock = _lock(base)
    if lock is None:
        print(json.dumps({"ok": True, "action": args.action, "skipped": "lock_busy",
                          "detail": "another gate run holds the lock, skip"},
                         ensure_ascii=False))
        return 0
    try:
        if args.action == "open":
            out, rc = do_open(base, date_text, args.dry_run, use_systemd)
        elif args.action == "close":
            out, rc = do_close(base, date_text, args.dry_run, use_systemd)
        else:
            out, rc = do_status(base, date_text, use_systemd, args.dry_run)
        out["systemd_used"] = use_systemd
        print(json.dumps(out, ensure_ascii=False))
        return rc
    finally:
        _unlock(lock)


if __name__ == "__main__":
    sys.exit(main())
