#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 37 轮补丁二：把「看得见的清晨」修出来。

日志里抓到的真凶（.dev/state-8177/card-host.log）：
  [E] splash:5651 - shader builtin atan requires 1 arg, got 2
上一轮那套「晨曦放射霞光射线」用了两参数 atan(y, x)，这个宿主不认；
整个天空 shader 因此编译失败 —— 所以界面一直是平的一块夜色（这也就是用户说的
「前端渲染不够」）。这个补丁：
  G1 霞光射线改成不用 atan 的写法（相位随距离旋转），太阳、日冕、地平线晨辉全部能画出来。
  G2 去掉两处 ui.*.render()：宿主报「widget method render not found」，每 70 毫秒刷一行错。
     标签栏的水面、水底的水面都改成只吃 draw_pass.time，自己会动，不需要外部推。
  G3 修掉几个越界的 sdf.box（宽高顶到控件外，会把整块填成浅色）。
用法：python tools/round37_fix2.py --dry / python tools/round37_fix2.py
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import round37_ui as R  # noqa: E402

# G1 · 两参数 atan → 不用 atan 的放射相位（太阳一出来，霞光就是放射状的）
RAY_OLD = r"""                                    let ang = atan(p.y - sy, p.x - sx)
                                    let ray1 = sin(ang * 14.0 + t * 0.85)
                                    let ray2 = cos(ang * 7.0 - t * 0.45)"""
RAY_NEW = r"""                                    let ux = (p.x - sx) / (rad * 5.0 + 34.0)
                                    let uy = (p.y - sy) / (rad * 5.0 + 34.0)
                                    let ray1 = sin(ux * 9.0 + uy * 2.4 + t * 0.85)
                                    let ray2 = cos(ux * 4.5 - uy * 6.5 - t * 0.45)"""

# G2a · 标签栏：只留水面与水线，光点交给「亮着的那一格」自己画
RAIL_INST_OLD = r"""                    tb: instance(0.0)
                    tt: instance(0.0)
                    tp: instance(0.0)
                    tw: instance(0.0)
"""
RAIL_BIND_OLD = r"""                draw_bg.tb: tab_from
                draw_bg.tt: tab_to
                draw_bg.tp: tab_p
                draw_bg.tw: tab_swell
"""
RAIL_IND_OLD = r"""                        // 标签滑轨：一条暗金水线，从窗口这头通到那头
                        let ry = sz.y - 1.7
                        sdf.box(0.0, ry, sz.x, 1.6, 0.8)
                        sdf.fill(#x2a3268)
                        // 高亮光点：tab_from → tab_to，走一格就滑一格
                        let padx = 10.0
                        let sp = 3.0
                        let cw = (sz.x - padx * 2.0 - sp * 4.0) / 5.0
                        let p = clamp(self.tp, 0.0, 1.0)
                        let e = p * p * (3.0 - 2.0 * p)
                        let a = self.tb * (1.0 - e) + self.tt * e
                        let cx = padx + a * (cw + sp) + cw * 0.5
                        let w = clamp(self.tw, 0.0, 1.0)
                        let d = abs(px - cx)
                        // 光点本体
                        let core = exp(-d / (7.0 + 12.0 * w))
                        c = c.mix(#xfff3d2, clamp(core * (0.35 + 0.5 * w), 0.0, 1.0))
                        // 一小段被点亮的滑轨
                        let seg = exp(-d / (30.0 + 34.0 * w))
                        c = c.mix(#xffc65c, clamp(seg * (0.22 + 0.42 * w), 0.0, 1.0))
                        sdf.fill(c)
                        // 顶上一条极细的天光
                        sdf.box(0.0, 0.0, sz.x, 1.0, 0.5)
                        sdf.fill(#xffffff1f)"""
RAIL_IND_NEW = r"""                        // 标签滑轨：一条暗金水线，从窗口这头通到那头
                        let ry = sz.y - 1.7
                        sdf.box(1.0, ry, sz.x - 2.0, 1.6, 0.8)
                        sdf.fill(#x2a3268)
                        // 水线本身也在流动：一整条很慢的折光，读起来像水在走
                        let flow = exp(-abs(px - (fract(self.draw_pass.time * 0.045) * (sz.x + 320.0) - 160.0)) / 74.0)
                        c = c.mix(#xffc65c, clamp(flow * 0.30, 0.0, 1.0))
                        // 顶上一条极细的天光
                        sdf.box(1.0, 0.0, sz.x - 2.0, 1.0, 0.5)
                        c = c.mix(#xffffff, 0.09)"""

# G2b · 水底：时间从 draw_pass.time 走，不再需要外部推
WATER_T_OLD = r"""                wt: instance(0.0)
                wp: instance(0.0)
                wa: instance(0.5)
                pixel: fn(){
                    let sz = self.rect_size
                    let p = self.pos * sz
                    let t = self.wt"""
WATER_T_NEW = r"""                pixel: fn(){
                    let sz = self.rect_size
                    let p = self.pos * sz
                    let t = self.draw_pass.time"""
