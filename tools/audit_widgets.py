# -*- coding: utf-8 -*-
"""main.splash 控件引用一致性审计。

为什么需要这道检查：
    `ui.xxx` 引用一个不存在的控件时，**不会有任何报错**，
    表现是整张卡片不渲染 —— 这是这个 DSL 最坑的地方之一。

用法：
    python tools/audit_widgets.py
退出码 0 = 通过，1 = 发现引用缺失。
"""
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
DEFAULT = REPO / "my-entry" / "morning-brief" / "bundle" / "main.splash"
P = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT

if not P.is_file():
    print(f"[FAIL] 找不到文件：{P}")
    sys.exit(1)

src = P.read_text(encoding="utf-8")

defined = set(re.findall(r"(?m)^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:=\s", src))
used = set(re.findall(r"ui\.([A-Za-z_][A-Za-z0-9_]*)", src))

missing = sorted(used - defined)

print(f"文件：{P}")
print(f"控件定义 {len(defined)} 个 / ui. 引用 {len(used)} 个")

if not missing:
    print("[PASS] 没有引用缺失的控件")
    sys.exit(0)

print("[FAIL] 以下控件被 ui. 引用但找不到定义（整张卡片会不渲染）：")
for name in missing:
    first = next(
        (
            i
            for i, line in enumerate(src.split("\n"), 1)
            if re.search(r"ui\." + re.escape(name) + r"\b", line)
        ),
        "?",
    )
    print(f"    {name}  首次引用在第 {first} 行")
print("\n修法：给控件补 `xxx := View{...}` 之类的定义（注意 `:=` 才是可被 ui. 寻址的 id）")
sys.exit(1)
