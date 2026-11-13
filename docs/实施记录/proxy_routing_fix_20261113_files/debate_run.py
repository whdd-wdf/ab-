#!/usr/bin/env python3
"""B线多 Agent 辩论决策 · 运行器（debate_run.py）。DESIGN.md §6。
流程：建包 → 取 Key → 每只持仓调 hub 三次（保守/激进/评判；辩论方失败时各重试一次）→ 解析 judge JSON
（不合格重试 ≤2 次，仍不合格记 log 并判 hold）→ 跑闸门 → 写日志 → 打印摘要。
影子模式只记日志、不下单；执行模式闸门通过且 action≠hold 时输出执行请求（供 cron worker 用浏览器下单）。
用法：python3 debate_run.py [--time 1000|1030|1400] [--mode shadow|execute] [--no-breadth]
Key 只存内存，绝不打印、绝不写日志。hub 经沙箱 Tailscale 隧道代理（端口 3130）访问。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
    CST = ZoneInfo("Asia/Shanghai")
except Exception:
    CST = timezone(timedelta(hours=8))

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import debate_packet  # noqa: E402
import debate_prompts as prompts  # noqa: E402
import debate_gate as gate  # noqa: E402

HUB_BASE = "http://100.125.193.42:3001/v1"
STATE_FILE = os.path.join(BASE, "debate_state.json")
LOGS_DIR = os.path.join(BASE, "logs")
SSH_BASE = ["ssh", "-i", "/home/hatch/.ssh/id_ed25519", "-o", "IdentitiesOnly=yes",
            "-o", "UserKnownHostsFile=/home/hatch/.ssh/known_hosts",
            "-o", "StrictHostKeyChecking=no", "-p", "64646",
            "-o", "ProxyCommand=nc -X connect -x 198.19.0.1:3128 %h %p",
            "root@137.175.6.84"]
REMOTE_KEY_CMD = (
    "python3 -c \"import sqlite3; "
    "db=sqlite3.connect('/var/lib/docker/volumes/freellmapi_freellmapi-data/_data/freeapi.db'); "
    "print(db.execute(\\\"SELECT value FROM settings WHERE key='unified_api_key'\\\").fetchone()[0])\""
)


def get_hub_key(timeout=60):
    """SSH 美国 VPS 查 sqlite 取 hub 统一 Key。只返回内存值，绝不打印。"""
    r = subprocess.run(SSH_BASE + [REMOTE_KEY_CMD], capture_output=True, text=True,
                       timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError("取 hub Key 失败（ssh rc=%s）：%s"
                           % (r.returncode, (r.stderr or "")[:300]))
    key = (r.stdout or "").strip()
    if len(key) < 20:
        raise RuntimeError("取 hub Key 失败：返回值长度异常（len=%d）" % len(key))
    return key


def _env_proxy_url():
    """沙箱出口代理原值（HTTPS_PROXY 等，端口 3128）：走公网。"""
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = (os.environ.get(var) or "").strip()
        if v:
            return v.rstrip("/")
    return None


def _tunnel_proxy_url():
    """沙箱访问 Tailscale 须走运行时隧道代理：出口代理端口 3128 → 3130。"""
    base = _env_proxy_url()
    if base and base.endswith(":3128"):
        return base[:-5] + ":3130"
    return base


def _is_tailscale_url(url):
    """Tailscale 内网地址：100.64.0.0/10（100.x.x.x）或 *.ts.net。"""
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if host.endswith(".ts.net"):
        return True
    parts = host.split(".")
    return len(parts) == 4 and parts[0] == "100" and all(p.isdigit() for p in parts)


def _opener(url=None):
    """按 URL 分流代理：Tailscale 内网走隧道代理（:3130），公网走出口代理（:3128）。
    2026-11-13 修复：旧版不分 URL 一律走 :3130，致 Modal 公网端点 264ms 即断连、
    辩论误判 Modal 已死而回落 hub；hub（100.125.193.42）仍走 :3130。"""
    if url is not None and _is_tailscale_url(url):
        proxy = _tunnel_proxy_url()
    else:
        proxy = _env_proxy_url()
    if proxy:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener()


def hub_request(key, path, payload=None, timeout=120):
    """GET（payload None）或 POST。返回 (status, parsed_json_or_None, raw_text, err)。"""
    url = HUB_BASE + path
    data = None
    headers = {"Authorization": "Bearer " + key}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if payload is not None else "GET")
    try:
        with _opener(url).open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            try:
                parsed = json.loads(raw) if raw.strip() else None
            except Exception:
                parsed = None
            return resp.status, parsed, raw, None
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        return e.code, None, raw, "HTTP %s" % e.code
    except Exception as e:
        return None, None, "", str(e)


# ---- Modal vLLM（用户 2026-11-12 令：所有讨论都用今天绑卡的 Modal LLM，速度很重要）----
# 端点：Modal T4 + vLLM + Qwen2.5-7B-Instruct-AWQ，OpenAI 兼容接口。
# 实测：热容器单次调用约 2 秒（qwen3:8b 笔记本约 3-4 分钟，LongCat 约 93 秒）。
# 冷启动约 2-3 分钟（容器启动＋模型加载）；Modal 代理约 150 秒超时会回 303，
# 故 modal_chat 遇 303/超时即等 60 秒重试，最多约 4 分钟；仍失败则回落 hub。
MODAL_URL = "https://whddwdzcxm--b-debate-llm-serve.us-east.modal.run/v1/chat/completions"
MODAL_MODEL = "Qwen/Qwen2.5-7B-Instruct-AWQ"
# 用户 2026-11-12 13:49：GPU 用完了。Modal 主路暂停，辩论直走 hub 回落；
# GPU 恢复后把本开关改回 True 即可重新启用 Modal（不用改调用处）。
# 用户 2026-11-12 14:00 再令：能用尽量用，否则浪费了；先研究问题，拿路径依据去试；不急。
# 研究结论（14:05 实测）：沙箱连热容器单次 1.4-1.6 秒，早前失败是冷启动、非连通问题；
# 冷启动约 2-3 分钟，modal_chat 重试可覆盖，失败回落 hub。故 14:10 起重新启用。
MODAL_ENABLED = True

# hub 评判回落模型（买入辩论解析失败时换模型再试）：LongCat-2.5 在前（任务给定
# 的链首，且实测可用）；lightning 是 instruct 模型、JSON 格式更稳，但 2026-11-13
# 实测正被限流（429，reset 约 8 分钟），只作第二备用。主模型仍为 qwen3:8b
# （买入辩论实测首选），回落链只在解析失败时启用。
HUB_JUDGE_FALLBACK = "longcat-2.5"
HUB_JUDGE_FALLBACK_2 = "nemotron-3.5-lightning-30b-a3b"


def modal_warmup(timeout=10):
    """触发 Modal 容器启动（预热），不等待结果。辩论任务开场调一次，
    容器约 2-3 分钟后就绪，后续调用即热容器速度。失败静默（辩论时再重试）。
    MODAL_ENABLED=False（GPU 用完）时直接返回，不发请求。"""
    if not MODAL_ENABLED:
        return
    try:
        req = urllib.request.Request(
            MODAL_URL,
            data=json.dumps({"model": MODAL_MODEL,
                             "messages": [{"role": "user", "content": "hi"}],
                             "max_tokens": 1}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with _opener(MODAL_URL).open(req, timeout=timeout) as resp:
            resp.read()
    except Exception:
        pass


def modal_chat(messages, temperature, max_tokens, timeout=60):
    """一次 Modal /v1/chat/completions 调用。返回 (content, finish_reason, err)。
    冷启动 303 时等 60 秒重试，最多 5 次（约 4 分钟）；连接类错误（端点已死，如
    Remote end closed connection）连续 2 次即停止，不再空等 4 分钟，由 llm_chat
    立即回落 hub（2026-11-13 14:30 实测：Modal 断连时 5 次重试纯烧时间）。"""
    last_err = ""
    conn_fail = 0  # 连续连接类错误计数（非 303）
    for attempt in range(5):
        try:
            req = urllib.request.Request(
                MODAL_URL,
                data=json.dumps({"model": MODAL_MODEL, "messages": messages,
                                 "temperature": temperature,
                                 "max_tokens": max_tokens}).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            with _opener(MODAL_URL).open(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
                parsed = json.loads(raw) if raw.strip() else None
                if parsed and "choices" in parsed:
                    ch = (parsed.get("choices") or [{}])[0]
                    content = ((ch.get("message") or {}).get("content") or "")
                    return content, ch.get("finish_reason"), None
                last_err = "Modal 返回异常 body=%.200s" % raw
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="ignore")
            last_err = "Modal HTTP %s" % e.code
            if e.code == 303:
                last_err = "Modal 冷启动中（303），容器加载约 2-3 分钟"
                conn_fail = 0  # 303 是冷启动，不是端点已死，重置计数
            else:
                conn_fail += 1
        except Exception as e:
            last_err = "Modal 调用失败：%s" % e
            conn_fail += 1
        if conn_fail >= 2:
            print("  Modal 连接类错误连续 %d 次（%s），不再重试，立即回落 hub"
                  % (conn_fail, last_err), flush=True)
            break
        if attempt < 4:
            # 连接类错误立即重试（端点已死时 60 秒等待无意义）；只有 303 冷启动
            # 或返回体异常时才等 60 秒。
            if conn_fail > 0:
                print("  Modal 连接失败（%s），立即重试（%d/5）"
                      % (last_err, attempt + 1), flush=True)
            else:
                print("  Modal 未就绪（%s），60 秒后重试（%d/5）"
                      % (last_err, attempt + 1), flush=True)
                time.sleep(60)
    return None, None, last_err


def llm_chat(key, model, messages, temperature, max_tokens, timeout=150,
             hub_model=None, skip_modal=False, hub_max_attempts=3):
    """辩论统一入口：先走 Modal（快，热容器约 2 秒）；Modal 失败则回落 hub。
    key/model 只用于回落分支；Modal 不需要 Key。
    MODAL_ENABLED=False 时（GPU 用完）直接走 hub，不浪费重试时间。
    hub_model：指定回落用的 hub 模型（默认用 model）；skip_modal=True 时跳过
    Modal 直走 hub（解析失败换模型重试时用，省掉 Modal 重试时间）；
    hub_max_attempts：hub 回落的最多尝试次数（默认 3；换模型重试时传 1，
    限流即快速失败，不烧 75 秒×2 的重试等待）。"""
    use_model = hub_model or model
    if MODAL_ENABLED and not skip_modal:
        content, fin, err = modal_chat(messages, temperature, max_tokens)
        if not err:
            return content, fin, None
        print("  Modal 失败回落 hub（%s）" % err, flush=True)
    return hub_chat(key, use_model, messages, temperature, max_tokens,
                    timeout=timeout, max_attempts=hub_max_attempts)


def hub_chat(key, model, messages, temperature, max_tokens, timeout=150,
             max_attempts=3):
    """一次 /v1/chat/completions 调用。返回 (content, finish_reason, err)。
    hub 点名模型限流时回 429/503（body 含 Soonest reset ~70s）；遇此等 75 秒重试，
    最多 max_attempts 次（默认 3）。2026-11-09 实测：LongCat 路由短暂限流，75 秒后恢复 200。
    超时/连接错误（status 为 None）同样重试（30 秒后），2026-11-09 补。"""
    last_err = ""
    for attempt in range(max_attempts):
        status, parsed, raw, err = hub_request(
            key, "/chat/completions",
            {"model": model, "messages": messages, "temperature": temperature,
             "max_tokens": max_tokens}, timeout=timeout)
        if not err and status == 200 and parsed and "choices" in parsed:
            ch = (parsed.get("choices") or [{}])[0]
            content = ((ch.get("message") or {}).get("content") or "")
            return content, ch.get("finish_reason"), None
        if err:
            last_err = err
        else:
            last_err = "hub 返回异常 status=%s body=%.200s" % (status, raw)
        if attempt < max_attempts - 1 and (status in (429, 502, 503) or status is None):
            time.sleep(75 if status in (429, 502, 503) else 30)
            continue
        return None, None, last_err
    return None, None, last_err


def _call_debater(key, model, prompt_fn, pkt, temperature, side_name):
    """调一次辩论方；失败时 75 秒后只重试该方一次，仍失败返回报错。
    2026-11-09 补：今早 4 轮 3 轮掉边，主因是单次调用无重试。"""
    text, fin, err = llm_chat(key, model, prompt_fn(pkt), temperature,
                             prompts.MAX_TOKENS_DEBATER)
    if err:
        print("  %s调用失败：%s，75 秒后重试一次" % (side_name, err))
        time.sleep(75)
        text, fin, err = llm_chat(key, model, prompt_fn(pkt), temperature,
                                 prompts.MAX_TOKENS_DEBATER)
        if err:
            print("  %s重试仍失败：%s，接受单边输入" % (side_name, err))
    return text, fin, err


def repair_json_text(seg):
    """修复 LLM 常见 JSON 畸形，返回修复后的字符串（修不了则原样返回）。
    修：① evidence 数组里写成 "key": value 键值对 → 转为 "key=value" 字符串
    （2026-11-13 实测：qwen3:8b 输出 "evidence": ["suggest_qty": 3700, ...]，
    非法 JSON，致 4/5 次评判解析失败）；② 对象/数组尾逗号。
    只当数组内容整体由键值对构成时才修①，避免误伤含冒号的合法字符串。"""
    out = seg

    def _fix_ev(m):
        inner = m.group(1)
        pairs = re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"\s*:\s*([^,\]]+)', inner)
        if not pairs:
            return m.group(0)
        # 去掉所有键值对与逗号/空白后若还有残留，说明数组里混有普通字符串，不动
        rest = re.sub(r'"[A-Za-z_][A-Za-z0-9_]*"\s*:\s*[^,\]]+', "", inner)
        rest = rest.replace(",", "").strip()
        if rest:
            return m.group(0)
        strs = ['"%s=%s"' % (k.strip(), v.strip()) for k, v in pairs]
        return '"evidence": [%s]' % ", ".join(strs)

    out = re.sub(r'"evidence"\s*:\s*\[([^\]]*)\]', _fix_ev, out)
    out = re.sub(r",\s*([}\]])", r"\1", out)
    return out


def extract_fields_regex(text):
    """最后手段：用正则从文本中抽取评判 JSON 的关键字段，拼成 dict。
    只当 code 与 action 都能抽到才返回，否则返回 None（由调用方判不合格）。"""
    def _str_field(name):
        m = re.search(r'"%s"\s*:\s*"((?:[^"\\]|\\.)*)"' % name, text)
        return m.group(1) if m else None

    def _num_field(name):
        m = re.search(r'"%s"\s*:\s*(-?[\d.]+)' % name, text)
        if not m:
            return None
        try:
            return float(m.group(1))
        except Exception:
            return None

    code = _str_field("code")
    action = _str_field("action")
    if not code or not action:
        return None
    d = {"code": code, "action": action}
    qty = _num_field("qty")
    if qty is not None:
        d["qty"] = int(qty)
    lp = _num_field("limit_price")
    if lp is not None:
        d["limit_price"] = lp
    conf = _num_field("confidence")
    if conf is not None:
        d["confidence"] = conf
    reason = _str_field("reason")
    if reason is not None:
        d["reason"] = reason
    m = re.search(r'"evidence"\s*:\s*\[(.*?)\]', text, re.S)
    ev = []
    if m:
        inner = m.group(1)
        ev = re.findall(r'"((?:[^"\\]|\\.)*)"', inner)
        if not ev:
            pairs = re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"\s*:\s*([^,\]]+)', inner)
            ev = ["%s=%s" % (k.strip(), v.strip()) for k, v in pairs]
    d["evidence"] = ev
    for k in ("bull_case", "bear_case", "conservative_view", "aggressive_view"):
        v = _str_field(k)
        if v is not None:
            d[k] = v
    return d


def extract_json(text):
    """从 LLM 输出中提取 JSON 对象。容错顺序：
    1) ```json 代码块；2) 整体解析；3) 首个 {...} 段；3b) 修复常见畸形后重解；
    4) 正则抽字段（最后手段）。"""
    if not text:
        return None
    # 1) ```json 代码块
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # 2) 整体解析
    try:
        return json.loads(text)
    except Exception:
        pass
    # 3) 首个 {...} 段
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        seg = text[start:end + 1]
        try:
            return json.loads(seg)
        except Exception:
            pass
        # 3b) 修复常见畸形后重解
        fixed = repair_json_text(seg)
        if fixed != seg:
            try:
                return json.loads(fixed)
            except Exception:
                pass
    # 4) 正则抽字段
    return extract_fields_regex(text)


