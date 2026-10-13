#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""晨报卡 · 看门狗：白屏时自动把卡片重启回来，模型转发服务掉线时把它拉起来。

它治的是什么
------------
宿主（makepad + D3D11）会偶发掉进一种状态：**逻辑全活着、一帧都画不出来**。
表现是窗口整片纯白 —— 连引擎自己画的标题栏都没了；而控件树依然完整、点击也
照样改状态。所以从卡片脚本内部根本察觉不到，只有重启卡片能恢复。
（2026-10-13 实测：用户正常使用、什么都没按，卡片自己变白。）

怎么判断白屏（踩过的两个坑都写在这儿）
------------------------------------
坑 1：**不能拿桌面截屏（BitBlt）当依据**。卡片被别的窗口盖住时，截到的是别人
      的窗口 —— 2026-10-13 就因此把一块浏览器画面当成了"卡片有画面"，而卡片
      其实全白。反过来加个"被遮挡就跳过"，又会让看门狗在卡片位于后台时**永远
      不出手**（用户就是这么中招的：卡片在后台变白，看门狗一次都没救）。
坑 2：**PrintWindow(PW_RENDERFULLCONTENT) 让窗口自己画一份，结论与卡片自带的
      `/g` 抓帧接口一致**，而且不受遮挡影响、也不依赖卡片还能响应 HTTP。

所以现在用 PrintWindow 取样，判定口径（本机 824×1504、采样约 1.1 万个点）：
    正常页面   色数 1 万上下、非白点 4 万上下
    白屏       色数 1、非白点 0
差距是数量级的，不存在中间态。

⚠️ 2026-10-13 的第二课：**看门狗自己差点成了白屏的制造者**。
第一版每 8 秒调一次 `/snap` 去数控件（想确认「卡片逻辑还活着」），实测
card-host 的内存会以 **0.6MB/s** 疯涨（snapshot 要把包括 418KB 脚本源码
在内的全部控件文本序列化一遍，每轮泄漏约 5MB），涨到 500MB+ 渲染直接崩
—— 卡片真白屏、看门狗再重启、重启后再涨，死循环。停掉 /snap 后空闲
3 分钟内存只涨 6MB（0.03MB/s），差 20 倍。
所以现在：**平时一次 /snap 都不调**，只在连续 2 次疑似白屏时才查一次
（诊断用 + 确认不是「窗口在但卡片没起来」的过渡态）。

⚠️ 第三课：**窗口要按尺寸过滤**。card-host 会多出 314x50 的小窗口
（同样是 MakepadWindow、标题同样匹配），只看「第一个匹配」抓到它，
小窗口当然只有十几个颜色 → 误判白屏 → 把好好的卡片连着重启五次。
主窗口在 250% DPI 下 824x1504、逻辑 412x752，下限卡 400 很稳。

除了白屏，它还看住 **127.0.0.1:8791（模型转发服务）**：那个服务一旦掉线，
卡片只会说「没接上模型」，而用户完全不知道该怎么救。看门狗发现端口没人听就
用 `launch.py --shim-only` 重新拉起来。

用法
----
    python tools/card_watchdog.py --port 8160
