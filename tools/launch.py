#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""晨报卡 · 启动器（可移植）

做三件事：
  1. 找到运行组件（hub.exe / card-host.exe）——环境变量 → 常见位置 → 仓库相邻目录
  2. 配好 AI 通路（有钥匙就用真模型；没有就降级为规则模式，并说明怎么配）
  3. 启动卡片，弹出窗口

用法：
    python tools/launch.py              # 默认端口 8160
    python tools/launch.py --port 8170  # 换端口
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUNDLE = REPO / "my-entry" / "morning-brief" / "bundle"

# 本地模型转发服务。用**项目内**这一份：它比早先放在 C:\rustbuild\tmp 的那版多了
# MiniMax 适配（摘掉上游不认的 response_format、剥 <think> 草稿），跟着仓库走。
SHIM = REPO / "tools" / "llm_shim.py"
SHIM_PORT = 8791

# MiniMax 的密钥放在仓库之外（C:\rustbuild\tmp\），不进包、不进版本库。
# 它同时供两条路用：
#   · 文本 —— 经上面的本地转发服务（宿主写死的 response_format MiniMax 不认）
#   · 生图 —— 宿主进程自己读 MINIMAX_API_KEY
#            （见 my-entry/patches/host-image-minimax.patch，二进制里已编入）
MINIMAX_KEY_FILE = Path(r"C:\rustbuild\tmp\minimax-key.txt")
MINIMAX_BASE_URL = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
# 实测：M3 最快（5.3s）且剥掉 <think> 后就是干净 JSON；M2/M2.7 都能用但慢 1.5~2s。
MINIMAX_TEXT_MODEL = os.environ.get("MINIMAX_TEXT_MODEL", "MiniMax-M3")

# 咕嘎的软萌音桥：桌面版桌宠用 edge-tts 的 zh-CN-XiaoyiNeural，
# 宿主自带的 Windows 引擎里没有这个音色（本机最像人的是 Huihui，成熟女声）。
# 有桥，卡片里的咕嘎说话就和桌面版一个声音；没有就退系统引擎，不影响其它功能。
VOICE_BRIDGE = REPO / "tools" / "edge_tts_bridge.py"
# 探测本地服务时一律绕过系统代理（沙箱/全局代理会把 127.0.0.1 的探针也劫走）
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_voice_python_cache = []


def find_voice_python():
    """挑一个**真装了 edge_tts + miniaudio** 的 Python，给语音桥用。

    为什么必须挑：宿主起桥时默认执行 `python`（见 model-service/src/voice/edge.rs
    的 python_path()），而 PATH 里第一个 python 往往不是装了库的那个。本机就是
    这个坑 —— 托管 3.13 没有 edge_tts，系统 3.12 有。桥一起来就报
    `No module named 'edge_tts'`，咕嘎被迫退回 Windows 系统引擎，音色立刻跑偏
    （用户反复反馈的「声音和桌宠不一致」就是这条）。

    宿主认 `GUGUA_VOICE_PYTHON` 这个环境变量，所以这里替它选好。
    """
    if _voice_python_cache:
        return _voice_python_cache[0]

    def probe(exe, extra=()):
        try:
            r = subprocess.run([exe, *extra, "-c", "import edge_tts, miniaudio"],
                               capture_output=True, timeout=25)
            return r.returncode == 0
        except Exception:
            return False

    cands = []
    env_py = os.environ.get("GUGUA_VOICE_PYTHON")
    if env_py:
        cands.append((env_py, ()))
    cands.append((sys.executable, ()))
    la = os.environ.get("LOCALAPPDATA", "")
    for ver in ("313", "312", "311", "310"):
        if la:
            cands.append((str(Path(la) / "Programs" / "Python" / f"Python{ver}" / "python.exe"), ()))
        cands.append((rf"C:\Python{ver}\python.exe", ()))
    for name in ("python", "python3"):
        w = shutil.which(name)
        if w:
            cands.append((w, ()))
    cands.append(("py", ("-3",)))

    seen = set()
    for exe, extra in cands:
        key = (exe, extra)
        if key in seen:
            continue
        seen.add(key)
        if extra == () and not Path(exe).is_file() and not shutil.which(exe):
            continue
        if probe(exe, extra):
            _voice_python_cache.append(exe)
            return exe
    _voice_python_cache.append(None)
    return None


