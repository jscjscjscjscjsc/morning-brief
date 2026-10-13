#!/usr/bin/env python3
"""独立测试宿主：不占用读者的应用端口，不覆盖真实存档。"""
import argparse
import json
import os
import pathlib
import socket
import subprocess
import time
import urllib.request
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, required=True)
parser.add_argument('--state', required=True)
parser.add_argument('--size', default='360x780')
parser.add_argument('--entry', action='store_true')
parser.add_argument('--skip', action='store_true')
args = parser.parse_args()
state = (ROOT / args.state).resolve()
assert state.parent == (ROOT / '.dev').resolve() and state.name.startswith('daybreak-'), '只允许隔离测试目录'
sock = socket.socket()
sock.settimeout(1)
if sock.connect_ex(('127.0.0.1', args.port)) == 0:
    raise SystemExit('端口已占用；不启动重复宿主')
sock.close()
state.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env.update({'MAKEPAD_REMOTE': str(args.port), 'MAKEPAD_HIDE_WINDOWS': '1'})
command = ['D:/morning-brief/.local-tools/target/release/card-host.exe',
           '--bundle', str(ROOT / 'my-entry/morning-brief/bundle'),
           '--app-data', str(state), '--allow-unsigned', '--size', args.size]
base = f'http://127.0.0.1:{args.port}'

def get(route):
    return json.load(urllib.request.urlopen(base + route, timeout=20))

with (state / 'host.log').open('w', encoding='utf-8') as log:
    child = subprocess.Popen(command, cwd='D:/morning-brief/OctoSense-App-Hub',
                             env=env, stdout=log, stderr=subprocess.STDOUT)
    print('隔离宿主已启动', args.port, args.size, flush=True)
    if args.entry or args.skip:
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline and child.poll() is None:
            try:
                if any(n.get('i') == 'cg_layer' for n in get('/snap').get('s', [])):
                    if args.skip:
                        get('/click?x=180&y=430&wait=1')
                        time.sleep(.08)
                        removed = not any(n.get('i') == 'cg_layer' for n in get('/snap').get('s', []))
                        evidence = ROOT / 'my-entry/evidence'
                        evidence.mkdir(parents=True, exist_ok=True)
                        (evidence / 'r44-entry-skip-proof.json').write_text(json.dumps({
                            'passed': removed, 'overlay_removed': removed,
                            'before_natural_finish': True}, ensure_ascii=False), encoding='utf-8')
                        print('片头点按跳过', removed, flush=True)
                        break
                    sequence = get('/gseq?n=16&every_ms=130&scale=0.75')
                    frames = [Image.open(p).convert('RGB') for p in sequence.get('png', [])]
                    evidence = ROOT / 'my-entry/evidence'
                    evidence.mkdir(parents=True, exist_ok=True)
                    for i, image in enumerate(frames):
                        image.save(evidence / f'r44-entry-{i:02}.jpg', quality=85)
                    if frames:
                        frames[0].save(evidence / 'r44-entry.gif', save_all=True,
                                       append_images=frames[1:], duration=130, loop=0)
                    (state / 'entry.json').write_text(json.dumps({'frames': len(frames),
                        'timings': sequence.get('frames', [])}, ensure_ascii=False, indent=2), encoding='utf-8')
                    print('入场抽样帧', len(frames), flush=True)
                    break
            except Exception as exc:
                print('等待入场', type(exc).__name__, flush=True)
            time.sleep(.05)
    raise SystemExit(child.wait())