"""
import argparse
import ctypes
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from ctypes import wintypes as wt
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LAUNCH = REPO / "tools" / "launch.py"
SHIM_PORT = 8791
LOGFILE = Path(os.environ.get("TEMP", ".")) / "morning-brief-watchdog.log"

try:
    ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)   # 否则坐标被 DPI 缩放
except Exception:
    pass
u32 = ctypes.WinDLL("user32", use_last_error=True)
g32 = ctypes.WinDLL("gdi32", use_last_error=True)
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
PW_RENDERFULLCONTENT = 2


class _BIH(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


def log(msg):
    line = time.strftime("[%m-%d %H:%M:%S] ") + msg
    print(line, flush=True)
    try:
        with LOGFILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def card_hwnd(title_hint="Card host"):
    """找卡片的主窗口（MakepadWindow + 标题含 Card host + 尺寸够大）。

    ⚠️ 尺寸过滤是 2026-10-13 加的，踩坑记录：
    card-host 有时会多出一个小窗口（实测 314x50），它同样是 MakepadWindow、
    标题同样匹配 —— 只看「第一个匹配」会抓到它。小窗口当然只有十几个颜色，
    于是被当成「白屏」，把好好的卡片连着重启了五次（看门狗日志 09:34~09:41）。
    主窗口在 250% DPI 下是 824x1504、逻辑 412x752，400 的下限卡得很稳。
    """
    found = []

    def cb(hwnd, _lp):
        cls = ctypes.create_unicode_buffer(64)
        u32.GetClassNameW(hwnd, cls, 64)
        if cls.value != "MakepadWindow":
            return True
        r = wt.RECT()
        u32.GetWindowRect(hwnd, ctypes.byref(r))
        w, hh = r.right - r.left, r.bottom - r.top
        if w < 400 or hh < 400:          # 辅助小窗口/最小化残留，不是主窗口
            return True
        n = u32.GetWindowTextLengthW(hwnd)
        b = ctypes.create_unicode_buffer(n + 2)
        u32.GetWindowTextW(hwnd, b, n + 2)
        if title_hint in b.value:
            found.append(hwnd)
        return True

    u32.EnumWindows(ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)(cb), 0)
    if found:
        _last_hwnd[0] = found[0]
        return found[0]
    return None


# 最近一次见到的主窗口句柄。窗口最小化时 card_hwnd() 会因为尺寸过滤返回
# None，但句柄本身还有效 —— 靠它做 SW_RESTORE 自救（见主循环）。
_last_hwnd = [None]


def window_stats():
    """用 PrintWindow 让窗口自己画一份。返回 (色数, 非白采样点, 窗口尺寸)。"""
    h = card_hwnd()
    if not h:
        return -1, -1, ""
    r = wt.RECT()
    u32.GetWindowRect(h, ctypes.byref(r))
    w, hh = r.right - r.left, r.bottom - r.top
    if w < 50 or hh < 50:
        return -1, -1, f"{w}x{hh}"
    hdc = u32.GetDC(0)
    if not hdc:
        return -1, -1, ""
    mem = g32.CreateCompatibleDC(hdc)
    bmp = g32.CreateCompatibleBitmap(hdc, w, hh)
    g32.SelectObject(mem, bmp)
    u32.PrintWindow(h, mem, PW_RENDERFULLCONTENT)
    bi = _BIH(ctypes.sizeof(_BIH), w, -hh, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * hh * 4)
    g32.GetDIBits(mem, bmp, 0, hh, buf, ctypes.byref(bi), 0)
    g32.DeleteObject(bmp)
    g32.DeleteDC(mem)
    u32.ReleaseDC(0, hdc)
    p = bytes(buf)
    uniq, nonwhite = set(), 0
    for i in range(0, len(p) - 4, 44):
        b_, g_, r_ = p[i], p[i + 1], p[i + 2]
        uniq.add((r_, g_, b_))
        if not (r_ > 245 and g_ > 245 and b_ > 245):
            nonwhite += 1
        if len(uniq) > 400:            # 早就够非白屏了，别白算
            return len(uniq), nonwhite, f"{w}x{hh}"
    return len(uniq), nonwhite, f"{w}x{hh}"


def try_wake():
    """先试温和的救法：置顶 + 强制重绘。能救回来就不用重启。"""
    h = card_hwnd()
    if not h:
        return
    SWP_NOSIZE, SWP_NOMOVE, SWP_SHOWWINDOW = 0x0001, 0x0002, 0x0040
    RDW_INVALIDATE, RDW_UPDATENOW, RDW_ALLCHILDREN, RDW_FRAME = 0x1, 0x100, 0x80, 0x400
    u32.ShowWindow(h, 9)                                   # SW_RESTORE
    u32.SetWindowPos(h, -1, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW)
    u32.RedrawWindow(h, None, None,
                     RDW_INVALIDATE | RDW_UPDATENOW | RDW_ALLCHILDREN | RDW_FRAME)


def http(port, path, timeout=6):
    with _OPENER.open(f"http://127.0.0.1:{port}{path}", timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def widget_count(port):
    try:
        d = json.loads(http(port, "/snap", timeout=5))
        return len(d.get("s") or [])
    except Exception:
        return -1


def port_alive(port):
    s = socket.socket()
    s.settimeout(1.5)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8160)
    ap.add_argument("--interval", type=float, default=8.0)
    ap.add_argument("--strikes", type=int, default=3, help="连续几次白才判定")
    ap.add_argument("--max-restarts", type=int, default=6)
    ap.add_argument("--no-shim", action="store_true", help="不看模型转发服务")
    args = ap.parse_args()

    pidfile = Path(os.environ.get("TEMP", ".")) / f"morning-brief-watchdog-{args.port}.pid"
    try:
        pidfile.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass

    log(f"看门狗上线：卡片端口 {args.port}，模型服务端口 {SHIM_PORT}，每 {args.interval:.0f}s 看一眼")
    strikes = 0
    restarts = 0
    misses = 0
    shim_tries = 0

    while True:
        time.sleep(args.interval)

        # ---- 模型转发服务：掉线就拉起来 ----
        if not args.no_shim and shim_tries < 10:
            if not port_alive(SHIM_PORT):
                shim_tries += 1
                log(f"模型转发服务（:{SHIM_PORT}）没人听 —— 重新拉起（第 {shim_tries} 次）")
                try:
                    subprocess.run([sys.executable, str(LAUNCH), "--shim-only"],
                                   cwd=str(REPO), timeout=120,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(3)
                    log(f"  {'起来了' if port_alive(SHIM_PORT) else '还是不行'}")
                except Exception as e:
                    log(f"  拉起失败：{e}")

        # ---- 卡片：窗口找不到先别急着判死 ----
        # ⚠️ 2026-10-13 实测：主窗口会**自己进入最小化**（GetWindowRect 变成
        # (-16000,-16000) 的伪矩形，尺寸 157×25/314×50），用户看到的"白屏"
        # 很大一部分是它 —— 最小化的窗口恢复回来时 D3D 内容没重绘。
        # 尺寸过滤会把最小化窗口滤成 None，原来的逻辑直接判"窗口不在了"
        # 退出 —— 等于见死不救。现在先试一次恢复（SW_RESTORE），
        # 恢复后窗口回来了就继续看护；连续 3 次仍找不到才认输退出。
        if card_hwnd() is None:
            u32.ShowWindow(_last_hwnd[0], 9) if _last_hwnd[0] else None
            time.sleep(1.5)
            if card_hwnd() is not None:
                if misses:
                    log("窗口被最小化了，已恢复（虚惊一场）。")
                misses = 0
                continue
            misses += 1
            if misses >= 3:
                log("卡片窗口已经不在了，看门狗退出。")
                break
            continue
        misses = 0

        uniq, nonwhite, dim = window_stats()
        white = uniq >= 0 and uniq < 200 and nonwhite < 800

        if not white:
            if strikes:
                log(f"恢复正常（色数={uniq}），计数清零")
            strikes = 0
            continue

        strikes += 1
        # ⚠️ /snap 只在「第 2 次疑似」时查一次，平时一次都不调 —— 2026-10-13
        # 实测的硬教训：每 8 秒调一次 /snap，card-host 内存以 0.6MB/s 疯涨
        #（snapshot 要把包括 418KB 脚本源码在内的全部控件文本序列化一遍），
        # 涨到 500MB+ 渲染直接崩 → 卡片真白屏。也就是说**看门狗自己就是
        # 白屏的制造者**：停掉 /snap 后空闲 3 分钟内存只涨 6MB（原来涨 100MB+）。
        # 现在它只在疑似白屏时登场，做两件事：确认卡片逻辑还活着（控件数），
        # 留一份现场给日志。
        wc = widget_count(args.port) if strikes >= 2 else -1
        log(f"疑似白屏 {strikes}/{args.strikes}（色数={uniq} 非白={nonwhite} "
            f"控件={wc} {dim}）")

        if strikes < args.strikes:
            continue

        strikes = 0
        # 先温和救一次：置顶 + 强制重绘
        log("先试置顶 + 强制重绘…")
        try_wake()
        time.sleep(4)
        u2, n2, _ = window_stats()
        if not (u2 >= 0 and u2 < 200 and n2 < 800):
            log(f"救回来了（色数={u2}），不重启。")
            continue

        restarts += 1
        if restarts > args.max_restarts:
            log(f"已经重启过 {args.max_restarts} 次，不再自动重启（避免死循环）。")
            continue

        log(f"置顶也救不回来 → 重启卡片（第 {restarts} 次）")
        try:
            http(args.port, "/quit", timeout=5)
        except Exception as e:
            log(f"  /quit 没成功：{e}")
        for _ in range(40):
            time.sleep(0.5)
            if card_hwnd() is None:
                break
        log("  旧窗口已关闭，重新拉起…")
        try:
            subprocess.run([sys.executable, str(LAUNCH), "--port", str(args.port),
                            "--no-watchdog"], cwd=str(REPO), timeout=300,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(8)
            u3, _n3, _ = window_stats()
            log(f"  重启完成：色数={u3} 控件数={widget_count(args.port)}")
        except Exception as e:
            log(f"  重启失败：{e}")

    try:
        pidfile.unlink()
    except Exception:
        pass


if __name__ == "__main__":
    main()
