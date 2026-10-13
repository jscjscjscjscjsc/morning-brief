#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 39 轮 · 破晓时间线：首页列表上方加一条抛物线弧，
每条新闻是弧上一枚金色光点；越早越贴近地平线。点光点 = 读那一条。
弧与光点共用同一抛物公式 h = 4u(1-u)，不用 sin（脚本侧安全）。"""
import argparse, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "my-entry" / "morning-brief" / "bundle" / "main.splash"

OLD = """                            let rows = show_rows()
                            if rows.len() == 0 {"""

NEW = """                            // ---- 破晓时间线 · 每条新闻是弧上一枚光点，越早越贴近地平线 ----
                            let arc_rows = show_rows()
                            if arc_rows.len() > 0 {
                                View{width: Fill height: 176 flow: Overlay
                                    View{width: Fill height: Fill show_bg: true new_batch: true
                                        draw_bg +: {
                                            pixel: fn(){
                                                let sz = self.rect_size
                                                let px = self.pos.x
                                                let py = self.pos.y
                                                var c = #x0d1234
                                                let h = 4.0 * px * (1.0 - px)
                                                let ay = 0.86 - 0.70 * h
                                                let d = abs(py - ay)
                                                c = c.mix(#x2a3268, clamp(1.0 - d * 14.0, 0.0, 1.0) * 0.8)
                                                let hg = exp(-abs(py - 0.86) * 6.0) * exp(-px * 3.0)
                                                c = c.mix(#xffc65c, clamp(hg * 0.5, 0.0, 1.0))
                                                return vec4(c.x, c.y, c.z, 1.0)
                                            }
                                        }
                                    }
                                    for i r in arc_rows {
                                        let n = 0.0 + arc_rows.len()
                                        let u = (0.0 + i + 0.5) / n
                                        let hh = 4.0 * u * (1.0 - u)
                                        GestureView{width: Fit height: Fit align: Align{x: u y: 0.86 - 0.70 * hh} on_tap: |x, y| open_story(r)
                                            RoundedView{width: 30 height: 30 flow: Overlay draw_bg.color: #xffc65c draw_bg.border_radius: 15.0 draw_bg.border_size: 1.0 draw_bg.border_color: #xffe6bd
                                                Label{align: Align{x: 0.5 y: 0.5} text: rank_text(i) draw_text.color: #x161028 draw_text.text_style: theme.font_bold{font_size: 12}}
                                            }
                                        }
                                    }
                                    Label{width: Fill align: Align{x: 0.5 y: 0.97} text: "破晓时间线 · 点一枚光点，读那一条" draw_text.color: #x6c72a6 draw_text.text_style.font_size: 10}
                                }
                            }
                            let rows = show_rows()
                            if rows.len() == 0 {"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    raw = SRC.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    n = text.count(OLD)
    print("arc hits:", n)
    assert n == 1
    if not args.dry:
        text = text.replace(OLD, NEW)
        out = text.encode("utf-8")
        if bom:
            out = b"\xef\xbb\xbf" + out
        SRC.write_bytes(out)
        print("written", len(out))


if __name__ == "__main__":
    main()

