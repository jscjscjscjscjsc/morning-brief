#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 38 轮 · 破晓时间线（Daybreak Timeline）第一步：把全屏每帧重绘换成
「静态梯度 + 量化慢速 + 交互驱动」，修下半屏渲染饥饿，同时立起新的背景语言。

用法:
  python tools/round38_ui.py --dry
  python tools/round38_ui.py
"""
import argparse, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "my-entry" / "morning-brief" / "bundle" / "main.splash"

OLD_WATER = """        water := View{width: Fill height: Fill show_bg: true new_batch: true
            draw_bg +: {
                pixel: fn(){
                    let sz = self.rect_size
                    let p = self.pos * sz
                    let t = self.draw_pass.time
                    let px = self.pos.x
                    let py = self.pos.y
                    // 清晨天色：夜靛 → 晨紫 → 玫瑰金（从上到下）
                    var c = #x0a0f28
                    c = c.mix(#x131a44, clamp(py * 2.2, 0.0, 1.0))
                    c = c.mix(#x2a2350, clamp((py - 0.42) * 2.6, 0.0, 1.0))
                    c = c.mix(#x41254f, clamp((py - 0.74) * 3.4, 0.0, 1.0))
                    c = c.mix(#x5a2b46, clamp((py - 0.93) * 6.0, 0.0, 1.0))
                    // 水面：两组缓慢交错的横向波纹
                    let w1 = sin(px * 7.0 + t * 0.55 + sin(py * 9.0 + t * 0.30) * 1.6)
                    let w2 = cos(px * 11.0 - t * 0.42 + cos(py * 14.0 - t * 0.22) * 1.2)
                    let rip = (w1 + w2) * 0.5
                    let band = exp(-abs(py - 0.62) * 3.0)
                    c = c.mix(#x3a4a9c, clamp((rip * 0.5 + 0.5) * band * 0.30, 0.0, 1.0))
                    // 晨光微尘：两簇很慢的光斑
                    let d1 = length(p / sz - vec2(fract(t * 0.013) * 1.4 - 0.2, 0.30))
                    let d2 = length(p / sz - vec2(fract(t * 0.009 + 0.5) * 1.5 - 0.25, 0.52))
                    c = c.mix(#xd8974a, clamp(exp(-d1 * 3.4) * 0.30 + exp(-d2 * 4.0) * 0.22, 0.0, 1.0))
                    // 水底还会自己荡开两圈很慢的波纹：不靠外部推，谁看它都在动
                    let q = fract(t * 0.09)
                    let dd = length(p / sz - vec2(0.30, 0.34))
                    let r1 = 1.0 - smoothstep(0.0, 0.012, abs(dd - (0.05 + 0.40 * q)))
                    let r2 = 1.0 - smoothstep(0.0, 0.018, abs(dd - (0.05 + 0.62 * q)))
                    let ring = (r1 * 0.42 + r2 * 0.24) * (1.0 - q)
                    c = c.mix(#xffe6bd, clamp(ring * 0.42, 0.0, 1.0))
                    return vec4(c.x, c.y, c.z, 1.0)
                }
            }
        }"""

NEW_WATER = """        water := View{width: Fill height: Fill show_bg: true new_batch: true
            draw_bg +: {
                wp: instance(0.0)
                wa: instance(0.5)
                pixel: fn(){
                    let sz = self.rect_size
                    let p = self.pos * sz
                    let tq = floor(self.draw_pass.time * 2.0) * 0.5
                    let px = self.pos.x
                    let py = self.pos.y
                    // 清晨天色：夜靛 → 晨紫 → 玫瑰金（静态梯度，不再每帧重算）
                    var c = #x0a0f28
                    c = c.mix(#x131a44, clamp(py * 2.2, 0.0, 1.0))
                    c = c.mix(#x2a2350, clamp((py - 0.42) * 2.6, 0.0, 1.0))
                    c = c.mix(#x41254f, clamp((py - 0.74) * 3.4, 0.0, 1.0))
                    c = c.mix(#x5a2b46, clamp((py - 0.93) * 6.0, 0.0, 1.0))
                    // 固定的旭日光晕：位置即「今天」的锚点
                    let ds = length(p / sz - vec2(0.72, 0.30))
                    c = c.mix(#xd8974a, clamp(exp(-ds * 3.0) * 0.25, 0.0, 1.0))
                    // 2fps 的晨光微尘：慢到几乎察觉，但界面是活的
                    let d1 = length(p / sz - vec2(fract(tq * 0.013) * 1.4 - 0.2, 0.30))
                    c = c.mix(#xd8974a, clamp(exp(-d1 * 3.4) * 0.18, 0.0, 1.0))
                    // 点按涟漪：从落点荡开的同心圆，随 wp 衰减归零后完全静止
                    let dd = length(p / sz - vec2(self.wa, 0.40))
                    let ring = sin(dd * 40.0 - tq * 6.0) * exp(-dd * 5.0) * self.wp
                    c = c.mix(#xffe6bd, clamp(ring * 0.35, 0.0, 1.0))
                    return vec4(c.x, c.y, c.z, 1.0)
                }
            }
        }"""

OLD_RAIL_G = """                        // 两道极慢的横向折光：界面在呼吸
                        let g1 = exp(-abs(px - (fract(self.draw_pass.time * 0.033) * (sz.x + 460.0) - 230.0)) / 152.0)
                        let g2 = exp(-abs(px - (fract(self.draw_pass.time * 0.019 + 0.42) * (sz.x + 560.0) - 280.0)) / 196.0)
                        c = c.mix(#x27316c, clamp((g1 * 0.7 + g2 * 0.5) * 0.55, 0.0, 1.0))"""

NEW_RAIL_G = """                        // 静置折光：两道固定柔光，呼吸感交给水面与涟漪
                        let g1 = exp(-abs(px - sz.x * 0.30) / 152.0)
                        let g2 = exp(-abs(px - sz.x * 0.78) / 196.0)
                        c = c.mix(#x27316c, clamp((g1 * 0.7 + g2 * 0.5) * 0.40, 0.0, 1.0))"""

OLD_RAIL_FLOW = """                        // 水线本身也在流动：一整条很慢的折光，读起来像水在走
                        let flow = exp(-abs(px - (fract(self.draw_pass.time * 0.045) * (sz.x + 320.0) - 160.0)) / 74.0)
                        c = c.mix(#xffc65c, clamp(flow * 0.30, 0.0, 1.0))"""

NEW_RAIL_FLOW = """                        // 水线静置：金色在中央微微发亮，点按时由涟漪接替动感
                        let flow = exp(-abs(px - sz.x * 0.5) / 220.0)
                        c = c.mix(#xffc65c, clamp(flow * 0.22, 0.0, 1.0))"""

OLD_SKY_T = """                                    let t = self.draw_pass.time
                                    let r = self.sr"""

NEW_SKY_T = """                                    let t = floor(self.draw_pass.time * 3.0) / 3.0
                                    let r = self.sr"""

OLD_PULSE = """    water_pulse = 1.0
    water_at = 0.12 + 0.19 * b"""

NEW_PULSE = """    water_pulse = 1.0
    water_at = 0.12 + 0.19 * b
    ui.water.wp = 1.0
    ui.water.wa = 0.12 + 0.19 * b"""

OLD_STEP = """    water_t = water_t + 0.07
    water_pulse = water_pulse * 0.96
    if water_pulse < 0.01 { water_pulse = 0.0 }"""

NEW_STEP = """    water_t = water_t + 0.07
    water_pulse = water_pulse * 0.96
    if water_pulse < 0.01 { water_pulse = 0.0 }
    ui.water.wp = water_pulse
    if water_pulse == 0.0 && water_tid != nil { stop_interval(water_tid) water_tid = nil }"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    raw = SRC.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    pairs = [
        ("water", OLD_WATER, NEW_WATER),
        ("rail_g", OLD_RAIL_G, NEW_RAIL_G),
        ("rail_flow", OLD_RAIL_FLOW, NEW_RAIL_FLOW),
        ("sky_t", OLD_SKY_T, NEW_SKY_T),
        ("pulse", OLD_PULSE, NEW_PULSE),
        ("step", OLD_STEP, NEW_STEP),
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

