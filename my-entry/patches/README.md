# patches —— 对官方仓库的改动，以及我们对上游的回报

本目录有三类东西，别混着看：

| 文件 | 是什么 | 现在的状态 |
| --- | --- | --- |
| `host-services.patch` | 给官方 `OctoSense-App-Hub` 加的**两个宿主服务**（`llm` = 模型 + 语音，`model` = 文本补全），含 `voice/edge.rs`：咕嘎的 edge-tts 软萌音桥 | **本轮 canonical**，已在 `a15580c` 上验证可干净应用 |
| `host-image-minimax.patch` | 给官方 `makepad` 改的**生图后端**（`sys.photo` 走 MiniMax，回落 pollinations） | **本轮 canonical**，已在本机 `db4691d` 上验证可干净应用 |
| `host-font-monospace-cjk.patch` | 给官方 `makepad` 修的**等宽字体缺 CJK 兜底**（`theme.font_code` 的中文渲染成豆腐块：页签「新报」、报头期号） | **本轮 canonical**，本机重建 card-host 后验证（细节见 `UPSTREAM-font-monospace.md`） |
| `host-voice.patch` / `host-voice-card-host.patch` | 初赛那一轮提交的语音补丁 | **历史存档**：它的 `llm-service` 内容已被 `host-services.patch` 完整吸收；它对更早的上游 HEAD，**今天已经不能直接 `git apply`** |
| `UPSTREAM-net-headers.md` | 报给上游的缺陷：`net.http_request` 拒绝保留头却不说明是哪个头 | 已定稿 |
| `UPSTREAM-regex-p.md` | 报给上游的缺陷：`regex()` 不支持 `\p{...}`，且失败方式是「静默吞掉调用方」 | 已定稿 |
| `UPSTREAM-font-monospace.md` | 报给上游的缺陷：International 字体集的等宽链只挂 LiberationMono，中文等宽整段豆腐 | 已定稿（含补丁与验证） |

## 为什么会有 `host-services.patch`

`morning-brief` 跑在官方的 **reference `card-host`** 上。本轮它要用两样东西，
而 reference `card-host` **两样都不提供**（它注册的服务是空的）：

| 能力 | 卡片怎么用 | 谁提供 |
| --- | --- | --- |
| `model` | `host.request("model.complete", …)` 取一段结构化答复 | `crates/model-service` |
| `llm` | `llm.speech` / `speak` / `listening`（朗读晨报、听主编说话） | `crates/llm-service` |

官方 `HOST-SERVICES.md` L22 把话讲得很清楚：

> a store app that needs something else needs **a new service in the shells, not a workaround in the bundle**

**换成"补丁给宿主加服务"，正是官方指定的做法。** 所以这两个 crate 是**上游生态贡献**，
不是卡片里的绕路。

补丁做了这些事（12 个文件，13 个 hunk）：

| 文件 | 改了什么 |
| --- | --- |
| `Cargo.toml` | 把 `crates/llm-service`、`crates/model-service` 加进 workspace |
| `crates/card-host/Cargo.toml` | 加上两个 crate 的 path 依赖 |
| `crates/card-host/src/host.rs` | `register_host_services()` + `install_audio_output()`；挂载时注册、收 `Event::AudioDevices` |
| `crates/llm-service/**` | 新增：`llm.speech` / `speak` / `speaking` / `listen_start` / `listen_poll` / `listen_stop`；音色优选；PCM 队列 |
| `crates/model-service/**` | 新增：`model.complete`（只认 5 个键，回复固定形状；`<think>` 草稿剥离） |

### 一个刻意的设计：卡片**不声明** `llm`

卡片对语音是**全降级**的：宿主没有这些方法时，`llm.speech` 请求失败，
卡片自动隐藏语音按钮、显示「这台机器没有可用的语音能力，全程打字也算数」，
其余功能（生成、编辑部、头版、阅读页、画像、档案、核验台）一律照常。

