# ISSUE-10：App Hub 迁移会误删名为 `bundle` 的应用数据

日期：2026-10-14。组件：[`OctoSense-App-Hub`](https://github.com/OctoSense-org/OctoSense-App-Hub) 的旧安装布局迁移。交付为[源码补丁](../my-entry/patches/app-hub-legacy-migration-data-loss.patch)及本地证据，尚未提交官方上游。

## 问题

旧布局把已安装包放在 `<root>/<app-id>/bundle`。新布局把审阅后的安装放在 `<root>/.bundles/<app-id>/bundle`，而 `<root>/<app-id>/` 同时是应用可写的数据目录。因此 `bundle`、`.bundle-previous` 和 `.bundle-next` 这些名字本身不能证明目录是安装包。

在基线提交 `386359153ed6377b5f047bd9ed2767a6a2ac2bc7` 中，迁移函数会在发现新布局已有安装时删除旧布局的 `bundle`，并且还会清理两个更新暂存名。于是一个已经安装的新包，只要应用数据中存在：

```text
<root>/.bundles/<app-id>/bundle/       # 当前新布局安装
<root>/<app-id>/bundle/notes.txt       # 用户数据，恰好也叫 bundle
```

源码中的列表扫描在 [`octosense_appstore::installed_apps`（lib.rs:88）](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/386359153ed6377b5f047bd9ed2767a6a2ac2bc7/crates/appstore/src/lib.rs#L88) 调用批量迁移；[非系统卡片的打开路径（cardapp.rs:89）](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/386359153ed6377b5f047bd9ed2767a6a2ac2bc7/crates/appstore/src/cardapp.rs#L89) 则直接调用单应用迁移。另一个打开前检查入口 [`try_may_open_from_environment`（catalog.rs:107）](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/386359153ed6377b5f047bd9ed2767a6a2ac2bc7/crates/app-hub-app/src/catalog.rs#L107) 会构造后端，经 [`recover_installations`（catalog.rs:671）](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/386359153ed6377b5f047bd9ed2767a6a2ac2bc7/crates/app-hub-app/src/catalog.rs#L671) 调用批量迁移。

基线函数先清理 `.bundle-next` 和 `.bundle-previous`，再在现代 `bundle` 已存在时把旧 `bundle` 视为过期副本并递归删除。

因此，即使从未使用过旧布局，只要一个全新现代安装的应用把普通数据写到 `bundle/notes.txt`，下一次扫描/打开触发迁移就会确定性删除它；无需损坏 manifest、断网或并发竞争。函数级基线回归记录了删除后的 `NotFound`（0 项通过、1 项失败）。这些调用链是源码核对结果，本轮没有通过 GUI 点击扫描或打开来复现。

## 修复行为

修复集中在 `crates/app-hub/src/client.rs`，配套更新了 `install_layout` 回归和 appstore 的测试夹具：

- 新安装目录存在内容时直接保护所有旧路径；不再按名字删除应用数据。
- 新安装目录不存在，或是一次中断留下的空、普通目录时，才检查旧 `bundle`，其次检查 `.bundle-previous`。
- 候选必须是有限大小和深度的普通目录树，manifest 的应用 ID 必须匹配，且实际 BLAKE3 摘要必须等于 manifest 声明。`.bundle-next` 永远不作为已发布安装采用。
- 只把识别出的候选目录重命名到新布局；旧目录中的兄弟路径（包括未知文件、旧 previous 和 next）保持原样。
- 拒绝根目录、候选目录及其子项中的符号链接和 Windows reparse point；直接调用的 `app_id` 也限制为单个普通路径组件。
- 创建新目录后若重命名失败，会清理本次创建的空目录，使下一次迁移仍可重试；已有非空新安装不会被覆盖。

保留兄弟路径是有意的数据保护取舍：迁移不再替用户判断哪些旧文件可以删除，代价是过期或中断的包可能继续占用空间，需要另行清理。摘要检查只用于识别旧布局，不等同于发布者认证；原有 catalog、签名、准入和启动检查保持不变，仍是运行安装的权威门槛。

appstore 的历史测试夹具原来填写空摘要，无法满足新的识别条件，因此改为计算真实目录摘要；此处只改测试夹具，不改 appstore 的运行逻辑。

## 验证结果

日志和来源哈希归档在 [`my-entry/evidence/hub-migration-20261014/`](../my-entry/evidence/hub-migration-20261014/)：

| 检查 | 结果 |
| --- | --- |
| 基线函数红测 | 1 项失败 |
| 真实 contract 函数补充红测 | 2 项通过、15 项失败 |
| 真实 contract 函数补充绿测 | 17 项通过、0 项失败 |
| 完整 `install_layout` 集成测试 | 20/20 通过 |
| 完整 admission suite | 27 个结果分组，合计 350 项通过、0 项失败、0 项忽略 |

admission suite 本身已经包含这 20 项 `install_layout` 集成测试；表中的 20/20 是单独运行的交叉记录，不能再加到 350 上。350 为 347 项单元/集成测试与 3 项文档测试之和。

[`clean-apply.json`](../my-entry/evidence/hub-migration-20261014/clean-apply.json) 记录了针对基线的 `git apply --check` 与实际应用均退出 0，并确认三处源码与当前工作树一致。这是干净应用和内容匹配检查，完整 Cargo 测试是在本地实际 App Hub 工作区运行的。[`verification.json`](../my-entry/evidence/hub-migration-20261014/verification.json) 保存源码、补丁、日志 SHA-256 和实际依赖 revision；[`repository-checks.txt`](../my-entry/evidence/hub-migration-20261014/repository-checks.txt) 记录 `brace.py`、`audit_widgets.py`、`audit_globals.py` 均退出 0。这三道检查只核验晨报卡既有 Splash 源码，不能替代 Rust 回归。

归档日志实际执行的 Cargo 测试参数如下（完整工具路径、退出码见各日志）：

```powershell
cargo test -p octosense-app-hub --test install_layout -- --nocapture
cargo test -p octosense-app-contract -p octosense-app-policy -p octosense-app-hub -- --nocapture
```

第二条是 AGENTS.md 要求的 admission 套件，使用真实 Store、catalog、签名与准入测试。函数补充 harness 对比的是实际基线/修复迁移函数及实际 contract 源码，只证明列出的迁移场景，不覆盖 Store、catalog 签名和完整 App Hub 集成。

## 验证边界

完整测试在 Windows 上使用 Rust/Cargo 1.98.1、MinGW、真实 App Hub Cargo workspace 和实际 app-contract/app-policy/app-hub 源码完成，未在归档的完整套件中使用 stub 替代。这是完整工作区中的指定三包测试，不代表所有 workspace package 都跑过。makepad、octoscript、octoscript-makepad 沿官方 workspace 的路径补丁机制接入，但本机 checkout revision 早于精确 Git pin；makepad 还有一处预先存在且未由本修复修改的 `widgets/src/window.rs` 工作树改动。验证期间 Cargo 对锁文件的环境性归一化已恢复，补丁不包含 `Cargo.lock`。

GUI、shell 端到端和 appstore package suite 未运行，appstore 摘要夹具调整只有源码核对；没有 Unix 结果，也没有声称外部进程竞争文件系统检查与重命名时的保证。没有运行候选应用的 Splash 脚本来证明修复。交付仍是本地补丁、测试和报告，尚未向官方上游提交 issue 或 PR。
