#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盒内 AI 对接虚拟程序：一轮管控（选股→把关→辩论→提交→成交确认）。
只调本地 Ollama qwen2.5:3b，只读写 /workspace/ab-/virtual/ 内虚拟文件。
每一步提示词只给原始数字与规则，不给结论；AI 自己算、自己输出。
运行：nohup python3 /workspace/run_virtual_control.py > /workspace/vc_runner.log 2>&1 &
产物：/workspace/virtual_control_log.md（全程记录）、/workspace/vc_step_*.txt（AI 原文）、
      /workspace/vc_summary.json（解析出的关键值与时间戳，供沙箱核实）。
"""
import json, os, re, subprocess, sys, time, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

BASE = "/workspace/ab-/virtual"
LOG = "/workspace/virtual_control_log.md"
SUMMARY = "/workspace/vc_summary.json"
OLLAMA = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"
CST = timezone(timedelta(hours=8))

def now_cst():
    return datetime.now(CST)

def ts():
    return now_cst().strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
    line = "[%s CST] %s" % (ts(), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def save_step(name, prompt, output):
    with open("/workspace/vc_step_%s.txt" % name, "w", encoding="utf-8") as f:
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

def call_ollama(prompt, num_predict, label):
    """调一次本地模型；500/异常则重启 Ollama 后重试一次。返回 (output, seconds, attempts)。"""
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

def main():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("# 虚拟程序对接测试：盒内 AI 一轮管控实录\n\n开始时间 %s CST\n\n" % ts())
    log("脚本启动。模型=%s，虚拟目录=%s" % (MODEL, BASE))
    summary = {"started_cst": ts(), "steps": {}}

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

    cand_lines = []
    for code in ["600176", "002475", "000596", "600919", "600018", "603198", "000001", "600000"]:
        q = quotes[code]
        cand_lines.append("%s %s：前收 %.2f，现价 %.2f" % (code, q["name"], q["prev_close"], q["price"]))
    cand_table = "\n".join(cand_lines)

    # ---- 步骤 A：选股 ----
    prompt_a = (
        "你是 B 线尾盘选股员。今天是 2026-11-13，B 线目前空仓（0 只），B 线可用资金 %.2f 元。\n"
        "下面是 8 只候选股的虚拟行情（只有前收和现价两个数字）：\n%s\n\n"
        "B 线买入闸门：涨幅=(现价-前收)/前收×100%%，须≤5%%；买入价取现价，须≤P4限价（P4限价=前收×1.03）；"
        "单笔金额须≥5000 元且≤50000 元；买入后 B 线持仓≤3 只。\n"
        "任务：逐只算出涨幅（写出算式和结果），筛掉涨幅>5%% 的，从剩下的里挑 1 只，写出挑股理由（只能用上表数字），"
        "并定买入价（取现价）和股数（100 的整数倍，使金额在 5000 到 50000 元之间，写出金额乘法算式）。"
        "控制在 600 字以内。最后一行按此格式写：定稿：代码XXXXXX，买入价X.XX，数量Y股。"
        % (b_avail, cand_table))
    out_a, dt_a, att_a = call_ollama(prompt_a, 800, "步骤A选股")
    summary["steps"]["A_pick"] = {"seconds": dt_a, "attempts": att_a, "ok": out_a is not None}
    if out_a is None:
        log("步骤A失败，停止"); json.dump(summary, open(SUMMARY, "w"), ensure_ascii=False, indent=2); return
    save_step("A_pick", prompt_a, out_a)

    m = re.search(r"定稿：代码(\d{6})，买入价([\d.]+)，数量(\d+)股", out_a)
    if not m:
        m2 = re.search(r"代码\D{0,3}(\d{6})", out_a)
        log("步骤A未按格式给定稿行（正则未命中），停止，不替 AI 猜数字")
        summary["steps"]["A_pick"]["parse"] = "定稿行未命中"
        json.dump(summary, open(SUMMARY, "w"), ensure_ascii=False, indent=2); return
    code, price, qty = m.group(1), float(m.group(2)), int(m.group(3))
    prev_close = quotes[code]["prev_close"]
    p4 = round(prev_close * 1.03, 2)
    amount = round(price * qty, 2)
    log("步骤A解析：代码=%s 买入价=%s 数量=%d 金额=%.2f 前收=%.2f P4=%.2f" % (code, price, qty, amount, prev_close, p4))
    summary["pick"] = {"code": code, "name": quotes[code]["name"], "price": price,
                       "qty": qty, "amount": amount, "prev_close": prev_close, "p4": p4}

    # ---- 步骤 B：把关 ----
    prompt_b = (
        "你是 B 线合规把关员。对下面这笔买单逐项验算合规，每项写出算式和结果，最后给结论。\n"
        "买单：代码 %s（%s），买入价 %.2f，数量 %d 股，前收 %.2f，P4限价 %.2f。\n"
        "B 线状态：当前持仓 0 只，可用资金 %.2f 元。\n"
        "逐项验算：1）涨幅=(买入价-前收)/前收×100%%，须≤5%%；2）买入价≤P4限价；3）金额=买入价×数量，须≥5000 元；"
        "4）金额须≤50000 元（单只上限）；5）金额≤B 线可用资金；6）买入后持仓 1 只≤3 只。\n"
        "每项写“通过”或“不通过”。最后一行写：合规结论：通过 或 合规结论：拒绝。控制在 500 字以内。"
        % (code, quotes[code]["name"], price, qty, prev_close, p4, b_avail))
    out_b, dt_b, att_b = call_ollama(prompt_b, 800, "步骤B把关")
    summary["steps"]["B_gate"] = {"seconds": dt_b, "attempts": att_b, "ok": out_b is not None}
    if out_b is None:
        log("步骤B失败，停止"); json.dump(summary, open(SUMMARY, "w"), ensure_ascii=False, indent=2); return
    save_step("B_gate", prompt_b, out_b)
    b_pass = "合规结论：通过" in out_b
    log("步骤B解析：合规结论=%s" % ("通过" if b_pass else "拒绝/未明"))
    summary["gate_ai"] = "通过" if b_pass else "拒绝或未明"

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
