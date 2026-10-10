"""A stand-in for a model endpoint, so the app's plumbing can be checked with no
key and no tokens.

It answers every `POST /v1/chat/completions` with one JSON object. Which object
is decided by `--say`, so the same script can serve the availability probe
(`{"ready": true}`) and, with more work, the editor's other calls.

    python mock_model_endpoint.py --port 8799 --say '{"ready": true}'

`--say` must be a superset object: the app asks for different shapes at
different steps, and the reply schema never sets `additionalProperties: false`,
so one object with every key satisfies all of them. The keys seen so far:

    ready, q, a, b, digest, votes, intro, picks, drops, items, claims,
    results, clashes, fixes, headline, image, story(text) -> "text",
    to, sub, body, say, tool, args

`--delay` simulates provider latency so a screenshot's "用时 N 秒" reads as a
real number rather than 0. Usage is estimated from the bytes actually sent and
returned (the same rough 4-chars-per-token rule the host reports as
`estimated`), so it moves with the payload instead of being a fixed stub.

Start the host with the endpoint pointed at it:

    OCTOS_MODEL_KEY=mock \
    OCTOS_MODEL_BASE_URL=http://127.0.0.1:8799/v1 \
    octo run <bundle> --port 8141
"""

import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Rough, deliberately conservative: CJK is ~1 token/char, ASCII ~1 per 4.
def est_tokens(text: str) -> int:
    n = 0
    for ch in text:
        n += 1 if ord(ch) > 0x2E80 else 0.25
    return int(n) + 1


def make_handler(say: str, calls: list, delay: float):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # quiet
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                payload = {"raw": raw.decode("utf-8", "replace")}
            calls.append({"path": self.path, "payload": payload})
            # One line per call, so a run's shape is visible as it happens.
            system = ""
            try:
                system = payload["messages"][0]["content"][:60]
            except Exception:
                pass
            print(f"[mock] {self.path} model={payload.get('model')!r} task={system!r}", flush=True)

            prompt_text = ""
            try:
                prompt_text = "\n".join(
                    str(m.get("content") or "") for m in payload.get("messages") or []
                )
            except Exception:
                pass
            usage = {
                "prompt_tokens": est_tokens(prompt_text),
                "completion_tokens": est_tokens(say),
            }
            usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]

            if delay > 0:
                time.sleep(delay)

            body = json.dumps(
                {
                    "id": "mock",
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": say}, "finish_reason": "stop"}],
                    "usage": usage,
                },
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            body = json.dumps({"calls": len(calls)}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8799)
    ap.add_argument("--say", default='{"ready": true}', help="the JSON object every call is answered with")
    ap.add_argument("--delay", type=float, default=0.0, help="seconds to wait before each reply")
    ap.add_argument("--usage", action="store_true", help="print the estimated usage on every call")
    args = ap.parse_args()
    calls: list = []
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.say, calls, args.delay))
    print(f"[mock] answering http://127.0.0.1:{args.port}/v1/chat/completions with {args.say}", flush=True)
    if args.delay:
        print(f"[mock] delaying every reply by {args.delay}s", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        print(f"[mock] {len(calls)} call(s) seen", flush=True)
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
