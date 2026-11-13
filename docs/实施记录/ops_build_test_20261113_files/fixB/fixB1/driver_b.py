#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fixB driver: call local Ollama qwen2.5-coder:7b in the box for a batch of jobs.
Manifest JSON: {"jobs": [{"name":..., "prompt_file":..., "out_file":...,
"num_predict":2048, "num_ctx":16384, "temperature":0.2}], "log_file":...}
Jobs run sequentially; raw model output to out_file; progress to log jsonl.
Standard library only."""
import json
import os
import sys
import time
import urllib.request


def ollama(prompt, num_predict, num_ctx=16384, temperature=0.2, timeout=1500):
    payload = {"model": "qwen2.5-coder:7b", "prompt": prompt, "stream": False,
               "options": {"num_ctx": num_ctx, "num_predict": num_predict,
                           "temperature": temperature}}
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read())
    return result.get("response", ""), time.time() - t0


def main():
    manifest_path = sys.argv[1]
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    log_path = manifest.get("log_file") or os.path.join(
        os.path.dirname(os.path.abspath(manifest_path)), "run_log.jsonl")
    for job in manifest["jobs"]:
        name = job["name"]
        out_file = job["out_file"]
        n_pred = job.get("num_predict", 2048)
        n_ctx = job.get("num_ctx", 16384)
        temp = job.get("temperature", 0.2)
        t_start = time.time()
        try:
            with open(job["prompt_file"], "r", encoding="utf-8") as f:
                prompt = f.read()
            text, secs = ollama(prompt, n_pred, n_ctx, temp)
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(text)
            rec = {"name": name, "status": "ok", "chars": len(text),
                   "prompt_chars": len(prompt),
                   "ollama_secs": round(secs, 1),
                   "total_secs": round(time.time() - t_start, 1),
                   "out_file": out_file}
        except Exception as e:
            rec = {"name": name, "status": "error", "error": repr(e),
                   "total_secs": round(time.time() - t_start, 1),
                   "out_file": out_file}
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(json.dumps(rec, ensure_ascii=False), flush=True)
    print("MANIFEST DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
