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
