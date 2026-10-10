#!/usr/bin/env python3
"""Measure each model.complete `task` value against the host's 4096-byte cap.

The host refuses a call whose task is over TASK_MAX (4096 bytes) or whose input
json is over INPUT_MAX (32768). Task values here are `"lit" + expr + "lit"`
joins; the only expression is charter_v(...), which returns "v1"/"v2", so it is
accounted as 2 bytes each.

Output fields are measured the same way as a report, not a guarantee: `input`
usually serialises a runtime string whose length only shows up at run time.
"""
import re
import sys
from pathlib import Path

TASK_MAX = 4096
INPUT_MAX = 32768
KEYS = {"task", "input", "schema", "class", "allow_urls"}


def scan_block(block: str):
    """Return {key: {'lit': bytes, 'expr': count, 'strings': n}}."""
    out = {k: {"lit": 0, "expr": 0} for k in KEYS}
    i, n = 0, len(block)
    cur = None
    while i < n:
        # a top-level key sits on its own line at 8 spaces of indent
        m = re.match(r"\n {8}([a-z_]+):", block[i:])
        if m and m.group(1) in KEYS:
            cur = m.group(1)
            i += m.end()
            continue
        c = block[i]
        if c == '"' and cur:
            i += 1
            while i < n:
                if block[i] == "\\":
                    nxt = block[i + 1] if i + 1 < n else ""
                    if nxt in "nt":
                        out[cur]["lit"] += 1
                    else:
                        out[cur]["lit"] += len(nxt.encode("utf-8"))
                    i += 2
                    continue
                if block[i] == '"':
                    i += 1
                    break
                out[cur]["lit"] += len(block[i].encode("utf-8"))
                i += 1
            continue
        if cur == "task" and block.startswith("charter_v(", i):
            out[cur]["expr"] += 1
        i += 1
    return out


def main():
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    rc = 0
    starts = [m.start() for m in re.finditer(r'host\.request\("model\.complete"', text)]
    print(f"model.complete call sites: {len(starts)}   (task cap {TASK_MAX}B, input cap {INPUT_MAX}B)\n")
    for k, s in enumerate(starts, 1):
        close = text.find("}, fn(", s)
        block = text[s:close if close != -1 else s + 4000]
        line = text.count("\n", 0, s) + 1
        r = scan_block(block)
        task = r["task"]["lit"] + 2 * r["task"]["expr"]
        inp = r["input"]["lit"] + 2 * r["input"]["expr"]
        note = ""
        if task > TASK_MAX:
            note = "  ** OVER TASK CAP **"
            rc = 1
        elif task > TASK_MAX - 400:
            note = "  (close to the cap)"
        print(f"  #{k:2d} line {line:5d}  task={task:5d}B  input~{inp:5d}B{note}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
