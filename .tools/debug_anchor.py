import io

s = io.open('listing.json', encoding='utf-8').read()

anchor = '"→ 阅读页（摘要 / AI 解读 / 线索时间轴 / 追问信）。"'
print('anchor repr:', repr(anchor))
print('anchor count:', s.count(anchor))

i = s.find('追问信')
seg = s[i - 4:i + 5]
print('file seg repr:', repr(seg))
print('file seg == anchor tail?', anchor.startswith('"→'))
for j, ch in enumerate(anchor[:12]):
    print(j, repr(ch), hex(ord(ch)))
print('---- file ----')
k = s.find('阅读页')
for j, ch in enumerate(s[k - 2:k + 10]):
    print(j, repr(ch), hex(ord(ch)))