WATER_RING_OLD = r"""                    // 你按下时荡开的两圈同心波纹（手机轻点也算）
                    let q = clamp(self.wp, 0.0, 1.0)
                    let ax = clamp(self.wa, 0.0, 1.0)
                    let dd = length(p / sz - vec2(ax, 0.34))
                    let r1 = 1.0 - smoothstep(0.0, 0.014, abs(dd - (0.05 + 0.40 * (1.0 - q))))
                    let r2 = 1.0 - smoothstep(0.0, 0.020, abs(dd - (0.05 + 0.62 * (1.0 - q))))
                    let ring = (r1 * 0.55 + r2 * 0.30) * q
                    c = c.mix(#xffe6bd, clamp(ring * 0.75, 0.0, 1.0))"""
WATER_RING_NEW = r"""                    // 水底还会自己荡开两圈很慢的波纹：不靠外部推，谁看它都在动
                    let q = fract(t * 0.09)
                    let dd = length(p / sz - vec2(0.30, 0.34))
                    let r1 = 1.0 - smoothstep(0.0, 0.012, abs(dd - (0.05 + 0.40 * q)))
                    let r2 = 1.0 - smoothstep(0.0, 0.018, abs(dd - (0.05 + 0.62 * q)))
                    let ring = (r1 * 0.42 + r2 * 0.24) * (1.0 - q)
                    c = c.mix(#xffe6bd, clamp(ring * 0.42, 0.0, 1.0))"""
WATER_BIND_OLD = r"""            draw_bg.wt: water_t
            draw_bg.wp: water_pulse
            draw_bg.wa: water_at
"""

# G2c · 别再调那两个不存在的 render()
TAB_STEP_RENDER_OLD = r"""    ui.tab_rail.render()
    if tab_p >= 1.0 && tab_swell == 0.0 && water_pulse == 0.0 {
        tab_from = tab_to
        ui.tab_rail.render()"""
TAB_STEP_RENDER_NEW = r"""    if tab_p >= 1.0 && tab_swell == 0.0 && water_pulse == 0.0 {
        tab_from = tab_to"""
FIELD_RENDER_OLD = r"""    ui.water.render()
    if tab_tid == nil { ui.tab_rail.render() }"""
FIELD_RENDER_NEW = r"""    if tab_tid == nil { sync_tabs() }"""

# G3 · 越界的 sdf.box（宽高顶满控件会把整块填成浅色）
SECLINE_OLD = r"""            sdf.box(0.0, 0.0, sz.x, 1.6, 0.8)"""
SECLINE_NEW = r"""            sdf.box(1.0, 0.0, sz.x - 2.0, 1.6, 0.8)"""

# 亮着的那一格：脚下金线加宽 + 托一层暖光，一眼看出「就是这一页」
TABON_OLD = r"""            // 脚下一道金色水线：这就是「你正在这一页」
            sdf.box(2.0, sz.y - 2.8, sz.x - 4.0, 2.6, 1.3)
            sdf.fill(#xffc65c)
            sdf.box(6.0, sz.y - 2.0, sz.x - 12.0, 7.0, 3.0)
            sdf.fill(#xffc65c22)"""
TABON_NEW = r"""            // 脚下一道金色水线：这就是「你正在这一页」
            sdf.box(2.0, sz.y - 3.0, sz.x - 4.0, 3.0, 1.5)
            sdf.fill(#xffc65c)
            sdf.box(3.0, sz.y - 9.0, sz.x - 6.0, 9.0, 3.0)
            sdf.fill(#xffc65c2e)"""


def apply(s):
    s.swap("G1 霞光射线去 atan", RAY_OLD, RAY_NEW, 1)
    s.swap("G2a 标签栏实例声明", RAIL_INST_OLD, "", 1)
    s.swap("G2a 标签栏绑定", RAIL_BIND_OLD, "", 1)
    s.swap("G2a 标签栏指示光", RAIL_IND_OLD, RAIL_IND_NEW, 1)
    s.swap("G2b 水底时间", WATER_T_OLD, WATER_T_NEW, 1)
    s.swap("G2b 水底自荡波纹", WATER_RING_OLD, WATER_RING_NEW, 1)
    s.swap("G2b 水底绑定", WATER_BIND_OLD, "", 1)
    s.swap("G2c tab_step 不再调 render", TAB_STEP_RENDER_OLD, TAB_STEP_RENDER_NEW, 1)
    s.swap("G2c field_step 不再调 render", FIELD_RENDER_OLD, FIELD_RENDER_NEW, 1)
    s.swap("G3 水线不越界", SECLINE_OLD, SECLINE_NEW, 1)
    s.swap("G3 亮标签金线加宽", TABON_OLD, TABON_NEW, 1)
    for bad in ("atan(", "ui.tab_rail.render()", "ui.water.render()", "self.wt", "self.tb"):
        n = s.text.count(bad)
        assert n == 0, "还有残留：%s ×%d" % (bad, n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(R.SRC))
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    s = R.Splash(pathlib.Path(args.file))
    apply(s)
    if args.dry:
        print("--dry：补丁二锚点全部命中，未写盘。")
        return
    s.save()
    print("已写盘：", args.file)


if __name__ == "__main__":
    main()
