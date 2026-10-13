#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 37 轮补丁四：守夜人那句话做成一颗小药丸，别压在正文上（截图里发现的问题）。

I1 自检提示改成底部一颗胶囊（自己的底色 + 发丝描边），不再是一行直接糊在卡片上。
I2 文案收短，够一颗胶囊装下。
用法：python tools/round37_fix4.py --dry / python tools/round37_fix4.py
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import round37_ui as R  # noqa: E402

TOAST_OLD = r"""            // 守夜人的一句话：只有自检发现文案读不出来时才露头
            watch_line := Label{visible: false width: Fill margin: Inset{left: 18 right: 18 bottom: 6}
                text: "" draw_text.color: #xffd98a draw_text.text_style.font_size: 10}"""
TOAST_NEW = r"""            // 守夜人的一句话：只有自检发现文案读不出来时才露头。
            // 做成底部一颗会淡出的胶囊 —— 它是一条系统提示，不压在正文上。
            watch_toast := RoundedView{visible: false width: Fit height: Fit flow: Down align: Align{x: 0.5}
                margin: Inset{left: 40 right: 40 bottom: 8} new_batch: true
                draw_bg.color: #x0d1132ee draw_bg.border_radius: 12.0
                draw_bg.border_size: 1.0 draw_bg.border_color: #xffc65c66
                padding: Inset{top: 7 bottom: 7 left: 12 right: 12}
                watch_line := Label{width: Fill text: "" draw_text.color: #xffd98a draw_text.text_style.font_size: 10}
            }"""

VIS_OLD = r"""    ui.watch_line.set_visible(heal_line != "")"""
VIS_NEW = r"""    ui.watch_toast.set_visible(heal_line != "")"""

HEALNOTE_OLD = r"""    heal_line = "界面自检 · " + t + "（第 " + ("" + heal_n) + " 次，已恢复）"
    heal_until = time_now() + 10.0
    ui.watch_line.set_text(heal_line)
    ui.watch_line.set_visible(true)"""
HEALNOTE_NEW = r"""    heal_line = "界面自检 · " + t + " · 第 " + ("" + heal_n) + " 次"
    heal_until = time_now() + 10.0
    ui.watch_line.set_text(heal_line)
    ui.watch_toast.set_visible(true)"""

SYNCBREAK_OLD = r'''    heal_line = "界面自检 · 有一条文案没读出来，其余照常（第 " + ("" + heal_n) + " 次）'''

SYNCBREAK_NEW = r'''    heal_line = "界面自检 · 有一段没读出来 · 第 " + ("" + heal_n) + " 次'''

GUARD_OLD = r"""        heal_note("「读稿」这格要等你先点开一条新闻")"""
GUARD_NEW = r"""        heal_note("「读稿」要等你先点开一条新闻")"""


def apply(s):
    s.swap("I1 提示改胶囊", TOAST_OLD, TOAST_NEW, 1)
    s.swap("I1 可见性跟随", VIS_OLD, VIS_NEW, 1)
    s.swap("I2 提示文案收短", HEALNOTE_OLD, HEALNOTE_NEW, 1)
    s.swap("I2 自检文案收短", SYNCBREAK_OLD, SYNCBREAK_NEW, 1)
    s.swap("I2 守卫文案收短", GUARD_OLD, GUARD_NEW, 1)
    s.swap("I2 守夜人补设可见性", r"""    if heal_line != "" { ui.watch_line.set_text(heal_line) }""",
           r"""    if heal_line != "" {
        ui.watch_line.set_text(heal_line)
        ui.watch_toast.set_visible(true)
    }""", 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(R.SRC))
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    s = R.Splash(pathlib.Path(args.file))
    apply(s)
    if args.dry:
        print("--dry：补丁四锚点全部命中，未写盘。")
        return
    s.save()
    print("已写盘：", args.file)


if __name__ == "__main__":
    main()
