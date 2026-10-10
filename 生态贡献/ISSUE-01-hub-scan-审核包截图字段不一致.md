# ISSUE-01 · `hub scan` 的审核包里，截图字段和 listing 里的截图对不上

**上报对象**：`hub`（OctoSense-App-Hub / `crates/app-hub`）
**核实时的 app-hub 提交**：`a15580cbdcc734bd6387ad89f43e371a5155c321`
**核实时的 hub 二进制**：本机自建 `hub`（`hub --help` 列出的子命令：`keygen / pubkey / certify / stamp / sign-manifest / check / publish / withdraw / remove / scan / verify`）
**严重度**：中（不影响出包，影响**审阅方与自动化审阅**读到的信息）
**状态**：未修复，本轮已按现状绕过并留存证据

---

## 一句话

`hub scan <bundle> --packet <out.json>` 产出的审核包里，**顶层的 `screenshots` 是空数组 `[]`**，而**同一份 JSON 里 `listing.screenshots` 正确列出了四张真实存在的截图**。任何只读顶层 `screenshots` 的消费者（自动审阅脚本、AI 审阅、人工先扫一眼 JSON 的维护者）都会得出「这个应用一张截图都没交」的结论。

---

## 复现步骤

```bash
# 1. 取一个带有四张截图的 bundle（截图路径写在 listing.json 里）
$ ls bundle/screenshots/
01-intent.png  02-plan.png  03-done.png  04-story.png

$ python -c "import json;print(json.load(open('bundle/listing.json'))['screenshots'])"
['screenshots/01-intent.png', 'screenshots/02-plan.png', 'screenshots/03-done.png', 'screenshots/04-story.png']

# 2. 跑扫描，把审核包落盘
$ hub scan bundle --packet build/review.json

# 3. 对比两个字段
$ python -c "
import json
d = json.load(open('build/review.json'))
print('根 screenshots      =', d['screenshots'])
print('listing.screenshots =', d['listing']['screenshots'])
"
根 screenshots      = []
listing.screenshots = ['screenshots/01-intent.png', 'screenshots/02-plan.png', 'screenshots/03-done.png', 'screenshots/04-story.png']
```

四张 PNG 都真实存在、都在 `bundle/` 内、都被 `hub check` 接受（`hub check --allow-unsigned` 输出 `PASSED`）。

---

## 观察到的审核包结构

顶层键（`build/review.json`，约 218 KB）：

```
app_id, card_data, card_source, entry, grants, listing, manifest, questions, schema, screenshots, version
```

其中：

| 字段 | 值 |
|---|---|
| `screenshots` | `[]`（空） |
| `listing.screenshots` | 4 个真实路径 |
| `questions` | 7 条审核员必答问题（正常） |
| `grants` | 4 条（正常） |

也就是说，同一个事实在两个字段里给了两种答案，且**默认被读到的那一个（顶层、名字更短、更显眼）是错的那个**。

---

## 为什么这值得修（而不是「读的人自己当心」）

1. **`scan` 的产物就是给审阅方读的**，而审阅方里越来越多是脚本或模型。字段名 `screenshots` 在顶层，语义上就是「这份审核里的截图」，空数组是一个**合法且明确的断言**：没有截图。这不是缺字段（缺字段还能判断为未知），而是**给了错误的确定值**。
2. **本应用已经因此吃过一次亏**：初赛阶段的自动检查把「截图缺失」当成材料不全。事后再拿 `listing.screenshots` 去解释，沟通成本远高于一次修字段。
3. 空数组还会让审计方产生**反向怀疑**：既然 `listing` 里有、顶层没有，那到底哪一份是权威的？多来源不一致比单一来源缺失更伤可信度。

---

## 修复建议（按侵入性从小到大）

1. **最小改动（推荐）**：`scan` 写包时，若顶层 `screenshots` 为空而 `listing.screenshots` 非空，就把 `listing.screenshots` 的内容复制到顶层；两者本来就是同一事实，没有理由不一致。
2. **或者**：干脆**删掉顶层 `screenshots` 字段**，只保留 `listing.screenshots`，让「截图在哪」只有一个答案。
3. **如果顶层 `screenshots` 另有含义**（比如它表示「扫描器自己拍下来的运行时截图」，与发布方随包提供的宣传截图不是一回事），那就改名，例如 `captured_screenshots` / `runtime_captures`，并在 `--help` 与文档里写清两者区别。当前的命名让人无法区分这两种可能。
4. 无论选哪条，建议在 `scan` 的输出里加**一条一致性断言**并在 CI 里跑：`screenshots` 与 `listing.screenshots` 要么都空，要么指向同一组文件；不一致就报错而不是静默写出。

---

## 本轮应用的绕过方式（可复核）

- 不依赖顶层 `screenshots` 字段，改从 `listing.screenshots` 取；四张截图同时在仓库 README、`review/ANSWERS.md` 附件清单与提交 issue 正文里各列一遍，保证任何一条路径都能查到。
- 证据文件：`build/review.json`（`hub scan` 原始产物，未手改）。
