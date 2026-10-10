#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给「晨报卡」的语音层挑音色、出试听样本。

背景：宿主 shell 的语音服务（见 `my-entry/patches/host-voice.patch`）在 Windows 上
落到系统自带的 SAPI 音色，听感偏机械。想要「更像人」的中文播报，最省事的一条路
是 edge-tts 的神经音色（zh-CN-XiaoxiaoNeural / YunxiNeural / YunyangNeural …）。
本脚本做两件事，都是给人和给宿主用的“参照”：

  1. `--list`   列出这台机器上 edge-tts 能给到的中文音色和它们的定位
                （News / Novel / Dialect、Warm / Lively / Professional …）。
                这份名单就是应用侧 `vc_pick_voice()` 优先级表的出处。
  2. `--sample` 用最自然的那一档音色把一句晨报稿子念出来，落成 mp3 供试听；
                `--voice` 可以指定别的音色，做 A/B 对比。

注意：这个脚本是**开发与试听工具**，不是应用运行时的一部分。商店应用拿不到
`llm` 服务族（官方规定只发给系统应用），因此应用侧只能“在宿主给出的音色里挑一个”；
真正把音色换成神经音色，要么在宿主侧接入（补丁的 `voice.rs`），要么这台机器上装了
带 Natural 音色的引擎。

用法：

    python tools/voice-edge-tts.py --list
    python tools/voice-edge-tts.py --sample --out build/voice-sample.mp3
    python tools/voice-edge-tts.py --voice zh-CN-YunxiNeural --text "今天的晨报好了。" --out build/a.mp3
"""

import argparse
import asyncio
import sys

# 和应用侧 vc_pick_voice() 同一张优先级表：越靠前越“像人”。
# 前两个是新闻播报定位（News / Professional），中间两个偏故事讲述，最后是方言与卡通。
PREFERRED = [
    "zh-CN-XiaoxiaoNeural",   # Female · News, Novel · Warm
    "zh-CN-YunyangNeural",    # Male   · News · Professional, Reliable
    "zh-CN-YunxiNeural",      # Male   · Novel · Lively, Sunshine
    "zh-CN-XiaoyiNeural",     # Female · Cartoon, Novel · Lively
    "zh-CN-YunjianNeural",    # Male   · Sports, Novel · Passion
    "zh-CN-YunxiaNeural",     # Male   · Cartoon, Novel · Cute
    "zh-CN-liaoning-XiaobeiNeural",
    "zh-CN-shaanxi-XiaoniNeural",
]

# 一句真实的晨报稿子，用来试听（和卡片里念的是同一类句子）。
SAMPLE = (
    "今天的晨报好了。本期聚焦开源与底层技术的进展，"
    "一共选了五条，其中三条来自一手来源。"
    "有一条传闻还没有被证实，我在理由里写明了。"
)


def _voices_sync():
    """edge-tts 的 voices 列举是异步的，这里包一层，方便同步调用。"""
    import edge_tts

    async def go():
        return await edge_tts.list_voices()

    return asyncio.run(go())


def cmd_list(_args):
    rows = [v for v in _voices_sync() if str(v.get("Locale", "")).startswith("zh")]
    if not rows:
        print("edge-tts 没有返回任何中文音色（检查网络或 edge-tts 版本）")
        return 1
    rows.sort(key=lambda v: (PREFERRED.index(v["ShortName"]) if v["ShortName"] in PREFERRED else 99,
                             v["ShortName"]))
    print(f"{'音色 id':<36}{'性别':<8}{'定位'}")
    print("-" * 78)
    for v in rows:
        voice = v.get("VoiceTag") or {}
        uses = ", ".join(voice.get("ContentCategories") or [])
        styles = ", ".join(voice.get("VoicePersonalities") or [])
        tag = " · ".join(x for x in (uses, styles) if x)
        mark = "★" if v["ShortName"] == PREFERRED[0] else " "
        print(f"{mark}{v['ShortName']:<35}{v.get('Gender',''):<8}{tag}")
    print("-" * 78)
    print(f"★ = 首选（News 定位里听感最自然的一档）：{PREFERRED[0]}")
    return 0


def _pick_default():
    names = {v["ShortName"] for v in _voices_sync()}
    for want in PREFERRED:
        if want in names:
            return want
    return None


def cmd_say(args):
    import edge_tts

    voice = args.voice
    if not voice:
        voice = _pick_default()
        if not voice:
            print("这台机器 / 这次联网下 edge-tts 没有可用的中文音色", file=sys.stderr)
            return 1
        print(f"未指定 --voice，自动选中最自然的一档：{voice}")

    text = args.text or SAMPLE
    out = args.out

    async def go():
        # rate 稍放慢一点：新闻播报本身快，念晨报稿子慢半拍更像在跟你说话。
        await edge_tts.Communicate(text, voice, rate=args.rate).save(out)

    asyncio.run(go())
    print(f"已写出 {out}（音色 {voice}，{len(text)} 字）")
    return 0


def main():
    ap = argparse.ArgumentParser(description="晨报卡语音层 · 音色挑选与试听")
    ap.add_argument("--list", action="store_true", help="列出 edge-tts 的中文音色（按像人程度排序）")
    ap.add_argument("--sample", action="store_true", help="用首选音色念一句晨报稿子")
    ap.add_argument("--voice", default="", help="指定音色 id，如 zh-CN-YunxiNeural")
    ap.add_argument("--text", default="", help="要念的文本；不带则用内置的晨报样句")
    ap.add_argument("--rate", default="-8%", help="语速，默认 -8%%（比默认稍慢，更像对话）")
    ap.add_argument("--out", default="build/voice-sample.mp3", help="输出 mp3 路径")
    args = ap.parse_args()

    if args.list:
        return cmd_list(args)
    return cmd_say(args)


if __name__ == "__main__":
    sys.exit(main())
