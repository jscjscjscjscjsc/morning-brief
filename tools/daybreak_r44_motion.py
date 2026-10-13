#!/usr/bin/env python3
"""原生帧对比：悬停/按压波纹不是只检查控件树。仅操作指定测试宿主。"""
import argparse
import json
import time
from PIL import Image, ImageChops
from daybreak_regression import Bridge, ROOT, json_write

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, required=True)
args = parser.parse_args()
b = Bridge(args.port)
b.assert_live()
time.sleep(1.4)
node = next(n for n in b.nodes() if n.get('ty') == 'Button' and n.get('t') == '往期')
x, y, w, h = node['r']
evidence = ROOT / 'my-entry/evidence'

def frames():
    sequence = b.get('/gseq', n=6, every_ms=35, scale=1)
    return [Image.open(p).convert('RGB') for p in sequence.get('png', [])]

b.get('/m', k='move', x=0, y=0, wait=.2)
before = Image.open(b.get('/g', scale=1)['png']).convert('RGB')
b.get('/m', k='move', x=x+w/2, y=y+h/2, wait=.01)
hover = frames()
assert len(hover) == 6 and any(ImageChops.difference(before, im).getbbox() for im in hover), '悬停没有可见反馈'
b.get('/m', k='down', x=x+w/2, y=y+h/2, wait=.01)
pressed = frames()
assert any(ImageChops.difference(hover[-1], im).getbbox() for im in pressed), '按压没有可见反馈'
b.get('/m', k='up', x=x+w/2, y=y+h/2, wait=.1)
assert not b.errors(), b.errors()
images = [before] + hover + pressed
images[0].save(evidence / 'r44-water-touch.gif', save_all=True, append_images=images[1:], duration=60, loop=0)
json_write(evidence / 'r44-motion-proof.json', {'passed': True, 'frames': len(images),
    'hover_visible': True, 'press_visible': True, 'runtime_errors': b.errors(),
    'scope': '原生交互桥的悬停与按压；不是实体手机触觉马达测试'})
print(json.dumps({'passed': True, 'hover_visible': True, 'press_visible': True, 'frames': len(images)}, ensure_ascii=False))
