# patches —— 官方仓库的本地改动（语音能力靠它）

## 这是什么

`morning-brief` 跑在官方的 **OctoSense App Hub `card-host`** 上。本轮给主编加了语音能力，
但它**不是卡片里几行代码能做到的**：麦克风和扬声器属于宿主，卡片只能通过宿主服务请求。

所以本轮改了官方仓库 `OctoSense-App-Hub` 的两处，补成 `host-voice.patch`：

| 文件 | 改了什么 |
| --- | --- |
| `crates/llm-service/src/voice.rs` | 新增：`llm.speech` / `speak` / `speaking`（TTS + 能力探测）；本轮加了 `pick_voice()`——**没指定音色时自动挑最自然的那个** |
| `crates/llm-service/src/voice/stt.rs` | 新增：`llm.listen_start` / `listen_poll` / `listen_stop`（麦克风会话） |
| `crates/llm-service/src/voice/player.rs` | 新增：PCM 队列（服务渲染，宿主播放） |
| `crates/llm-service/src/lib.rs` | 注册上面 6 个方法 |
| `crates/llm-service/Cargo.toml` | 依赖 `makepad-system-speech`（官方自带，不下模型） |
| `crates/card-host/src/host.rs` | 安装 `cx.audio_output` 播放队列里的 PCM；接 `Event::AudioDevices` |
| `Cargo.toml` / `Cargo.lock` | 把 `crates/llm-service` 加进 workspace |

## 音色：为什么默认不再用引擎的「那个老声音」

系统音色之间的差别很大：Windows 老的 SAPI 音色平得像念说明书，新系统的 `Natural` /
`Neural` 音色自然得多，而 `edge-tts` 那类云端神经音色（`zh-CN-XiaoxiaoNeural`、
`zh-CN-YunxiNeural`、`zh-CN-YunyangNeural`）基本就是「人在念新闻」的听感。

所以 `speak` 的行为改成：**卡片指定 `voice` 就用它；没指定就按一张优先级表挑这台机器上
最自然的那个中文音色**，而不是把 `TtsOptions::default()` 交给引擎碰运气（引擎的默认
往往就是它最老的那个音色）。

优先级表（`voice.rs` 的 `PREFERRED`，按子串匹配，所以同一张表同时覆盖 SAPI、
OneCore 与 edge-tts 的命名）：

```
Natural → Neural → Xiaoxiao → Yunyang → Yunxi → Huihui → Yaoyao
```

配套的工具在本仓库 `tools/voice-edge-tts.py`：

```bash
python tools/voice-edge-tts.py --list        # 列出这台机器能拿到的中文音色（按像人程度排序）
python tools/voice-edge-tts.py --sample      # 用首选音色念一句晨报稿子，落成 mp3 试听
python tools/voice-edge-tts.py --voice zh-CN-YunxiNeural --text "今天的晨报好了。" --out build/a.mp3
```

改完补丁记得跑一次自检（会按 unified diff 的规则逐 hunk 数 +/- 行并对账，`--fix` 可
直接修正头部计数）：

```bash
python .tools/check_patch.py my-entry/patches/host-voice.patch
```

> 说明：`llm-service` 这个 crate 本身也是本机新增的（官方仓库里还没有），
> patch 会**整个 crate 一起创建**，所以队友拿到的是完整的 `llm` 服务（LLM + 语音）。

## 怎么用（在官方仓库里打补丁）

```bash
cd <你的 OctoSense-App-Hub>
git apply <本仓库>/my-entry/patches/host-voice.patch
```

然后重建 card-host：

```powershell
$env:CARGO_TARGET_DIR='C:\rustbuild\octosense-hub'   # 用纯 ASCII 路径！中文路径会 dlltool 失败
$env:TEMP='C:\rustbuild\tmp'; $env:TMP='C:\rustbuild\tmp'
$env:PATH = 'C:\cargo-home\bin;' + (Resolve-Path 'tools-rust\mingw64\bin').Path + ';' + $env:PATH
cd OctoSense-App-Hub
cargo build --release -p octosense-card-host
```

⚠️ **重建前必须先停掉正在运行的 card-host**（否则 Windows 会拒绝覆盖 exe：`拒绝访问。(os error 5)`）。

## 用不到语音也可以不打

卡片对语音是**全降级设计**：宿主没有这些方法时，`llm.speech` 请求失败，
卡片会自动隐藏语音按钮、显示「这台机器没有可用的语音能力，全程打字也算数」，
其余功能（生成、编辑部、头版、阅读页、画像、档案）全部照常。

## 系统前提（Windows）

- TTS：系统自带（本机实测有 Huihui / Yaoyao / Kangkang 三个中文声音），无需安装
- STT：`Windows.Media.SpeechRecognition`。**首次使用需要在系统里打开一次「在线语音识别」**，
  否则会报 `permission denied`。本机通过注册表打开（用户级、可逆）：

```powershell
New-Item -Path 'HKCU:\SOFTWARE\Microsoft\Speech_OneCore\Settings\OnlineSpeechPrivacy' -Force | Out-Null
New-ItemProperty -Path 'HKCU:\SOFTWARE\Microsoft\Speech_OneCore\Settings\OnlineSpeechPrivacy' `
  -Name HasAccepted -PropertyType DWord -Value 1 -Force | Out-Null
```

或者：设置 → 隐私和安全性 → 语音 → 打开「在线语音识别」。
