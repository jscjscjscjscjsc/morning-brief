#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 37 轮 · 水面上的浏览器（Waterfront）—— main.splash 的锚点切片升级脚本

为什么是一个脚本，而不是手工改：
  · 这个文件 5900 行，手工改必然漏掉同步点；脚本每处都 assert 命中次数。
  · 同一个脚本重跑一次就是同一个结果，评审可以复核（AGENTS.md 的纪律）。

三件事：
  1) 顶部横幅变成真正的标签栏：头版 / 情报池 / 复盘 / 立场 / 读稿 五格，
     可见性由 sync_tabs() 单点决定，永远是「五选一」——不再出现切到空栏目 = 白屏。
  2) 清晨水面材质：划过有微澜，按下有同心波纹；整屏有晨光微尘与水波折光。
  3) 守夜人：每 0.5 秒重落一次可见性，任何一条文案出错都不会把整个界面撂倒。

用法：
  python tools/round37_ui.py --dry     # 只检查锚点，不写文件
  python tools/round37_ui.py           # 写回 bundle/main.splash（保留原换行）
"""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "my-entry" / "morning-brief" / "bundle" / "main.splash"

class Splash(object):
    def __init__(self, path):
        raw = path.read_bytes()
        self.bom = raw.startswith(b"\xef\xbb\xbf")
        if self.bom:
            raw = raw[3:]
        text = raw.decode("utf-8")
        self.crlf = text.count("\r\n") * 2 > text.count("\n")
        self.text = text.replace("\r\n", "\n")
        self.path = path
        self.hits = []

    def span(self, label, start, end, new, expect=1):
        """把 [start .. end] 之间（含两端）整段换成 new。"""
        n = self.text.count(start)
        assert n == expect, "[%s] 起始锚点命中 %d 次（期望 %d）：%r" % (label, n, expect, start[:70])
        i = self.text.find(start)
        j = self.text.find(end, i)
        assert j > i, "[%s] 结束锚点没找到：%r" % (label, end[:70])
        self.text = self.text[:i] + new + self.text[j + len(end):]
        self.hits.append(label)

    def swap(self, label, old, new, expect=1):
        n = self.text.count(old)
        assert n == expect, "[%s] 锚点命中 %d 次（期望 %d）：%r" % (label, n, expect, old[:70])
        self.text = self.text.replace(old, new)
        self.hits.append(label)

    def insert_before(self, label, anchor, new):
        n = self.text.count(anchor)
        assert n == 1, "[%s] 锚点命中 %d 次：%r" % (label, n, anchor[:70])
        self.text = self.text.replace(anchor, new + anchor)
        self.hits.append(label)

    def save(self):
        out = self.text.replace("\n", "\r\n") if self.crlf else self.text
        data = out.encode("utf-8")
        if self.bom:
            data = b"\xef\xbb\xbf" + data
        self.path.write_bytes(data)

# ---------------------------------------------------------------------
# 第 37 轮的核心：标签栏 + 守夜人 + 水面
# ---------------------------------------------------------------------
TABS = r"""
// =====================================================================
// 第 37 轮 · 水面上的浏览器（Waterfront）
// ---------------------------------------------------------------------
// 这一轮只做三件事，但每一件都对着一个具体的毛病：
//
// ① 顶部横幅 = 真正的标签栏。五个格子：头版 / 情报池 / 复盘 / 立场 / 读稿。
//    旧的毛病：切到某个栏目时那块内容是空的，而可见性是一次性写死的，
//    于是整屏什么都不剩（白屏），只能退出重开。现在可见性只由 sync_tabs() 决定，
//    它永远「五选一」，并且自己会把不成立的标签收回 —— 没有「全部隐藏」这条路。
// ② 清晨水面材质：划过是微澜，按下是同心波纹；整屏有晨光微尘与水波折光。
// ③ 守夜人：每 0.5 秒重落一次可见性。任何一条文案读不出来，只影响那一条，
//    并且自愈的事会如实写在标签栏下面 —— 故障也是过程的一部分。
// =====================================================================
let active_tab = "front"        // front / pool / review / stand / story
let story_tab = false           // 「读稿」这格占着没有
let story_tab_text = ""         // 读稿格子上的短标题（前四个字）
let story_back = "intent"       // 进读稿之前停在哪个阶段，关掉要还回去
let tab_from = 0.0              // 上一格（0..4）
let tab_to = 0.0                // 现在这一格
let tab_p = 1.0                 // 滑动进度 0..1，1 = 停稳
let tab_dir = 1.0               // 往右切 +1 / 往左切 -1
let tab_tid = nil
let tab_swell = 0.0             // 切换时的一次水涌：1 → 0
let watch_tid = nil
let watch_hits = 0
let heal_n = 0                  // 自愈次数（如实写进界面）
let heal_line = ""
let heal_until = 0
let water_t = 0.0
let water_tid = nil
let water_pulse = 0.0           // 每次点按，水面中心泛一下
let water_at = 0.5              // 波纹落在水面的哪个横坐标（0..1）

fn tab_slot(t){
    if t == "front" { return 0.0 }
    if t == "pool" { return 1.0 }
    if t == "review" { return 2.0 }
    if t == "stand" { return 3.0 }
    if t == "story" { return 4.0 }
    0.0
}

fn tab_front_text(){
    if phase == "fetching" { return "头版·印" }
    if phase == "refused" { return "头版·休" }
    if phase == "done" || phase == "story" { return "头版" }
    "头版"
}

fn tab_pool_text(){
    if cand.len() > 0 { return "情报池 " + ("" + cand.len()) }
    if picked.len() > 0 { return "情报池 " + ("" + picked.len()) }
    "情报池"
}

fn tab_review_text(){
    if panel.len() > 0 { return "复盘 " + ("" + panel.len()) + "/" + ("" + roles.len()) }
    "复盘"
}

fn tab_stand_text(){
    let n = fix_count() + clash_count()
    if n > 0 { return "立场 " + ("" + n) }
    "立场"
}

fn tab_story_text(){
    if story_tab_text != "" { return story_tab_text }
    "读稿"
}

// 自愈要写在界面上 —— 过程与故障都摊开，是这个应用一贯的立场
fn heal_note(t){
    heal_n = heal_n + 1
    heal_line = "界面自检 · " + t + "（第 " + ("" + heal_n) + " 次，已恢复）"
    heal_until = time_now() + 10.0
    ui.watch_line.set_text(heal_line)
    ui.watch_line.set_visible(true)
}

// 任何一条文案读不出来时走这里：只记一笔，界面照旧。
// 可见性在 sync_ui() 的最前面就落定了，所以文案出错 = 少一行字，不是整屏空。
fn sync_break(){
    heal_n = heal_n + 1
    heal_line = "界面自检 · 有一条文案没读出来，其余照常（第 " + ("" + heal_n) + " 次）"
    heal_until = time_now() + 8.0
}

