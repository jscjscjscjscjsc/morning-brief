#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 37 轮补丁三：把「清晨」调准 —— 太阳落到地平线上方，标题后面加一层柔光罩，
海面安静下来（上一版的 24px 刻度尺在这个尺寸上读起来像铁丝网）。
用法：python tools/round37_fix3.py --dry / python tools/round37_fix3.py
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import round37_ui as R  # noqa: E402

SUN_OLD = r"""                                    let sx = min(sz.x * 0.58, sz.x - 150.0)
                                    let sy = hy + rad * 1.15 - r * (rad * 1.15 + hy * 0.44)"""
SUN_NEW = r"""                                    let sx = min(sz.x * 0.70, sz.x - 110.0)
                                    let sy = hy - rad * 0.50 - r * (hy * 0.30)"""

SCRIM_OLD = r"""                                    // 地平线最炽热晨辉"""
SCRIM_NEW = r"""                                    // 标题后面一层柔光罩：太阳再亮，字也读得清
                                    let tmask = (1.0 - smoothstep(0.30, 0.66, p.y / hy)) * (1.0 - smoothstep(0.58, 0.94, p.x / sz.x))
                                    col = col.mix(#x0f1440, tmask * 0.40 * above)

                                    // 地平线最炽热晨辉"""

WAVE_OLD = r"""                                    let w1 = sin(p.y * 1.6 - t * 3.0 + sin(p.x * 0.07 + t * 1.2) * 2.8)
                                    let w2 = cos(p.y * 3.0 + t * 3.8 + cos(p.x * 0.11 - t * 1.5) * 2.0)"""
WAVE_NEW = r"""                                    let w1 = sin(p.y * 0.9 - t * 2.2 + sin(p.x * 0.05 + t * 0.9) * 2.2)
                                    let w2 = cos(p.y * 1.7 + t * 2.8 + cos(p.x * 0.09 - t * 1.1) * 1.6)"""

RULER_OLD = r"""                                    // 地平线极细金色光棱与 24px 经纬刻度尺
                                    let ld = abs(p.y - hy)
                                    col = col.mix(#xffeed5, (1.0 - smoothstep(0.3, 1.2, ld)) * 0.50)
                                    let tk = (1.0 - step(1.0, p.x - floor(p.x / 24.0) * 24.0)) * step(hy, p.y) * (1.0 - step(hy + 4.0, p.y))
                                    col = col.mix(#xffdca0, tk * 0.35)"""
RULER_NEW = r"""                                    // 地平线一线金棱（不再刻 24px 刻度尺：这个尺寸上读起来像铁丝网）
                                    let ld = abs(p.y - hy)
                                    col = col.mix(#xffeed5, (1.0 - smoothstep(0.4, 1.6, ld)) * 0.55)"""

REFL_OLD = r"""                                    let refl = (1.0 - smoothstep(wid * 0.18, wid, rx)) * wave * (1.0 - dep * 0.75) * (0.35 + 0.65 * r) * below
                                    col = col.mix(#xffcb5c, clamp(refl * 0.95, 0.0, 1.0))"""
REFL_NEW = r"""                                    let refl = (1.0 - smoothstep(wid * 0.14, wid * 0.9, rx)) * wave * (1.0 - dep * 0.75) * (0.35 + 0.65 * r) * below
                                    col = col.mix(#xffcb5c, clamp(refl * 0.72, 0.0, 1.0))"""

MELT_OLD = r"""                                    let bf = smoothstep(sz.y - 18.0, sz.y, p.y)"""
MELT_NEW = r"""                                    let bf = smoothstep(sz.y - 48.0, sz.y, p.y)"""


def apply(s):
    s.swap("H1 太阳落到地平线上方", SUN_OLD, SUN_NEW, 1)
    s.swap("H2 标题柔光罩", SCRIM_OLD, SCRIM_NEW, 1)
    s.swap("H3 海面安静下来", WAVE_OLD, WAVE_NEW, 1)
    s.swap("H4 去掉刻度尺", RULER_OLD, RULER_NEW, 1)
    s.swap("H5 倒影收窄", REFL_OLD, REFL_NEW, 1)
    s.swap("H6 底色融得更远", MELT_OLD, MELT_NEW, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(R.SRC))
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    s = R.Splash(pathlib.Path(args.file))
    apply(s)
    if args.dry:
        print("--dry：补丁三锚点全部命中，未写盘。")
        return
    s.save()
    print("已写盘：", args.file)


if __name__ == "__main__":
    main()
