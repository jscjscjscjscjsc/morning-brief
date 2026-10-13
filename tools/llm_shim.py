#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地模型转发服务（给晨报卡的宿主用）。

为什么需要它
------------
卡片宿主只会说一种话：OpenAI 兼容，且**固定**带
`response_format: {"type": "json_object"}`（见 OctoSense-App-Hub 的
crates/model-service/src/lib.rs）。可上游各有各的脾气，以 MiniMax 为例：

  · `response_format` 直接被拒：
        400 invalid params, unknown response_format type 'json_object' (2013)
  · `MiniMax-M2` 是推理模型，正文里裹着 `<think>…</think>` 草稿

原生直连必然失败，所以在中间垫一层做归一化。它做四件事：

  1. 删掉 `response_format`（上游不认这个字段）
  2. 剥掉 `<think>…</think>`；顺带兜底反向：content 空而
     reasoning_content/reasoning/thinking 有货时，把它当正文用
  3. 从文本里提取纯 JSON（有些模型会包 ``` 围栏或写前言）
  4. 抬高 `max_tokens`（推理模型的草稿会先吃掉一大截预算，卡片给的
     1024~2048 常常不够，JSON 会写到一半断掉）

用法
----
    set SHIM_KEY=<上游密钥>
    python tools/llm_shim.py

环境变量
--------
    SHIM_UPSTREAM    上游根地址（含 /v1），默认 https://api.minimax.chat/v1
    SHIM_KEY         上游密钥
    SHIM_PORT        监听端口，默认 8791
    SHIM_MODEL       对外声明的模型名，默认 MiniMax-M2
    SHIM_FORCE_MODEL 强制改写请求里的模型名（默认取 SHIM_MODEL）。
                     卡片按自己的 class 发 deepseek-ai/...，上游不认识，
                     统一改掉；卡片对模型名不敏感，只用返回的 meta.usage。
    SHIM_MIN_TOKENS  max_tokens 下限，默认 6000
    SHIM_DEBUG=1     把每次响应摘要写进 shim-resp.log
"""
import json
import os
import re
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ.get("SHIM_UPSTREAM", "https://api.minimax.chat/v1").rstrip("/")
KEY = os.environ.get("SHIM_KEY", "")
PORT = int(os.environ.get("SHIM_PORT", "8791"))
MODEL = os.environ.get("SHIM_MODEL", "MiniMax-M2")
FORCE_MODEL = os.environ.get("SHIM_FORCE_MODEL", MODEL)
MIN_TOKENS = int(os.environ.get("SHIM_MIN_TOKENS", "6000"))
DEBUG = os.environ.get("SHIM_DEBUG", "") == "1"
DEBUG_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shim-resp.log")

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_THINK = re.compile(r"<think\b[^>]*>.*?</think\s*>", re.S | re.I)
_THINK_OPEN = re.compile(r"<think\b[^>]*>.*$", re.S | re.I)


def log_debug(entry):
    if not DEBUG:
        return
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _dedup_v1(path):
    """宿主发的是 `/v1/chat/completions`，而上游根地址常写在 `/v1` 上，
    直接拼会变成 `.../v1/v1/...` —— 上游回 404。这里去掉重复的那一段。"""
    if UPSTREAM.endswith("/v1") and path.startswith("/v1/"):
        return path[3:]
    return path


def strip_think(t):
    """剥掉推理模型的 <think> 草稿；被 max_tokens 截断只剩开头的也一并清掉。"""
    if not t:
        return t or ""
    out = _THINK.sub("", t)
    out = _THINK_OPEN.sub("", out)
    return out.strip()


def extract_json_text(text):
    """从可能带围栏/前言/结语的文本里，取出第一个完整 JSON 对象或数组。"""
    if not text:
        return None
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(.+?)\s*```", t, re.S)
    if m:
        t = m.group(1).strip()
    if t.startswith("{") or t.startswith("["):
        return t
    for opener, closer in (("{", "}"), ("[", "]")):
        i = t.find(opener)
        if i < 0:
            continue
        depth = 0
        in_str = False
        esc = False
        for j in range(i, len(t)):
            ch = t[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return t[i:j + 1]
    return None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            body = json.dumps({
                "object": "list",
                "data": [{"id": MODEL, "object": "model", "owned_by": "shim"}],
            }).encode()
            return self._send(200, body)
        return self._send(404, b'{"error":"not found"}')

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except Exception:
            payload = {}

        # 1) 上游不认 response_format —— 宿主固定要发，这里必须摘掉。
        payload.pop("response_format", None)
        # 也顺手摘掉上游可能不认的其它 OpenAI 专属字段。
        for k in ("stream_options", "presence_penalty", "frequency_penalty", "logprobs", "top_logprobs"):
            payload.pop(k, None)

        # 2) 抬高 max_tokens：推理模型的草稿会吃掉预算，JSON 容易写一半就断。
        try:
            cur = payload.get("max_tokens")
            if not isinstance(cur, int) or cur < MIN_TOKENS:
                payload["max_tokens"] = MIN_TOKENS
        except Exception:
            pass

        # 3) 模型名归一：上游只认它自己的名字。
        if FORCE_MODEL:
            payload["model"] = FORCE_MODEL

        url = UPSTREAM + _dedup_v1(self.path)
        req = urllib.request.Request(
            url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + KEY},
            method="POST",
        )
        try:
            with _OPENER.open(req, timeout=200) as r:
                body = r.read()
        except urllib.error.HTTPError as e:
            body = e.read()
            return self._send(e.code if 400 <= e.code < 600 else 502, body)
        except Exception as e:
            return self._send(502, json.dumps(
                {"error": {"message": "shim transport error: %s" % e}}).encode())

        try:
            d = json.loads(body.decode("utf-8", "replace"))
        except Exception:
            return self._send(200, body)

        changed = []
        try:
            choices = d.get("choices") or [{}]
            choice = choices[0]
            msg = choice.get("message") or {}
            content = msg.get("content") or ""
            reasoning = (msg.get("reasoning_content") or msg.get("reasoning")
                         or msg.get("thinking") or "")

            clean = strip_think(content)
            if clean != content:
                changed.append("strip-think")
                content = clean

            if not content.strip() and reasoning.strip():
                content = strip_think(reasoning)
                msg["reasoning_content"] = ""
                msg["reasoning"] = ""
                changed.append("reasoning->content")

            if content.strip():
                j = extract_json_text(content)
                if j and j.strip() != content.strip():
                    content = j
                    changed.append("extracted-json")
                # 补齐「主编协议」的形状：推理模型偶发只回 {"tool": ...} 或只回
                # {"say": ...}，而主编辑协议 required = [say, tool]，宿主会直接拒收
                # （实测报错：output is missing "say" → 卡片显示「主编没接上模型」）。
                # 只在这两个键露过面时补对侧的空值——其它 schema
                # （cover/panel/judge/fact…）都没有这两个键，绝不会被误伤。
                try:
                    o = json.loads(content)
                    if isinstance(o, dict):
                        patched = False
                        if "tool" in o and "say" not in o:
                            o["say"] = ""
                            patched = True
                        if "say" in o and "tool" not in o:
                            o["tool"] = "none"
                            patched = True
                        if patched:
                            content = json.dumps(o, ensure_ascii=False)
                            changed.append("filled-shape")
                except Exception:
                    pass

            msg["content"] = content
            choice["message"] = msg
            choices[0] = choice
            d["choices"] = choices
        except Exception as e:
            changed.append("normalize-error:%s" % e)

        head = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        log_debug({
            "model": d.get("model"),
            "content_len": len(head),
            "finish": (d.get("choices") or [{}])[0].get("finish_reason"),
            "changed": changed,
            "head": head[:100],
        })
        return self._send(200, json.dumps(d, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    print("[shim] 127.0.0.1:%d -> %s  model=%s" % (PORT, UPSTREAM, FORCE_MODEL), flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