fn phase_known(){
    if phase == "intent" { return true }
    if phase == "asking" { return true }
    if phase == "plan" { return true }
    if phase == "denied" { return true }
    if phase == "fetching" { return true }
    if phase == "judging" { return true }
    if phase == "refused" { return true }
    if phase == "done" { return true }
    if phase == "story" { return true }
    false
}

fn set_tab(t){
    if t == "story" && !story_tab {
        heal_note("「读稿」这格要等你先点开一条新闻")
        return
    }
    if t == active_tab {
        if t == "story" { phase = "story" }
        sync_tabs()
        return
    }
    let a = tab_slot(active_tab)
    let b = tab_slot(t)
    tab_from = a
    tab_to = b
    tab_p = 0.0
    if b < a { tab_dir = -1.0 } else { tab_dir = 1.0 }
    active_tab = t
    tab_swell = 1.0
    water_pulse = 1.0
    water_at = 0.12 + 0.19 * b
    if t == "story" { phase = "story" }
    if tab_tid == nil { tab_tid = start_interval(0.02, || tab_step()) }
    sync_tabs()
}

fn tab_step(){
    tab_p = min(1.0, tab_p + 0.08)
    tab_swell = tab_swell * 0.90
    if tab_swell < 0.02 { tab_swell = 0.0 }
    water_pulse = water_pulse * 0.95
    if water_pulse < 0.01 { water_pulse = 0.0 }
    ui.tab_rail.render()
    if tab_p >= 1.0 && tab_swell == 0.0 && water_pulse == 0.0 {
        tab_from = tab_to
        ui.tab_rail.render()
        if tab_tid != nil { stop_timer(tab_tid) }
        tab_tid = nil
    }
}

// 可见性单点：五个格子，永远有且只有一个内容区亮着
fn sync_tabs(){
    if active_tab == "story" && !(story_tab && story != nil) { active_tab = "front" }
    if story_tab && story == nil { story_tab = false }

    let prep = phase == "intent" || phase == "asking" || phase == "plan" || phase == "judging" || phase == "denied"
    let front = active_tab == "front"
    let story_on = active_tab == "story"
    let paper = phase == "fetching" || phase == "done" || phase == "story"

    ui.tab_front_on.set_text(tab_front_text())
    ui.tab_front_off.set_text(tab_front_text())
    ui.tab_pool_on.set_text(tab_pool_text())
    ui.tab_pool_off.set_text(tab_pool_text())
    ui.tab_review_on.set_text(tab_review_text())
    ui.tab_review_off.set_text(tab_review_text())
    ui.tab_stand_on.set_text(tab_stand_text())
    ui.tab_stand_off.set_text(tab_stand_text())
    ui.tab_story_on.set_text(tab_story_text())
    ui.tab_story_off.set_text(tab_story_text())
    ui.tab_story_on.set_visible(story_on)
    ui.tab_story_off.set_visible(!story_on)

    ui.tab_front_on.set_visible(front)
    ui.tab_front_off.set_visible(!front)
    ui.tab_pool_on.set_visible(active_tab == "pool")
    ui.tab_pool_off.set_visible(active_tab != "pool")
    ui.tab_review_on.set_visible(active_tab == "review")
    ui.tab_review_off.set_visible(active_tab != "review")
    ui.tab_stand_on.set_visible(active_tab == "stand")
    ui.tab_stand_off.set_visible(active_tab != "stand")

    ui.story_pane.set_visible(story_on)
    ui.pool_pane.set_visible(active_tab == "pool")
    ui.review_pane.set_visible(active_tab == "review")
    ui.stand_pane.set_visible(active_tab == "stand")
    if front {
        ui.browse.set_visible(prep)
        ui.run_pane.set_visible(!prep && paper)
        ui.refuse_pane.set_visible(phase == "refused")
    } else {
        ui.browse.set_visible(false)
        ui.run_pane.set_visible(false)
        ui.refuse_pane.set_visible(false)
    }
    ui.watch_line.set_visible(heal_line != "")
}

// 守夜人：每半秒重落一次可见性。它是幂等的，所以哪怕上一拍 sync_ui 中途出错，
// 半秒之内界面也会被拨回来 —— 这就是「用着用着白屏、只能退出重开」的死因。
fn watch_tick(){
    watch_hits = watch_hits + 1
    if !cg_done && cg_tid == nil { cg_off() }
    if story_tab && story == nil { story_tab = false }
    if !phase_known() { phase = "intent" active_tab = "front" }
    if heal_line != "" && time_now() > heal_until { heal_line = "" }
    if heal_line != "" { ui.watch_line.set_text(heal_line) }
    sync_tabs()
}

fn field_kick(){
    if water_tid == nil { water_tid = start_interval(0.07, || field_step()) }
}

fn field_step(){
    water_t = water_t + 0.07
    water_pulse = water_pulse * 0.96
    if water_pulse < 0.01 { water_pulse = 0.0 }
    tab_swell = tab_swell * 0.94
    if tab_swell < 0.02 { tab_swell = 0.0 }
    ui.water.render()
    if tab_tid == nil { ui.tab_rail.render() }
}

fn go_prep(){
    active_tab = "front"
    if !(phase == "intent" || phase == "asking" || phase == "plan") { restart() }
    sync_tabs()
}

// ---- 新栏目要念的三段话：都是既有数据，零额外调用 ----
fn pool_head_text(){
    if work_n == 0 {
        if phase == "fetching" { return "正在取数。拿到候选后会按信源等级排在这里 —— 传闻、转载、二手、一手，各占多少。"
        }
        if picked.len() > 0 { return "这一期已经见报 " + ("" + picked.len()) + " 条（来自往期恢复，取数记录不在内存里）。"
        }
        return "今天还没有取数。回到「头版」按下「生成晨报」，批准之后这里会列出每一条候选和它的信源等级。"
    }
    "今天扫了 " + ("" + work_n) + " 条原始条目，" + ("" + work_cand) + " 条进了池子，见报 " + ("" + picked.len()) + " 条。"
}

fn pool_rows_text(){
    if cand.len() == 0 {
        if phase == "fetching" { return "正在取数…" }
        return "池子还是空的。"
    }
    let out = ""
    let i = 0
    for r in cand {
        if i < 16 {
            if out != "" { out = out + "\n" }
            out = out + pad2(i + 1) + "  [" + tier_label(r) + "]  " + row_title(r) + "\n      " + row_src(r)
        }
        i = i + 1
    }
    let rest = cand.len() - 16
    if rest > 0 { out = out + "\n… 还有 " + ("" + rest) + " 条在池子里" }
    out
}

