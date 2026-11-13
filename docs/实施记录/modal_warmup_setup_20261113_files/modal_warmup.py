#!/usr/bin/env python3
"""Modal 预热脚本（独立运行）。POST Modal 端点唤醒容器（scaledown 到零后需预热）。
用法：python3 modal_warmup.py
输出一行 JSON：{"status": "ok"|"failed", "http_code": int|null, "elapsed_ms": int, "error": str|null}
预热失败不抛异常、不阻塞辩论（辩论自有 hub 回落）。Modal 端点无鉴权，不含任何密钥。
注意：Modal 是公网地址，走环境代理原值（:3128 出口代理），不要改写成 :3130
（:3130 是 Tailscale 隧道代理，只通 Tailscale 内网；2026-11-13 实测经 :3130 调 Modal
立即断连，经 :3128 则 200）。
"""
import json
import os
import sys
import time
import urllib.request

MODAL_URL = "https://whddwdzcxm--b-debate-llm-serve.us-east.modal.run/v1/chat/completions"
MODAL_MODEL = "Qwen/Qwen2.5-7B-Instruct-AWQ"


def _opener():
    """公网地址用环境代理原值，不改写端口。"""
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = (os.environ.get(var) or "").strip()
        if v:
            base = v.rstrip("/")
            return urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": base, "https": base}))
    return urllib.request.build_opener()


def main():
    start = time.monotonic()
    try:
        req = urllib.request.Request(
            MODAL_URL,
            data=json.dumps({"model": MODAL_MODEL,
                             "messages": [{"role": "user", "content": "hi"}],
                             "max_tokens": 1}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with _opener().open(req, timeout=15) as resp:
            resp.read()
            code = resp.status
        elapsed = int((time.monotonic() - start) * 1000)
        print(json.dumps({"status": "ok", "http_code": code,
                          "elapsed_ms": elapsed, "error": None},
                         ensure_ascii=False))
        return 0
    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        print(json.dumps({"status": "failed", "http_code": None,
                          "elapsed_ms": elapsed, "error": str(e)[:200]},
                         ensure_ascii=False))
        return 0


if __name__ == "__main__":
    sys.exit(main())
