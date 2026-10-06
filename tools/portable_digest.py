# -*- coding: utf-8 -*-
"""设置 bundle 的跨平台摘要（Linux 路径算法），供提交官方 hub 使用。

背景（官方 issue #75 / 未合并的修复 PR #79）：
    官方 `digest_dir`（crates/app-contract/src/bundle.rs）把相对路径用
    `to_string_lossy()` 写进 blake3。Windows 产出 `assets\\icon.svg`，
    Linux 产出 `assets/icon.svg` —— 同一个 bundle 因此有两个摘要。
    官方维护者在 Linux 上验证提交，所以 manifest 必须写 **Linux 版摘要**。

本脚本：
    1. 用正斜杠路径重算摘要（与 Linux 上的官方实现逐字节一致）
    2. 写进 manifest.json
    3. 用带修复补丁的 hub 复验（若已构建）

注意：
    - 本地 `card-host` 用 `--stamp` 启动时会**把摘要改回 Windows 版**，
      所以每次跑完本地测试，提交前要重新执行本脚本。
    - `hub stamp`（Windows 版）同样会写回 Windows 摘要，提交前不要跑它。

用法：
    python tools/portable_digest.py            # 设置并显示
    python tools/portable_digest.py --check    # 只检查，不写
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUNDLE = REPO / "my-entry" / "morning-brief" / "bundle"
MANIFEST = BUNDLE / "manifest.json"
MANIFEST_NAME = "manifest.json"


def collect(root: Path):
    """收集 (正斜杠相对路径, 绝对路径)，排除 manifest，按路径排序。"""
    files = []
    stack = [root]
    while stack:
        d = stack.pop()
        for entry in sorted(os.listdir(d)):
            p = d / entry
            if p.is_symlink():
                raise RuntimeError(f"{p}: bundle 不允许包含符号链接")
            if p.is_dir():
                stack.append(p)
            elif p.is_file():
                rel = p.relative_to(root).as_posix()   # 关键：强制正斜杠
                if rel == MANIFEST_NAME:
                    continue
                files.append((rel, p))
    files.sort()
    return files


def portable_digest(root: Path) -> str:
    """复刻官方算法，但路径用正斜杠（= Linux 上的结果）。"""
    # blake3 的 Python 绑定不一定有；优先用自带的 Rust 小工具，缺失时回退
    tool = Path(r"C:\rustbuild\portable-digest-target\release\portable-digest.exe")
    if tool.is_file():
        r = subprocess.run([str(tool), str(root)], capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            lines = [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
            if lines:
                return lines[-1]
    # 回退：Python 实现（需要 blake3 包）
    try:
        import blake3  # type: ignore
    except ImportError:
        raise RuntimeError("需要 blake3 包，或先构建 portable-digest 工具")
    h = blake3.blake3()
    for rel, p in collect(root):
        b = p.read_bytes()
        h.update(rel.encode())
        h.update(b"\x00")
        h.update(len(b).to_bytes(8, "little"))
        h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检查，不写入")
    args = ap.parse_args()

    if not MANIFEST.is_file():
        print(f"[FAIL] 找不到 {MANIFEST}")
        return 1

    want = portable_digest(BUNDLE)
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    have = d["integrity"]["bundle_blake3"]

    print(f"bundle      : {BUNDLE}")
    print(f"当前 manifest: {have}")
    print(f"跨平台摘要   : {want}")

    if have == want:
        print("[OK] 摘要已是跨平台版本")
        return 0

    if args.check:
        print("[WARN] 摘要不是跨平台版本 —— 提交官方前请运行本脚本（不带 --check）")
        return 1

    d["integrity"]["bundle_blake3"] = want
    MANIFEST.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
    print("[OK] 已写入跨平台摘要 —— 现在可以用带修复补丁的 hub 验证：")
    print(f'     hub check {BUNDLE} --allow-unsigned')
    return 0


if __name__ == "__main__":
    sys.exit(main())
