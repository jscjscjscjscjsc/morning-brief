#!/usr/bin/env python3
"""Cheap structural sanity check for a Splash program.

It is not a parser. It tokenises just enough (line comments, "..." strings with
escapes and embedded newlines) to count bracket nesting, so a migration that
unbalanced the file shows up immediately. The same scan run over the pre-edit
copy is the baseline.
"""
import sys
from pathlib import Path

CLOSE = {"(": ")", "{": "}", "[": "]"}


def scan(path: Path):
    s = path.read_text(encoding="utf-8")
    i, n, line = 0, len(s), 1
    stack = []
    problems = []
    while i < n:
        c = s[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            while i < n and s[i] != "\n":
                i += 1
            continue
        if c == '"':
            i += 1
            while i < n:
                if s[i] == "\\":
                    i += 2
                    continue
                if s[i] == '"':
                    i += 1
                    break
                if s[i] == "\n":
                    line += 1
                i += 1
            else:
                problems.append(f"unterminated string starting before line {line}")
            continue
        if c in "({[":
            stack.append((c, line))
            i += 1
            continue
        if c in ")}]":
            if not stack:
                problems.append(f"extra {c!r} at line {line}")
            else:
                o, ol = stack.pop()
                if CLOSE[o] != c:
                    problems.append(f"open {o!r}@{ol} closed by {c!r}@{line}")
            i += 1
            continue
        i += 1
    if stack:
        problems.append(f"{len(stack)} unclosed: " + ", ".join(f"{o}@{l}" for o, l in stack[-5:]))
    return problems, stack


def main():
    rc = 0
    for raw in sys.argv[1:]:
        path = Path(raw)
        problems, stack = scan(path)
        status = "OK" if not problems else "PROBLEMS"
        print(f"{status:8s} {path}  (open brackets left: {len(stack)})")
        for p in problems:
            print("   -", p)
        if problems:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
