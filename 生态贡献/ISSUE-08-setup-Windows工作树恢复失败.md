# ISSUE-08：setup 无法恢复 Windows 残留 worktree 注册

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
