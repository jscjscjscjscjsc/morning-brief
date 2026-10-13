#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""咕嘎的软萌音桥 · edge-tts 合成，写给晨报卡的宿主进程用。

为什么需要这个桥：
    晨报卡的桌面版桌宠用的是 edge-tts 的 `zh-CN-XiaoyiNeural`（软萌少女音）
    + 提高音调；而卡片宿主的语音只走 Windows 自带引擎（本机最像人的是
    Huihui 的 SAPI 音，离"人声"很远）。宿主进程里没有 Python 运行时，
    所以由它按需拉起本脚本：喂一段文本，换回一段 16-bit 单声道 PCM。

协议（宿主侧照抄即可）：
    启动：python edge_tts_bridge.py --serve
    宿主写一行 JSON 到 stdin，桥回一行 JSON 到 stdout：
        请求  {"text": "...", "voice": "zh-CN-XiaoyiNeural", "rate": "+14%", "pitch": "+16Hz"}
        成功  {"ok": true, "sample_rate": 24000, "samples_b64": "...", "seconds": 3.2, "cached": false}
        失败  {"ok": false, "error": "..."}
    PCM 是 s16le 单声道。合成结果按 (text,voice,rate,pitch) 的哈希缓存到
    临时目录，同一句话第二次说是零网络开销。

为什么走「常驻进程 + 行 JSON」而不是一次一进程：
   边缘首句合成约 1~2 秒，拉起一次 Python 解释器还要 ~0.3 秒；
   常驻可以把解释器启动只付一次，之后每句只有网络合成的时间。