fn pool_panel_text(){
    if panel.len() == 0 {
        if phase == "judging" { return "三位初审正在各自独立地读候选，谁也不看谁的意见…" }
        return "还没有初审意见。出报时三位编辑会背靠背各写一句点评，原话会留在这里。"
    }
    let out = ""
    for p in panel {
        let lb = s_of(p, "label")
        if lb == "" { lb = "初审编辑" }
        let st = s_of(p, "state")
        if out != "" { out = out + "\n" }
        if st == "fail" { out = out + "· " + lb + "：这次没答复" }
        else {
            let dg = s_of(p, "digest")
            if dg == "" { dg = "（这位编辑没有留下点评）" }
            out = out + "· " + lb + "：" + dg
        }
    }
    out
}

fn pool_work_text(){
    let out = ""
    let t1 = tier_line()
    if t1 != "" { out = t1 }
    let t2 = work_line()
    if t2 != "" {
        if out != "" { out = out + "\n" }
        out = out + t2
    }
    let t3 = src_line()
    if t3 != "" {
        if out != "" { out = out + "\n" }
        out = out + t3
    }
    if out == "" { out = "还没有这一期的取数记录。" }
    out
}

fn review_head_text(){
    if replay_text() == "" {
        return "还没有可以回放的过程。出过一期之后，这里会摊开：候选池扫了多少条、三位初审各自的原话、主编终审的取舍理由 —— 零额外 AI 调用，全是本来就要落盘的数据。"
    }
    "这一期是怎么做出来的：候选池 → 三位初审 → 主编终审 → 对账。"
}

fn review_fc_text(){
    let out = ""
    let a = fc_hist_text()
    if a != "" { out = a }
    let b = fc_review_line()
    if b != "" {
        if out != "" { out = out + "\n\n" }
        out = out + b
    }
    if out == "" { out = "还没有可对账的预测记录。" }
    out
}

fn stand_head_text(){
    let n = fix_count()
    if n > 0 { return "这一期有一处更正要登在最前面 —— 报错了，就写在最前面。" }
    if clash_count() > 0 { return "今天本报注意到两处口径不一致：两个数字都在，我不替你选。" }
    "立场这一格放三样东西：更正、口径不一致、以及本报写死的编辑方针（可以被读者引用与追责）。"
}