所以 `manifest.json` 的 `capabilities` **只有 `storage / net / images / model`**。
理由写在 `HOST-SERVICES.md` 里：商店宿主上语音服务不存在，
声明了反而会被门拒绝 —— 不声明、能用到就用，才是这份能力表的本意。

## 怎么用

```bash
# 1) 宿主服务（两个 crate + card-host 接线）
cd <你的 OctoSense-App-Hub>          # 本补丁基于 a15580c
git apply <本仓库>/my-entry/patches/host-services.patch
cargo build --release -p octosense-card-host
#   补丁不含 Cargo.lock：第一次 build 会自己把新 crate 的依赖解出来。

# 2) 生图后端（可选；不打则退回 pollinations）
cd <你的 makepad>                    # 本补丁基于 db4691d
git apply <本仓库>/my-entry/patches/host-image-minimax.patch
```

⚠️ **重建前必须先停掉正在运行的 card-host**（否则 Windows 会拒绝覆盖 exe：`拒绝访问。(os error 5)`）。

```powershell
$env:CARGO_TARGET_DIR='C:\rustbuild\octosense-hub'   # 用纯 ASCII 路径！中文路径会 dlltool 失败
$env:TEMP='C:\rustbuild\tmp'; $env:TMP='C:\rustbuild\tmp'
$env:PATH = 'C:\cargo-home\bin;' + (Resolve-Path 'tools-rust\mingw64\bin').Path + ';' + $env:PATH
cd OctoSense-App-Hub
cargo build --release -p octosense-card-host --bin card-host
```

### 补丁怎么自检

```bash
# 逐 hunk 数 +/- 行并对账（--fix 可直接修正头部计数）
python .tools/check_patch.py my-entry/patches/host-services.patch
python .tools/check_patch.py my-entry/patches/host-image-minimax.patch
```

本轮两个补丁都用**临时 worktree + `git apply --check`** 真验过：

```bash
git clone <OctoSense-App-Hub> /tmp/hub-check && cd /tmp/hub-check
git config core.autocrlf false && git rm --cached -rq . && git reset --hard -q   # 切成 LF 工作树
git apply --check <本仓库>/my-entry/patches/host-services.patch                 # → 干净通过
```

> 为什么要多那一步行尾处理：这个仓库在 Windows 上默认按 CRLF 检出，
> 而补丁是 LF 的。`git status` 会说「干净」（因为 git 内部做了归一），
> 但 `git apply` 是逐字节比对的 —— 于是会报一堆 `patch does not apply`。
> 这不是补丁坏了，是工作树的行尾不是仓库里的行尾。

## MiniMax 生图后端做了什么

`makepad/widgets/src/splash.rs` 里 `sys.photo(q)` 原来硬编码
`https://image.pollinations.ai/prompt/{enc}?…&model=flux`。两个问题：

1. **`model=flux` 已经下线**——现在 `GET image.pollinations.ai/models` 只剩 `sana`，
   这是「生图太拉」的真凶；
2. 应用侧改不动后端（`makepad/` 不在应用仓库里）。

补丁的做法：`sys.photo` 先看环境变量 `MINIMAX_API_KEY`。

* 有 key → 后台线程打 `POST https://api.minimaxi.com/v1/image_generation`，
  **返回的是公开 https 的阿里云 OSS 带签名地址**，交给卡片显示；
  第一次调用返回空串（还在画），之后命中缓存就返回地址 —— 卡片侧轮询取图。
* 没有 key → 一行不改，照旧退回落 pollinations。

这样做的关键理由：**应用在结构上无法持有密钥**（受管控 isolate 里密码框是 inert 的，
用户没法输入；`host.request` 只能调宿主已注册的服务）。
key 只在宿主进程的环境变量里、只在调用那一刻用掉一次，**不必进包、也不必进仓库**。

没打这个补丁的机器上，`MINIMAX_API_KEY` 设了也没用，生图依旧走 pollinations —— 不会坏。