def read_minimax_key():
    """MiniMax 官方钥匙（存在仓库之外，不进包、不进版本库）。没有返回 ""。"""
    try:
        if MINIMAX_KEY_FILE.is_file():
            return MINIMAX_KEY_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def say(msg):
    print(msg, flush=True)


def has_marker(path, marker):
    """二进制里是否含某个能力标记。

    card-host 有多个历史构建，早期的那个不认识 `model` 能力：用它启动，
    整个卡片会被拒（`refused: unknown capability "model"`）而只剩空白。
    这个坑踩过，所以选宿主时顺手核一下标记，选错了就直接跳过。
    """
    try:
        return marker.encode() in Path(path).read_bytes()
    except Exception:
        return True  # 读不动就别拦，交给运行时报错


def find_bin(name, env_var, marker=None):
    """按优先级找可执行文件。marker 给了就要求二进制里含该标记。"""
    # 1) 环境变量
    v = os.environ.get(env_var)
    if v and Path(v).is_file() and (marker is None or has_marker(v, marker)):
        return Path(v)
    # 2) 常见安装位置（新构建在前；不认 model 的旧构建会被 marker 挡掉）
    candidates = [
        Path(r"D:\morning-brief\.local-tools\target\release") / name,
        Path(r"C:\rustbuild\octosense-hub\release") / name,
        Path(r"C:\rustbuild\octosense-hub\x86_64-pc-windows-gnu\release") / name,
    ]
    for c in candidates:
        if c.is_file() and (marker is None or has_marker(c, marker)):
            return c
    # 3) 仓库相邻：<repo>/../OctoSense-App-Hub/target/release/<name>
    for base in (REPO.parent, REPO):
        for sub in ("OctoSense-App-Hub/target/release", "OctoSense-App-Hub/target/debug"):
            c = base / sub / name
            if c.is_file() and (marker is None or has_marker(c, marker)):
                return c
    return None


def find_octo():
    """官方 octo 驱动脚本。"""
    for base in (REPO.parent, REPO):
        for b in (base, Path(r"D:\morning-brief"), Path(r"D:\morning-brief\OctoScript-App-Design-Flow")):
            if (b / "OctoScript-App-Design-Flow" / "tools" / "octo").is_file():
                return b / "OctoScript-App-Design-Flow" / "tools" / "octo"
            if (b / "tools" / "octo").is_file():
                return b / "tools" / "octo"
        c = base / "OctoScript-App-Design-Flow" / "tools" / "octo"
        if c.is_file():
            return c
    return None


def read_minimax_key():
    """MiniMax 官方钥匙（存在仓库之外，不进包、不进版本库）。没有返回 ""。"""
    try:
        if MINIMAX_KEY_FILE.is_file():
            return MINIMAX_KEY_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def start_shim(upstream, key, force_model, min_tokens=None):
    """起本地转发服务并等它就绪。返回 True/False。

    为什么非要有这一层：宿主只会说一种话 —— OpenAI 兼容，且**固定**带
    `response_format: {"type":"json_object"}`（见 crates/model-service/src/lib.rs）。
    MiniMax 直接把这个字段拒掉（400 unknown response_format type 'json_object'），
    而且 M 系是推理模型、正文裹着 <think>…</think>。所以在中间垫一层做归一化：
    摘字段、抬 max_tokens、剥 <think>、必要时从文本里抠 JSON。

    已在跑的那个可能是旧配置（上游/改写规则都不一样），一律先收掉再起。
    """
    old = port_owner(SHIM_PORT)
    if old:
        subprocess.run(["taskkill", "/F", "/PID", str(old)], capture_output=True, timeout=10)
        time.sleep(0.5)
    e = dict(os.environ)
    e["SHIM_UPSTREAM"] = upstream
    e["SHIM_KEY"] = key
    e["SHIM_PORT"] = str(SHIM_PORT)
    e["SHIM_MODEL"] = force_model
    e["SHIM_FORCE_MODEL"] = force_model
    if min_tokens:
        e["SHIM_MIN_TOKENS"] = str(min_tokens)
    # ⚠️ 必须脱离控制台。
    # 转发服务原来是个普通子进程，和 launch.py 共用同一个控制台 —— 用户
    # 双击 .cmd 跑完之后关掉那个黑窗口（或 cmd 自己退出），转发服务会收到
    # 控制台关闭事件跟着死掉。卡片那边只显示「没接上模型」，而端口 8791
    # 早就没人听了（2026-10-13 实测：正常双击打开，8791 无监听）。
    flags = 0
    if os.name == "nt":
        flags = 0x00000008 | 0x00000200        # DETACHED_PROCESS | NEW_PROCESS_GROUP
    logf = None
    try:
        logf = open(Path(os.environ.get("TEMP", ".")) / "morning-brief-shim.log", "a",
                    encoding="utf-8", errors="replace")
    except Exception:
        logf = subprocess.DEVNULL
    subprocess.Popen([sys.executable, str(SHIM)],
                     env=e, stdout=logf, stderr=subprocess.STDOUT,
                     creationflags=flags, close_fds=True)
    for _ in range(20):          # 最多等 4 秒
        time.sleep(0.2)
        try:
            with _opener.open(f"http://127.0.0.1:{SHIM_PORT}/v1/models", timeout=2):
                return True
        except Exception:
            continue
    return False


