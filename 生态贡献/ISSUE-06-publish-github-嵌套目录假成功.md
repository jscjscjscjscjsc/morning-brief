# ISSUE-06：publish-github 在嵌套应用目录假成功

## 第三条上游提交（2026-10-14）

团队此前的合并补丁已按独立问题拆分，本条目录检查提交为 [App Flow PR #194](https://github.com/OctoSense-org/OctoSense-App-Flow/pull/194)，当前待维护者审阅；UTF-8/LF 修复仍保留在 ISSUE-07，没有夹带进本 PR。原团队补丁与历史日志保持不变，不作为本轮新发现重复编号。

基线 `d0344682df7c52ae5a79055f20f148f542d115e0`；上游提交 `2f0c62c3e81be228f6e40570e59b00d134433911`，代码树 `5226fb6ddbfdcc2ad4b1863e97db64fe3e43143c` 与已验证本地提交 `542eceeba5f27d47846444bc0e9232de24255fd2` 完全一致，`tools/octo` 的 `100755` 可执行权限保持不变。

本条只改四个上游文件：`tools/octo`、发布测试及中英文 `docs/PUBLISHING`。在生成工作流或普通 `new` 创建任何目录之前检查最近 `.git` 边界；嵌套布局明确拒绝，即使 `--replace` 也不会写入。独立内层 Git 仓库、linked worktree 根目录、仓库外新建应用和 `new --system` 保持支持。没有实现自动 monorepo 发布，也没有搬动或改写晨报卡现有定制 workflow。

### 本轮验证

Windows / Python 3.12.10。固定版本源码导出到独立临时目录，真实 Git 仓库与 linked worktree fixture；使用 Python UTF-8 模式隔离后续 ISSUE-07。临时目录必须位于所有 Git 仓库之外，以正确测试独立新建应用。

| 检查 | 同一套用例基线 | 本条修复后 |
|---|---|---|
| 发布套件，16 项 | 4 个失败点，3 个跳过子用例 | `OK (skipped=3)` |
| 更广 CLI 套件，39 项，Unicode 导出路径 | 3 个失败，6 个跳过 | 相同 3 个失败、6 个跳过 |

发布套件三个跳过子用例依赖 Windows 符号链接权限，没有当作验收通过。更广 CLI 的三个既有失败涉及两项 Release shell fixture，以及一项 SDK 路径 JSON 转义断言；未扩大到这些问题，不声称完整 CLI 套件全绿。`tools/check-links.py` 输出 `0 broken, 0 pending`；`git diff --check` 和归档补丁反向应用检查通过。配置现有 hub/card-host 路径后 `octo doctor` 通过，但不等于原生宿主功能验收。

初次离线导出漏带 `docs`，导致三个附带 fixture 读取错误；原输出保留在 `initial-partial-export/`。补齐文档 fixture 后，上表最终复核只保留三个既有 CLI 失败，没有把导出准备错误计为生态 bug。

- [最终结果](../my-entry/evidence/publisher-root-upstream-20261014/results.json)
- [发布红测试](../my-entry/evidence/publisher-root-upstream-20261014/publish-red.txt) / [发布绿测试](../my-entry/evidence/publisher-root-upstream-20261014/publish-green.txt)
- [CLI 基线](../my-entry/evidence/publisher-root-upstream-20261014/cli-baseline.txt) / [CLI 修复后](../my-entry/evidence/publisher-root-upstream-20261014/cli-fixed.txt)
- [链接、diff、doctor 检查](../my-entry/evidence/publisher-root-upstream-20261014/checks.txt)
- [目录检查独立补丁](../my-entry/patches/app-flow-publisher-root-only.patch) / [复核工具](../tools/verify_publisher_root.py)

实际执行的复核命令中占位符仅替换本机目录：

```powershell
python -X utf8 tools/verify_publisher_root.py --source <patched-checkout> --out my-entry/evidence/publisher-root-upstream-20261014 --scratch-root <existing-temp-outside-git>
```

没有推送应用 tag、创建 Release、运行 GitHub Actions 发布、提交应用上架，也没有执行 Rust/GUI 验收。本条源代码 PR 和晨报卡归档提交完成后停止。

## 原团队合并补丁记录（保留历史说明）

2026-10-14，第 46 轮。本轮新发现并修复的开发工具缺陷，独立于其他队伍的宿主启动、超时、跨 App 桥接和日历 PR。

## 影响与复现

基线：官方 App Flow（本地目录沿用旧名 `OctoScript-App-Design-Flow`），commit `d0344682df7c52ae5a79055f20f148f542d115e0`。

晨报卡在 Git 仓库的 `my-entry/morning-brief/` 下，而非仓库根。在基线执行：

```powershell
python OctoScript-App-Design-Flow/tools/octo publish-github my-entry/morning-brief
```

命令返回成功，把 workflow 写到 `my-entry/morning-brief/.github/workflows/`；GitHub 只会执行**仓库根**的 `.github/workflows/`。模板又固定使用 `app/bundle`、`app/components`，因此把文件简单搬到根目录仍不足以支持此布局。

## 根因与修复

原命令仅验证 `bundle/manifest.json`，把应用目录直接当成仓库根。修复新增最近 `.git` 边界检查，兼容普通仓库和 linked worktree 的 `.git` 文件。

- `publish-github` 在写入前拒绝不支持的嵌套布局，提示真实根目录及需要审核的 bundle/component 路径；`--replace` 也不能绕过。
- 普通 `new` 同样在创建任何目录前检查，避免生成注定不能执行的发布配置。
- 独立仓库、linked worktree 根目录和仓库外新建应用继续可用；`new --system` 保留系统应用在 shell 仓库内创建的既有用法。

这是阻止假成功的最小修复，**未实现自动 monorepo 发布**。已有晨报卡根目录的定制 workflow 仍由人工维护。

## 验证与交付

真实 Git fixtures 覆盖嵌套应用拒绝、写入前保护、独立内层仓库、linked worktree，以及系统应用兼容。修复前发布套件 15 项出现 4 次失败；修复后结果见 [验证记录](../my-entry/evidence/ecosystem-20261014/README.md)。Windows 符号链接权限不足的既有子用例有明确 skip，未当作通过。

- [补丁（含编码修复及全部回归）](../my-entry/patches/octo-publisher-root-utf8.patch)
- [先失败日志](../my-entry/evidence/ecosystem-20261014/publish-root-red.txt)
- [复核脚本](../tools/verify_ecosystem.py)

未执行 GitHub Actions 发布，未向官方上游创建 PR；本轮产物统一保存在我们的仓库。
