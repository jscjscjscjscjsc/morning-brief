#!/usr/bin/env python3
"""Replicate octosense_app_contract::bundle::digest_dir exactly.

Definition (from crates/app-contract/src/bundle.rs):
  - Walk every file under the bundle root (recursively).
  - Skip the ROOT-level manifest.json only (relative path == "manifest.json").
  - Refuse symlinks.
  - Give each file a "portable name": relative path with '/' separators.
  - Sort files by portable name (byte/string sort).
  - blake3 over, for each file in sorted order:
        name_bytes + b"\x00" + len(bytes).to_le_bytes(8) + content_bytes
  - Output hex.
"""
import sys
import os
from pathlib import Path

from blake3 import blake3

MANIFEST_FILE = "manifest.json"


def portable_name(root: Path, path: Path) -> str:
    rel = path.relative_to(root)
    return "/".join(rel.parts)


def collect(root: Path):
    out = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        d = Path(dirpath)
        for name in filenames:
            p = d / name
            if p.is_symlink():
                raise SystemExit(f"{p}: a bundle may not hold a symlink")
            rel = p.relative_to(root)
            if rel == Path(MANIFEST_FILE):
                continue
            out.append(p)
    return out


def digest_dir(root: Path) -> str:
    files = collect(root)
    named = [(portable_name(root, p), p) for p in files]
    named.sort(key=lambda t: t[0])
    h = blake3()
    for name, p in named:
        b = p.read_bytes()
        h.update(name.encode("utf-8"))
        h.update(b"\x00")
        h.update(len(b).to_bytes(8, "little"))
        h.update(b)
    return h.hexdigest()


if __name__ == "__main__":
    target = Path(sys.argv[1])
    print(digest_dir(target))
