# 生态贡献 · 历史记录与 2026-10-14 复核

这里记录晨报卡实际遇到的上游问题、复现证据与补丁。历史观察与当前结论分开保存：上游已解决的兼容问题、撤回的归因，以及此前轮次的补丁，都不重复计入本轮修复。

本轮围绕晨报卡的发布和 Windows 开发流程复核。App Flow 基线为 `d0344682df7c52ae5a79055f20f148f542d115e0`；它固定的 App Hub 工具链为 `386359153ed6377b5f047bd9ed2767a6a2ac2bc7`。官方仓库未纳入本作品 Git 历史，源头修复以本仓库保存的补丁、复现脚本和各报告为准。

## 2026-10-14 本轮问题

| 编号 | 对象 | 复现的问题 | 状态与验证入口 |
|---|---|---|---|
| [ISSUE-09](ISSUE-09-setup-只读Git对象导致转换失败.md) | OctoSense `tools/setup.py` | Windows 只读 Git 对象使 clone 转 worktree 的完成清理与失败回滚报 `WinError 5` | 已提交 [上游 PR #540](https://github.com/OctoSense-org/OctoSense/pull/540)；目标 4 项通过；完整套件由 8 错降到 5 错，详见记录 |
| [ISSUE-06](ISSUE-06-publish-github-嵌套目录假成功.md) | App Flow `tools/octo` 发布流程 | 晨报卡应用在 `my-entry/morning-brief`；生成器将该目录当仓库根，写入 GitHub 不读取的嵌套 workflow 目录，并仍使用根目录 bundle 模板 | 已修复；发布回归 16 项 OK（3 个既有子用例 skip） |
| [ISSUE-07](ISSUE-07-octo-Windows编码与行尾.md) | App Flow `tools/octo` | 文本 I/O 依赖 Windows 默认编码，写入时还可能转换行尾，影响 UTF-8 源码与 bundle 字节 | 已修复；4 项编码回归通过 |
| [ISSUE-08](ISSUE-08-setup-Windows工作树恢复失败.md) | OctoSense `tools/setup.py` | 残留 worktree 注册识别失败，中文路径解码受默认编码影响 | 已修复；3 项目标回归通过，完整套件 5 个基线错误见报告 |

这些问题服务于晨报卡的实际开发与发布路径。贡献是否完成、哪些用例通过，以对应报告的命令和输出为准；本索引不以报告数量代替效果证据。ISSUE-09 已提交上游 PR，其余三条保持各自报告记录的提交状态。

## 历史报告的当前状态

| 编号 | 对象 | 2026-10-14 复核结论 |
|---|---|---|
| [ISSUE-01](ISSUE-01-hub-scan-审核包截图字段不一致.md) | App Hub `hub scan` | 撤回「顶层截图必须与 listing 截图一致」的缺陷归因：两字段语义不同，上游文档明确 scan 包不携带截图。保留原输出，不计本轮修复 |
| [ISSUE-02](ISSUE-02-octo-publish-github%20生成的%20workflow%20不可用.md) | App Flow / App Hub 发布接口 | 旧 `publisher-*` 缺失已由上游实现解决；旧的禁止提交 workflow 建议失效。不计本轮修复，当前嵌套路径问题另见 ISSUE-06 |
| [ISSUE-03](ISSUE-03-能力门拒绝时同步重入VM.md) | makepad `splash_host.rs` | 历史报告记录能力拒绝时同步重入 VM；当时应用已绕过。本轮未运行 Rust 宿主重现，不能据此断言当前上游仍有同一故障 |
| [ISSUE-04](ISSUE-04-等宽字体缺CJK兜底中文豆腐块.md) | makepad `font_policy.rs` | 历史补丁 `my-entry/patches/host-font-monospace-cjk.patch`，此前轮次记录过本机重建验证。本轮未重复运行，不计新增修复 |
| [ISSUE-05](ISSUE-05-开机窗口内宿主请求被静默吞掉.md) | makepad / 宿主请求投递 | 历史启动时序观察；应用以重试及延后探测等方式绕过。本轮未重现或定位当前运行时根因，不计本轮修复 |

ISSUE-01、ISSUE-02 顶部已补复核说明，正文中的原始输出保留为历史证据；阅读时应先看复核结论，不能继续使用已撤回或过时的建议。

## 历史补丁档案

- `my-entry/patches/host-font-monospace-cjk.patch`：此前轮次保存的等宽中文字体补丁，对应 ISSUE-04。
- `my-entry/patches/host-services.patch`、`host-voice.patch`：此前轮次保存的本地宿主模型与语音服务扩展，使用说明见 `my-entry/patches/README.md`。这些本地改动不等于当前官方 shell 已提供同一接口，也不证明新版本宿主兼容。

## 验证边界与复核方法

本轮报告按可复现命令、确切版本、源码位置、修复前后结果组织。Python 工具测试通过，只证明相应用例覆盖的工具行为；不会自动证明应用能在原生宿主运行、模型服务可用或 GitHub 发布成功。

本轮未编译或运行 Rust `hub` / `card-host`，未新增实机截图，也未执行付费模型、语音或图像服务。历史轮次的实机记录不能替代本轮验证。旧 `hub scan` 输出字段差异也不再作为失败用例。

本地读取当前上游源码即可核对 ISSUE-01 / ISSUE-02 的复核依据：

```powershell
rg -n 'Paths to screenshots|screenshots: Vec::new' OctoSense-App-Hub/crates/app-hub/src/scan.rs
rg -n 'Bundle-relative paths|pub screenshots' OctoSense-App-Hub/crates/app-policy/src/listing.rs
rg -n 'packet carries no screenshots' OctoSense-App-Hub/docs/SUBMITTING.md
rg -n 'publisher-prepare|publisher-attach|publisher-verify|publisher-pack' OctoSense-App-Hub/crates/app-hub/src/bin/hub.rs
```

上游源码不随本仓库分发；换机器时请先按报告检出相同提交。修复补丁的应用与回归命令见 ISSUE-06 / ISSUE-07 / ISSUE-08。
