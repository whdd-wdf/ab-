#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract named top-level functions from a file, by ast line spans."""
import ast
import sys

path = sys.argv[1]
names = sys.argv[2:]
with open(path, encoding="utf-8") as f:
src = f.read()
lines = src.split("\n")
tree = ast.parse(src)
for node in tree.body:
if isinstance(node, ast.FunctionDef) and node.name in names:
end = getattr(node, "end_lineno", node.lineno)
print("\n".join(lines[node.lineno - 1:end]))
print()
