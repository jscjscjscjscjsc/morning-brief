# -*- coding: utf-8 -*-
"""校验 review/ANSWERS.md 中 Q1 引用的「符号 -> 行号」是否仍与 main.splash 一致。

为什么需要：main.splash 每改一次，行号就可能漂移；ANSWERS.md 是给评委对账用的，
一旦漂移就会被记成「Cite the text in its source」失分项。
"""
import sys, re

MAIN = r"C:/Users/Admin（无密码）/Desktop/数据文件/黑客松比赛项目/my-entry/morning-brief/bundle/main.splash"

# (符号, ANSWERS.md 中声明的行号, 备注)  —— 允许 ±TOL 行容差
# TOL 必须是 0：ANSWERS.md 是给评委逐条对账的，差 1 行就算「引用不准」。
TOL = 0
EXPECT = [
    ("aq_start", 3375, "审批入口"),
    ("make_plan", 3784, "生成计划"),
    ("approve", 3805, "批准"),
    ("run_brief", 3690, "跑简报"),
    ("deny", 3847, "拒绝"),
    ("dom_hit", 509, "信源域名命中"),
    ("tier_of_h", 515, "按主机取 tier"),
    ("tier_of", 532, "按 url 取 tier"),
    ("tier_label", 536, "tier 标签"),
    ("panel_ask", 3036, "三视角入口"),
    ("panel_role", 3042, "单个角色调用"),
    ("panel_put", 3068, "写回角色结果"),
    ("panel_check", 3097, "汇总三视角"),
    ("judge", 3250, "AI 判官"),
    ("judge_try", 3255, "判官一次尝试"),
    ("drops_from_ai", 3212, "AI 丢弃理由"),
    ("refuse_check", 3338, "拒刊判据"),
    ("refuse_go", 3354, "走拒刊页"),
    ("fc_kick", 2044, "事实核查发起"),
    ("claim_save", 2262, "保存论断"),
    ("fact_kick", 2297, "事实核查 kick"),
    ("fact_save", 2266, "保存事实结果"),
    ("fc_review", 2119, "核查复核"),
    ("fc_save", 1970, "核查落盘"),
    ("fc_hist_text", 2007, "核查历史文本"),
    ("trail_begin", 270, "轨迹开始"),
    ("trail_set_pool", 287, "轨迹设池"),
    ("trail_set_panel", 300, "轨迹设三视角"),
    ("trail_set_judge", 307, "轨迹设判官"),
    ("trail_save", 323, "轨迹落盘"),
    ("charter_v", 26, "宪章版本"),
    ("charter_version_line", 31, "宪章版本行"),
    ("charter_text", 40, "宪章正文"),
]


def main():
    with open(MAIN, "r", encoding="utf-8") as f:
        lines = f.readlines()
    total = len(lines)
    print(f"main.splash: {total} 行")
    print(f"{'符号':<22}{'声明':>6}{'实际':>6}  判定")
    print("-" * 56)
    bad = 0
    for name, want, note in EXPECT:
        hits = [i for i, ln in enumerate(lines, 1)
                if re.search(r'(^|[^A-Za-z0-9_])' + re.escape(name) + r'\s*[(=:]', ln)]
        if not hits:
            print(f"{name:<22}{want:>6}{'--':>6}  ✗ 未找到 ({note})")
            bad += 1
            continue
        near = min(hits, key=lambda h: abs(h - want))
        ok = abs(near - want) <= TOL
        mark = "✓" if ok else "✗ 漂移"
        if not ok:
            bad += 1
        extra = "" if len(hits) == 1 else f"   (共{len(hits)}处: {hits[:6]})"
        print(f"{name:<22}{want:>6}{near:>6}  {mark}{extra}")
    print("-" * 56)
    print(f"结论：{'全部一致' if bad == 0 else f'{bad} 处需修正'}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
