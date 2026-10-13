#!/usr/bin/env python3
"""扫描 splash 源码，找出把 splash 关键字当变量名/对象 key 用的地方。

踩过的坑（两次）：
  ① 可用性探测的 schema 里写了 properties:{ ok: {...} } —— 裸 `ok` 被当成 ok 表达式，
     紧跟 `:` 就报 Expected expression … found Operator(:)，整个构造被 skip。
  ② vf_peer_scan_s 里写了 `let ok = false` —— 整个函数被 parser skip，
     倒排索引静默失效，核验台「同行家数」恒 0 且界面上没有任何提示。

失败方式之所以致命：parser 只打一行 [E] 日志，然后把**整个函数**丢掉，
调用点照样能编过（函数名仍在编译好的单元里？不——干脆报 not found）。
无论如何，界面上只会表现为「某个数字恒为 0 / 某个区块不出现」，不吃异常、不超时。

用法：
  python check_keywords.py bundle/main.splash
退出码 1 表示发现可疑用法。
"""
import re
import sys

# makepad/platform/script/src/parser.rs 里的关键字
KEYWORDS = {
    "and", "break", "catch", "continue", "do", "elif", "else", "false", "fn",
    "for", "if", "in", "is", "let", "loop", "match", "me", "mut", "nil", "or",
    "return", "scope", "self", "true", "try", "use", "var", "while", "ok",
}

# let <name> =      /  var <name> =      /  fn <name>(      /  for <name> in
PAT_DECL = re.compile(r"\b(?:let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*[=:]")
PAT_FN = re.compile(r"\bfn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
PAT_FOR = re.compile(r"\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b")
# 对象字面量里的 key：{ name:  —— 只在 { 或 , 之后才算（避免匹配 if x { a: b } 之外的东西）
PAT_KEY = re.compile(r"[{,]\s*([A-Za-z_][A-Za-z0-9_]*)\s*:")

PATTERNS = [
    ("声明(let/var)", PAT_DECL),
    ("函数名(fn)", PAT_FN),
    ("循环变量(for..in)", PAT_FOR),
    ("对象 key({k:)", PAT_KEY),
]

GLOBALS_WHITELIST = set()


def strip_comments(line: str) -> str:
    """去掉 // 注释（不处理字符串里的 //，够用了；字符串里的关键字是合法用法）。"""
    out = []
    i = 0
    in_str = False
    while i < len(line):
        c = line[i]
        if c == '"':
            in_str = not in_str
            out.append(c)
            i += 1
            continue
        if not in_str and c == "/" and i + 1 < len(line) and line[i + 1] == "/":
            break
        out.append(c)
        i += 1
    return "".join(out)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check_keywords.py <main.splash> [more.splash ...]")
        return 2
    bad = 0
    for path in sys.argv[1:]:
        try:
            with open(path, "r", encoding="utf-8", newline="") as f:
                raw = f.read()
        except OSError as e:
            print(f"!! 读不到 {path}: {e}")
            return 2
        lines = raw.split("\n")
        for ln_no, raw_line in enumerate(lines, 1):
            line = strip_comments(raw_line)
            if not line.strip():
                continue
            for kind, pat in PATTERNS:
                for m in pat.finditer(line):
                    name = m.group(1)
                    if name in KEYWORDS:
                        col = m.start(1) + 1
                        print(f"{path}:{ln_no}:{col} [{kind}] 关键字 `{name}` 被当作标识符")
                        print(f"    {raw_line.rstrip()}")
                        bad += 1
    if bad:
        print(f"\n发现 {bad} 处可疑用法（关键字当标识符）。必须改名，否则该函数/构造会被 parser 整块丢掉。")
        return 1
    print("OK: 没有把 splash 关键字当标识符用。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
