#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""晨光档案：隔离状态 + 原生交互桥回归。样本不是新闻，不调用网络/模型。

prepare 只写项目 .dev/daybreak-* 下的新测试目录；不会覆盖真实读者的存档。
check 只操作显式指定的测试宿主；不启动、结束或重置任何其他进程。
"""
import argparse
import datetime as dt
import json
import pathlib
import shutil
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOCAL_TZ = dt.timezone(dt.timedelta(hours=8))

def json_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

def fixture():
    reports = []
    for n, day in enumerate([12, 13], 1):
        timestamp = dt.datetime(2026, 10, day, 8, 10, tzinfo=LOCAL_TZ).timestamp()
        rows = []
        for r in range(3):
            rows.append({'id': f'qa-{n}-{r}', 'title': f'[离线回归样本{n}] 清晨线索 {r+1}',
                         'link': '', 'source': '离线交互测试', 'summary': '这是隔离目录中的回归样本，不是真实新闻，也不会额外联网。',
                         'published': timestamp, 'image': '', 'discussion': '', 'points': None, 'comments': None})
        reports.append({'id': f'qa-issue-{n}', 'ts': timestamp, 'rows': rows,
                        'intro': f'[离线回归样本{n}] 用来验证独立日报、阅读位置、关闭恢复和错误隔离。',
                        'whys': [{'id': r['id'], 'why': '测试独立文档内的取舍理由。'} for r in rows],
                        'cover_head': f'清晨样本 {n} · 让变化有来处。', 'cover_url': '', 'cover_note': '',
                        'sources': '隔离测试 · 0 次网络 / 模型调用', 'failures': '', 'work': '3 条隔离测试线索', 'tiers': '离线测试',
                        'pool_head': f'样本{n} · 只显示这一期的线索', 'pool_rows': f'样本{n}的候选快照',
                        'pool_panel': f'样本{n}的编辑观点', 'pool_work': f'样本{n}的工作量',
                        'review_head': f'样本{n}的回放', 'review_time': '本机交互回归，无模型预算', 'review_fc': '无真实事实核查',
                        'stand_head': f'样本{n}的立场', 'stand_ledger': '测试样本，不发布事实', 'stand_creed': '存档与工作台分离，原文保留。',
                        'forecast': [], 'fixes': [], 'clashes': [], 'drops': [], 'decisions': []})
    return {'schema': 1, 'reports': reports, 'open': [r['id'] for r in reports], 'focus': reports[0]['id'], 'sessions': {}, 'quiet': False}

def safe_state(value):
    state = (ROOT / value).resolve()
    dev = (ROOT / '.dev').resolve()
    if state.parent != dev or not state.name.startswith('daybreak-'):
        raise ValueError('测试状态只允许位于本项目 .dev/daybreak-*，拒绝其他路径')
    return state

def prepare(args):
    state = safe_state(args.state)
    if state.exists():
        raise FileExistsError('测试目录已存在；请换一个新目录，不覆盖已有数据')
    data = fixture()
    if args.case == 'broken-session':
        data['sessions'][data['focus']] = 'unexpected persisted type'
        data['reports'].append(None)
        data['reports'][1]['rows'].extend([None, 42, 'bad row', {'summary': 'missing title'}])
        data['reports'][1]['whys'].append(42)
    elif args.case == 'paused-reader':
        row = data['reports'][0]['rows'][0]
        data['sessions'][data['focus']] = {'tab': 'story', 'row': row, 'title': row['title'], 'sum': row['summary'],
                                         'state': 'loading', 'more': [None, {'name': '测试媒体', 'url': ''}],
                                         'comments': [None, {'author': '回归', 'text': '旧请求不可串到新的日报。'}]}
    elif args.case == 'quiet':
        data['quiet'] = True
    target = state / 'morning-brief' / 'reports.json'
    if args.case == 'corrupt-json':
        target.parent.mkdir(parents=True)
        target.write_text('{"schema":1,"reports":', encoding='utf-8', newline='\n')
    else:
        json_write(target, data)
    json_write(state / 'qa-fixture.json', {'case': args.case, 'created_for': 'daybreak-regression', 'network_expected': 0})
    if args.legacy:
        bundle = state / 'legacy-bundle'
        shutil.copytree(ROOT / 'my-entry' / 'morning-brief' / 'bundle', bundle)
        shutil.copyfile(ROOT / '.dev' / 'round43-main-before.splash', bundle / 'main.splash')
        print('LEGACY_BUNDLE', str(bundle))
    print('STATE', str(state), 'CASE', args.case)

class Bridge:
    def __init__(self, port):
        self.base = f'http://127.0.0.1:{port}'
        self.events = []

    def get(self, route, **params):
        query = '?' + urllib.parse.urlencode(params) if params else ''
        with urllib.request.urlopen(self.base + route + query, timeout=15) as response:
            raw = response.read().decode('utf-8')
        return json.loads(raw)

    def nodes(self):
        return [n for n in self.get('/snap').get('s', []) if n.get('ty') != 'Splash']

    def tap(self, *, ident=None, text=None, prefix=None):
        nodes = self.nodes()
        possible = [n for n in nodes if n.get('ty') == 'Button' and n.get('r', [0, 0, 0, 0])[2] > 0]
        matches = [n for n in possible if (ident is not None and n.get('i') == ident) or
                   (text is not None and n.get('t') == text) or (prefix is not None and n.get('t', '').startswith(prefix))]
        if not matches and prefix == '展开这条线索':
            # 真实窄屏中正文在折叠线下面，像读者一样滚动，而不是点击屏幕外坐标。
            for attempt in range(5):
                raw=self.get('/snap').get('s', [])
                frame=next((n.get('r') for n in raw if n.get('ty')=='Splash'), [0,29,360,750])
                self.get('/m', k='scroll', x=frame[0]+frame[2]*0.5, y=frame[1]+frame[3]*0.72, dx=0, dy=190, wait=1)
                matches=[n for n in self.nodes() if n.get('ty')=='Button' and n.get('t','').startswith(prefix) and n.get('r',[0,0,0,0])[2]>0]
                if matches:break
        if not matches:
            raise AssertionError(f'按钮未找到：{ident or text or prefix}')
        node = matches[0]
        x, y, w, h = node['r']
        self.get('/click', x=x+w/2, y=y+h/2, wait=0.08)
        self.events.append(node.get('t', ident))
        return node

    def select_report(self, stamp):
        visible = [n.get('t') for n in self.nodes() if n.get('ty') == 'Button']
        if stamp in visible:
            return self.tap(text=stamp)
        # 手机宽度中页签可横向滚动；往期抽屉也是不依赖悬停的等价入口。
        self.tap(text='往期')
        return self.tap(prefix=stamp)

    def assert_live(self):
        nodes = self.nodes()
        assert len(nodes) > 12, f'界面节点过少：{len(nodes)}'
        assert any(n.get('ty') == 'Button' and n.get('t') == '往期' for n in nodes), '日报工具栏丢失'
        assert not any(n.get('i') == 'cg_layer' for n in nodes), '入场遮罩没有退出'
        return nodes

    def text(self, ident):
        return next((n.get('t', '') for n in self.nodes() if n.get('i') == ident), '')

    def screenshot(self, path):
        result = self.get('/g', scale=1)
        assert result.get('png'), result
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(result['png'], path)
        return result

    def errors(self):
        return [line for line in self.get('/log', n=300).get('l', []) if '[E]' in line or 'panicked' in line.lower()]

def check(args):
    state = safe_state(args.state)
    marker = json.loads((state / 'qa-fixture.json').read_text(encoding='utf-8'))
    b = Bridge(args.port)
    nodes = b.assert_live()
    case = marker['case']
    if case == 'corrupt-json':
        assert any(n.get('i') == 'home_title' for n in nodes), '损坏存档没有回到工作台'
    else:
        # 不能把被 ScrollXView 裁切的页签误判成丢失：用可点按的档案入口验证。
        b.tap(text='往期')
        labels = [n.get('t', '') for n in b.nodes() if n.get('ty') == 'Button']
        assert any(t.startswith('10/12 08:10') for t in labels), '第一份有效日报被丢掉'
        assert any(t.startswith('10/13 08:10') for t in labels), '第二份有效日报被丢掉'
        b.tap(text='往期')
        if case == 'broken-session':
            assert any('样本1' in n.get('t','') for n in nodes), '会话损坏时正文没有恢复'
        if case == 'paused-reader':
            assert '样本1' in b.text('story_title'), '中断前的阅读正文丢失'
            assert '旧请求' in b.text('story_state'), '未给中断的请求提供恢复说明'
        # 跨日报 / 跨栏目 / 阅读前后条：全程使用空链接的离线样本。
        b.select_report('10/12 08:10')
        if b.text('story_title') and case == 'paused-reader':
            b.tap(ident='tab_front_off')
        b.tap(prefix='展开这条线索')
        first_title=b.text('story_title')
        assert '样本1' in first_title, '打开了错误日报的新闻'
        b.select_report('10/13 08:10')
        b.tap(ident='tab_pool_off')
        assert '样本2' in b.text('pool_head'), '栏目数据串到了其他日报'
        b.select_report('10/12 08:10')
        assert b.text('story_title') == first_title, '独立日报的阅读位置未恢复'
        for i in range(args.cycles):
            b.tap(ident='tab_pool_off')
            b.tap(ident='tab_review_off')
            b.tap(ident='tab_stand_off')
            b.tap(ident='tab_front_off')
            b.assert_live()
        # 最后停在复盘，等待防抖落盘；不先切走这份日报。
        b.tap(ident='tab_review_off')
        time.sleep(0.6)
        saved=json.loads((state/'morning-brief'/'reports.json').read_text(encoding='utf-8'))
        assert saved['sessions']['qa-issue-1']['tab'] == 'review', '当前栏目未及时保存'
        b.screenshot(state/'proof-desktop.png')
    errors=b.errors()
    assert not errors, errors[:8]
    result={'case':case,'passed':True,'clicks':len(b.events),'cycles':args.cycles,'nodes':len(b.nodes()),'runtime_errors':errors}
    json_write(state/'qa-result.json',result)
    print(json.dumps(result,ensure_ascii=False))

def main():
    parser=argparse.ArgumentParser(description='隔离目录中的晨光档案回归，不操作真实存档')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--state',required=True)
    p.add_argument('--case',choices=['valid','broken-session','paused-reader','quiet','corrupt-json'],default='valid')
    p.add_argument('--legacy',action='store_true');p.set_defaults(func=prepare)
    p=sub.add_parser('check');p.add_argument('--state',required=True);p.add_argument('--port',type=int,required=True)
    p.add_argument('--cycles',type=int,default=12);p.set_defaults(func=check)
    args=parser.parse_args();args.func(args)

if __name__=='__main__':
    main()
