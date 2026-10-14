# App Hub 迁移数据保护证据

日期：2026-10-14。平台：Windows。上游基线：`386359153ed6377b5f047bd9ed2767a6a2ac2bc7`。

本目录保存了[迁移源码补丁](../../patches/app-hub-legacy-migration-data-loss.patch)的验证记录，[中文问题报告](../../../生态贡献/ISSUE-10-AppHub迁移误删应用数据.md)说明触发与取舍。文件校验和、三处源码的基线/工作树摘要、依赖 checkout revision、测试限制和计数说明见 [`verification.json`](verification.json)。针对基线固定提交执行的 `git apply --check` 与实际应用结果见 [`clean-apply.json`](clean-apply.json)；两步均退出 0，且三处源文件与当前工作树匹配。干净导出只执行应用及内容匹配检查，完整 Cargo 测试是在实际 App Hub 工作区运行的。

本目录的 `.gitattributes` 保留捕获日志的原始字节，避免 Git 行尾转换使 SHA-256 失效；日志结尾空行也保留。

## 触发与修复

基线的 `adopt_legacy_install` 会把旧布局中的 `bundle`、`.bundle-previous`、`.bundle-next` 当成可清理的安装暂存路径。现代安装已经存在时，应用数据 `<root>/<app-id>/bundle/notes.txt` 仍会被当作旧包删除。源码核对确认，列表扫描（appstore `lib.rs:88`）、卡片打开（`cardapp.rs:89`）和打开前检查构造后端后的恢复（app-hub-app `catalog.rs:671`）都调用迁移函数，所以全新现代安装无需曾有旧安装就会确定性丢失。精确源码链接见问题报告。基线红测直接执行迁移函数并观察 `NotFound`，没有运行 GUI 扫描/打开。

当前修复先保护内容非空的新安装目录。只有没有新安装，或新安装目录是空的普通目录时，才通过匹配 manifest ID、实际 BLAKE3 和有界普通树检查识别旧 `bundle` 或 `.bundle-previous`，再直接重命名识别出的目录。空目录支持中断后的重试，非空现代安装不会被覆盖。`.bundle-next` 不采用，符号链接和 Windows reparse point（含嵌套项）不跟随，旧目录的兄弟路径保持不变。保留旧兄弟路径会留下可能过期或部分下载的文件，但避免仅凭名字误删用户数据。摘要是旧布局识别证据，不替代既有 catalog、签名、准入和启动门槛。

## 测试汇总

| 记录 | 实际结果 |
| --- | --- |
| [`baseline-function-red.txt`](baseline-function-red.txt) | 0 通过、1 失败 |
| [`contract-function-red.txt`](contract-function-red.txt) | 2 通过、15 失败 |
| [`contract-function-green.txt`](contract-function-green.txt) | 17 通过、0 失败 |
| [`install-layout-green.txt`](install-layout-green.txt) | 20 通过、0 失败 |
| [`admission-suite.txt`](admission-suite.txt) | 27 个 `test result` 分组，350 通过、0 失败、0 忽略 |

admission suite 已包含同一组 20 项 `install_layout` 测试，因此 350 是完整套件的合计，不能再把单独的 20 项加一次。按日志分组复核为：app-contract 58 项、app-hub 194 项、app-policy 95 项，另有 3 项文档测试，总计 350。全部 27 个结果分组均无失败或忽略。

三道项目静态检查（`brace.py`、`audit_widgets.py`、`audit_globals.py`）的实际输出在 [`repository-checks.txt`](repository-checks.txt)，均为退出码 0；它们核验晨报卡既有 Splash 源码，不替代 Rust 测试。[`admission-suite.json`](admission-suite.json) 记录完整命令和退出码。

实际执行的 Cargo 测试参数如下，完整工具路径在日志首行，执行目录为 App Hub 工作区：

```powershell
cargo test -p octosense-app-hub --test install_layout -- --nocapture
cargo test -p octosense-app-contract -p octosense-app-policy -p octosense-app-hub -- --nocapture
```