def model_env():
    """返回 (环境变量字典, 说明文字)。

    应用只走官方的 model.complete，钥匙由宿主持有、应用看不到，
    所以这里配的是**宿主**的环境变量（OCTOS_MODEL_*），不是应用的。

    AI 通路的优先级：
      1. 已有 OCTOS_MODEL_KEY / OCTOS_LLM_KEY（用户自己配的）
      2. MiniMax 官方钥匙（仓库外的钥匙文件）—— 走本地转发服务归一化后转发
      3. 本地转发服务（走自己的网关，钥匙文件另存）
      4. 通用云钥匙兜底（余额用尽会 402，很难查）
      5. 都没有 → 规则模式（应用自动降级，不崩）
    """
    env = {}

    # ① 用户显式给"卡片"配的钥匙 —— OCTOS_* 是这张卡片专用的，
    #    出现它就代表明确意图，优先尊重。
    explicit = os.environ.get("OCTOS_MODEL_KEY") or os.environ.get("OCTOS_LLM_KEY")
    if explicit:
        env["OCTOS_MODEL_KEY"] = explicit
        if os.environ.get("OCTOS_MODEL_BASE_URL"):
            env["OCTOS_MODEL_BASE_URL"] = os.environ["OCTOS_MODEL_BASE_URL"]
        return env, "使用你显式配置的模型钥匙"

    # ② MiniMax 官方钥匙 —— 现在的首选（实测可用、有余额）。
    #    宿主写死的 response_format 会被 MiniMax 拒，必须过本地转发服务。
    mm_key = read_minimax_key()
    if SHIM.is_file() and mm_key:
        if start_shim(MINIMAX_BASE_URL, mm_key, MINIMAX_TEXT_MODEL, min_tokens=6000):
            env["OCTOS_MODEL_BASE_URL"] = f"http://127.0.0.1:{SHIM_PORT}/v1"
            env["OCTOS_MODEL_KEY"] = mm_key
            env["OCTOS_MODEL_FAST"] = MINIMAX_TEXT_MODEL
            env["OCTOS_MODEL_STRONG"] = MINIMAX_TEXT_MODEL
            return env, f"MiniMax 官方钥匙（{MINIMAX_TEXT_MODEL}，经本地转发服务归一化）"

    # ③ 本地转发服务（走自己的网关）。⚠️ 必须排在 SILICONFLOW_API_KEY 这类
    #    "通用云钥匙"**前面**：原来顺序反了，只要环境里恰好有个 SILICONFLOW_API_KEY，
    #    这一层就永远轮不到，卡片被甩去直连硅基流动 —— 余额一耗尽模型全线 402，
    #    用户看到的就是"没接上模型 / no model"（2026-10-12 实例）。
    shim_key_file = Path(r"C:\rustbuild\tmp\shim-key.txt")
    if SHIM.is_file() and shim_key_file.is_file():
        shim_key = shim_key_file.read_text(encoding="utf-8").strip()
        if shim_key and start_shim(
                os.environ.get("SHIM_UPSTREAM", "https://opencode.ai/zen/go/v1"),
                shim_key, os.environ.get("SHIM_FORCE_MODEL", "kimi-k2.6")):
            env["OCTOS_MODEL_BASE_URL"] = f"http://127.0.0.1:{SHIM_PORT}/v1"
            env["OCTOS_MODEL_KEY"] = shim_key
            env["OCTOS_MODEL_FAST"] = os.environ.get("OCTOS_MODEL_FAST", "deepseek-ai/DeepSeek-V4-Flash")
            env["OCTOS_MODEL_STRONG"] = os.environ.get("OCTOS_MODEL_STRONG", "deepseek-ai/DeepSeek-V4-Pro")
            return env, "本地转发服务（走你自己的网关；模型名与 JSON 都由它归一化）"

    # ④ 通用云钥匙兜底（余额用尽会 402，卡片只会说"没接上模型"，很难查）
    key = os.environ.get("SILICONFLOW_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if key:
        env["OCTOS_MODEL_KEY"] = key
        if os.environ.get("OCTOS_MODEL_BASE_URL"):
            env["OCTOS_MODEL_BASE_URL"] = os.environ["OCTOS_MODEL_BASE_URL"]
        return env, "环境里的通用云钥匙（余额用尽会 402，慎用）"

    return env, "规则模式（未配置模型钥匙：主编挑选/编辑部评审将自动降级，其余功能不受影响）"


def port_owner(port):
    """返回正在 LISTEN 该端口的 PID；没有就 None。"""
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=10).stdout
    except Exception:
        return None
    needle = f":{port}"
    for line in out.splitlines():
        p = line.split()
        if len(p) >= 5 and p[0].upper() == "TCP" and p[3].upper() == "LISTENING" and p[1].endswith(needle):
            try:
                return int(p[4])
            except ValueError:
                return None
    return None


