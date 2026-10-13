# ISSUE-04 · International 字体集的等宽链缺 CJK，中文等宽文字整段豆腐

**上报对象**：`makepad`（`platform/src/font_policy.rs`）
**严重度**：中（不影响功能，但页签/报头等"品牌位置"的中文整段显示为方框，任何中文卡片都会撞上）
**状态**：已定位、本机修复并验证；补丁与完整说明见 `my-entry/patches/host-font-monospace-cjk.patch` / `UPSTREAM-font-monospace.md`

---

## 一句话

`FontSet::International`（native 一律选它）的 `monospace` 链只挂了 `LIBERATION_MONO`，
而 `lazy_chain(FontRole::Monospace)` 返回 `NO_LAZY_FONTS` —— 等宽角色遇到 CJK
**两条兜底路都断了**，只能画 tofu。同屏的 normal/bold 中文全部正常，唯独等宽的成排方框。

## 关键源码

```rust
// platform/src/font_policy.rs（修复前）
monospace: FontChain { role: FontRole::Monospace, members: MONOSPACE },   // [LIBERATION_MONO]

pub const fn lazy_chain(&self, role: FontRole) -> &'static [LazyFontAsset] {
    if !matches!(self.set, FontSet::Latin) { return NO_LAZY_FONTS; }
    match role {
        FontRole::Regular | FontRole::Italic => LATIN_LAZY_REGULAR,
        FontRole::Bold | FontRole::BoldItalic => LATIN_LAZY_BOLD,
        FontRole::Monospace | FontRole::Icons => NO_LAZY_FONTS,   // ← 中文无处可去
    }
}
```

`widgets/src/text_roles.rs` 自己的注释写着这条规矩——「Every role below carries the
COMPLETE chain — latin, symbols, CJK, colour emoji」——等宽是唯一漏掉的。

## 怎么复现

任何用 `theme.font_code`（等宽角色）渲染中文的卡片，Windows 上跑起来就能看到：
页签文字、期号、日期标签成排方框；把同一行改走 `theme.font_bold` 立刻正常。
本仓库的复现实例：`main.splash` 里 `IssueInactive`/`IssueActive`（页签）、
`sky_issue()`（报头期号）三处。

## 修复

```rust
const INTERNATIONAL_MONOSPACE: &[FontAsset] = &[LIBERATION_MONO, LXGW_REGULAR, LXGW_BOLD];
// INTERNATIONAL_POLICY.monospace 改用 INTERNATIONAL_MONOSPACE；Latin 集不动
// （那是给 wasm / 无 CJK 场景的）。测试断言同步改成对比 INTERNATIONAL_MONOSPACE。
```

## 验证

本机重建 card-host 后：页签「新报」、报头「独立日报 / 10.13 周二」全部正常渲染；
等宽拉丁与图标行为未变；LXGW 本来就随 International 集打包，无新增体积。

## 附带说明（同类隐患）

`FontPolicy` 的资产表、manifest 与 `lazy_chain` 三者是一套对账关系；以后任何"角色
链"的改动都建议加一条测试：**每种角色对 latin/sym/CJK/emoji 各来一个字符，断言
`glyph_index` 不落在 .notdef**。现在只有成员相等性断言，覆盖不到"链里有的字体
其实缺这个脚本"的情形。
