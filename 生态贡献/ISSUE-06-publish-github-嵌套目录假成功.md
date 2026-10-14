# ISSUE-06：publish-github 在嵌套应用目录假成功

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
