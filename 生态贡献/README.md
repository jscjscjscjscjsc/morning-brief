# 生态贡献 · 本轮（复赛）新增

这个目录记录本项目在「绕过上游缺陷」时**顺手回流给上游**的东西。规则来自比赛要求，也来自项目自己的复盘：**只绕过不报告，等于把问题留给下一个人。**

每一条都尽量满足四个条件，方便维护者直接复核：

1. **可复现**——给出命令行与原始输出，而不是描述；
2. **可定位**——给出具体文件与代码片段（而不是「在某个地方」）；
3. **可判断**——说清危害与影响面，以及为什么不能靠「读的人自己当心」解决；
4. **可动手**——给按侵入性排序的修复建议，最好带上回归测试该测什么。

---

## 本轮三条

| 编号 | 对象 | 一句话 | 严重度 | 状态 |
|---|---|---|---|---|
| [ISSUE-01](ISSUE-01-hub-scan-审核包截图字段不一致.md) | `hub scan` | 审核包顶层 `screenshots` 是空数组，而同一份包里的 `listing.screenshots` 正确列出四张真实截图——自动审阅会把「交了四张截图」读成「一张没交」 | 中 | 未修，已绕过并留存原始产物 |
| [ISSUE-02](ISSUE-02-octo-publish-github%20生成的%20workflow%20不可用.md) | `octo publish-github` | 生成的 `.github/workflows/publish-app.yml` 调用了 `hub` 里根本没有的四个 `publisher-*` 子命令，还硬编码了一条本仓库不存在的路径；而 `PUBLISHING.md` 明写「这套东西还不存在，不要加这种 workflow」 | **高** | 未修，已按要求不提交该文件 |
| [ISSUE-03](ISSUE-03-能力门拒绝时同步重入VM.md) | `makepad` `splash_host.rs` | 能力门拒绝时用 `vm.call` **同步重入** VM，和正常路径的异步回执（`splash_host_respond`）不是同一条机制，观察到以 `pop_stack_resolved on empty stack` 收场——一个与「能力没授予」无关的错误 | 中高 | 未修，已绕过 |

---

## 除了报 issue，本轮还往上游补了什么

**语音能力（服务层贡献，不是绕过）**

`my-entry/patches/host-voice.patch`：为官方 `card-host` 新增一整个 `crates/llm-service`，提供 `llm.speech / speak / speaking / listen_start / listen_poll / listen_stop`，Windows 上落到 `makepad-system-speech` 与 `Windows.Media.SpeechRecognition`。

这不是「给应用开小灶」：补丁**没有**改 `app-policy`，也就是**没有**把 `llm` 能力发给商店应用——那会违反官方规定。它做的是官方文档点名要求的事：`HOST-SERVICES.md` L22「a store app that needs something else needs **a new service in the shells (below), not a workaround in the bundle**」。于是本应用在商店宿主上**刻意不声明 `llm`**，把语音当「有则更好」的可选增强；一旦宿主装了这个补丁，语音立刻可用。

本轮在补丁上又加了一层：**未指定音色时挑最自然的那个**（`crates/llm-service/src/voice.rs`），并把推荐的中文神经音色写进注释，便于接入 `edge-tts` 一类云端神经音色时直接对齐命名。

---

## 怎么复核

```bash
# ISSUE-01：重跑一次就复现（需要自建 hub）
hub scan my-entry/morning-brief/bundle --packet build/review.json
python -c "import json;d=json.load(open('build/review.json'));print(d['screenshots']);print(d['listing']['screenshots'])"

# ISSUE-02：两个证据都在仓库里
cat .github/workflows/publish-app.yml      # 用了 publisher-*
hub --help                                 # 没有 publisher-*

# ISSUE-03
sed -n '270,300p' makepad/widgets/src/splash_host.rs   # 同步 vm.call
grep -n "pop_stack_resolved on empty stack" makepad/platform/script/src/thread.rs
```
