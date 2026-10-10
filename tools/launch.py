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
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUNDLE = REPO / "my-entry" / "morning-brief" / "bundle"

# 可能需要启动的本地转发服务（当钥匙需要特殊头时）
SHIM = Path(r"C:\rustbuild\tmp\llm-shim.py")
SHIM_PORT = 8791
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


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
        c = base / "OctoScript-App-Design-Flow" / "tools" / "octo"
        if c.is_file():
            return c
    return None


def model_env():
    """返回 (环境变量字典, 说明文字)。

    应用只走官方的 model.complete，钥匙由宿主持有、应用看不到，
    所以这里配的是**宿主**的环境变量（OCTOS_MODEL_*），不是应用的。

    AI 通路的优先级：
      1. 已有 OCTOS_MODEL_KEY / OCTOS_LLM_KEY（用户自己配的）
      2. 本地转发服务（如果配置了钥匙）
      3. 都没有 → 规则模式（应用会自动降级，不崩）
    """
    env = {}
    key = (os.environ.get("OCTOS_MODEL_KEY") or os.environ.get("OCTOS_LLM_KEY")
           or os.environ.get("SILICONFLOW_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    if key:
        env["OCTOS_MODEL_KEY"] = key
        if os.environ.get("OCTOS_MODEL_BASE_URL"):
            env["OCTOS_MODEL_BASE_URL"] = os.environ["OCTOS_MODEL_BASE_URL"]
        return env, "使用环境变量里的模型钥匙（钥匙留在宿主，应用看不到）"

    # 本地转发服务：把需要特殊头的上游包一层
    shim_key_file = Path(r"C:\rustbuild\tmp\shim-key.txt")
    if SHIM.is_file() and shim_key_file.is_file():
        shim_key = shim_key_file.read_text(encoding="utf-8").strip()
        # 服务没起就起一个
        up = False
        try:
            with _opener.open(f"http://127.0.0.1:{SHIM_PORT}/v1/models", timeout=2):
                up = True
        except Exception:
            pass
        if not up and shim_key:
            env_shim = dict(os.environ)
            env_shim["SHIM_KEY"] = shim_key
            env_shim["SHIM_PORT"] = str(SHIM_PORT)
            subprocess.Popen([sys.executable, str(SHIM)],
                             env=env_shim, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2.5)
            up = True
        if up:
            # 模型的超时由宿主自己的 model 服务管（开发宿主给了 180 秒，
            # 引擎型模型单次可到 60 秒以上；默认 60 秒会把编辑部并行调用判为失败）。
            env["OCTOS_MODEL_BASE_URL"] = f"http://127.0.0.1:{SHIM_PORT}/v1"
            env["OCTOS_MODEL_KEY"] = shim_key
            env["OCTOS_MODEL_FAST"] = os.environ.get("OCTOS_MODEL_FAST", "deepseek-ai/DeepSeek-V4-Flash")
            env["OCTOS_MODEL_STRONG"] = os.environ.get("OCTOS_MODEL_STRONG", "deepseek-ai/DeepSeek-V4-Pro")
            return env, "使用本地模型转发服务"

    return env, "规则模式（未配置模型钥匙：主编挑选/编辑部评审将自动降级，其余功能不受影响）"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8160)
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()

    say("=" * 62)
    say("  晨报卡 Morning Brief — 正在启动")
    say("=" * 62)

    if not BUNDLE.is_dir():
        say(f"[错误] 找不到作品包：{BUNDLE}")
        return 1

    octo = find_octo()
    if not octo:
        say("[错误] 找不到官方驱动 tools/octo。")
        say("       请先按 07_官方仓库下载说明.md 下载 OctoScript-App-Design-Flow。")
        return 1

    hub = find_bin("hub.exe", "OCTO_HUB")
    card_host = find_bin("card-host.exe", "OCTO_CARD_HOST", marker="model.complete")
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
    env["OCTOSENSE_APP_HUB"] = str(REPO.parent / "OctoSense-App-Hub")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    extra, note = model_env()
    env.update(extra)
    say(f"  AI 通路  {note}")
    say("")

    app_data = Path(os.environ.get("TEMP", ".")) / "morning-brief-state"
    cmd = [sys.executable, "-u", str(octo), "run", str(BUNDLE),
           "--port", str(args.port), "--timeout", str(args.timeout),
           "--detach", "--app-data", str(app_data)]

    say("  正在启动（首次约 5–15 秒）…")
    say(f"  窗口标题：Card host [remote]　端口：{args.port}")
    say("-" * 62)
    r = subprocess.run(cmd, env=env, cwd=str(REPO))
    if r.returncode != 0:
        say(f"\n[错误] 启动失败（退出码 {r.returncode}）。")
        say("       若提示端口被占用，换一个：python tools/launch.py --port 8170")
        return r.returncode

    say("")
    say("=" * 62)
    say("  已启动。用法：")
    say("    1. 勾选主题（或直接写一句你想看什么），点「生成晨报」")
    say("    2. 主编会先问一句 —— 选 A 或 B（也可点「你定，不用问」）")
    say("    3. **点「批准并取数」之前不会联网**；点「暂不」则什么都不发生")
    say("    4. 出报后：结果页看头版与淘汰率，点任意条目进阅读页")
    say("    5. 右下角「AI 主编」可以对话，让它替你操作")
    say("    关闭窗口即退出。")
    say("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