fn stand_ledger_text(){
    "截至今天：累计更正 " + ("" + fix_total) + " 条 · 发现口径不一致 " + ("" + clash_total) + " 次。\n这条台账只增不减，写在本机。"
}
"""

# sync_ui 的三处手术：可见性提到最前 + 三段 try/catch 兜底
SYNC_OPEN = r"""fn sync_ui(){
    // 第 37 轮：可见性先落定。文案在后面出任何错，界面也是完整的。
    sync_tabs()
    try {
    ui.intent_line.set_text(intent_preview())"""

SYNC_MID1 = r"""    ui.limit_label.set_text("" + limit)
    } catch err { sync_break() }
    try {
    ui.gen_pane.set_visible(phase == "intent")"""

SYNC_MID2 = r"""    ui.rv_btn.set_text(rv_text())
    } catch err { sync_break() }
    try {
    ui.list.render()"""

SYNC_END = r"""    if ag_open { ui.ag_log_box.render() }
    } catch err { sync_break() }
    sync_panes()
}"""


# ---------------------------------------------------------------------
# 一、模板：把「可点的东西」统一成一块水面
#     全部走「锚点替换 + assert 命中数」，禁止整段重写。
# ---------------------------------------------------------------------

# 深色小胶囊（主编对话条上那一排动作）：按下时从中心荡开一圈同心波纹
CHIPDK_OLD = r"""let ChipDk = ButtonFlat{height: 32 padding: Inset{left: 13 right: 13}
    draw_bg +: {border_radius: 16.0 color: #xffffff0d color_hover: #xffffff1c color_down: #xffffff2a border_size: 1.0
        border_color: #xffffff22 border_color_hover: #xffc65c80 border_color_down: #xffc65c}
    draw_text +: {color: soft color_hover: #xffffff color_down: #xffffff text_style +: {font_size: 12}}
}"""
CHIPDK_NEW = r"""let ChipDk = ButtonFlat{height: 32 padding: Inset{left: 13 right: 13}
    draw_bg +: {
        pixel: fn(){
            let sz = self.rect_size
            let sdf = Sdf2d.viewport(self.pos * sz)
            sdf.box(1.0, 1.0, sz.x - 2.0, sz.y - 2.0, 16.0)
            let d = length(self.pos * sz - sz * 0.5)
            let ring = sin(d * 0.26 - self.draw_pass.time * 8.6) * exp(-d * 0.05)
            var c = #xffffff0d
            c = c.mix(#xffffff22, self.hover * 0.9)
            c = c.mix(#xffffff30, self.down * 0.8)
            c = c.mix(#xffffff, clamp(ring, 0.0, 1.0) * self.down * 0.32)
            sdf.fill(c)
            var bc = #xffffff22
            bc = bc.mix(#xffc65c, self.hover)
            sdf.stroke(bc, 1.0)
            return sdf.result
        }
    }
    draw_text +: {color: soft color_hover: #xffffff color_down: #xffffff text_style +: {font_size: 12}}
}"""

# 圆形数字钮：手机上也够大（44pt 触区），划过是微澜，按下从圆心荡开
NUMBTN_OLD = r"""let NumBtn = ButtonFlat{width: 38 height: 38 padding: Inset{left: 0 right: 0} align: Align{x: 0.5 y: 0.5}
    draw_bg +: {border_radius: 19.0 color: surface2 color_hover: #x262d68 color_down: #x2f3778 border_size: 1.0
        border_color: #x2b3373 border_color_hover: #x4a5296 border_color_down: gold}
    draw_text +: {color: ink color_hover: #xffffff color_down: gold text_style +: {font_size: 17}}
}"""
NUMBTN_NEW = r"""let NumBtn = ButtonFlat{width: 40 height: 40 padding: Inset{left: 0 right: 0} align: Align{x: 0.5 y: 0.5}
    draw_bg +: {
        pixel: fn(){
            let sz = self.rect_size
            let sdf = Sdf2d.viewport(self.pos * sz)
            sdf.box(1.0, 1.0, sz.x - 2.0, sz.y - 2.0, sz.y * 0.5 - 1.0)
            let d = length(self.pos * sz - sz * 0.5)
            let ring = sin(d * 0.24 - self.draw_pass.time * 8.4) * exp(-d * 0.042)
            var c = #x1c2252
            c = c.mix(#x272e6c, self.hover * 0.85)
            c = c.mix(#x2f3778, self.down * 0.9)
            c = c.mix(#xfff2d0, clamp(ring, 0.0, 1.0) * self.down * 0.30)
            sdf.fill(c)
            var bc = #x2b3373
            bc = bc.mix(#x4a5296, self.hover)
            bc = bc.mix(#xffc65c, self.down)
            sdf.stroke(bc, 1.0)
            return sdf.result
        }
    }
    draw_text +: {color: ink color_hover: #xffffff color_down: gold text_style +: {font_size: 17}}
}"""

# 描边幽灵钮：划过是水波微澜，不是换色
GHOST_OLD = r"""let GhostBtn = ButtonFlat{height: 44 padding: Inset{left: 18 right: 18}
    draw_bg +: {border_radius: 22.0 color: #x151a4300 color_hover: #x1c2252 color_down: #x232a62 border_size: 1.0
        border_color: #x2b3373 border_color_hover: #x4a5296 border_color_down: #x5a62a8}
    draw_text +: {color: soft color_hover: ink color_down: ink text_style +: {font_size: 14}}
}"""
GHOST_NEW = r"""let GhostBtn = ButtonFlat{height: 44 padding: Inset{left: 18 right: 18}
    draw_bg +: {
        pixel: fn(){
            let sz = self.rect_size
            let sdf = Sdf2d.viewport(self.pos * sz)
            sdf.box(1.0, 1.0, sz.x - 2.0, sz.y - 2.0, 22.0)
            let px = self.pos.x * sz.x
            let d = length(self.pos * sz - sz * 0.5)
            let hw = sin(px * 0.26 + self.draw_pass.time * 4.0) * exp(-abs(px - sz.x * 0.5) * 0.02) * self.hover
            let ring = sin(d * 0.24 - self.draw_pass.time * 8.4) * exp(-d * 0.045)
            var c = #x151a4300
            c = c.mix(#x1c2352, clamp(self.hover * 0.85 + hw * 0.25, 0.0, 1.0))
            c = c.mix(#x232a62, self.down * 0.9)
            c = c.mix(#xfff2d0, clamp(ring, 0.0, 1.0) * self.down * 0.28)
            sdf.fill(c)
            var bc = #x2b3373
            bc = bc.mix(#x4a5296, self.hover)
            bc = bc.mix(#xffc65c, self.down)
            sdf.stroke(bc, 1.0)
            return sdf.result
        }
    }
    draw_text +: {color: soft color_hover: ink color_down: ink text_style +: {font_size: 14}}
}"""

# 纯文字小按钮
BARBTN_OLD = r"""let BarBtn = ButtonFlat{height: 30 padding: Inset{left: 6 right: 8}
    draw_bg +: {border_radius: 15.0 color: #xffffff00 color_hover: #xff7a8a1a color_down: #xff7a8a33 border_size: 0.0}
    draw_text +: {color: accent color_hover: #xffa0ab color_down: accent text_style +: {font_size: 13}}
}"""
BARBTN_NEW = r"""let BarBtn = ButtonFlat{height: 30 padding: Inset{left: 8 right: 10}
    draw_bg +: {
        pixel: fn(){
            let sz = self.rect_size
            let sdf = Sdf2d.viewport(self.pos * sz)
            sdf.box(1.0, 1.0, sz.x - 2.0, sz.y - 2.0, 15.0)
            let d = length(self.pos * sz - sz * 0.5)
            let ring = sin(d * 0.28 - self.draw_pass.time * 8.8) * exp(-d * 0.055)
            var c = #xffffff00
            c = c.mix(#xff7a8a1f, self.hover * 1.6)
            c = c.mix(#xff7a8a33, self.down * 1.2)
            c = c.mix(#xffffff, clamp(ring, 0.0, 1.0) * self.down * 0.35)
            sdf.fill(c)
            return sdf.result
        }
    }
    draw_text +: {color: accent color_hover: #xffa0ab color_down: #xfff1cf text_style +: {font_size: 13}}
}"""

# 卡片表面（RowCard / RowCardImg 共用同一句底：一张卡就是一小块水面）
CARD_BG_OLD = r"""    new_batch: true show_bg: true draw_bg.color: paper draw_bg.border_radius: 16.0
    draw_bg.border_size: 1.0 draw_bg.border_color: hair"""
CARD_BG_NEW = r"""    show_bg: true new_batch: true
    draw_bg +: {
        pixel: fn(){
            let sz = self.rect_size
            let sdf = Sdf2d.viewport(self.pos * sz)
            sdf.box(1.0, 1.0, sz.x - 2.0, sz.y - 2.0, 16.0)
            let px = self.pos.x * sz.x
            // 一道极慢的横向折光扫过：卡片在呼吸
            let g1 = exp(-abs(px - (fract(self.draw_pass.time * 0.026) * (sz.x + 320.0) - 160.0)) / 122.0)
            var c = #x151a43
            c = c.mix(#x1d2456, clamp(g1 * 0.55, 0.0, 1.0))
            // 划过：表面起一层更亮的微澜
            c = c.mix(#x232b63, self.hover * 0.20)
            sdf.fill(c)
            // 顶缘一线天光
            sdf.box(3.0, 1.8, sz.x - 6.0, 1.0, 0.5)
            sdf.fill(#xffffff22)
            sdf.stroke(#x262d68, 1.0)
            return sdf.result
        }
    }"""

# 面板：全项目基础卡容器，同样是一块水面
PANEL_OLD = r"""let Panel = RoundedView{width: Fill height: Fit flow: Down spacing: 10
    padding: Inset{top: 16 bottom: 16 left: 16 right: 16}
    new_batch: true show_bg: true draw_bg.color: paper draw_bg.border_radius: 20.0
    draw_bg.border_size: 1.0 draw_bg.border_color: hair
}"""
PANEL_NEW = r"""let Panel = View{width: Fill height: Fit flow: Down spacing: 10
    show_bg: true new_batch: true padding: Inset{top: 16 bottom: 16 left: 16 right: 16}
    draw_bg +: {
        pixel: fn(){
            let sz = self.rect_size
            let sdf = Sdf2d.viewport(self.pos * sz)
            sdf.box(1.0, 1.0, sz.x - 2.0, sz.y - 2.0, 20.0)
            let px = self.pos.x * sz.x
            let g1 = exp(-abs(px - (fract(self.draw_pass.time * 0.024) * (sz.x + 360.0) - 180.0)) / 142.0)
            var c = #x151a43
            c = c.mix(#x1b2254, clamp(g1 * 0.5, 0.0, 1.0))
            sdf.fill(c)
            sdf.box(3.0, 1.8, sz.x - 6.0, 1.1, 0.55)
            sdf.fill(#xffffff26)
            sdf.stroke(#x262d68, 1.0)
            return sdf.result
        }
    }
}
// 水面卡：第 37 轮新栏目用的表面 —— 一道更宽的折光 + 顶缘天光，读起来像「纸浮在水上」
let Glass = View{width: Fill height: Fit flow: Down spacing: 8
    show_bg: true new_batch: true padding: Inset{top: 15 bottom: 15 left: 16 right: 16}
    draw_bg +: {
        pixel: fn(){
            let sz = self.rect_size
            let sdf = Sdf2d.viewport(self.pos * sz)
            sdf.box(1.0, 1.0, sz.x - 2.0, sz.y - 2.0, 18.0)
            let px = self.pos.x * sz.x
            let g1 = exp(-abs(px - (fract(self.draw_pass.time * 0.030) * (sz.x + 340.0) - 170.0)) / 132.0)
            let g2 = exp(-abs(px - (fract(self.draw_pass.time * 0.017 + 0.5) * (sz.x + 420.0) - 210.0)) / 168.0)
            var c = #x151a43
            c = c.mix(#x1d2456, clamp((g1 + g2) * 0.55, 0.0, 1.0))
            sdf.fill(c)
            sdf.box(3.0, 1.8, sz.x - 6.0, 1.1, 0.55)
            sdf.fill(#xffffff2b)
            sdf.stroke(#x262d68, 1.0)
            return sdf.result
        }
    }
}"""

# 栏目标题下方的水线：一条从金到透明的细线，标题像是印在水面上
SECLINE_NEW = r"""let SecLine = View{width: Fill height: 2 show_bg: true new_batch: true
    draw_bg +: {
        pixel: fn(){
            let sz = self.rect_size
            let sdf = Sdf2d.viewport(self.pos * sz)
            let u = self.pos.x
            var c = #xffc65c
            c = c.mix(#xff7a8a, u * 0.8)
            sdf.box(0.0, 0.0, sz.x, 1.6, 0.8)
            sdf.fill(vec4(c.x, c.y, c.z, (1.0 - u) * (1.0 - u) * 0.85))
            return sdf.result
        }
    }
}"""

# 浏览器式标签：上圆下平、坐在水面上；亮着的那格顶上一线天光、脚下一道金水线
TAB_OLD_START = r"""// ---- 浏览器标签式导航项 (Browser Tab Item) · Awwwards 级设计 ----
// ---- 浏览器标签式导航项 (Browser Tab Item) · Awwwards 级设计 (自包含安全样式) ----"""
TAB_OLD_END = "}\nlet BarBtn = ButtonFlat{"
TAB_NEW = r"""// ---- 浏览器式栏目标签 (Browser Tab)——上圆下平，坐在一条水线上；亮着的那格
//      顶上一线天光、脚下一道金水线，像浏览器里被选中的那页。全宽等分，不会挤出去。
let TabActive = ButtonFlat{width: Fill height: 46 padding: Inset{left: 6 right: 6 top: 8 bottom: 6} align: Align{x: 0.5 y: 0.5}
    draw_bg +: {
        pixel: fn(){
            let sz = self.rect_size
            let sdf = Sdf2d.viewport(self.pos * sz)
            sdf.box(1.0, 1.0, sz.x - 2.0, sz.y, 14.0)
            let px = self.pos.x * sz.x
            let dist = length(self.pos * sz - vec2(sz.x * 0.5, sz.y * 0.5))
            // 划过：细密水纹；按下：从中心荡开的同心波纹
            let hw = sin(px * 0.28 + self.draw_pass.time * 4.4) * exp(-abs(px - sz.x * 0.5) * 0.018) * self.hover
            let dw = sin(dist * 0.26 - self.draw_pass.time * 9.2) * exp(-dist * 0.045) * self.down
            var c = #x202a5e
            c = c.mix(#x2e3a8e, clamp(self.hover * 0.5 + hw * 0.35, 0.0, 1.0))
            c = c.mix(#xffffff, clamp(dw * 0.34, 0.0, 1.0))
            sdf.fill(c)
            // 顶上一线天光
            sdf.box(4.0, 1.6, sz.x - 8.0, 1.2, 0.6)
            sdf.fill(#xfff0cf6b)
            // 脚下一道金色水线：这就是「你正在这一页」
            sdf.box(2.0, sz.y - 2.8, sz.x - 4.0, 2.6, 1.3)
            sdf.fill(#xffc65c)
            sdf.box(6.0, sz.y - 2.0, sz.x - 12.0, 7.0, 3.0)
            sdf.fill(#xffc65c22)
            return sdf.result
        }
    }
    draw_text +: {color: #xfff3d8 color_hover: #xffffff color_down: #xfff3d8 text_style: theme.font_bold{font_size: 13}}
}
let TabInactive = ButtonFlat{width: Fill height: 46 padding: Inset{left: 6 right: 6 top: 8 bottom: 6} align: Align{x: 0.5 y: 0.5}
    draw_bg +: {
        pixel: fn(){
            let sz = self.rect_size
            let sdf = Sdf2d.viewport(self.pos * sz)
            sdf.box(1.0, 1.0, sz.x - 2.0, sz.y, 14.0)
            let px = self.pos.x * sz.x
            let dist = length(self.pos * sz - vec2(sz.x * 0.5, sz.y * 0.5))
            let hw = sin(px * 0.28 + self.draw_pass.time * 4.0) * exp(-abs(px - sz.x * 0.5) * 0.02) * self.hover
            let dw = sin(dist * 0.26 - self.draw_pass.time * 9.2) * exp(-dist * 0.045) * self.down
            var c = #x10153a
            c = c.mix(#x1e2554, clamp(self.hover * 0.75 + hw * 0.35, 0.0, 1.0))
            c = c.mix(#xfff2d0, clamp(dw * 0.24, 0.0, 1.0))
            sdf.fill(c)
            return sdf.result
        }
    }
    draw_text +: {color: #x9199ca color_hover: #xeceefe color_down: #xfff1cf text_style +: {font_size: 13}}
}
"""
TAB_NEW = TAB_NEW + "let BarBtn = ButtonFlat{"


# ---------------------------------------------------------------------
# 二、手术点：新栏目标签栏、水底、三个新页面、守夜人
# ---------------------------------------------------------------------

# ⑦A 旧的标签栏整块撤掉（新的放到卡片最顶上，像浏览器那样）
RAIL_OLD = r"""            // ---- 顶部标签栏 · 浏览器标签式日报导航 (Awwwards 级设计) ----
            tab_bar := View{width: Fill height: 42 flow: Right padding: Inset{left: 16 right: 16 top: 4 bottom: 0} spacing: 4
                tab_front_on := TabActive{text: "今日头版" on_click: || set_tab("front")}
                tab_front_off := TabInactive{text: "今日头版" on_click: || set_tab("front")}
                tab_pool_on := TabActive{text: "多源情报池" on_click: || set_tab("pool")}
                tab_pool_off := TabInactive{text: "多源情报池" on_click: || set_tab("pool")}
                tab_review_on := TabActive{text: "编辑部复盘" on_click: || set_tab("review")}
                tab_review_off := TabInactive{text: "编辑部复盘" on_click: || set_tab("review")}
                tab_stand_on := TabActive{text: "立场与更正" on_click: || set_tab("stand")}
                tab_stand_off := TabInactive{text: "立场与更正" on_click: || set_tab("stand")}
            }
"""

# ⑦B 新的标签栏：五格等分，坐在一条会呼吸的水线上；高亮的那格由 shader 里的
#     一颗金色光点滑过去（tab_from → tab_to，tab_step 每 20 毫秒喂一次）
RAIL_NEW = r"""            // ---- 浏览器式栏目标签 · 五个格子等分，坐在一条水线上 ----
            //      点哪一格哪一格亮；正在翻开的那一格，金色光点会顺着水线滑过去。
            tab_rail := View{width: Fill height: Fit flow: Down show_bg: true new_batch: true
                draw_bg +: {
                    tb: instance(0.0)
                    tt: instance(0.0)
                    tp: instance(0.0)
                    tw: instance(0.0)
                    pixel: fn(){
                        let sz = self.rect_size
                        let sdf = Sdf2d.viewport(self.pos * sz)
                        // 栏底：夜靛过渡到纸色的水面
                        var c = #x0c1030
                        c = c.mix(#x141b47, self.pos.y)
                        let px = self.pos.x * sz.x
                        // 两道极慢的横向折光：界面在呼吸
                        let g1 = exp(-abs(px - (fract(self.draw_pass.time * 0.033) * (sz.x + 460.0) - 230.0)) / 152.0)
                        let g2 = exp(-abs(px - (fract(self.draw_pass.time * 0.019 + 0.42) * (sz.x + 560.0) - 280.0)) / 196.0)
                        c = c.mix(#x27316c, clamp((g1 * 0.7 + g2 * 0.5) * 0.55, 0.0, 1.0))
                        sdf.fill(c)
                        // 标签滑轨：一条暗金水线，从窗口这头通到那头
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
                        sdf.fill(#xffffff1f)
                        return sdf.result
                    }
                }
                draw_bg.tb: tab_from
                draw_bg.tt: tab_to
                draw_bg.tp: tab_p
                draw_bg.tw: tab_swell
                View{width: Fill height: Fit flow: Right spacing: 3 padding: Inset{left: 10 right: 10 top: 6 bottom: 0}
                    tab_front_on := TabActive{text: "头版" on_click: || set_tab("front")}
                    tab_front_off := TabInactive{text: "头版" on_click: || set_tab("front")}
                    tab_pool_on := TabActive{text: "情报池" on_click: || set_tab("pool")}
                    tab_pool_off := TabInactive{text: "情报池" on_click: || set_tab("pool")}
                    tab_review_on := TabActive{text: "复盘" on_click: || set_tab("review")}
                    tab_review_off := TabInactive{text: "复盘" on_click: || set_tab("review")}
                    tab_stand_on := TabActive{text: "立场" on_click: || set_tab("stand")}
                    tab_stand_off := TabInactive{text: "立场" on_click: || set_tab("stand")}
                    tab_story_on := TabActive{text: "读稿" on_click: || set_tab("story")}
                    tab_story_off := TabInactive{text: "读稿" on_click: || set_tab("story")}
                }
            }
"""

# ⑩ 水底：整张卡的最深处就是一汪水面。天光、旭日的倒影、慢波、以及
#     你点任意处时荡开的两圈按压波纹（water_at / water_pulse 由 field_step 喂）
WATER_ANCHOR = r"""        View{width: Fill height: Fill flow: Down
            // ---- 地平线带 · 所有阶段共用；太阳的高度 = 今天这份报做到哪了 ----"""
WATER_NEW = r"""        water := View{width: Fill height: Fill show_bg: true new_batch: true
            draw_bg +: {
                wt: instance(0.0)
                wp: instance(0.0)
                wa: instance(0.5)
                pixel: fn(){
                    let sz = self.rect_size
                    let p = self.pos * sz
                    let t = self.wt
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
                    // 你按下时荡开的两圈同心波纹（手机轻点也算）
                    let q = clamp(self.wp, 0.0, 1.0)
                    let ax = clamp(self.wa, 0.0, 1.0)
                    let dd = length(p / sz - vec2(ax, 0.34))
                    let r1 = 1.0 - smoothstep(0.0, 0.014, abs(dd - (0.05 + 0.40 * (1.0 - q))))
                    let r2 = 1.0 - smoothstep(0.0, 0.020, abs(dd - (0.05 + 0.62 * (1.0 - q))))
                    let ring = (r1 * 0.55 + r2 * 0.30) * q
                    c = c.mix(#xffe6bd, clamp(ring * 0.75, 0.0, 1.0))
                    return vec4(c.x, c.y, c.z, 1.0)
                }
            }
            draw_bg.wt: water_t
            draw_bg.wp: water_pulse
            draw_bg.wa: water_at
        }
"""

# ⑨ 三个新页面：全部用既有数据，不新增任何取数
PANES_ANCHOR = r"""                refuse_pane := View{visible: false width: Fill height: Fill flow: Down"""
PANES_NEW = r"""                // ---- 情报池：今天从哪些地方、取了多少条、筛掉了什么 ----
                pool_pane := View{visible: false width: Fill height: Fill flow: Down
                    ScrollYView{width: Fill height: Fill flow: Down spacing: 14 padding: Inset{left: 20 right: 20 top: 16 bottom: 220}
                        View{width: Fill height: Fit flow: Down spacing: 9
                            Label{width: Fill text: "多源情报池" draw_text.color: ink draw_text.text_style: theme.font_bold{font_size: 22}}
                            SecLine{}
                            Label{width: Fill text: "今天从哪些信源、按什么规则取了多少条 —— 以及哪些进了池子还没上版。" draw_text.color: secondary draw_text.text_style.font_size: 12}
                        }
                        pool_head := Label{width: Fill text: "" draw_text.color: gold draw_text.text_style.font_size: 12}
                        Glass{
                            Label{width: Fill text: "候选 · 上池" draw_text.color: faint draw_text.text_style: theme.font_code{font_size: 10}}
                            pool_rows := Label{width: Fill text: "" draw_text.color: ink draw_text.text_style.font_size: 13}
                        }
                        Glass{
                            Label{width: Fill text: "取数与兜底" draw_text.color: faint draw_text.text_style: theme.font_code{font_size: 10}}
                            pool_panel := Label{width: Fill text: "" draw_text.color: soft draw_text.text_style.font_size: 12}
                        }
                        Glass{
                            Label{width: Fill text: "工作记录" draw_text.color: faint draw_text.text_style: theme.font_code{font_size: 10}}
                            pool_work := Label{width: Fill text: "" draw_text.color: secondary draw_text.text_style.font_size: 12}
                        }
                        View{width: Fill height: Fit flow: Right align: Align{y: 0.5} spacing: 10
                            GhostBtn{text: "回到头版" on_click: || set_tab("front")}
                            BarBtn{text: "重新出报 ›" on_click: || go_prep()}
                        }
                    }
                }
                // ---- 编辑部复盘：这一期是怎么被判进来的 ----
                review_pane := View{visible: false width: Fill height: Fill flow: Down
                    ScrollYView{width: Fill height: Fill flow: Down spacing: 14 padding: Inset{left: 20 right: 20 top: 16 bottom: 220}
                        View{width: Fill height: Fit flow: Down spacing: 9
                            Label{width: Fill text: "编辑部复盘" draw_text.color: ink draw_text.text_style: theme.font_bold{font_size: 22}}
                            SecLine{}
                            Label{width: Fill text: "三位编辑各自推荐了什么、留下了什么、事实核查记了几笔 —— 出报留痕里都有。" draw_text.color: secondary draw_text.text_style.font_size: 12}
                        }
                        review_head := Label{width: Fill text: "" draw_text.color: gold draw_text.text_style.font_size: 12}
                        Glass{
                            Label{width: Fill text: "时间与预算" draw_text.color: faint draw_text.text_style: theme.font_code{font_size: 10}}
                            review_time := Label{width: Fill text: "" draw_text.color: ink draw_text.text_style.font_size: 13}
                        }
                        Glass{
                            Label{width: Fill text: "事实核查 · 编辑部内部对照" draw_text.color: faint draw_text.text_style: theme.font_code{font_size: 10}}
                            review_fc := Label{width: Fill text: "" draw_text.color: soft draw_text.text_style.font_size: 12}
                        }
                        View{width: Fill height: Fit flow: Right align: Align{y: 0.5} spacing: 10
                            GhostBtn{text: "回到头版" on_click: || set_tab("front")}
                            BarBtn{text: "看情报池 ›" on_click: || set_tab("pool")}
                        }
                    }
                }
                // ---- 立场与更正：不改已发的稿，但每一笔更正都记账 ----
                stand_pane := View{visible: false width: Fill height: Fill flow: Down
                    ScrollYView{width: Fill height: Fill flow: Down spacing: 14 padding: Inset{left: 20 right: 20 top: 16 bottom: 220}
                        View{width: Fill height: Fit flow: Down spacing: 9
                            Label{width: Fill text: "立场与更正" draw_text.color: ink draw_text.text_style: theme.font_bold{font_size: 22}}
                            SecLine{}
                            Label{width: Fill text: "我们只做两件事：说清楚自己站在哪，以及错了就记一笔。" draw_text.color: secondary draw_text.text_style.font_size: 12}
                        }
                        stand_head := Label{width: Fill text: "" draw_text.color: gold draw_text.text_style.font_size: 12}
                        Glass{
                            Label{width: Fill text: "更正台账" draw_text.color: faint draw_text.text_style: theme.font_code{font_size: 10}}
                            stand_ledger := Label{width: Fill text: "" draw_text.color: ink draw_text.text_style.font_size: 13}
                        }
                        Glass{
                            Label{width: Fill text: "本报的立场" draw_text.color: faint draw_text.text_style: theme.font_code{font_size: 10}}
                            stand_creed := Label{width: Fill text: "" draw_text.color: soft draw_text.text_style.font_size: 12}
                        }
                        View{width: Fill height: Fit flow: Right align: Align{y: 0.5} spacing: 10
                            GhostBtn{text: "回到头版" on_click: || set_tab("front")}
                            BarBtn{text: "看复盘 ›" on_click: || set_tab("review")}
                        }
                    }
                }
"""

# ⑪ 守夜人那一行：界面自检时露一下，平时不占地方
WATCH_ANCHOR = r"""        ag_dock := View{width: Fill height: Fill flow: Down align: Align{x: 0.5 y: 1.0}
            ag_panel := RoundedView{"""
WATCH_NEW = r"""        ag_dock := View{width: Fill height: Fill flow: Down align: Align{x: 0.5 y: 1.0}
            // 守夜人的一句话：只有自检发现文案读不出来时才露头
            watch_line := Label{visible: false width: Fill margin: Inset{left: 18 right: 18 bottom: 6}
                text: "" draw_text.color: #xffd98a draw_text.text_style.font_size: 10}
            ag_panel := RoundedView{"""

# ⑪ boot：起守夜人和水面的心跳
BOOT_OLD = r"""    trail_load()
    iv_load()
    sync_ui()"""
BOOT_NEW = r"""    trail_load()
    iv_load()
    sync_ui()
    // 第 37 轮：水面心跳（每 70 毫秒推一格波纹）＋ 守夜人（每半秒重落一次可见性）
    field_kick()
    if watch_tid == nil { watch_tid = start_interval(0.5, || watch_tick()) }"""

# ⑧ 入口：任何地方点开一条新闻，都切到「读稿」那一格，并且返回时回到原来那格
OPEN_OLD = r'''    story_state = "loading"
    phase = "story"
    art_q = ""'''

OPEN_NEW = r'''    story_state = "loading"
    story_tab = true
    active_tab = "story"
    phase = "story"
    art_q = ""'''

CLOSE_OLD = r'''    art_note = ""
    phase = "done"
    sync_ui()'''

CLOSE_NEW = r'''    art_note = ""
    phase = "done"
    active_tab = "front"
    story_tab = false
    sync_ui()'''

# 清晨太阳常驻：还没开工也先给一线晨光，不要一整块冷夜
SKY_OLD = r"""    sky_h_to = h
    sky_r_to = r
}"""
SKY_NEW = r"""    // 第 37 轮：清晨太阳常驻 —— 哪怕还没开工，天上也先有一线晨光、水面也有倒影，
    // 不做「一整块冷夜」。开工之后太阳再往上升。
    if r < 0.34 { r = 0.34 }
    sky_h_to = h
    sky_r_to = r
}"""



# ---------------------------------------------------------------------
# 三、新页面的文案接线 + 总的落盘流程
# ---------------------------------------------------------------------

PANE_SYNC = r"""// 三个新页面的文案：只读既有数据，不新增任何取数；任何一段读不出来都只少一行字。
fn review_time_text(){
    let n = "" + fix_count()
    let c = "" + clash_count()
    "本期修正 " + n + " 处 · 与决策台判断不一致 " + c + " 处"
}

fn stand_creed_text(){
    "不补齐条数 · 失败明说 · 每条可核实（来源、时间、原文链接）· 改过的稿重算 blake3 · 更正一律记账"
}

fn sync_panes(){
    try { ui.pool_head.set_text(pool_head_text()) } catch err { sync_break() }
    try { ui.pool_rows.set_text(pool_rows_text()) } catch err { sync_break() }
    try { ui.pool_panel.set_text(pool_panel_text()) } catch err { sync_break() }
    try { ui.pool_work.set_text(pool_work_text()) } catch err { sync_break() }
    try { ui.review_head.set_text(review_head_text()) } catch err { sync_break() }
    try { ui.review_time.set_text(review_time_text()) } catch err { sync_break() }
    try { ui.review_fc.set_text(review_fc_text()) } catch err { sync_break() }
    try { ui.stand_head.set_text(stand_head_text()) } catch err { sync_break() }
    try { ui.stand_ledger.set_text(stand_ledger_text()) } catch err { sync_break() }
    try { ui.stand_creed.set_text(stand_creed_text()) } catch err { sync_break() }
}

"""

TAB_HEAD = r'''let active_tab = "front"'''
TAB_TAIL = r"""    } else if active_tab == "review" || active_tab == "stand" {
        ui.browse.set_visible(false)
        ui.refuse_pane.set_visible(false)
        ui.run_pane.set_visible(true)
    }
}"""

PANE_SYNC_ANCHOR = r"""fn sync_ui(){"""

SYNC_OPEN_OLD = r"""fn sync_ui(){
    ui.intent_line.set_text(intent_preview())"""

SYNC_MID1_OLDS = [
    r"""    ui.limit_label.set_text("" + limit)
    sync_tabs()
    ui.gen_pane.set_visible(phase == "intent")""",
    r"""    ui.limit_label.set_text("" + limit)
    ui.gen_pane.set_visible(phase == "intent")""",
]
SYNC_MID2_OLDS = [
    r"""    ui.rv_btn.set_text(rv_text())
    ui.list.render()""",
]
SYNC_END_OLDS = [
    r"""    if ag_open { ui.ag_log_box.render() }
}""",
]

CHECK = ("tab_rail", "water", "ui.pool_pane", "ui.review_pane", "ui.stand_pane", "ui.watch_line",
         "ui.tab_story_on", "ui.pool_rows", "ui.stand_ledger", "sync_panes()", "field_kick()")


def apply(s):
    before = len(s.text)
    log = []

    def pick(tag, cands, new):
        for cand in cands:
            n = s.text.count(cand)
            if n:
                s.swap(tag, cand, new, n)
                log.append("%s ×%d" % (tag, n))
                return
        raise AssertionError("%s：一个候选锚点都没命中" % tag)

    # ① 旧的 active_tab / set_tab / sync_tabs 整块换成 TABS（新逻辑 + 新文案 + 守夜人）
    s.span("① 栏目标签逻辑", TAB_HEAD, TAB_TAIL, TABS)
    # ② sync_panes：三个新页面的文案接线，插在 sync_ui 之前
    s.insert_before("② sync_panes", PANE_SYNC_ANCHOR, PANE_SYNC)
    # ③ sync_ui 四处手术：可见性提到最前，文案各关进 try/catch
    s.swap("③a sync_ui 开头", SYNC_OPEN_OLD, SYNC_OPEN)
    pick("③b", SYNC_MID1_OLDS, SYNC_MID1)
    pick("③c", SYNC_MID2_OLDS, SYNC_MID2)
    pick("③d", SYNC_END_OLDS, SYNC_END)
    log.append("③ sync_ui 手术 ×4")

    # ④ 模板：可点的东西统一成一块水面
    s.span("④g 浏览器式标签", TAB_OLD_START, TAB_OLD_END, TAB_NEW)
    s.swap("④a ChipDk", CHIPDK_OLD, CHIPDK_NEW)
    s.swap("④b NumBtn", NUMBTN_OLD, NUMBTN_NEW)
    s.swap("④c GhostBtn", GHOST_OLD, GHOST_NEW)
    s.swap("④d BarBtn", BARBTN_OLD, BARBTN_NEW)
    s.swap("④e 卡片表面 ×2", CARD_BG_OLD, CARD_BG_NEW, 2)
    s.swap("④f 面板 + 水线 + 水面卡", PANEL_OLD, PANEL_NEW + "\n" + SECLINE_NEW)
    log.append("④ 模板 ×7")

    # ⑤ 清晨太阳常驻：没开工也先给一线晨光
    s.swap("⑤ 晨光常驻", SKY_OLD, SKY_NEW)

    # ⑥ 标签栏：旧的撤掉，新的挪到卡片最顶上（像浏览器那样）
    s.swap("⑥a 撤旧标签栏", RAIL_OLD, "")
    s.insert_before("⑥b 新标签栏", WATER_ANCHOR, RAIL_NEW)
    # ⑦ 水底：整张卡最深处的一汪水面
    s.insert_before("⑦ 水底", WATER_ANCHOR, WATER_NEW)
    # ⑧ 三个新页面
    s.insert_before("⑧ 新页面", PANES_ANCHOR, PANES_NEW)
    # ⑨ 守夜人那一行 + 心跳
    s.swap("⑨a 守夜人", WATCH_ANCHOR, WATCH_NEW)
    s.swap("⑨b 心跳", BOOT_OLD, BOOT_NEW)
    # ⑩ 读稿入口：点开一条新闻就切到「读稿」那格，返回时回到头版
    s.swap("⑩a 读稿入口", OPEN_OLD, OPEN_NEW)
    s.swap("⑩b 返回头版", CLOSE_OLD, CLOSE_NEW)

    for need in CHECK:
        assert s.text.count(need) > 0, "检查项没落进文件：%s" % need
    print("改动前 %d 字符 -> 改动后 %d 字符（%+d）" % (before, len(s.text), len(s.text) - before))
    for line in log:
        print("   ", line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(SRC))
    ap.add_argument("--dry", action="store_true", help="只验锚点，不写盘")
    args = ap.parse_args()
    s = Splash(pathlib.Path(args.file))
    apply(s)
    if args.dry:
        print("--dry：锚点全部命中，未写盘。", args.file)
        return
    s.save()
    print("已写盘：", args.file)


if __name__ == "__main__":
    main()

