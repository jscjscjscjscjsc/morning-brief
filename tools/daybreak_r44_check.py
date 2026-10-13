#!/usr/bin/env python3
"""第44轮：阅读潮汐、关闭恢复、跨期导航、搜索及高频切页回归。"""
import argparse
import json
import time
from daybreak_regression import Bridge, ROOT, safe_state, json_write

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, required=True)
parser.add_argument('--state', required=True)
parser.add_argument('--name', default='desktop')
parser.add_argument('--cycles', type=int, default=25)
args = parser.parse_args()
state = safe_state(args.state)
b = Bridge(args.port)
deadline = time.monotonic() + 12
while True:
    try:
        b.assert_live()
        break
    except (AssertionError, OSError):
        if time.monotonic() > deadline:
            raise
        time.sleep(.15)

def choose_front():
    if not any(n.get('i') == 'tab_front_on' for n in b.nodes()):
        b.tap(ident='tab_front_off')

def persisted():
    time.sleep(.55)
    return json.loads((state / 'morning-brief/reports.json').read_text(encoding='utf-8'))

b.select_report('10/12 08:10')
choose_front()
b.tap(prefix='展开这条线索')
assert '样本1' in b.text('story_title'), '正文未及时更新'
assert 'qa-1-0' in persisted()['sessions']['qa-issue-1']['read_ids'], '打开记录未保存'
b.tap(text='下期 ›')
assert '10/13 08:10' in [n.get('t') for n in b.nodes()], '跨期按钮未切到另一份日报'
choose_front()
assert not persisted()['sessions']['qa-issue-2'].get('read_ids'), '阅读记录串期'
b.tap(text='‹ 上期')
assert '样本1' in b.text('story_title'), '返回上一期丢失阅读位置'
choose_front()
labels = [n.get('t', '') for n in b.nodes()]
assert any('阅读潮汐  1 / 3' in s for s in labels), '阅读潮汐计数错误'

# 关闭页签不删除文档；通过最近关闭入口恢复。
b.tap(text='×')
b.assert_live()
b.tap(text='往期')
b.tap(text='重开刚关闭')
assert persisted()['focus'] == 'qa-issue-1', '没有恢复刚关闭的页签'
choose_front()
evidence = ROOT / 'my-entry/evidence'
evidence.mkdir(parents=True, exist_ok=True)
# 截图从页首取景；不把保留的历史滚动位置误当成标题消失。
frame = next(n['r'] for n in b.nodes() if n.get('i') == 'report_pane')
b.get('/m', k='scroll', x=frame[0]+frame[2]*.5, y=frame[1]+frame[3]*.6, dx=0, dy=-2000, wait=.1)
b.screenshot(evidence / f'r44-{args.name}.png')

# 搜索只重建结果，不重建输入框。输入查询后必须找到正确一期。
b.tap(text='往期')
node = next(n for n in b.nodes() if n.get('i') == 'report_query_in')
x, y, w, h = node['r']
b.get('/click', x=x+w/2, y=y+h/2, wait=.08)
b.get('/t', t='样本 2', wait=.1)
results = [n.get('t', '') for n in b.nodes() if n.get('ty') == 'Button']
assert any(t.startswith('10/13 08:10') for t in results), '搜索没有返回目标日报'
assert not any(t.startswith('10/12 08:10  ·') for t in results), '搜索没有过滤另一份日报'
b.tap(text='往期')

for i in range(args.cycles):
    b.tap(ident='tab_pool_off')
    assert '样本1' in b.text('pool_head'), '情报池串期'
    b.tap(ident='tab_review_off')
    b.tap(ident='tab_stand_off')
    b.tap(ident='tab_front_off')
    b.assert_live()
errors = b.errors()
assert not errors, errors[:10]
data = persisted()
assert len(data['reports']) == 2, '关闭操作删除了日报'
assert len(data['open']) == 2, '重开页签没有持久化'
result = {'passed': True, 'name': args.name, 'cycles': args.cycles,
          'clicks': len(b.events), 'nodes': len(b.nodes()), 'runtime_errors': errors,
          'checks': ['独立阅读位置', '阅读潮汐持久化', '前后跨期', '关闭恢复', '档案搜索', '高频栏目切换']}
json_write(evidence / f'r44-{args.name}-proof.json', result)
print(json.dumps(result, ensure_ascii=False))
