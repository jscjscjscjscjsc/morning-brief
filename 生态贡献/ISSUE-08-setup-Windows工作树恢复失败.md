# ISSUE-08：setup 无法恢复 Windows 残留 worktree 注册

## 第二条上游提交（2026-10-14）

团队此前的修复已重新在上游 `ffd5e4889a9a1f84fdc5213edefe64c36b4377a2` 上复核并提交 [OctoSense PR #541](https://github.com/OctoSense-org/OctoSense/pull/541)，当前待维护者审阅。本轮不作为新发现重复编号，也未包含上一条 #540 的只读对象生产代码。

上游提交 `2792c2b99b33067799ffaa9710c87c484556543d` 的代码树为 `b72ab45ea0411a6409c9834bba08cac7ed5236a8`，与本地已验证提交 `93db8aef3819316cb17a37f55a867edba914774e` 完全一致。仅修改上游 `tools/setup.py`、`tools/test_setup.py`：保留团队的 UTF-8 解码、NUL 路径记录、`Path.resolve()` 比较，以及 Windows 可运行的 fixture 清理；新增锁定 worktree 不被强制清理的回归测试。

本轮实测 Windows / Python 3.12.10，使用临时本地 Git fixture：

| 检查 | 同一套用例的基线 | 本条修复后 |
|---|---|---|
| 普通残留注册、中文空格路径、关闭 Python UTF-8 模式、锁定注册保护，4 项 | 2 个错误 + 1 个失败；锁定保护通过 | 4 项通过 |
| 完整 setup 套件，21 项 | 7 个错误 + 1 个失败 | 5 个错误 |

剩余五个错误在前后是同一组：四项 CRLF 补丁 fixture 问题和一项只读 clone 清理问题（独立 PR #540 修复）。两条 PR 的代码用 `git merge-tree` 无冲突组合，组合后的 **8 项目标测试全部通过**。不宣称完整 setup 套件全绿。

`tools/setup.py --check --cargo` 已尝试，在缺少预先准备的 `.sources/octoscript-makepad` 处停止；未下载完整依赖，未执行 Rust、GUI、ROM 或模型服务测试。真实开发目录、源码 pins、用户修改及运行时二进制未改变。

- [本轮结果](../my-entry/evidence/setup-worktree-upstream-20261014/results.json)
- [目标红测试](../my-entry/evidence/setup-worktree-upstream-20261014/target-red.txt) / [目标绿测试](../my-entry/evidence/setup-worktree-upstream-20261014/target-green.txt)
- [完整基线](../my-entry/evidence/setup-worktree-upstream-20261014/suite-baseline.txt) / [完整修复后](../my-entry/evidence/setup-worktree-upstream-20261014/suite-fixed.txt)
- [两条 PR 组合验证](../my-entry/evidence/setup-worktree-upstream-20261014/integration.json) / [组合日志](../my-entry/evidence/setup-worktree-upstream-20261014/integration.txt)
- [上游提交版补丁](../my-entry/patches/octosense-setup-worktree-upstream.patch) / [本轮复核工具](../tools/verify_setup_worktree.py)

实际运行的复核命令中，`<patched-checkout>` 代表持有上述固定提交的本机目录：

```powershell
python -X utf8 tools/verify_setup_worktree.py --source <patched-checkout> --out my-entry/evidence/setup-worktree-upstream-20261014
python -X utf8 tools/verify_setup_worktree.py --source <patched-checkout> --out my-entry/evidence/setup-worktree-upstream-20261014 --integration-tree acb79aa7f4c703af33aee332cdd8b499cbfd851f
```

第二个命令要求源 checkout 的 Git 对象库中持有两条修复组合得到的该 tree。日志已脱敏。本条提交后停止，不自动开始第三条。

## 原团队修复记录（保留历史验证数字）

2026-10-14，第 46 轮。基线 OctoSense commit `ffd5e4889a9a1f84fdc5213edefe64c36b4377a2`。

## 复现与影响

使用本地 Git 源码 hub 建立 `.sources/makepad` worktree；删除检出目录但不清理 Git 注册后，再次执行准备源码逻辑。Windows Git 报：

```text
is a missing but already registered worktree;
use 'add -f' to override, or 'prune' or 'remove' to clear
```

该恢复场景正是原 `add_worktree()` 注释意图支持的路径。失败会阻止开发者重建依赖源码；无需外网或真实模型服务即可复现。

## 根因与修复

`git worktree list --porcelain` 在 Windows 返回 `C:/...`，Python 路径通常为 `C:\...`，直接比较字符串无法识别相同路径；中文路径还可能被 Git 引号转义。Git 子进程输出未指定 UTF-8，又会受到 CP936 默认编码影响。

修复改用 `--porcelain -z` 返回未转义的 NUL 记录，提取 `worktree ` 路径后用 `Path.resolve()` 比较；Git helper 显式 UTF-8 解码。只在识别到目标注册时沿用已有 `prune`，未新增强制删除用户源码或本地修改的行为。

## 验证及限制

三项真实 Git 回归通过：普通丢失 worktree、中文加空格路径、显式关闭 Python UTF-8 模式后解析中文路径。测试中的 `rm -rf` 改用 Python `shutil.rmtree`，无需 Windows 额外安装 Unix 命令。

**完整 setup 套件未全绿。** 原实现搭配新增测试的基线 19 项有 7 个错误；最终 20 项有 5 个错误、15 项通过。残留五个与原实现一致：四个是 Windows CRLF 补丁 fixture 问题，一个是 `convert_clone` 删除只读 Git 对象失败，本轮未扩大修改该生产逻辑。

- [目标红测试](../my-entry/evidence/ecosystem-20261014/setup-worktree-red.txt) / [目标绿测试](../my-entry/evidence/ecosystem-20261014/setup-worktree-green.txt)
- [完整基线](../my-entry/evidence/ecosystem-20261014/setup-worktree-baseline.txt) / [完整修复后套件](../my-entry/evidence/ecosystem-20261014/setup-worktree-suite-final.txt)
- [补丁（含回归）](../my-entry/patches/octosense-setup-worktree-windows.patch)
- [干净固定版本复核脚本](../tools/verify_ecosystem.py)

实际验证：Windows、Python 3.12、Git 2.55.0。未运行 setup 主入口下载完整依赖，未编译 Rust、ROM 或 GUI 宿主。
