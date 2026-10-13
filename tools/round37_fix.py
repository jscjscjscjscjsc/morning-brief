#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 37 轮补丁一：把标签栏挪到卡片最顶上，并让清晨的太阳真的看得见。

跑完 tools/round37_ui.py 之后跑这个。它做四件事：
  F1 标签栏从「整卡的背后」挪进主干列的第一格（现在被内容盖住了，看不见）。
  F2 晨光常驻抬到 0.55：开机就是清晨，太阳在天空带上半部，一眼能看见。
  F3 标签字号收到 12，五格等分 76pt 里「情报池 23」这种也放得下。
  F4 开机就把天亮起来（boot 里补一次 sky_kick）。
用法：python tools/round37_fix.py --dry / python tools/round37_fix.py
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import round37_ui as R  # noqa: E402  复用同一个 Splash 与同一份标签栏文本

COLUMN = r"""        View{width: Fill height: Fill flow: Down
            // ---- 地平线带 · 所有阶段共用；太阳的高度 = 今天这份报做到哪了 ----"""

REST_OLD = r"""    if r < 0.34 { r = 0.34 }"""
REST_NEW = r"""    if r < 0.55 { r = 0.55 }"""

SUN_OLD = r"""                                    let rad = min(sz.y * 0.20, 32.0)"""
SUN_NEW = r"""                                    let rad = min(sz.y * 0.24, 42.0)"""

GLOW_OLD = r"""                                    let hg = exp(-abs(p.y - hy) / 24.0) * exp(-abs(p.x - sx) / 160.0) * (0.95 - 0.45 * r)"""
GLOW_NEW = r"""                                    let hg = exp(-abs(p.y - hy) / 30.0) * exp(-abs(p.x - sx) / 170.0) * (1.05 - 0.35 * r)"""

TABFONT_OLD = r"""    draw_text +: {color: #xfff3d8 color_hover: #xffffff color_down: #xfff3d8 text_style: theme.font_bold{font_size: 13}}"""
TABFONT_NEW = r"""    draw_text +: {color: #xfff3d8 color_hover: #xffffff color_down: #xfff3d8 text_style: theme.font_bold{font_size: 12}}"""

TABFONT2_OLD = r"""    draw_text +: {color: #x9199ca color_hover: #xeceefe color_down: #xfff1cf text_style +: {font_size: 13}}"""
TABFONT2_NEW = r"""    draw_text +: {color: #x9199ca color_hover: #xeceefe color_down: #xfff1cf text_style +: {font_size: 12}}"""

BOOT_OLD = r"""    // 第 37 轮：水面心跳（每 70 毫秒推一格波纹）＋ 守夜人（每半秒重落一次可见性）
    field_kick()"""
BOOT_NEW = r"""    // 第 37 轮：水面心跳（每 70 毫秒推一格波纹）＋ 守夜人（每半秒重落一次可见性）
    sky_kick()
    field_kick()"""


def apply(s):
    s.swap("F1a 撤掉背后的标签栏", R.RAIL_NEW, "", 1)
    s.swap("F1b 标签栏放进主干列", COLUMN, r"""        View{width: Fill height: Fill flow: Down
""" + R.RAIL_NEW + r"""            // ---- 地平线带 · 所有阶段共用；太阳的高度 = 今天这份报做到哪了 ----""", 1)
    s.swap("F2a 晨光常驻抬到 0.55", REST_OLD, REST_NEW, 1)
    s.swap("F2b 太阳画大一点", SUN_OLD, SUN_NEW, 1)
    s.swap("F2c 地平线晨辉加宽", GLOW_OLD, GLOW_NEW, 1)
    s.swap("F3a 亮标签字号", TABFONT_OLD, TABFONT_NEW, 1)
    s.swap("F3b 暗标签字号", TABFONT2_OLD, TABFONT2_NEW, 1)
    s.swap("F4 开机天亮", BOOT_OLD, BOOT_NEW, 1)
    # 标签栏现在应当在主干列里：它前面紧挨着的就是那一行 View{...flow: Down}
    i = s.text.index("tab_rail := View{")
    assert "View{width: Fill height: Fill flow: Down" in s.text[i - 200:i], "标签栏没在主干列里"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(R.SRC))
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    s = R.Splash(pathlib.Path(args.file))
    apply(s)
    if args.dry:
        print("--dry：补丁锚点全部命中，未写盘。")
        return
    s.save()
    print("已写盘：", args.file)


if __name__ == "__main__":
    main()

