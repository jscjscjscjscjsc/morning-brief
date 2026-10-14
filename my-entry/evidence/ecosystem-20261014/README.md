# 第 46 轮生态修复验证证据

日期：2026-10-14。环境：Windows，Python 3.12，Git 2.55.0。日志为 UTF-8 / LF；将本机绝对目录替换为 `<WORKSPACE>` / `<TEMP>`，清理行尾空格与文件末尾空行，未改测试结果。补丁保留 Git 原始格式中的上下文空格。

## 本轮三类修复

| 问题 | 修复前 | 修复后及限制 |
| --- | --- | --- |
| 发布命令对子目录假成功 | [发布红测试](publish-root-red.txt)：15 项，4 failures | 最新发布套件 16 项，OK，3 个既有符号链接子用例 skip |
| Windows UTF-8 / LF | [编码红测试](encoding-red.txt)：4 项，1 failure + 3 errors | [编码绿测试](encoding-green.txt)：4 项全通过 |
| Windows worktree 恢复 | [工作树红测试](setup-worktree-red.txt)：两项真实 Git 恢复均报错 | [目标绿测试](setup-worktree-green.txt)：三项通过，包含 UTF-8 模式关闭时的中文路径 |

独立审查发现并修正 `new --system` 的创建兼容回归，保留嵌套系统 app 的既有用法：[修正前](publish-system-red.txt) / [修正后](publish-system-green.txt)。这不是另计的一条生态 bug。

## 干净源码应用验证

主仓库中的 `tools/verify_ecosystem.py` 从本地 Git **提交对象**导出两份固定版本源码，而不是使用已经改过的工作目录；执行两个补丁的 `git apply --check` 和实际应用，再运行选定回归。

```powershell
python -X utf8 tools/verify_ecosystem.py
```

默认依赖本仓库旁的 ignored 官方检出目录；可通过 `--flow-source` / `--sense-source` 指定其他已有 clone。脚本不联网、不推送、不改这些源仓库，输出到 ignored `build/ecosystem-verification/`。

测试子进程设置 Cargo 离线模式并禁用 rustup 自动安装。已安装 Rust 的机器若要执行条件性的构建用例，需先具备本地 target、SDK 产物和依赖缓存；缺少离线依赖可能报失败。本机没有 Rust，相关用例按既有条件跳过。

最近一次固定版本验证日志保存在 `clean-apply/`：发布 16 项 `OK (skipped=3)`、编码 4 项全过、CLI 原有 39 项 `OK (skipped=7)`、setup 目标 3 项全过。CLI 六个 skip 为 Rust / SDK 产物未构建，另一个为干净临时环境未配置 App Hub contract parity；没有把 skip 当作实际执行成功。原工作目录的 CLI 验证为 39 项、6 skip，见 [记录](flow-suite-green.txt)。

## 未通过及未运行的范围

完整 setup 套件仍有原实现同样存在的五个错误：四个 Windows CRLF patch fixture、一个删除只读 Git 对象的 `convert_clone` 失败。见 [完整基线](setup-worktree-baseline.txt)（19 项、7 errors）和 [修复后](setup-worktree-suite-final.txt)（20 项、5 errors、15 pass）。本轮选择最小恢复修复，未修改这些生产或 fixture 逻辑。

未编译 Rust 宿主、ROM 或 GUI，未运行模型/语音端到端流程，未实际触发 GitHub Actions 发布，未向官方仓库提交 PR。我们的补丁、回归和中文报告统一提交到 morning-brief。
