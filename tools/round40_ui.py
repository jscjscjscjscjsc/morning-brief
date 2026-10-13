#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 40 轮 · 报头排版升级：刊名字级对比 + 报纸式双细线 + 首页主标题层级。"""
import argparse, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "my-entry" / "morning-brief" / "bundle" / "main.splash"

OLD_TITLE = """                                View{width: Fill height: Fit flow: Down
                                    Label{text: "晨报卡" draw_text.color: ink draw_text.text_style: theme.font_bold{font_size: sky_title_size()}}
                                }"""

NEW_TITLE = """                                View{width: Fill height: Fit flow: Down spacing: 2
                                    Label{text: "晨报卡" draw_text.color: ink draw_text.text_style: theme.font_bold{font_size: sky_title_size() + 8}}
                                }"""

OLD_SUB = """                            if sky_h > 180.0 {
                                Label{width: Fill margin: Inset{top: 6} text: "每天一份可以核验的科技晨报" draw_text.color: secondary draw_text.text_style.font_size: 12}
                            }"""

NEW_SUB = """                            if sky_h > 180.0 {
                                Label{width: Fill margin: Inset{top: 6} text: "每天一份可以核验的科技晨报" draw_text.color: secondary draw_text.text_style.font_size: 12}
                            }
                            // 报纸式双细线：刊名与内容之间的一道「版线」
                            View{width: Fill height: Fit flow: Down spacing: 2 margin: Inset{top: 8}
                                SolidView{width: Fill height: 2 draw_bg.color: gold}
                                SolidView{width: Fill height: 1 draw_bg.color: hair}
                            }"""

OLD_HOME = """                        home_title := Label{width: Fill text: "今天想读什么？" draw_text.color: ink draw_text.text_style: theme.font_bold{font_size: 22}}"""

NEW_HOME = """                        home_title := Label{width: Fill text: "今天想读什么？" draw_text.color: ink draw_text.text_style: theme.font_bold{font_size: 26}}"""

OLD_DOT = """                                            let k = 0.55 + 0.45 * sin(self.draw_pass.time * 3.2)"""

NEW_DOT = """                                            let k = 0.55 + 0.45 * sin(floor(self.draw_pass.time * 2.0) * 3.2)"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    raw = SRC.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    pairs = [
        ("title", OLD_TITLE, NEW_TITLE),
        ("sub", OLD_SUB, NEW_SUB),
        ("home", OLD_HOME, NEW_HOME),
        ("dot", OLD_DOT, NEW_DOT),
    ]
    for name, old, new in pairs:
        n = text.count(old)
        print(name, "hits:", n)
        assert n == 1, name
        if not args.dry:
            text = text.replace(old, new)
    if not args.dry:
        out = text.encode("utf-8")
        if bom:
            out = b"\xef\xbb\xbf" + out
        SRC.write_bytes(out)
        print("written", len(out))


if __name__ == "__main__":
    main()