函数级基线复现的[源码](baseline_migration.rs)从固定提交提取迁移函数；其哈希和执行结果记录在红测日志中。17 项补充验证使用真实 contract 源码和实际迁移函数，验证数据保留、摘要/ID 不符、previous 恢复、next-only、空现代目录重试及 Windows junction 等场景；它不覆盖完整集成。完整 `install_layout` 则使用真实 Store、签名 catalog 和安装/启动检查。

## 独立复跑迁移函数

[`tools/verify_hub_migration.py`](../../../tools/verify_hub_migration.py) 与[17 项行为用例](../../../tools/hub_migration_cases.rs)提供一个较小的复核入口。需要 Git、已有 Rust/Cargo 工具链及链接器，另需 Cargo 依赖缓存或联网下载依赖。`--source` 指向含上述固定提交的官方 Git checkout；工具从该提交导出源码，忽略 checkout 内未提交的修改，先执行基线用例，再干净应用本仓库补丁并执行同一组用例。

在作品仓库根目录执行，例如 Windows PowerShell：

```powershell
python -X utf8 tools/verify_hub_migration.py `
    --source OctoSense-App-Hub `
    --cargo-path cargo `
    --output C:\Windows\Temp\hub-migration-verification `
    --offline
```

Windows 的 MinGW 工具应使用全英文 `--output` 路径，Cargo target 也会放在该目录中；默认输出位于仓库 `build/`，中文仓库路径可能使 MinGW 链接失败。`--cargo-path` 可以指定 Cargo 可执行文件的绝对路径，链接器须已在 PATH。已有依赖缓存时使用 `--offline`；首次下载依赖时去掉它。`--revision` 与 `--patch` 可显式指定，默认分别为本报告固定提交和交付补丁。

成功运行会生成 `summary.json`、`red.txt`、`green.txt`、源码提取哈希及补丁应用日志。工具要求基线真正执行全部 17 项且指定的笔记丢失用例失败，再要求修复后 17 项全通过；编译失败不算有效红测。该入口编译实际迁移函数、真实 app-contract 和必要的有界 admission 辅助函数，范围限于迁移行为，不覆盖整个 App Hub、Store、catalog/签名或 appstore UI。

本轮已用该工具从固定 Git 提交重新导出并实际运行：基线 2 通过、15 失败，干净应用后 17 通过、0 失败。归档见 [`portable-summary.json`](portable-summary.json)、[红测](portable-red.txt)、[绿测](portable-green.txt)、[基线提取记录](portable-red-extraction.json)与[补丁后提取记录](portable-green-extraction.json)。[应用预检](portable-apply-check.txt)和[实际应用](portable-apply.txt)均退出 0；两个 harness 使用同一份真实 contract 源码和相同 Cargo.lock 摘要。导出及应用后的源码为 LF，已核对与完整集成所测工作树的 LF 内容及迁移函数一致。

## 边界

admission 记录来自真实 App Hub Cargo workspace 中指定的 app-contract、app-policy、app-hub 三包，完整套件未使用 stub 替代。Windows 环境为 Rust/Cargo 1.98.1 与 MinGW，并使用英文临时 target 路径。makepad、octoscript 和 octoscript-makepad 通过官方 workspace path patch 机制接入，但本机 revision 早于精确 Git pin；makepad 的 `widgets/src/window.rs` 有一处已有工作树改动，本修复未修改。实际 revision 和 dirty 状态见 `verification.json`，因此不能把结果描述为精确 Git pins 的干净全 workspace 构建。Cargo 产生的锁文件环境性变动已恢复，不进入补丁。

GUI、shell 端到端和 appstore package suite 未运行，appstore 的摘要夹具调整仅作源码核对；未执行候选应用脚本。没有 Unix 结果，不声称对外部进程竞争文件系统检查与重命名的保证，也未向官方上游提交 issue 或 PR。
