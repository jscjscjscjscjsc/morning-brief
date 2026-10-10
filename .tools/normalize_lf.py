# -*- coding: utf-8 -*-
"""把 bundle 内的文本文件统一成 LF。

为什么必须做：`.gitattributes` 里 `**/bundle/** -text` 关掉了 git 的行尾转换，
官方 hub 的 bundle_blake3 又是逐字节算的。Windows 上任何一次
`open(path, "w")` 写回都会把全文的 \\n 变成 \\r\\n——digest 变了、diff 变成
一个巨大的 hunk、还可能让脚本解析器把 \\r 当成多余字符。

用法：
    python .tools/normalize_lf.py <文件或目录> [...]        # 只报告
    python .tools/normalize_lf.py --write <文件或目录> [...]  # 就地改写

二进制文件（png/jpg/svg 之外的图片、字体等）按扩展名跳过。
"""
import sys
from pathlib import Path

BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".ttf", ".otf",
              ".woff", ".woff2", ".blake3", ".zip", ".gz", ".pdf", ".mp4", ".wasm"}


def targets(args):
    for a in args:
        p = Path(a)
        if p.is_dir():
            yield from sorted(x for x in p.rglob("*") if x.is_file())
        elif p.is_file():
            yield p
        else:
            print(f"  skip (not found): {a}")


def main():
    argv = sys.argv[1:]
    write = "--write" in argv
    argv = [a for a in argv if a != "--write"]
    if not argv:
        print(__doc__)
        return 2
    changed = 0
    for p in targets(argv):
        if p.suffix.lower() in BINARY_EXT:
            print(f"  binary-jump              {p}")
            continue
        b = p.read_bytes()
        crlf = b.count(b"\r\n")
        lone_cr = b.count(b"\r") - crlf
        if not crlf and not lone_cr:
            print(f"  LF        (already clean) {p}")
            continue
        fixed = b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        print(f"  {'WRITE' if write else 'WOULD-FIX'}  crlf={crlf} lone_cr={lone_cr} "
              f"{len(b)}B -> {len(fixed)}B  {p}")
        if write:
            # 二进制写，绕过任何换行翻译
            with open(p, "wb") as f:
                f.write(fixed)
        changed += 1
    print(f"\n{'changed' if write else 'would change'}: {changed} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
