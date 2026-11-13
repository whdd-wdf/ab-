#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盒内 AI 对接虚拟程序：一轮管控（选股→把关→辩论→提交→成交确认）。
只调本地 Ollama qwen2.5:3b，只读写虚拟目录（默认 /workspace/ab-/virtual）内虚拟文件。
数字一律由程序算好：选股前先逐只调 virtual_ops.py check 拼表喂给 AI，
AI 只做判断、不自己算；定稿后须复述三元组（代码/名称/现价）与 quotes 比对；
辩论前再由程序复核五项（数据复核步，不经 AI），任一不符即停。
运行（盒内）：nohup python3 /workspace/run_virtual_control.py > /workspace/vc_runner.log 2>&1 &
干跑（沙箱验证，不调 Ollama）：python3 run_virtual_control.py --dry-run
  （VC_BASE/VC_WORKDIR 环境变量可改虚拟目录与产物目录，默认盒内路径）
产物：virtual_control_log.md（全程记录）、vc_step_*.txt（AI 原文）、
      vc_summary.json（解析出的关键值与时间戳，供沙箱核实）。
"""
import argparse, json, os, re, subprocess, sys, time, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

BASE = os.environ.get("VC_BASE", "/workspace/ab-/virtual")
WORKDIR = os.environ.get("VC_WORKDIR", "/workspace")
LOG = os.path.join(WORKDIR, "virtual_control_log.md")
SUMMARY = os.path.join(WORKDIR, "vc_summary.json")
OLLAMA = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"
CST = timezone(timedelta(hours=8))

# 干跑模式开关（main 里由命令行参数设置）
DRY_RUN = False
DRY_RUN_BAD_TRIPLE = False
DRY_PICK = None  # 干跑定稿候选：{"code","name","price","qty"}，取自 check 表

# 正例/反例（97 字）：涨幅闸门只看“涨幅≤5%”，负涨幅也通过，跌得多≠该买。
EXAMPLE = ("正例：某股涨 1.41%，涨幅 1.41%≤5%，闸门通过；反例：某股跌 -48.77%，"
           "涨幅 -48.77%也通过（≤5%指涨幅不超过5%，不是必须下跌、更不是跌得越多越好），"
           "下跌股另看趋势。")

def now_cst():
    return datetime.now(CST)

def ts():
    return now_cst().strftime("%Y-%m-%d %H:%M:%S")

def r2(x):
    # 与 virtual_ops.py 的 r2 同口径：round(x + 1e-9, 2)，辩论前复核比对涨幅时用。
    return round(float(x) + 1e-9, 2)

def log(msg):
    line = "[%s CST] %s" % (ts(), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def save_step(name, prompt, output):
    with open(os.path.join(WORKDIR, "vc_step_%s.txt" % name), "w", encoding="utf-8") as f:
        f.write("=== PROMPT ===\n%s\n\n=== OUTPUT ===\n%s\n" % (prompt, output))
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("\n## 步骤 %s AI 输出原文\n\n%s\n" % (name, output))

def restart_ollama():
    log("重启 Ollama 释内存…")
    for cmd in (["systemctl", "restart", "ollama"],
                ["sudo", "-n", "systemctl", "restart", "ollama"]):
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            break
        log("重启命令失败(%s)：%s" % (" ".join(cmd), (r.stderr or "")[:200]))
    else:
        log("Ollama 重启失败，继续重试调用")
    time.sleep(25)

def dry_fake(label):
    """干跑假回复：按步骤返回固定文本，不调 Ollama。定稿取 DRY_PICK
    （check 表里第一只四 gates 全过的候选，买入价=现价、数量=表中股数）。"""
    if label == "步骤A选股":
        p = DRY_PICK or {"code": "600919", "name": "江苏银行", "price": 12.98, "qty": 3800}
        restated_price = p["price"] + 1.00 if DRY_RUN_BAD_TRIPLE else p["price"]
        return ("按程序算好的表判断：%s %s 现价 %.2f，涨幅在 5%% 以内，P4 与金额闸门均通过，挑这只。\n"
                "定稿：代码%s，买入价%.2f，数量%d股\n"
                "复述：代码%s，名称%s，现价%.2f"
                % (p["code"], p["name"], p["price"], p["code"], p["price"], p["qty"],
                   p["code"], p["name"], restated_price))
    if label == "步骤B把关":
        return ("逐项读数：1）涨幅通过；2）买入价≤P4 通过；3）金额≥5000 通过；4）金额≤50000 通过；"
                "5）金额≤可用资金通过；6）持仓 1 只≤3 只通过；7）买价≈现价、偏差≤1% 通过。\n合规结论：通过")
    if label == "步骤C保守方":
        return "保守方意见：价格与涨幅虽在闸门内，但尾盘买入仍有隔夜风险，倾向观望。\n保守方结论：跳过"
    if label == "步骤C激进方":
        return "激进方意见：涨幅、P4、金额、偏差四项闸门全通过，现价买入符合 B 线右侧逻辑。\n激进方结论：买"
    if label == "步骤C评判":
        return "综合双方：四项闸门全通过，保守方风险提示不足以否决，决定买入。\n裁决：买，置信度0.80"
    if label == "步骤D成交确认":
        return "快照 fills_today 与 trade_log 均有这笔买入成交，延时符合预期。\n成交确认：已确认"
    return "干跑假回复（未匹配步骤）：%s" % label

def call_ollama(prompt, num_predict, label):
    """调一次本地模型；500/异常则重启 Ollama 后重试一次。返回 (output, seconds, attempts)。
    干跑模式不调 Ollama，直接返回固定假回复。"""
    if DRY_RUN:
        out = dry_fake(label)
        log("%s 干跑：返回固定假回复，%d 字" % (label, len(out)))
        return out, 0.0, 1
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False,
                       "options": {"num_ctx": 8192, "temperature": 0.2,
                                   "num_predict": num_predict}}).encode("utf-8")
    attempts = 0
    while attempts < 2:
        attempts += 1
        t0 = time.time()
        try:
            req = urllib.request.Request(OLLAMA, data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=1500) as resp:
                out = json.loads(resp.read().decode("utf-8"))["response"]
            dt = time.time() - t0
            log("%s 成功：attempt=%d 耗时 %.0f 秒，输出 %d 字" % (label, attempts, dt, len(out)))
            return out.strip(), dt, attempts
        except urllib.error.HTTPError as e:
            dt = time.time() - t0
            log("%s 失败：HTTP %s，attempt=%d，耗时 %.0f 秒" % (label, e.code, attempts, dt))
            if attempts < 2:
                restart_ollama()
        except Exception as e:
            dt = time.time() - t0
            log("%s 异常：%r，attempt=%d，耗时 %.0f 秒" % (label, e, attempts, dt))
            if attempts < 2:
                restart_ollama()
    return None, None, attempts

def run_cmd(args, label):
    t0 = time.time()
    r = subprocess.run(args, capture_output=True, text=True, cwd=BASE, timeout=120)
    dt = time.time() - t0
    log("%s：exit=%d 耗时 %.1f 秒，输出：%s" % (label, r.returncode, dt,
          (r.stdout or r.stderr or "")[:800]))
    return r

def run_check(code, buy_price=None):
    """调虚拟程序 check 接口（只读、不下单），返回解析后的 dict；失败返回 None。
    买价不传取当前价；传了则按该买价算涨幅/偏差/P4/股数/金额/gates。"""
    args = ["python3", "virtual_ops.py", "check", code]
    if buy_price is not None:
        args.append(str(buy_price))
    r = run_cmd(args, "check %s" % code)
    if r.returncode != 0:
        log("check %s 失败：%s" % (code, (r.stdout or r.stderr or "")[:200]))
        return None
    try:
        chk = json.loads(r.stdout)
    except Exception as e:
        log("check %s 输出不是 JSON：%r" % (code, e))
        return None
    if not chk.get("ok"):
        log("check %s 未返回 ok：%s" % (code, r.stdout[:200]))
        return None
    return chk

def main(argv=None):
    global DRY_RUN, DRY_RUN_BAD_TRIPLE, DRY_PICK
    ap = argparse.ArgumentParser(description="盒内 AI 对接虚拟程序：一轮管控（选股→把关→辩论→提交→成交确认）")
    ap.add_argument("--dry-run", action="store_true",
                    help="干跑：不调 Ollama，按步骤返回固定假回复，走通完整链路")
    ap.add_argument("--dry-run-bad-triple", action="store_true",
                    help="干跑：步骤 A 的复述现价故意写错，验证三元组不符即停、不进把关")
    args = ap.parse_args(argv)
    DRY_RUN = bool(args.dry_run or args.dry_run_bad_triple)
    DRY_RUN_BAD_TRIPLE = bool(args.dry_run_bad_triple)

    os.makedirs(WORKDIR, exist_ok=True)
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("# 虚拟程序对接测试：盒内 AI 一轮管控实录\n\n开始时间 %s CST\n\n" % ts())
    log("脚本启动。模型=%s，虚拟目录=%s，干跑=%s（错三元组=%s）"
        % (MODEL, BASE, DRY_RUN, DRY_RUN_BAD_TRIPLE))
    summary = {"started_cst": ts(), "steps": {},
               "dry_run": DRY_RUN, "dry_run_bad_triple": DRY_RUN_BAD_TRIPLE}

    quotes = json.load(open(os.path.join(BASE, "quotes.json"), encoding="utf-8"))
    quota = json.load(open(os.path.join(BASE, "virtual_quota.json"), encoding="utf-8"))
    b_avail = quota["B"]["available"]
    # 门控自查（基础设施，不经 AI）
    flag = os.path.join(BASE, ".trading_day")
    gate = os.path.exists(flag) and datetime.fromtimestamp(
        os.path.getmtime(flag), tz=CST).strftime("%Y-%m-%d") == now_cst().strftime("%Y-%m-%d")
    log("门控标志 .trading_day 当日=%s，B线可用=%.2f，B线持仓=%s" % (gate, b_avail, quota["B"]["holdings"]))
    summary["gate_open"] = gate
    summary["b_available"] = b_avail
    if not gate:
        log("门未开，停止"); json.dump(summary, open(SUMMARY, "w"), ensure_ascii=False, indent=2); return

    # ---- 程序预计算表（建议 1）：选股前先逐只调 check，拼表喂给 AI ----
    cand_codes = ["600176", "002475", "000596", "600919", "600018", "603198", "000001", "600000"]
    checks = {}
    cand_lines = []
    for code in cand_codes:
        chk = run_check(code)
        if chk is None:
            log("候选 %s 的 check 失败，跳过该只" % code)
            continue
        checks[code] = chk
        g = chk["gates"]
        cand_lines.append(
            "%s %s：前收 %.2f，现价 %.2f，涨幅 %.2f%%，P4 %.2f，股数 %d，金额 %.2f，"
            "gates 涨幅%s/P4%s/偏差%s/金额%s"
            % (code, chk["name"], chk["prev_close"], chk["price"],
               chk["change_pct"] * 100, chk["p4_limit"], chk["qty_50k"],
               chk["amount_50k"],
               "✓" if g["rise_ok"] else "✗", "✓" if g["p4_ok"] else "✗",
               "✓" if g["deviation_ok"] else "✗", "✓" if g["amount_ok"] else "✗"))
    if not cand_lines:
        log("8 只候选 check 全失败，停止")
        summary["steps"]["precheck"] = {"ok": False}
        json.dump(summary, open(SUMMARY, "w"), ensure_ascii=False, indent=2); return
    cand_table = "\n".join(cand_lines)
    summary["steps"]["precheck"] = {"ok": True, "codes": sorted(checks)}
    log("程序预计算表已拼好，共 %d 只候选" % len(cand_lines))
    # 干跑定稿候选：第一只四 gates 全过的（买入价=现价、数量=表中股数）
    for code in cand_codes:
        chk = checks.get(code)
        if chk and all(chk["gates"].values()):
            DRY_PICK = {"code": code, "name": chk["name"],
                        "price": chk["price"], "qty": chk["qty_50k"]}
            break
    if DRY_PICK is None:
        code0 = next((c for c in cand_codes if c in checks), None)
        if code0:
            DRY_PICK = {"code": code0, "name": checks[code0]["name"],
                        "price": checks[code0]["price"], "qty": checks[code0]["qty_50k"]}

    # ---- 步骤 A：选股（只读程序算好的表，不自己算） ----
    prompt_a = (
        "你是 B 线尾盘选股员。今天是 2026-11-13，B 线目前空仓（0 只），B 线可用资金 %.2f 元。\n"
        "下面是 8 只候选股的表，涨幅、P4、股数、金额都是程序算好的，"
        "你只做判断、不自己算，禁止自己重算：\n%s\n\n"
        "B 线买入闸门（直接读表，不用算）：涨幅须≤5%%；买入价取现价，须≤P4限价；"
        "单笔金额须≥5000 元且≤50000 元；买入后 B 线持仓≤3 只。\n"
        "%s\n"
        "任务：从表中挑 1 只（优先四 gates 全通过的），写出挑股理由（只能用上表数字），"
        "买入价取现价、数量取表中股数。"
        "控制在 600 字以内。倒数第二行按此格式写：定稿：代码XXXXXX，买入价X.XX，数量Y股。"
        "最后一行按此格式写：复述：代码XXXXXX，名称XXX，现价X.XX（名称与现价抄上表）。"
        % (b_avail, cand_table, EXAMPLE))
    out_a, dt_a, att_a = call_ollama(prompt_a, 800, "步骤A选股")
    summary["steps"]["A_pick"] = {"seconds": dt_a, "attempts": att_a, "ok": out_a is not None}
    if out_a is None:
        log("步骤A失败，停止"); json.dump(summary, open(SUMMARY, "w"), ensure_ascii=False, indent=2); return
    save_step("A_pick", prompt_a, out_a)

    m = re.search(r"定稿：代码(\d{6})，买入价([\d.]+)，数量(\d+)股", out_a)
    if not m:
        log("步骤A未按格式给定稿行（正则未命中），停止，不替 AI 猜数字")
        summary["steps"]["A_pick"]["parse"] = "定稿行未命中"
        json.dump(summary, open(SUMMARY, "w"), ensure_ascii=False, indent=2); return
    code, price, qty = m.group(1), float(m.group(2)), int(m.group(3))
    # ---- 三元组复述比对（建议 2）：复述行须与 quotes 的名称/现价一致，否则即停 ----
    mt = re.search(r"复述：代码(\d{6})，名称(.+?)，现价([\d.]+)", out_a)
    triple = {"ok": False}
    if mt:
        triple = {"code": mt.group(1), "name": mt.group(2).strip(),
                  "price": float(mt.group(3))}
    q = quotes.get(code)
    triple_ok = (mt is not None and q is not None and triple["code"] == code
                 and triple["name"] == q["name"]
                 and abs(triple["price"] - q["price"]) <= 0.01)
    summary["steps"]["A_pick"]["triple"] = triple
    summary["steps"]["A_pick"]["triple_ok"] = triple_ok
    if not triple_ok:
        log("三元组复述与 quotes 不符，停止，不替 AI 猜：定稿代码=%s 复述=%s quotes=%s"
            % (code, triple, ({"name": q["name"], "price": q["price"]} if q else None)))
        summary["triple_mismatch"] = {"pick_code": code, "restated": triple,
                                      "quotes": ({"name": q["name"], "price": q["price"]} if q else None)}
        json.dump(summary, open(SUMMARY, "w"), ensure_ascii=False, indent=2); return
    log("三元组复述与 quotes 一致：代码=%s 名称=%s 现价=%.2f" % (code, triple["name"], triple["price"]))
    prev_close = quotes[code]["prev_close"]
    p4 = round(prev_close * 1.03, 2)
    amount = round(price * qty, 2)
    log("步骤A解析：代码=%s 买入价=%s 数量=%d 金额=%.2f 前收=%.2f P4=%.2f" % (code, price, qty, amount, prev_close, p4))
    summary["pick"] = {"code": code, "name": quotes[code]["name"], "price": price,
                       "qty": qty, "amount": amount, "prev_close": prev_close, "p4": p4,
                       "triple_ok": True}

    # ---- 步骤 B：把关（直接给该只的 check 输出，AI 只读数判断，不自己算） ----
    chk_b = run_check(code, price)
    if chk_b is None:
        log("步骤B的 check 失败，停止")
        summary["steps"]["B_gate"] = {"ok": False, "error": "check 失败"}
        json.dump(summary, open(SUMMARY, "w"), ensure_ascii=False, indent=2); return
    gb = chk_b["gates"]
    prompt_b = (
        "你是 B 线合规把关员。对下面这笔买单逐项读数判断合规，每项只写“通过”或“不通过”"
        "（数字都是程序算好的，不用自己算，禁止自己重算）。\n"
        "买单：代码 %s（%s），买入价 %.2f，数量 %d 股，前收 %.2f，本笔金额 %.2f 元。\n"
        "程序 check 输出（买入价 %.2f）：涨幅 %.2f%%，P4限价 %.2f，偏差 %.2f%%，"
        "按 5 万上限股数 %d、金额 %.2f，gates 涨幅%s/P4%s/偏差%s/金额%s。\n"
        "B 线状态：当前持仓 0 只，可用资金 %.2f 元。\n"
        "%s\n"
        "逐项读数判断：1）涨幅≤5%%；2）买入价≤P4限价；3）金额≥5000 元；"
        "4）金额≤50000 元（单只上限）；5）金额≤B 线可用资金；6）买入后持仓 1 只≤3 只；"
        "7）买价≈现价：偏差≤1%%。\n"
        "每项写“通过”或“不通过”。最后一行写：合规结论：通过 或 合规结论：拒绝。控制在 500 字以内。"
        % (code, quotes[code]["name"], price, qty, prev_close, amount,
           chk_b["buy_price"], chk_b["change_pct"] * 100, chk_b["p4_limit"],
           chk_b["deviation_pct"] * 100, chk_b["qty_50k"], chk_b["amount_50k"],
           "通过" if gb["rise_ok"] else "不通过", "通过" if gb["p4_ok"] else "不通过",
           "通过" if gb["deviation_ok"] else "不通过", "通过" if gb["amount_ok"] else "不通过",
           b_avail, EXAMPLE))
    out_b, dt_b, att_b = call_ollama(prompt_b, 800, "步骤B把关")
    summary["steps"]["B_gate"] = {"seconds": dt_b, "attempts": att_b, "ok": out_b is not None}
    if out_b is None:
        log("步骤B失败，停止"); json.dump(summary, open(SUMMARY, "w"), ensure_ascii=False, indent=2); return
    save_step("B_gate", prompt_b, out_b)
    b_pass = "合规结论：通过" in out_b
    log("步骤B解析：合规结论=%s" % ("通过" if b_pass else "拒绝/未明"))
    summary["gate_ai"] = "通过" if b_pass else "拒绝或未明"

    # ---- 程序数据复核（建议 5）：步骤 B 之后、步骤 C 之前，不经 AI ----
    chk_d = run_check(code, price)
    if chk_d is None:
        log("辩论前复核的 check 失败，停止")
        summary["pre_debate_check"] = {"ok": False, "failures": ["check 失败"]}
        json.dump(summary, open(SUMMARY, "w"), ensure_ascii=False, indent=2); return
    failures = []
    qd = quotes.get(code)
    if qd is None or triple["name"] != qd["name"] or abs(price - qd["price"]) > 0.01:
        failures.append("三元组不符：定稿买入价/名称与 quotes 不一致")
    rise_pick = r2((price - prev_close) / prev_close)
    if abs(rise_pick - chk_d["change_pct"]) > 0.0001:
        failures.append("涨幅不符：定稿涨幅 %.4f 与 check change_pct %.4f 不一致"
                        % (rise_pick, chk_d["change_pct"]))
    if abs(p4 - chk_d["p4_limit"]) > 0.01:
        failures.append("P4 不符：定稿 P4 %.2f 与 check p4_limit %.2f 不一致"
                        % (p4, chk_d["p4_limit"]))
    if qty != chk_d["qty_50k"]:
        failures.append("股数不符：定稿 %d 股与 check qty_50k %d 不一致" % (qty, chk_d["qty_50k"]))
    if abs(amount - chk_d["amount_50k"]) > 0.01:
        failures.append("金额不符：定稿金额 %.2f 与 check amount_50k %.2f 不一致"
                        % (amount, chk_d["amount_50k"]))
    summary["pre_debate_check"] = {"ok": not failures, "failures": failures, "check": chk_d}
    if failures:
        log("辩论前程序复核不通过，跳过辩论、脚本结束：%s" % "; ".join(failures))
        json.dump(summary, open(SUMMARY, "w"), ensure_ascii=False, indent=2); return
    log("辩论前程序复核通过：三元组/涨幅/P4/股数/金额五项一致")

    # ---- 步骤 C：辩论（三方分三次调用）----
    debate_data = ("候选股：%s %s，前收 %.2f，现价 %.2f，涨幅 %.2f%%，拟买入价 %.2f，数量 %d 股，金额 %.2f 元。"
                   % (code, quotes[code]["name"], prev_close, quotes[code]["price"],
                      (quotes[code]["price"] / prev_close - 1) * 100, price, qty, amount))
    prompt_c1 = ("你是辩论保守方。%s\n只讲反对买入的理由和风险（价格、涨幅、金额、仓位），"
                 "限 300 字。最后一行写：保守方结论：买 或 保守方结论：跳过。" % debate_data)
    out_c1, dt_c1, att_c1 = call_ollama(prompt_c1, 500, "步骤C保守方")
    summary["steps"]["C_con"] = {"seconds": dt_c1, "attempts": att_c1, "ok": out_c1 is not None}
    if out_c1 is None:
        log("保守方失败，停止"); json.dump(summary, open(SUMMARY, "w"), ensure_ascii=False, indent=2); return
    save_step("C_conservative", prompt_c1, out_c1)

    prompt_c2 = ("你是辩论激进方。%s\n只讲支持买入的理由（价格、涨幅、金额、仓位），"
                 "限 300 字。最后一行写：激进方结论：买 或 激进方结论：跳过。" % debate_data)
    out_c2, dt_c2, att_c2 = call_ollama(prompt_c2, 500, "步骤C激进方")
    summary["steps"]["C_pro"] = {"seconds": dt_c2, "attempts": att_c2, "ok": out_c2 is not None}
    if out_c2 is None:
        log("激进方失败，停止"); json.dump(summary, open(SUMMARY, "w"), ensure_ascii=False, indent=2); return
    save_step("C_aggressive", prompt_c2, out_c2)

    prompt_c3 = ("你是辩论评判。候选股数据：%s\n保守方意见：\n%s\n激进方意见：\n%s\n"
                 "综合双方，决定买入还是跳过，并给置信度（0 到 1 之间的小数，写数字）。"
                 "限 300 字。最后一行按格式写：裁决：买，置信度0.XX 或 裁决：跳过，置信度0.XX。"
                 % (debate_data, out_c1, out_c2))
    out_c3, dt_c3, att_c3 = call_ollama(prompt_c3, 500, "步骤C评判")
    summary["steps"]["C_judge"] = {"seconds": dt_c3, "attempts": att_c3, "ok": out_c3 is not None}
    if out_c3 is None:
        log("评判失败，停止"); json.dump(summary, open(SUMMARY, "w"), ensure_ascii=False, indent=2); return
    save_step("C_judge", prompt_c3, out_c3)
    mj = re.search(r"裁决：(买|跳过)，置信度([\d.]+)", out_c3)
    if mj:
        verdict, conf = mj.group(1), float(mj.group(2))
    else:
        verdict, conf = ("买" if "裁决：买" in out_c3 else "跳过"), None
        log("评判未按格式给裁决行，置信度未解析到")
    log("步骤C解析：裁决=%s 置信度=%s" % (verdict, conf))
    summary["debate"] = {"verdict": verdict, "confidence": conf}

    # ---- 步骤 D：提交与跟进 ----
    if not (b_pass and verdict == "买" and conf is not None and conf >= 0.7):
        log("不提交：把关=%s，裁决=%s，置信度=%s（须把关通过且裁决买且置信度≥0.7 才提交）"
            % ("通过" if b_pass else "拒绝/未明", verdict, conf))
        summary["submit"] = {"submitted": False,
                             "reason": "gate=%s verdict=%s conf=%s" % ("通过" if b_pass else "拒绝", verdict, conf)}
        json.dump(summary, open(SUMMARY, "w"), ensure_ascii=False, indent=2)
        log("脚本结束（跳过，不下单）"); return

    order = {"order_id": "B-20261113-%s-1" % code, "code": code, "side": "买入",
             "price": price, "qty": qty, "line": "B", "prev_close": prev_close,
             "limit_price": p4}
    with open("/tmp/vc_order.json", "w", encoding="utf-8") as f:
        json.dump(order, f, ensure_ascii=False)
    log("订单 JSON：%s" % json.dumps(order, ensure_ascii=False))
    t_submit = now_cst()
    summary["submit"] = {"submitted": True, "order": order,
                         "submit_cst": t_submit.strftime("%Y-%m-%d %H:%M:%S")}
    r = run_cmd(["python3", "virtual_ops.py", "submit", "/tmp/vc_order.json"], "提交订单")
    if r.returncode != 0:
        log("提交失败，停止"); json.dump(summary, open(SUMMARY, "w"), ensure_ascii=False, indent=2); return
    run_cmd(["python3", "virtual_ops.py", "run"], "执行器 run")
    r = run_cmd(["python3", "virtual_ops.py", "snapshot"], "快照 snapshot")
    t_snap = now_cst()
    delay = (t_snap - t_submit).total_seconds()
    summary["submit"]["snapshot_cst"] = t_snap.strftime("%Y-%m-%d %H:%M:%S")
    summary["submit"]["delay_seconds"] = delay
    log("提交→快照延时 %.0f 秒" % delay)
    snap_files = sorted(os.listdir(os.path.join(BASE, "snapshots")))
    snap = json.load(open(os.path.join(BASE, "snapshots", snap_files[-1]), encoding="utf-8"))
    log("最新快照 %s：status=%s fills_today=%s" % (snap_files[-1], snap.get("status"), snap.get("fills_today")))
    r = run_cmd(["python3", "virtual_ops.py", "log", "5"], "trade_log 尾部")
    summary["submit"]["snapshot_file"] = snap_files[-1]
    summary["submit"]["snapshot"] = snap

    # ---- 步骤 D2：AI 读快照检出成交、报延时 ----
    fills = snap.get("fills_today", [])
    fill_txt = json.dumps(fills, ensure_ascii=False) if fills else "（无成交）"
    log_tail = r.stdout.strip()[-1200:]
    prompt_d = (
        "你是成交确认员。B 线买单已提交虚拟执行器，提交时间 %s，快照时间 %s。\n"
        "最新快照 fills_today：%s\n虚拟 trade_log 尾部：\n%s\n"
        "任务：1）指出快照里这笔买单是否成交（写出代码、价格、数量）；"
        "2）算延时=快照时间−提交时间，写出算式和结果（单位：秒）；3）确认 trade_log 里有没有这笔成交行。"
        "最后一行写：成交确认：已确认 或 成交确认：未确认。控制在 400 字以内。"
        % (t_submit.strftime("%H:%M:%S"), t_snap.strftime("%H:%M:%S"), fill_txt, log_tail))
    out_d, dt_d, att_d = call_ollama(prompt_d, 500, "步骤D成交确认")
    summary["steps"]["D_confirm"] = {"seconds": dt_d, "attempts": att_d, "ok": out_d is not None}
    if out_d is not None:
        save_step("D_confirm", prompt_d, out_d)
        log("步骤D解析：%s" % ("已确认" if "成交确认：已确认" in out_d else "未确认/未明"))
        summary["submit"]["ai_confirmed"] = "成交确认：已确认" in out_d
    log("脚本结束")
    json.dump(summary, open(SUMMARY, "w"), ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
