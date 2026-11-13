#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mechanical applier: extract ```python blocks from model output, take the
top-level function defs, replace same-named defs in the target file verbatim.
No hand edits. Reports NOOP when output equals the original, SYNTAX_FAIL when
the output does not parse, APPLIED otherwise (with unified diff)."""
import ast
import difflib
import json
import re
import sys


def extract_blocks(text):
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    if not blocks:
        blocks = [text]
    return blocks


def get_functions(code):
    tree = ast.parse(code)
    fns = {}
    lines = code.split("\n")
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", None)
            src = "\n".join(lines[node.lineno - 1:end])
            fns[node.name] = src.rstrip("\n")
    return fns


def replace_in_target(target_src, new_fns):
    tree = ast.parse(target_src)
    lines = target_src.split("\n")
    spans = {}  # name -> list of (start_idx, end_idx) 0-based, end exclusive
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            spans.setdefault(node.name, []).append(
                (node.lineno - 1, getattr(node, "end_lineno", node.lineno)))
    # replace from bottom up so earlier line numbers stay valid
    repls = []
    for name, src in new_fns.items():
        if name not in spans:
            return None, "UNKNOWN_FUNCTION:" + name
        for (s, e) in spans[name]:
            repls.append((s, e, src))
    repls.sort(reverse=True)
    new_lines = lines[:]
    for (s, e, src) in repls:
        new_lines[s:e] = src.split("\n")
    return "\n".join(new_lines), None


def main():
    model_out, target = sys.argv[1], sys.argv[2]
    with open(model_out, encoding="utf-8") as f:
        text = f.read()
    with open(target, encoding="utf-8") as f:
        orig = f.read()
    report = {"model_out": model_out, "target": target}
    blocks = extract_blocks(text)
    code = "\n\n".join(b for b in blocks if b.strip())
    if not code.strip():
        report["status"] = "NO_FN"
        print(json.dumps(report, ensure_ascii=False))
        return 0
    try:
        new_fns = get_functions(code)
    except SyntaxError as e:
        report["status"] = "SYNTAX_FAIL"
        report["error"] = str(e)
        print(json.dumps(report, ensure_ascii=False))
        return 0
    if not new_fns:
        report["status"] = "NO_FN"
        print(json.dumps(report, ensure_ascii=False))
        return 0
    report["functions"] = sorted(new_fns)
    noop, changed = [], []
    for name, src in new_fns.items():
        tree = ast.parse(orig)
        old = None
        olines = orig.split("\n")
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == name:
                old = "\n".join(olines[node.lineno - 1:getattr(node, "end_lineno", node.lineno)]).rstrip("\n")
                break
        if old is not None and old.strip() == src.strip():
            noop.append(name)
        else:
            changed.append(name)
    report["noop"] = noop
    report["changed"] = changed
    if not changed:
        report["status"] = "NOOP"
        print(json.dumps(report, ensure_ascii=False))
        return 0
    new_src, err = replace_in_target(orig, {k: v for k, v in new_fns.items() if k in changed})
    if err:
        report["status"] = "APPLY_FAIL"
        report["error"] = err
        print(json.dumps(report, ensure_ascii=False))
        return 0
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        report["status"] = "SYNTAX_FAIL_AFTER_APPLY"
        report["error"] = str(e)
        print(json.dumps(report, ensure_ascii=False))
        return 0
    with open(target, "w", encoding="utf-8") as f:
        f.write(new_src)
    diff = list(difflib.unified_diff(orig.split("\n"), new_src.split("\n"), lineterm=""))
    report["status"] = "APPLIED"
    report["diff_lines"] = len(diff)
    report["diff"] = "\n".join(diff)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
