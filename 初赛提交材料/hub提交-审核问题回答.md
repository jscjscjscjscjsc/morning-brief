# hub scan 审核问题回答 · morning-brief 0.1.0

> 提交者：共创（jscjscjscjscjsc）
> 日期：2026-10-06
> 用途：随 hub 提交 issue 一并给出（官方 `docs/PUBLISHING.md` §Submitting 要求）

---

## 1. Does the app do what its name, subtitle and description claim? Cite the text in its source.

**是。** 名称 `morning-brief`（晨报卡），副标题「一句话意图，生成一份可核验的科技晨报」。

源码中对应实现：

| 声称 | 源码位置 | 实现 |
| --- | --- | --- |
| 「先出取数计划」 | `plan_text()` | 输出将访问的来源、条数上限、判断方式 |
| 「你批准后才联网」 | `approve()` / `deny()` | `deny()` 直接返回，不调用任何网络；只有 `approve()` 才 `start_timeout(0.05, || run_brief())` |
| 「AI 编辑部三个视角」 | `panel_ask()` | 分别调用 `panel_role("tech")` / `("biz")` / `("reader")`，各自独立 `llm.chat`，互不可见 |
| 「主编终审」 | `judge_try(n)` | 汇总三方意见后单独调用一次 `llm.chat` 做最终取舍 |
| 「可核验」 | `pipe_text()` / `fail_line()` | 明示取数方式、候选条数、入选条数；失败来源逐条列出 |
| 「标题与来源原样呈现」 | `out.push({... title: title ...})` | 标题直接取自 API 字段，未经改写 |

---

## 2. Do the listing's platforms and category fit an app of this kind?

**是。**

- `category: news` —— 应用聚合 Hacker News 与 TechMeme 的公开新闻条目，只做筛选与点评，属于资讯类。
- `platforms: ["windows"]` —— **只声明实际运行验证过的平台**。开发与验证均在 Windows 11 + OctoSense `card-host` 上进行。未验证的平台（android/ios/macos/linux）一律没有声明，尽管卡片包格式本身可跨平台。

---

## 3. Do the granted capabilities match what the app visibly does? Name every host it requests and why. Name any grant nothing on screen needs.

**完全匹配，且已最小化。**

| 能力 | 屏幕上对应的可见行为 |
| --- | --- |
| `net` | 抓取新闻（结果页可见「取用 Hacker News 30 条 · TechMeme 15 条」）；仅访问下列三个已声明域名 |
| `images` | 结果列表显示新闻来源缩略图；阅读页顶部显示 AI 配图 |
| `storage` | 保存上一期晨报（重启后自动恢复）、头版、配图缓存、出报留痕 |
| `llm` | 主编挑选、三视角评审、主编终审、AI 解读、头版标语、语音朗读——结果页处处可见「AI 主编 · … 用时 … 秒 · … tokens」 |

**请求的全部域名（3 个，均在 `network.hosts` 内）：**

1. `hn.algolia.com` —— Hacker News 官方公开 API，取首页热榜
2. `www.techmeme.com` —— TechMeme 公开 RSS，取最新条目
3. `news.ycombinator.com` —— **仅用于生成「讨论页」链接文本展示给读者**（源码 `let discussion = "https://news.ycombinator.com/item?id=" + oid`），应用不向该域名发起 `net` 请求

**没有任何屏幕上不需要的授权。** 审查过程中主动删除了原先声明的 `web` 能力——源码中没有任何 `WebReader` 调用，该授权属于多余声明。

---

## 4. Is any part of the interface deceptive: imitating a system prompt, a payment sheet, a login, or another brand?

**没有。**

