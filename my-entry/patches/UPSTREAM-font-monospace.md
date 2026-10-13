# 报给上游的缺陷：International 字体集的等宽链缺 CJK，中文等宽文字整段豆腐

状态：已定位、已修（本机验证），建议同步回上游 `makepad`。

## 现象

卡片里所有用 `theme.font_code`（等宽角色）渲染的中文——日报页签「新报」、
站内日期标签、报头期号「No.009 / 独立日报」——在 Windows 上渲染成
一排空方框（tofu），而同屏的普通/加粗中文都正常。

同一份 splash 文件、同一个 card-host 二进制：如果文字改走 `theme.font_bold`
就正常，走 `theme.font_code` 就豆腐 —— 说明问题不在卡片，在字体角色的链。

## 根因（`platform/src/font_policy.rs`）

`FontSet::International`（native 一律选它）里：

```rust
monospace: FontChain { role: FontRole::Monospace, members: MONOSPACE },
```

而 `MONOSPACE = [LIBERATION_MONO]` —— 只有拉丁。缺字本来有两条兜底路：

* `lazy_chain(role)`：对 `Regular / Bold / Italic` 返回懒加载的
  `LATIN_LAZY_REGULAR/BOLD`（LXGW 中文 + emoji），**但对 `Monospace` 返回
  `NO_LAZY_FONTS`**；
* 直接往链里加成员 —— 没加。

于是等宽角色遇到 CJK 无路可走，只能画豆腐。`fonts/src/text_roles.rs` 自己的
注释就写着这条规矩：「Every role below therefore carries the COMPLETE chain —
latin, symbols, CJK, colour emoji」，等宽是唯一漏掉的。

## 修复

```rust
const INTERNATIONAL_MONOSPACE: &[FontAsset] = &[LIBERATION_MONO, LXGW_REGULAR, LXGW_BOLD];
// INTERNATIONAL_POLICY.monospace 改用 INTERNATIONAL_MONOSPACE
// （Latin 集保持不变：那是给 wasm/无 CJK 场景的）
```

同时把单元测试里 `assert_eq!(international.monospace, latin.monospace)`
改成断言 `international.monospace.members == INTERNATIONAL_MONOSPACE`。

补丁：`host-font-monospace-cjk.patch`（在 makepad 仓库根 `git apply`）。

## 验证

本机重建 card-host 后：页签「新报」、报头「独立日报 / 10.13 周二」全部正常
渲染（之前是一排方框）。回归无副作用——Latin 集策略未动，等宽拉丁/图标
行为不变，LXGW 本来就随 International 集一起打包。

## 怎么用

```bash
cd <你的 makepad>
git apply <本仓库>/my-entry/patches/host-font-monospace-cjk.patch
# 然后按 README 里那套重建 card-host（CARGO_TARGET_DIR 用纯 ASCII 路径）
```
