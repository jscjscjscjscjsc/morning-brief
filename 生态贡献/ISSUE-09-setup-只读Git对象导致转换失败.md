# ISSUE-09：Windows 只读 Git 对象使 clone 转 worktree 失败

2026-10-14。上游：[OctoSense PR #540](https://github.com/OctoSense-org/OctoSense/pull/540)，已提交、待维护者审阅。本条完成即停止，不自动继续第二条。

## 问题与边界

晨报卡 Windows 环境准备中，队员在 ISSUE-08 完整回归发现另一项独立错误：`tools/setup.py --convert` 已创建新 worktree，却在清理原 clone 的 `.sources/.makepad.converting/.git/objects/` 时遇到 `PermissionError: [WinError 5]`，转换报失败并留下旧 clone。

根因是 Windows 不允许删除带只读属性的 Git loose object。原实现直接 `shutil.rmtree(aside)`；部分检出失败时的 `shutil.rmtree(path)` 也有同一问题，可能阻止恢复原 clone。

本条与 ISSUE-08 的残留 worktree 注册/编码修复分开，不重复提交队员的补丁；也没有继续使用已经撤回的 ISSUE-01 截图缺陷归因。

## 修复

基线：`OctoSense-org/OctoSense` 的 `ffd5e4889a9a1f84fdc5213edefe64c36b4377a2`。

上游 PR 提交：`8283b306ac7207c875e66f724c97ea8ad45cde51`。其 Git tree 为 `697625a3356c0abc73ed78fbcf544695965952c7`，与本地已验证提交 `68f1774c94fc1389a08b50007ca41f95643b946b` 完全一致；GitHub API 创建提交的元数据导致提交号不同。

仅改 `tools/setup.py` 与 `tools/test_setup.py`：

- 转换清理专用 `remove_conversion_tree()`，同时用于完成后的旧 clone 清理与失败时的部分检出清理。
- 只对 Windows 下 `os.unlink` 因只读普通文件而触发的 `PermissionError` 清除该文件只读属性并重试一次；可写文件的权限错误、目录、符号链接及其他异常继续抛出。
- 保留原有未提交、未跟踪、忽略、暂存及 stash 检查；不增加删除范围，不改真实依赖目录、不运行源码准备主入口。
- 使用 `onerror` 保持 Python 3.12 之前版本可解析；其他 Python/操作系统的实际执行仍未验证。

## 验证

Windows / Python 3.12.10。用 `-X utf8` 排除另一条默认编码问题；fixture 全部是临时本地 Git 仓库，不访问外网。

| 检查 | 修复前 | 修复后 |
|---|---|---|
| 既有正常转换、真实只读 Git 对象、失败回滚、保留用户文件，4 项 | 3 个 `WinError 5`，1 项通过 | 4 项通过 |
| 完整 setup 套件，同样的 20 项 | 8 个错误 | 5 个错误 |

剩余五项在修复前后是同一组：四项 Windows CRLF 补丁 fixture 错误，一项 stale-registration fixture 调用系统中不存在的 `rm`。不宣称完整套件全绿，不宣称 Rust、ROM、GUI 或正式应用发布已经验证。

- [结果 JSON](../my-entry/evidence/setup-readonly-20261014/results.json)
- [目标红测试](../my-entry/evidence/setup-readonly-20261014/target-red.txt) / [目标绿测试](../my-entry/evidence/setup-readonly-20261014/target-green.txt)
- [完整基线](../my-entry/evidence/setup-readonly-20261014/suite-baseline.txt) / [完整修复后](../my-entry/evidence/setup-readonly-20261014/suite-fixed.txt)
- [可应用补丁](../my-entry/patches/octosense-setup-readonly-clone.patch)
- [复核工具](../tools/verify_setup_readonly.py)

实际执行的复核命令（`<patched-checkout>` 是持有该补丁的上游 checkout）：

```powershell
python -X utf8 tools/verify_setup_readonly.py --source <patched-checkout> --out my-entry/evidence/setup-readonly-20261014
```

补丁仅提交源代码 PR，未替换晨报卡的运行时二进制，也未合并上游 main。测试日志已去掉个人路径。