def load_state():
    default = {"mode": "shadow", "shadow_days": 0, "shadow_start": "2026-11-09",
               "last_shadow_date": None}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            st = json.load(f)
        for k, v in default.items():
            st.setdefault(k, v)
        return st
    except Exception:
        return dict(default)


def save_state(st):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


def _view_for_log(text):
    """辩论方输出进日志：能解析存结构，否则存截断原文。"""
    if not text:
        return {"error": "hub 调用失败，无输出"}
    parsed = extract_json(text)
    if isinstance(parsed, dict):
        return parsed
    return {"raw": text[:3000]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--time", choices=["1000", "1030", "1400"], default=None)
    ap.add_argument("--mode", choices=["shadow", "execute"], default=None)
    ap.add_argument("--no-breadth", action="store_true")
    args = ap.parse_args()
    now = datetime.now(CST)
    date_str = now.strftime("%Y-%m-%d")
    time_slot = args.time or ("1000" if now.hour < 12 else "1400")
    state = load_state()
    mode = args.mode or state.get("mode", "shadow")
    run_ts = now.strftime("%Y%m%d_%H%M")
    os.makedirs(LOGS_DIR, exist_ok=True)
    jsonl_path = os.path.join(LOGS_DIR, "debate_%s.jsonl" % run_ts)
    md_path = os.path.join(LOGS_DIR, "debate_%s.md" % date_str.replace("-", ""))

    print("== B线辩论 %s %s 模式=%s ==" % (date_str, time_slot, mode))
    print("预热 Modal LLM（容器约 2-3 分钟就绪，热容器单次约 2 秒）...", flush=True)
    modal_warmup()
    packets = debate_packet.build_packets(fetch_breadth=not args.no_breadth)
    if not packets:
        print("无 B 线持仓，本轮结束。")
        return 0
    print("持仓 %d 只：%s" % (len(packets),
          ", ".join("%s %s股" % (p["code"], p["qty"]) for p in packets)))

    try:
        key = get_hub_key()
    except Exception as e:
        print("取 hub Key 失败：%s" % e)
        return 1
    status, models, _raw, err = hub_request(key, "/models", timeout=30)
    model = prompts.MODEL
    if models and isinstance(models.get("data"), list):
        ids = {m.get("id") for m in models["data"]}
        if prompts.MODEL not in ids and prompts.MODEL_FALLBACK in ids:
            model = prompts.MODEL_FALLBACK
        elif prompts.MODEL not in ids:
            print("hub 模型列表无 LongCat-2.5（共 %d 个），仍用 %s 试调" % (len(ids), model))
    else:
        print("GET /v1/models 失败（%s），仍用 %s 试调" % (err or status, model))
    print("模型：%s" % model)

    summary = []
    exec_requests = []
    for pkt in packets:
        code = pkt["code"]
        print("-- %s %s 现价 %s 成本 %s S1 %s S2 %s TP3 %s TP5 %s --"
              % (code, pkt["name"], pkt["price"], pkt["cost"], pkt["s1"],
                 pkt["s2"], pkt["tp3"], pkt["tp5"]))
        cons_text, cons_fin, cons_err = _call_debater(
            key, model, prompts.build_conservative_prompt, pkt,
            prompts.TEMP_CONSERVATIVE, "保守方")
        aggr_text, aggr_fin, aggr_err = _call_debater(
            key, model, prompts.build_aggressive_prompt, pkt,
            prompts.TEMP_AGGRESSIVE, "激进方")
        judge_msgs = prompts.build_judge_prompt(pkt, cons_text, aggr_text)
        judge = None
        judge_err = ""
        judge_last_raw = ""
        judge_fin = None
        for _attempt in range(3):  # 首调 + 重试 ≤2 次
            text, judge_fin, err = llm_chat(key, model, judge_msgs,
                                            prompts.TEMP_JUDGE, prompts.MAX_TOKENS_JUDGE)
            judge_last_raw = text or ""
            if err:
                judge_err = err
                continue
            cand = extract_json(text)
            if cand is None:
                judge_err = "judge 输出无法解析为 JSON"
                continue
            ok, verr = prompts.validate_judge(cand, pkt)
            if not ok:
                judge_err = verr
                continue
            judge = cand
            break
        judge_ok = judge is not None
        if not judge_ok:
            judge = {"code": code, "action": "hold", "qty": 0,
                     "limit_price": pkt.get("price") or pkt.get("prev_close"),
                     "reason": "judge 输出不合格（%s），已降级 hold" % judge_err,
                     "confidence": 0.0, "evidence": ["judge 重试 2 次仍不合格"],
                     "conservative_view": "（解析失败）",
                     "aggressive_view": "（解析失败）"}
            print("  judge 不合格 → hold（%s）" % judge_err)
        g = gate.check(judge, pkt, logs_dir=LOGS_DIR, date_str=date_str, now=now)
        entry = {"ts": now.isoformat(timespec="seconds"), "date": date_str,
                 "time_slot": time_slot, "mode": mode, "code": code,
                 "packet": pkt,
                 "conservative": _view_for_log(cons_text),
                 "aggressive": _view_for_log(aggr_text),
                 "judge": judge, "gate": g,
                 "finish_reasons": {"conservative": cons_fin,
                                    "aggressive": aggr_fin, "judge": judge_fin},
                 "errors": {"conservative": cons_err or None,
                            "aggressive": aggr_err or None,
                            "judge": judge_err if not judge_ok else None},
                 "one_sided": bool(cons_err or aggr_err),
                 "effective_action": g["effective_action"],
                 "effective_qty": g["effective_qty"]}
        if not judge_ok:
            entry["judge_raw"] = judge_last_raw[:1000]
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        summary.append((code, judge, g))
        print("  决策：%s %s 股 @%s 置信 %.2f 闸门 %s%s"
              % (g["effective_action"], g["effective_qty"],
                 judge.get("limit_price"), judge.get("confidence") or 0,
                 "通过" if g["approved"] else "拒绝",
                 ("（%s）" % g["reject_reason"]) if not g["approved"] else
                 ("（已降级 hold）" if g["downgraded"] else "")))
        if mode == "execute" and g["approved"] and g["effective_action"] != "hold":
            exec_requests.append({
                "code": code, "action": g["effective_action"],
                "qty": g["effective_qty"], "limit_price": judge.get("limit_price"),
                "valid_until": g["valid_until"],
                "reason": judge.get("reason")})

    # 当日汇总 md（追加）
    header = "# B线辩论 %s\n\n" % date_str
    if not os.path.exists(md_path):
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(header)
    with open(md_path, "a", encoding="utf-8") as f:
        f.write("## %s %s（%s）\n\n" % (date_str, time_slot, mode))
        f.write("| 代码 | 决策 | 数量 | 限价 | 置信 | 闸门 | 理由 |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for code, judge, g in summary:
            f.write("| %s | %s | %s | %s | %.2f | %s | %s |\n"
                    % (code, g["effective_action"], g["effective_qty"],
                       judge.get("limit_price"), judge.get("confidence") or 0,
                       "通过" if g["approved"] else "拒绝：" + (g["reject_reason"] or ""),
                       (judge.get("reason") or "").replace("|", "/")))
        f.write("\n")
    print("日志：%s" % jsonl_path)
    print("汇总：%s" % md_path)

    # 影子天数：14:00 轮计 1 天（同日不重复计）
    if time_slot == "1400" and state.get("last_shadow_date") != date_str:
        state["shadow_days"] = int(state.get("shadow_days", 0)) + 1
        state["last_shadow_date"] = date_str
        save_state(state)
        print("影子天数：%s" % state["shadow_days"])

    if mode == "execute":
        if exec_requests:
            print("EXECUTE_REQUESTS:")
            print(json.dumps(exec_requests, ensure_ascii=False, indent=2))
        else:
            print("执行模式：本轮无可执行决策。")
    else:
        print("影子模式：只记日志，不下单。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