"""
import argparse
import asyncio
import base64
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time

VOICE_DEFAULT = "zh-CN-XiaoyiNeural"   # 桌面版同款软萌音
RATE_DEFAULT = "+14%"
PITCH_DEFAULT = "+16Hz"
CACHE_DIR = os.path.join(tempfile.gettempdir(), "guga-edge-tts-cache")
CACHE_MAX = 240
CACHE_TTL = 7 * 24 * 3600

_voice = VOICE_DEFAULT

# 开屏 CG 配乐的哨兵文本：卡片说这句话 = 点播 B 版《木琴纸韵》。
# 用带方括号的固定串而不是「真实句子」，是为了跟人话天然不撞车。
CG_BGM_MARKER = "[CG-BGM]"
# 配乐放在 bundle 之外：hub 的结构性准入（app-hub/src/gate.rs）只放行
# card/json/l0/octoscript/splash/svg/png/jpg/jpeg/webp/ttf/otf/txt/md ——
# 任何音频扩展名都会被拒收。它只服务桌面版的开屏配乐，不进作品包。
_CG_BGM_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "my-entry", "morning-brief", "media", "b-music.wav")
_cg_bgm_cache = None


def _cg_bgm_offset(text):
    """哨兵文本 -> 起始秒（None = 不是点播）。支持 [CG-BGM] 与 [CG-BGM:4.6]。"""
    if text == CG_BGM_MARKER:
        return 0.0
    if text.startswith("[CG-BGM:") and text.endswith("]"):
        try:
            return float(text[len("[CG-BGM:"):-1])
        except ValueError:
            return None
    return None


def _cg_bgm(from_sec=0.0):
    """读 bundle 里的配乐 wav，转成 24k 单声道 s16 的原始采样。

    只在第一次读盘，之后常驻内存 —— CG 每次开机都要用，且不该再进一次网络。
    `from_sec` 支持「从第几秒起的后半段」（落点对齐用）。
    文件缺失 / 读不动时抛错，宿主会照常退回系统引擎（卡片侧无感）。
    """
    global _cg_bgm_cache
    if _cg_bgm_cache is None:
        import wave
        with wave.open(_CG_BGM_PATH, "rb") as wf:
            if wf.getsampwidth() != 2:
                raise RuntimeError("cg bgm wav is not s16")
            raw = wf.readframes(wf.getnframes())
            sr = wf.getframerate()
            ch = wf.getnframes()
        if ch <= 0:
            raise RuntimeError("cg bgm wav is empty")
        _cg_bgm_cache = (raw, sr)
    raw, sr = _cg_bgm_cache
    if from_sec > 0.0:
        start = int(from_sec * sr) * 2
        if start >= len(raw):
            raise RuntimeError("cg bgm offset beyond the track")
        raw = raw[start:]
    return raw, sr, False


def _has_deps():
    """edge_tts + miniaudio 都在才算这个解释器能用。"""
    try:
        import edge_tts   # noqa: F401
        import miniaudio  # noqa: F401
        return True
    except Exception:
        return False


def _better_pythons():
    """可能装了库的解释器，按可能性排序。"""
    import shutil
    yield sys.executable
    la = os.environ.get("LOCALAPPDATA", "")
    for ver in ("313", "312", "311", "310"):
        if la:
            yield os.path.join(la, "Programs", "Python", "Python" + ver, "python.exe")
        yield "C:\\Python" + ver + "\\python.exe"
    for name in ("python", "python3"):
        w = shutil.which(name)
        if w:
            yield w


def reexec_if_needed():
    """当前解释器没装库时，就地换成装了的那个。

    为什么需要：宿主起桥时执行的是 `python`（PATH 里第一个），而它不一定装了
    edge_tts —— 本机托管 3.13 就没装，桥一起来就 "No module named 'edge_tts'"，
    咕嘎只能退回系统引擎。launch.py 会用 GUGUA_VOICE_PYTHON 指定解释器，
    这里再兜一层：不管谁拉起它，只要换得到能用的解释器，就自己换过去。
    """
    if _has_deps():
        return False
    if os.environ.get("GUGA_VOICE_REEXEC") == "1":
        return False                      # 防无限重入
    me = os.path.abspath(__file__)
    for exe in _better_pythons():
        try:
            if not os.path.isfile(exe):
                continue
            if os.path.abspath(exe).lower() == os.path.abspath(sys.executable).lower():
                continue
            r = subprocess.run([exe, "-c", "import edge_tts, miniaudio"],
                               capture_output=True, timeout=25)
            if r.returncode != 0:
                continue
        except Exception:
            continue
        env = dict(os.environ)
        env["GUGA_VOICE_REEXEC"] = "1"
        try:
            sys.stderr.write("[guga-voice-bridge] re-exec -> %s\n" % exe)
            sys.stderr.flush()
            os.execve(exe, [exe, me, *sys.argv[1:]], env)
        except Exception:
            continue
    return False


def _load_asr():  # pragma: no cover - 兼容旧名
    pass


def _cache_path(key):
    return os.path.join(CACHE_DIR, key + ".pcm.json")


def _cache_get(key):
    p = _cache_path(key)
    try:
        if not os.path.exists(p):
            return None
        if time.time() - os.path.getmtime(p) > CACHE_TTL:
            os.remove(p)
            return None
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _cache_put(key, value):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        files = []
        for name in os.listdir(CACHE_DIR):
            fp = os.path.join(CACHE_DIR, name)
            try:
                files.append((os.path.getmtime(fp), fp))
            except OSError:
                pass
        if len(files) >= CACHE_MAX:
            files.sort()
            for _, fp in files[: len(files) - CACHE_MAX + 1]:
                try:
                    os.remove(fp)
                except OSError:
                    pass
        with open(_cache_path(key), "w", encoding="utf-8") as f:
            json.dump(value, f)
    except Exception:
        pass


def _is_loopback(url):
    """是不是指向本机的代理。"""
    u = (url or "").lower()
    return ("127.0.0.1" in u) or ("localhost" in u) or ("[::1]" in u)


def system_proxy():
    """读 Windows 的系统代理（HKCU Internet Settings）。

    为什么需要：edge-tts 打的是 speech.platform.bing.com，在部分网络下
    IPv4 直连会被重置（TLS handshake 阶段 connection reset）；系统里已经
    配好的本地代理能一路通到 HTTP 层。桥优先用 EDGE_TTS_PROXY 环境变量，
    没配就自动读系统代理；都没有就直连（在能直连的网络里同样工作）。

    ⚠️ 但**本机回环地址上的代理要跳过**：开发/沙箱环境常把 HTTPS_PROXY 指向
    127.0.0.1 上的一个临时代理，它会把到 bing 的连接掐断
    （实测 `Server disconnected` / `Cannot connect to host`）。那种代理是
    环境残留，不是用户配的；用户真配的代理（如 Clash 的 127.0.0.1:7890）
    会写在注册表里，下面那段照样读得到。EDGE_TTS_PROXY 是这个变量的显式
    指定，无条件尊重。
    """
    env = os.environ.get("EDGE_TTS_PROXY")
    if env:
        return env
    for k in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        v = os.environ.get(k)
        if v and not _is_loopback(v):
            return v
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
        if enable:
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
            if server:
                if not server.startswith("http"):
                    server = "http://" + server
                return server
    except Exception:
        pass
    return None


async def _synth_mp3(text, voice, rate, pitch, proxy=None):
    import edge_tts
    kw = {}
    if proxy:
        kw["proxy"] = proxy
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch,
                                       volume="+0%", **kw)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


def _mp3_to_pcm(mp3_bytes):
    """mp3 -> (samples list[int16], sample_rate)。用 miniaudio 解码。"""
    import miniaudio
    decoded = miniaudio.decode(mp3_bytes, output_format=miniaudio.SampleFormat.SIGNED16,
                               nchannels=1, sample_rate=24000)
    return list(decoded.samples), decoded.sample_rate


def synth(text, voice, rate, pitch, use_cache=True):
    """同步合成一段，返回 (pcm_s16le_bytes, sample_rate, cached)。"""
    # 开屏 CG 的配乐：卡片用一句哨兵文本走同一条嗓子通路点播 ——
    # 宿主只认「Speak」，卡片也只需要一句「说话」，B 版配乐（木琴纸韵）
    # 就顺着同一条 PCM 队列流进扬声器。文件就在 bundle 里，读一次缓存住。
    _bgm_off = _cg_bgm_offset(text)
    if _bgm_off is not None:
        return _cg_bgm(_bgm_off)
    key = hashlib.sha256(
        (text + "|" + voice + "|" + rate + "|" + pitch).encode("utf-8")).hexdigest()[:32]
    if use_cache:
        hit = _cache_get(key)
        if hit is not None:
            raw = base64.b64decode(hit["samples_b64"])
            return raw, hit["sample_rate"], True

    # 网络这条路：**先直连，失败再走代理**。
    # 本机实测：直连最稳；127.0.0.1 上的沙箱代理会把连接掐断、系统注册表里
    # 那个代理对 bing 的 WebSocket 直接回 403。反过来（有些网络里 IPv4 直连
    # 在 TLS 阶段被重置）就轮到代理救命 —— 所以两条都留着，谁行谁上。
    # 注意：原来只在"返回空音频"时才退到直连，而握手失败是**抛异常**，
    # 根本没机会退 —— 于是咕嘎永远退回系统引擎。这里把异常也当失败处理。
    proxy = system_proxy()
    attempts = [None] + ([proxy] if proxy else [])
    mp3 = b""
    why = "edge-tts 没有可用通路"
    for p in attempts:
        tag = f"代理 {p}" if p else "直连"
        try:
            chunk = asyncio.run(asyncio.wait_for(
                _synth_mp3(text, voice, rate, pitch, p), timeout=25))
            if chunk:
                mp3 = chunk
                break
            why = f"{tag}返回空音频"
        except Exception as e:                       # noqa: BLE001
            why = f"{tag}失败：{type(e).__name__}: {str(e)[:120]}"
    if not mp3:
        raise RuntimeError(why)
    samples, sr = _mp3_to_pcm(mp3)
    if not samples:
        raise RuntimeError("解码后没有采样")
    # int16 小两端
    raw = bytearray()
    for s in samples:
        if s > 32767:
            s = 32767
        elif s < -32768:
            s = -32768
        raw += int(s).to_bytes(2, "little", signed=True)
    raw = bytes(raw)
    if use_cache:
        _cache_put(key, {"samples_b64": base64.b64encode(raw).decode("ascii"),
                         "sample_rate": sr, "seconds": len(samples) / float(sr or 1)})
    return raw, sr, False


def serve():
    """常驻模式：逐行读请求，逐行回结果。"""
    global _voice
    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            out.write(json.dumps({"ok": False, "error": "bad json"}) + "\n")
            out.flush()
            continue
        text = (req.get("text") or "").strip()
        if not text:
            out.write(json.dumps({"ok": False, "error": "empty text"}) + "\n")
            out.flush()
            continue
        voice = req.get("voice") or _voice
        rate = req.get("rate") or RATE_DEFAULT
        pitch = req.get("pitch") or PITCH_DEFAULT
        try:
            raw, sr, cached = synth(text, voice, rate, pitch)
            out.write(json.dumps({
                "ok": True,
                "sample_rate": sr,
                "samples_b64": base64.b64encode(raw).decode("ascii"),
                "seconds": round(len(raw) / 2.0 / float(sr or 1), 2),
                "cached": cached,
                "voice": voice,
            }) + "\n")
        except Exception as e:
            out.write(json.dumps({"ok": False, "error": str(e)[:200]}) + "\n")
        out.flush()


def main():
    # 先确保手上有能用的解释器（换掉了就不会返回）。
    reexec_if_needed()
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true", help="常驻：逐行 JSON 请求/响应")
    ap.add_argument("--probe", action="store_true", help="探测：合成一句短音并回报")
    ap.add_argument("--text", default="咕嘎～本鹅在呢。")
    ap.add_argument("--voice", default=VOICE_DEFAULT)
    ap.add_argument("--rate", default=RATE_DEFAULT)
    ap.add_argument("--pitch", default=PITCH_DEFAULT)
    ap.add_argument("--out", default="", help="把 PCM 写到文件（调试用）")
    args = ap.parse_args()

    global _voice
    _voice = args.voice

    if args.probe:
        t0 = time.time()
        raw, sr, cached = synth(args.text, args.voice, args.rate, args.pitch, use_cache=False)
        info = {"ok": True, "engine": "edge-tts", "voice": args.voice,
                "sample_rate": sr, "seconds": round(len(raw) / 2.0 / sr, 2),
                "ms": int((time.time() - t0) * 1000)}
        print(json.dumps(info, ensure_ascii=False))
        if args.out:
            with open(args.out, "wb") as f:
                f.write(raw)
        return 0

    if args.serve:
        # 启动自检：探一句短的，把引擎状态写进日志（宿主可以据此知道桥能用）
        try:
            t0 = time.time()
            synth("咕嘎，本鹅上线了。", _voice, RATE_DEFAULT, PITCH_DEFAULT)
            sys.stderr.write("[guga-voice-bridge] ready in %dms, voice=%s\n"
                             % (int((time.time() - t0) * 1000), _voice))
        except Exception as e:
            sys.stderr.write("[guga-voice-bridge] probe failed: %s\n" % e)
        sys.stderr.flush()
        serve()
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