def image_name(pid):
    """进程名（小写）。查不到返回空串。"""
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=10).stdout
    except Exception:
        return ""
    first = out.strip().splitlines()[0] if out.strip() else ""
    return first.split(",")[0].strip('"').lower()


def pick_port(preferred):
    """挑一个真能用的端口。

    两种占用要分开处理：
      · 被**本作品自己**残留的 card-host 占着 —— 收掉它。这类残留从不优雅退出
        （实测 %TEMP%\\makepad-remote 下堆了 279 个 card-host.exe-<pid> 孤儿目录），
        而且卡片本来就该是单例，留着它只会让下一次双击撞「端口被占用」。
      · 被别的程序占着 —— 老老实实往后顺延，不动别人的进程。

    返回 (端口, 说明或 None)；彻底找不到返回 (None, None)。
    """
    port = preferred
    for _ in range(100):
        pid = port_owner(port)
        if pid is None:
            return port, None
        if image_name(pid).startswith("card-host"):
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=10)
            time.sleep(0.8)
            if port_owner(port) is None:
                return port, f"收掉了上一次残留的卡片进程（pid {pid}，它一直占着 {port}）"
        port += 1
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8160)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--no-watchdog", action="store_true",
                    help="不起看门狗（看门狗自己重启卡片时会带上这个，避免套娃）")
    ap.add_argument("--shim-only", action="store_true",
                    help="只把模型转发服务拉起来就退出（看门狗用它把掉线的转发服务救回来）")
    ap.add_argument("--bundle", type=str, default="",
                    help="指定作品包目录（默认 my-entry/morning-brief/bundle；"
                         "失败状态演示用 my-entry/demo-partial/bundle）")
    args = ap.parse_args()

    if args.shim_only:
        key = read_minimax_key()
        if not SHIM.is_file() or not key:
            return 1
        ok = start_shim(MINIMAX_BASE_URL, key, MINIMAX_TEXT_MODEL, min_tokens=6000)
        return 0 if ok else 1

    say("=" * 62)
    say("  晨报卡 Morning Brief — 正在启动")
    say("=" * 62)

    bundle = Path(args.bundle).resolve() if args.bundle else BUNDLE
    if not bundle.is_dir():
        say(f"[错误] 找不到作品包：{bundle}")
        return 1

    octo = find_octo()
    if not octo:
        say("[错误] 找不到官方驱动 tools/octo。")
        say("       请先按 07_官方仓库下载说明.md 下载 OctoScript-App-Design-Flow。")
        return 1

    hub = find_bin("hub.exe", "OCTO_HUB")
    card_host = find_bin("card-host.exe", "OCTO_CARD_HOST")
    if not hub or not card_host:
        say("[错误] 找不到运行组件 hub.exe / card-host.exe。")
        say("       请先按 07_官方仓库下载说明.md 下载并构建 OctoSense-App-Hub。")
        say("       注意：card-host 必须是认识 `model` 能力的构建（二进制里含 model.complete），")
        say("       旧构建会让卡片以「unknown capability: model」被拒而只剩空白。")
        say(f"       也可以手动设置环境变量 OCTO_HUB / OCTO_CARD_HOST 指向它们。")
        return 1

    say(f"  驱动     {octo}")
    say(f"  宿主     {card_host}")
    env = dict(os.environ)
    env["OCTO_HUB"] = str(hub)
    env["OCTO_CARD_HOST"] = str(card_host)
    # NOTE: the App Hub checkout lives INSIDE this repo, not next to it.
    # (REPO.parent / "OctoSense-App-Hub" pointed at a directory that does
    #  not exist; harmless for `octo run` but wrong for kit/beauty flows.)
    env["OCTOSENSE_APP_HUB"] = str(REPO / "OctoSense-App-Hub")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    extra, note = model_env()
    env.update(extra)
    say(f"  AI 通路  {note}")

    # 生图：宿主进程读 MINIMAX_API_KEY（补丁见 my-entry/patches/host-image-minimax.patch，
    # 后端已编入 card-host.exe）。带上 key，卡片里的 sys.photo 就先请 MiniMax 出图；
    # 不带就逐字节退回 pollinations（现在只剩 sana，质量不稳）。
    mm_key = read_minimax_key()
    if mm_key:
        env["MINIMAX_API_KEY"] = mm_key
        if not os.environ.get("MINIMAX_IMAGE_MODEL"):
            env["MINIMAX_IMAGE_MODEL"] = "image-01"
        say(f"  生图     MiniMax {env['MINIMAX_IMAGE_MODEL']}（16:9）")
    else:
        say("  生图     pollinations 兜底（未找到 MiniMax 钥匙）")

    # 咕嘎的嗓子：桥在就给宿主指路（edge-tts 直连偶发被重置，桥自己读系统代理）
    if VOICE_BRIDGE.is_file():
        env["GUGUA_VOICE_BRIDGE"] = str(VOICE_BRIDGE)
        # 关键一步：宿主起桥默认执行 `python`，而 PATH 里第一个 python 常常
        # 不是装了 edge_tts 的那个 → 桥一启动就 "No module named 'edge_tts'"，
        # 咕嘎被退回系统引擎、音色跑偏。宿主认 GUGUA_VOICE_PYTHON，这里选好。
        vp = find_voice_python()
        if vp:
            env["GUGUA_VOICE_PYTHON"] = vp
            say(f"  咕嘎嗓子  edge-tts 软萌音（解释器 {vp}）")
        else:
            say("  咕嘎嗓子  桥在，但没找到装了 edge_tts 的 Python —— 会退回系统引擎")
    else:
        say("  咕嘎嗓子  未找到 tools/edge_tts_bridge.py，用系统语音引擎")

    # 给卡片留一张字条：edge 桥已配置。开屏 CG 的配乐靠它决定要不要点播
    # （开机头几秒的宿主往返不可靠，探嗓子的结果会静默丢失，字条不依赖往返）。
    # 每次启动都重写：桥没了就把旧字条删掉，卡片的降级才不会踏空。
    app_data = Path(os.environ.get("TEMP", ".")) / "morning-brief-state"
    if bundle != BUNDLE:
        # 指定了别的作品包（如失败状态演示）：用独立存档目录，别把真实晨报的档案写花。
        app_data = Path(os.environ.get("TEMP", ".")) / "morning-brief-demo-state"
    bridge_flag = app_data / "morning-brief" / "voice-bridge.on"
    try:
        if env.get("GUGUA_VOICE_BRIDGE"):
            bridge_flag.parent.mkdir(parents=True, exist_ok=True)
            bridge_flag.write_text("edge-tts bridge configured by launch.py\n", encoding="utf-8")
        elif bridge_flag.is_file():
            bridge_flag.unlink()
    except Exception as e:
        say(f"  咕嘎嗓子  字条没写成（{e}）；CG 配乐会退回探嗓子路径")
    say("")

    # 端口自愈：上一次的卡片要是没退干净，会一直占着端口，让下一次双击「没反应」。
    port, port_note = pick_port(args.port)
    if port is None:
        say(f"[错误] {args.port} 往后 100 个端口都被占用，请手动指定：--port 9000")
        return 1
    if port_note:
        say(f"  端口     {port_note}")
    elif port != args.port:
        say(f"  端口     {args.port} 被其它程序占用，改用 {port}")

    cmd = [sys.executable, "-u", str(octo), "run", str(bundle),
           "--port", str(port), "--timeout", str(args.timeout),
           "--detach", "--app-data", str(app_data)]

    # 开屏配乐：B 版《木琴纸韵》。由启动器在卡片起窗前放 —— 卡片侧的宿主请求
    # 在开机窗口里时灵时不灵（实测边界在 0~12 秒之间飘），而这边一声 PlaySound
    # 是确定的。6.8 秒放完就退；字条改成 launcher-plays，卡片看到就不再自己点播。
    # 配乐在 bundle 之外（hub 准入不许 bundle 里出现音频扩展名）。
    music = bundle.parent / "media" / "b-music.wav"
    if env.get("GUGUA_VOICE_BRIDGE") and music.is_file():
        try:
            flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0
            subprocess.Popen(
                [sys.executable, "-c",
                 "import winsound, time\n"
                 "winsound.PlaySound(r'%s', winsound.SND_FILENAME | winsound.SND_ASYNC)\n"
                 "time.sleep(7.5)\n" % str(music)],
                creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True)
            if bridge_flag.is_file():
                bridge_flag.write_text("launcher-plays\n", encoding="utf-8")
            say("  开场配乐  B 版《木琴纸韵》（启动器直接播，卡片不再重复点播）")
        except Exception as e:
            say(f"  开场配乐  没放成（{e}）；交给卡片自己点播")
    say("")
    say("  正在启动（首次约 5–15 秒）…")
    say(f"  窗口标题：Card host [remote]　端口：{port}")
    say("-" * 62)
    r = subprocess.run(cmd, env=env, cwd=str(REPO))
    if r.returncode != 0:
        say(f"\n[错误] 启动失败（退出码 {r.returncode}）。")
        say("       常见原因：宿主/驱动没找到，或端口被别的程序占着。")
        say("       换个端口再试：python tools/launch.py --port 8170")
        return r.returncode

    # 看门狗：宿主偶发会掉进「逻辑活着、一帧画不出来」的白屏态，只有重启能救。
    # 它在旁边盯着窗口像素，真白了就自动把卡片拉起来（细节见 card_watchdog.py）。
    WD = REPO / "tools" / "card_watchdog.py"
    pidfile = Path(os.environ.get("TEMP", ".")) / f"morning-brief-watchdog-{port}.pid"
    if args.no_watchdog or not WD.is_file():
        pass
    else:
        alive = False
        try:
            if pidfile.is_file():
                old_pid = int(pidfile.read_text(encoding="utf-8").strip() or 0)
                out = subprocess.run(["tasklist", "/FI", f"PID eq {old_pid}", "/NH"],
                                     capture_output=True, text=True, errors="replace",
                                     timeout=10).stdout
                alive = str(old_pid) in out
        except Exception:
            alive = False
        if alive:
            say("  看门狗   已在运行（同一个端口只留一只）")
        else:
            wd_flags = 0
            if os.name == "nt":
                wd_flags = 0x00000008 | 0x00000200      # DETACHED_PROCESS|NEW_PROCESS_GROUP
            try:
                subprocess.Popen([sys.executable, str(WD), "--port", str(port), "--interval", "8"],
                                 cwd=str(REPO), creationflags=wd_flags,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                say("  看门狗   已上岗（白屏会自动重启卡片）")
            except Exception as e:
                say(f"  看门狗   没起来：{e}")

    say("")
    say("=" * 62)
    say("  已启动。用法：")
    say("    1. 勾选主题（或直接写一句你想看什么），点「生成晨报」")
    say("    2. 主编会先问一句 —— 选 A 或 B（也可点「你定，不用问」）")
    say("    3. **点「批准并取数」之前不会联网**；点「暂不」则什么都不发生")
    say("    4. 出报后：结果页看头版与淘汰率，点任意条目进阅读页")
    say("    5. 右下角「AI 主编」可以对话，让它替你操作")
    say("    关掉这个黑窗口不影响卡片（它已经独立运行）；关掉卡片窗口才会退出。")
    say("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
