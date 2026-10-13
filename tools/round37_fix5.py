#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 37 轮补丁五：自检提示胶囊修正（截图里它变成了中间一根竖条）。

J1 胶囊宽度写死成 Fill（原来 width: Fit 里套 width: Fill 的 Label，量不出宽度）。
用法：python tools/round37_fix5.py --dry / python tools/round37_fix5.py
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import round37_ui as R  # noqa: E402

TOAST_OLD = r"""            watch_toast := RoundedView{visible: false width: Fit height: Fit flow: Down align: Align{x: 0.5}
                margin: Inset{left: 40 right: 40 bottom: 8} new_batch: true"""
TOAST_NEW = r"""            watch_toast := RoundedView{visible: false width: Fill height: Fit flow: Down align: Align{x: 0.5}
                margin: Inset{left: 30 right: 30 bottom: 8} new_batch: true"""


def apply(s):
    s.swap("J1 胶囊宽度", TOAST_OLD, TOAST_NEW, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(R.SRC))
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    s = R.Splash(pathlib.Path(args.file))
    apply(s)
    if args.dry:
        print("--dry：补丁五锚点命中，未写盘。")
        return
    s.save()
    print("已写盘：", args.file)


if __name__ == "__main__":
    main()
