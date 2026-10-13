#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 38b 轮 · 移除未验证语法（instance 赋值 / stop_interval），背景改为
静态梯度 + 2fps 微尘 + 固定光晕；涟漪计时改为 idle 门控。"""
import argparse, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "my-entry" / "morning-brief" / "bundle" / "main.splash"

OLD_WATER = """        water := View{width: Fill height: Fill show_bg: true new_batch: true
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

NEW_WATER = """        water := View{width: Fill height: Fill show_bg: true new_batch: true
            draw_bg +: {
                pixel: fn(){
                    let sz = self.rect_size
                    let p = self.pos * sz
                    let tq = floor(self.draw_pass.time * 2.0) * 0.5
                    let py = self.pos.y
                    // 清晨天色：夜靛 → 晨紫 → 玫瑰金（静态梯度）
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
                    // 水底两圈固定的慢波纹理：不耗帧，也有水的质感
                    let dd = length(p / sz - vec2(0.30, 0.34))
                    let r1 = 1.0 - smoothstep(0.0, 0.012, abs(dd - 0.21))
                    let r2 = 1.0 - smoothstep(0.0, 0.018, abs(dd - 0.43))
                    c = c.mix(#xffe6bd, clamp((r1 * 0.42 + r2 * 0.24) * 0.16, 0.0, 1.0))
                    return vec4(c.x, c.y, c.z, 1.0)
                }
            }
        }"""

OLD_PULSE = """    water_pulse = 1.0
    water_at = 0.12 + 0.19 * b
    ui.water.wp = 1.0
    ui.water.wa = 0.12 + 0.19 * b"""

NEW_PULSE = """    water_pulse = 1.0
    water_at = 0.12 + 0.19 * b"""

OLD_STEP = """    water_t = water_t + 0.07
    water_pulse = water_pulse * 0.96
    if water_pulse < 0.01 { water_pulse = 0.0 }
    ui.water.wp = water_pulse
    if water_pulse == 0.0 && water_tid != nil { stop_interval(water_tid) water_tid = nil }"""

NEW_STEP = """    water_pulse = water_pulse * 0.96
    if water_pulse < 0.01 { water_pulse = 0.0 }
    if water_pulse > 0.0 {
        water_t = water_t + 0.07
    }"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    raw = SRC.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    pairs = [
        ("water", OLD_WATER, NEW_WATER),
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

