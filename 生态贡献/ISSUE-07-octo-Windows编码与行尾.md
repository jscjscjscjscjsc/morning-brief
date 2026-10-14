# ISSUE-07：octo 默认编码与行尾破坏 UTF-8 bundle

2026-10-14，第 46 轮。基线 App Flow commit `d0344682df7c52ae5a79055f20f148f542d115e0`。

## 影响与根因

`tools/octo` 多处 `Path.read_text()` / `write_text()` 未指定编码，Windows 默认 CP936 的 Python 会按本地代码页读取 UTF-8 文件。含「晨报📰…」的 manifest、listing 或源码可能解码失败或出现乱码。Windows 文本写入还会把 LF 转成 CRLF；bundle 摘要依赖逐字节内容，因此写回会改变摘要。

另一个可见症状是 workflow 首次按 UTF-8 写入后，第二次被默认代码页读取，幂等检查可能误判成自定义文件。带 Unicode 的已签名 manifest 应按 sealed 规则被拒绝启动，而不应先报编码错误。

## 修复

格式确定的模板、JSON、源码和 workflow 统一显式按 UTF-8 读取；新增 `write_utf8()`，用 `Path.open(encoding="utf-8", newline="\n")` 保持输出 LF。沿用 Python 3.9 支持，不使用仅新版 `Path.write_text()` 支持的 newline 参数。

已签名 bundle 的检查仍保留原始字节、不重新 stamp；`run` 继续在启动宿主前拒绝 sealed release。另修正一条既有测试对 TOML 中 JSON 兼容路径转义未解码的问题，使中文 workspace 下的 SDK 路径断言正确。

## 复现与验证

新增 4 个回归用真实 UTF-8 文件模拟默认 CP936/CRLF 行为，仅在调用方未指定编码/行尾时介入；并非通过 mock 直接返回预期文本。覆盖 `new` 字节保持、发布幂等、signed check 不改字节、signed run 正确拒绝。

```powershell
cd OctoScript-App-Design-Flow
python -X utf8 -m unittest discover -s tools -p test_octo_encoding.py -v
```

修复前 1 failure、3 errors，修复后 4 项通过；CLI 原有套件 39 项，结果 `OK (skipped=6)`，跳过项依赖未构建的 Rust/SDK 产物。Python 3.9 兼容性做了源码审查，实际运行版本为 Python 3.12。

- [红测试](../my-entry/evidence/ecosystem-20261014/encoding-red.txt) / [绿测试](../my-entry/evidence/ecosystem-20261014/encoding-green.txt)
- [可应用补丁（与 ISSUE-06 合并，避免修改同一文件的应用顺序歧义）](../my-entry/patches/octo-publisher-root-utf8.patch)
- [固定版本复核脚本](../tools/verify_ecosystem.py)

本轮未编译或运行 Rust 宿主，也未声称端到端 UI 已验证。


## 2026-10-14 正式上游提交补充

已提交 [官方 App Flow PR #195](https://github.com/OctoSense-org/OctoSense-App-Flow/pull/195)，当前 OPEN，待维护者审阅合并。署名为共创队（晨报卡；报名 ID：小鞠老师），并链接项目仓库。团队原合并补丁保留，本次仅提交编码/行尾生产修复及测试，不重复编号。

上游代码树 `d329dcb9596bb96958f18637f26cc64fcc4425d5` 与已测试本地提交 `a65199ff95d289743c22cf4cfb107009dc36e226` 一致；公开 head `cf48cff380a412f7f99a9730344127bf4beeafa2`。

本次在固定源码导出的中文路径 fixture 中复核：4 项目标回归由 1 failure + 3 errors 变为全通过；同一修正 SDK 路径断言的 CLI 套件前后均为 39 项、2 个 release-shell fixture 失败和 6 个跳过，不声称完整套件全绿。实际运行 Windows / Python 3.12.10。此环境结论应与上文历史机器结果区分。

与 #194 的独立补丁在 `cmd_publish_github` 有一处相邻代码冲突；已在临时 fixture 中明确保留目录检查，再按 UTF-8 读取 manifest。组合后编码 4 项通过，发布 16 项 `OK (skipped=3)`；三项 symlink 子用例因 Windows 权限跳过。上游先合并其中一条后，另一条需要按该已测试顺序重基。

- [独立上游补丁](../my-entry/patches/app-flow-octo-utf8-lf-only.patch)
- [复核结果](../my-entry/evidence/upstream-octo-encoding-20261014/results.json) / [组合验证](../my-entry/evidence/upstream-octo-encoding-20261014/integration.json)
- [可复跑工具](../tools/verify_octo_encoding.py)：参数与 `verify_publisher_root.py` 相同，`--source` 指向该 PR checkout，`--scratch-root` 必须位于所有 Git 仓库之外。

没有运行 Rust/GUI、真实 GitHub workflow、tag 或 release。
