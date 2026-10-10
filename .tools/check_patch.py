#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验（并可选修正）unified diff 的 hunk 头计数。

为什么需要：我们手工往上游补丁里加代码时，只改内容、忘了改 `@@ -a,b +c,d @@`
里的 d，补丁就会「看起来对、一应用就废」。这个脚本按 unified diff 的规则逐 hunk
数一遍 +/- 行，和头部声明的数字对账；`--fix` 直接把头部改成实际值。

unified diff 的计数规则（容易记错的那条）：
  - 以 '+' 开头（且不是 '+++'）的行 → 计入新文件的 d
  - 以 '-' 开头（且不是 '---'）的行 → 计入旧文件的 b
  - 空行 或 以 ' ' 开头 → 两边都各 +1
  - '\\ No newline at end of file' 不计入任何一边

用法：
    python .tools/check_patch.py my-entry/patches/host-voice.patch
    python .tools/check_patch.py my-entry/patches/host-voice.patch --fix
"""

import argparse
import re
import sys

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def scan(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    lines = text.split("\n")
    # 文件以换行结尾时 split 会多出最后一个空串 —— 那是行尾符，不是 patch 里的一行。
    if lines and lines[-1] == "":
        lines.pop()
    problems = []
    hunks = []  # (line_index, old_start, old_count, new_start, new_count, real_old, real_new)

    i = 0
    while i < len(lines):
        m = HUNK.match(lines[i])
        if not m:
            i += 1
            continue
        old_start = int(m.group(1))
        old_count = int(m.group(2)) if m.group(2) is not None else 1
        new_start = int(m.group(3))
        new_count = int(m.group(4)) if m.group(4) is not None else 1

        real_old = real_new = 0
        j = i + 1
        while j < len(lines):
            ln = lines[j]
            if HUNK.match(ln) or ln.startswith("diff --git ") or ln.startswith("--- "):
                break
            if ln.startswith("+++") or ln.startswith("---"):
                j += 1
                continue
            if ln.startswith("\\"):  # \ No newline at end of file
                j += 1
                continue
            if ln == "" or ln.startswith(" "):
                real_old += 1
                real_new += 1
            elif ln.startswith("+"):
                real_new += 1
            elif ln.startswith("-"):
                real_old += 1
            else:
                break
            j += 1

        hunks.append((i, old_start, old_count, new_start, new_count, real_old, real_new))
        if (old_count, new_count) != (real_old, real_new):
            problems.append(
                f"  行 {i + 1}: 头部声明 -{old_count} +{new_count}，实际 -{real_old} +{real_new}"
            )
        i = j
    return lines, hunks, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("patch")
    ap.add_argument("--fix", action="store_true", help="把头部计数改写成实际值")
    args = ap.parse_args()

    lines, hunks, problems = scan(args.patch)
    print(f"{args.patch}: {len(hunks)} 个 hunk")
    if not problems:
        print("结论：全部 hunk 的计数与实际内容一致")
        return 0

    print(f"发现 {len(problems)} 处不一致：")
    for p in problems:
        print(p)

    if not args.fix:
        print("（加 --fix 可直接修正头部）")
        return 1

    for idx, _, _, _, _, real_old, real_new in hunks:
        m = HUNK.match(lines[idx])
        if not m:
            continue
        old_start, new_start = m.group(1), m.group(3)
        fixed = f"@@ -{old_start},{real_old} +{new_start},{real_new} @@"
        if lines[idx] != fixed:
            lines[idx] = fixed
    with open(args.patch, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lines) + "\n")
    print("已修正；请重跑本脚本确认")
    return 0


if __name__ == "__main__":
    sys.exit(main())
