import io
import json

p = 'listing.json'
s = io.open(p, encoding='utf-8').read()

reps = []

# 1) 版本说明：初赛版本 → 复赛版本 v0.2.0
old_rn = '"release_notes": "初赛版本：'
assert s.count(old_rn) == 1, ('release_notes anchor', s.count(old_rn))
reps.append((old_rn, '"release_notes": "复赛版本 v0.2.0：'))

# 2) 版本说明结尾补上本轮新增能力，并点明走的是官方 model.complete
old_tail = '→ 阅读页（摘要 / AI 解读 / 线索时间轴 / 追问信）。"'
assert s.count(old_tail) == 1, ('tail anchor', s.count(old_tail))
new_tail = (
    '→ 阅读页（摘要 / AI 解读 / 线索时间轴 / 追问信）。'
    '本轮新增：信源太薄时主编可拒刊（「今日休刊」，读者可一键否决）、'
    '出报把本期硬事实记进本机台账并在下一期自动对账与更正、同期候选口径互校、'
    '出报链路留痕可回放、编辑部宪法带版本号。'
    '所有模型调用走官方 model.complete —— 由宿主挑模型、管预算，应用看不到也拿不到密钥。"'
)
reps.append((old_tail, new_tail))

# 3) 语音承诺：补上“没有语音服务时”的边界，避免过度承诺
old_v1 = '常驻 AI 主编能用一句话操作整个程序，能听你说话、也能开口回答。'
assert s.count(old_v1) == 1, ('voice claim 1', s.count(old_v1))
reps.append((
    old_v1,
    '常驻 AI 主编能用一句话操作整个程序；设备提供语音服务时还能听你说话、也能开口回答，'
    '没有语音服务时全程打字、其余功能不受影响。',
))

old_v2 = '语音已升级为分段朗读：一段一段念、显示念到第几段、随时插话会停下并保留断点。'
assert s.count(old_v2) == 1, ('voice claim 2', s.count(old_v2))
reps.append((
    old_v2,
    '语音在有语音服务的宿主上支持分段朗读：一段一段念、显示念到第几段、随时插话会停下并保留断点；'
    '宿主没有语音服务时每一步都回一行状态提示，不静默失败。',
))

for a, b in reps:
    s = s.replace(a, b)

json.loads(s)  # 必须是合法 JSON 才写回
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('listing.json ok; bytes', len(s.encode('utf-8')))
