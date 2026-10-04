# -*- coding: utf-8 -*-
"""main.splash 全局状态声明审计。

为什么需要这道检查：
    漏声明一个全局状态（例如 `let iv_box = []`），运行时才会在 `.len()` 处抛错，
    表现是「整张卡片空白、界面上没有任何提示」—— 括号体检和控件引用检查都发现不了。

用法：
    python tools/audit_globals.py
退出码 0 = 无缺失，1 = 发现缺失。
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

# 已知的名字来源
top_lets = set(re.findall(r"(?m)^let\s+([A-Za-z_][A-Za-z0-9_]*)\s*=", src))
inner_lets = set(re.findall(r"(?m)^\s+let\s+([A-Za-z_][A-Za-z0-9_]*)\s*=", src))
fns = set(re.findall(r"(?m)^fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", src))
widgets = set(re.findall(r"(?m)^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:=\s", src))
params = set()
for m in re.finditer(r"(?m)^fn\s+[A-Za-z_][A-Za-z0-9_]*\s*\(([^)]*)\)", src):
    for p in m.group(1).split(","):
        p = p.strip()
        if p:
            params.add(p)
forvars = set(re.findall(r"for\s+([A-Za-z_][A-Za-z0-9_]*)", src))
forvars |= set(re.findall(r"for\s+[A-Za-z_][A-Za-z0-9_]*\s+([A-Za-z_][A-Za-z0-9_]*)", src))
lambdas = set()
for lv in re.findall(r"\|([A-Za-z_, ]+)\|", src):
    for v in lv.split(","):
        v = v.strip()
        if v:
            lambdas.add(v)
# 形参风格 `) do net.HttpEvents{ on_response: |res| ... }` 已含在上面

known = top_lets | inner_lets | fns | widgets | params | forvars | lambdas

# 状态命名约定前缀：这些是本项目用来标全局状态的
PREFIXES = ("iv_", "rv_", "ag_", "vc_", "aq_", "th_", "fc_", "pk_", "pf_")
PATTERN = re.compile(r'(?<![A-Za-z0-9_."])(' + "|".join(PREFIXES) + r")[a-z0-9_]*")

suspects = {}
for lineno, line in enumerate(src.split("\n"), 1):
    stripped = line.strip()
    if stripped.startswith("//"):
        continue
    for m in PATTERN.finditer(line):
        name = m.group(0)
        if name in known:
            continue
        # 同行内有声明/定义/循环变量，算局部
        if re.search(r"\b(let|fn|for)\s+" + re.escape(name) + r"\b", line):
            continue
        suspects.setdefault(name, []).append(lineno)

print(f"文件：{P}")
print(f"顶层全局 {len(top_lets)} 个 / 函数 {len(fns)} 个 / 控件定义 {len(widgets)} 个")

if not suspects:
    print("[PASS] 没有发现未声明的状态变量")
    sys.exit(0)

print("[FAIL] 以下状态变量被使用但找不到声明（运行时会让整张卡片不渲染）：")
for name, lines in sorted(suspects.items(), key=lambda kv: kv[1][0]):
    print(f"    {name}  首次出现在第 {lines[0]} 行（共 {len(lines)} 处）")
print("\n修法：在文件顶部的声明区补 `let <name> = <初值>`（数组用 []，文本用 \"\"，数字用 0）")
sys.exit(1)