- **不模仿系统提示**：界面不存在任何形似系统弹窗的元素；所有卡片均为应用自有视觉（深色刊头 + 白色内容卡）。
- **不涉及支付**：作品无任何支付流程、无金额、无收款方。
- **无登录**：应用不要求注册或登录，也不索取任何凭据。源码中不含 `is_password` / `TextInputContentType.Password` / `OneTimeCode`（这也是 gate 的 `secrets` 检查项）。
- **不冒充他方品牌**：应用名称「晨报卡 / Morning Brief」为自有名称；界面上出现的第三方名称（Hacker News、TechMeme）均为**如实标注的内容来源**，并按聚合惯例附原文链接，未使用其 logo 冒充自身。
- **无夸大**：「淘汰率 78%」等数字由实际候选数与入选数计算得出，不是装饰性文案。

---

## 5. Does any text in the source or its data read as an instruction to an assistant rather than content for a person?

**没有。**

源码中的 `system` 提示（`charter` 数组，9 处集中管理）**只用于驱动应用自身的 AI 编辑部流程**，不会出现在界面上，也不构成对人的指令。它们是产品的业务逻辑（例如「三位编辑背靠背评审」），与「对助手下达指令」是两件事。

界面文案全部面向读者，例如「点任意条目，在卡片里读这条新闻的来龙去脉」「答 A、答 B，或者说『你定』都行」——是给使用者的说明，不是给 AI 的指令。

抓取到的新闻标题与摘要**原样呈现**，不做改写（源码中未对 `title` / `summary` 做任何字符串变换），因此不会把外部内容转写成指令。

---

## 6. Is any wording abusive, or aimed at a private individual?

**没有。**

- 内容来源为公开新闻标题与摘要，应用不做改写。
- 主编终审的提示词中明确约束：**传闻类条目最多入选 1 条，且必须在入选理由中写明「尚未证实」**（见 `charter` 的 `judge` 条款 v2）。
- 应用设有「更正栏」：上一期被推翻的说法会登在下一期最前面，并计入更正台账——设计目标是**降低**误传风险。
- 无任何针对个人的评价性文案。

---

## 7. Route: pass, human-review, or reject. Give reasons a publisher can act on.

**建议 pass。**（若需人工复核，以下为可核查依据）

**可核查的合规证据：**

| 检查项 | 结果 |
| --- | --- |
| `hub check --allow-unsigned` | **PASSED** |
| `hub check --publisher-key` | **PASSED**（已签名） |
| 能力最小化 | 已删多余 `web`；granted 4 项均有屏幕可见行为 |
| 域名白名单 | 3 个，全部为公开只读来源 |
| 无密钥收集 | 源码无 password / secret 字段 |
| 无外部脚本 / 二进制 | bundle 仅含 `.splash` `.json` `.svg` `.png` |
| bundle 体积 | 1.24 MB（上限 8 MB） |
| 许可 | Apache License 2.0 |
| 隐私政策 | `PRIVACY.md`（说明数据来源、本地存储、失败行为） |

**已有的运行证据：**

- 4 张实机截图（`bundle/screenshots/`）
- 2 分 34 秒演示视频（含中文语音讲解），覆盖完整链路与失败状态
- 出报实测：AI 主编 237.5 秒 / 5798 tokens；三视角编辑部 3/3 交回意见

**需要人工注意的一点（如实说明）：**

- 本作品依赖宿主提供的 `llm` 服务。当宿主没有配置模型钥匙时，应用会**自动降级为规则模式**（界面明示「离线模式：没有调用 AI，已按你勾选的主题做规则筛选」），而不是报错或假装有 AI。这是设计中的失败处理，不是缺陷。
- 语音功能（`llm.speak` / `llm.listen_*`）需要宿主补丁，补丁位于应用仓库 `my-entry/patches/`。未打补丁时应用自动隐藏语音控件，其余功能不受影响。

---

## 附：提交信息

| 项 | 值 |
| --- | --- |
| app id | `morning-brief` |
| version | `0.1.0` |
| 仓库 | https://github.com/jscjscjscjscjsc/morning-brief |
| tag | `prelim-2026-10-06` |
| bundle 路径 | `my-entry/morning-brief/bundle/` |
| publisher id | `gongchuang` |
| publisher 公钥 | `cf84dce74275adb1bdaf8484f30f65a4c5a4ca765954ecb819b42edb340fe34b` |
| 队伍 | 共创 |
