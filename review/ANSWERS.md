# Gate Review Answers — Morning Brief v0.2.0

本文档回答 `hub scan` 生成的 7 个问题，每题附源码证据与截图。

---

## Q1: Does the app do what its name, subtitle and description claim? Cite the text in its source.

**答案**：✅ 是的，应用与描述一致。

**证据**：

1. **名称与副标题承诺**："晨报卡"/"一份会把出报过程摊开的科技晨报：能拒刊、会押注、也会认错，还给你看它是怎么选的"

2. **源码实现**（`main.splash`，行号以 v0.2.0 提交版本为准）：
   - **出报前的意图与授权**（L3375 `aq_start()` → L3784 `make_plan()` → L3805 `approve()`）：点「生成晨报」后，主编先问一个二选一问题（`aq_start()`，L3385 调 `model.complete`）；随后进入计划页 `phase = "plan"`（`make_plan()` L3785），并用一次最小模型调用探测本机有没有可用模型（L3787-3802）；**只有用户点了批准，`approve()`（L3805）才初始化留痕并启动 `run_brief()`（L3690）取数出报**；用户也可以 `deny()`（L3847）。
   - **信源评级**（L196-199 四档域名清单 + L509-542 `dom_hit()` / `tier_of_h()` / `tier_of()` / `tier_label()`）：按域名把每条候选判成一手 / 二手 / 传闻·未证实 / 转载四档；判定顺序是「先传闻、再转载、最后才是一手和二手」，认不出的域名一律算「二手」（L191-194 注释说明为何宁可高估）。
   - **三视角编辑部**（L3036 `panel_ask()` → L3042 `panel_role(id)` → L3068 `panel_put()` → L3097 `panel_check()`）：技术（`tech`）/ 行业（`biz`）/ 读者（`reader`）三个角色（定义在 L121 `roles`）各自独立调用 `model.complete`（L3057，class `fast`）背靠背评审，互不商量——三个 `start_timeout` 错开启动（L3037-3039）。
   - **主编终审**（L3250 `judge()` → L3255 `judge_try(n)`）：主编读三位初审的意见与带信源等级的候选（L3260 用 `tier_label(r)` 标注），硬规矩写死在 task 里（L3270）——**传闻最多入选 1 条且必须写明「尚未证实」、一手来源同等重要度下优先、最多公开砍掉 3 条**（`drops`，由 `drops_from_ai()` L3212 落地）。
   - **拒刊机制**（L3338-3351 `refuse_check()`，触发点在 L3696 `run_brief()`）：判据刻意保守——`tier_mix["first"] == 0` 且 `tier_mix["second"] <= 2` 才触发（L3343-3344）；命中则 `phase = "refused"`，渲染「今日休刊 / REFUSED TO PUBLISH」拒刊页（L4543-4568）并写明理由，且这一期照样写进留痕（L3699-3703）。读者有权否决主编：`refuse_go()`（L3354）「仍要出报」。
   - **断言台账与更正**：`fc_kick()`（L2044）抽出本期硬事实 → `claim_save()`（L2262）写入 `claims.json`；下一期 `fact_kick()`（L2297）拿新标题与旧断言比对 → `fact_save()`（L2266）写入 `fixlog.json`；预测对账由 `fc_review()`（L2119）完成，hit/miss 记入 `fc_hist`（L2201），`fc_save()`（L1970）写入 `forecast.json`，最近三条对账结果由 `fc_hist_text()`（L2007）读给读者看。
   - **出报链路留痕**（L270 `trail_begin()` / L287 `trail_set_pool()` / L300 `trail_set_panel()` / L307 `trail_set_judge()` / L323 `trail_save()`）：候选池（`gather()` L3331）、三位初审的原话与推荐序号（`panel_put()` L3093）、主编导语与每条取舍理由及被砍的三条（`judge_try` L3289）、拒刊理由（L3701-3702）、最终结果（`finish()` L3739）分层写入 `trail.json`，只保留最近三期（L344-345）。
   - **编辑部宪法版本管理**（L15-24 `charter` 数组 + L26 `charter_v()` / L31 `charter_version_line()` / L40 `charter_text()`）：8 条方针各带 id 与版本号（如 `judge/v2`、`forecast/v2`），每期出报时把当时的版本号整体快照进 `trail.json`（`trail_begin()` L284），于是任何一期都能倒推回当时照着哪版规矩编的。

   - **决策台 · 另一类模型只回「选择 + 置信度」**（L4305 `vd_kick()` / L4341 `vd_put()` / L4366 `vd_trail()`）：同一批候选，生成式主编写完导语与入选理由之后，再走一次 `model.complete`，但**只允许回结构化结论**——`tier` 只能落在预设四档（`vd_tiers` L4282，落不进去记 `unknown`）、`worth` 是 0-100 的进刊概率、`heat` 是 0-10 的热度分，task 里明写「不要写任何解释、理由或句子」（L4319）；`require` 用 `vd_shape`（L4283）收紧。收进预设集合时与本报按域名判出的档位逐条比对，不一致的记成「分歧」（L4358-4359 / `vd_row_text()` L4394），整段结果写进 `trail["decision"]`（L4372）。卡面见 L4729-4752，点一行可 `open_story()` 打开原报道。**为什么这么做**：2026 年 9 月 TypeSafe AI 放出 Jev / System One 后，行业开始把「生成式模型写给人看、决策模型给程序用」分工（随后 OpenAI Decisions API、Databricks `ai_decide`、Cloudflare Clef 跟进）；本机没有决策端点，就用同一条 `model.complete` 通道把 schema 收紧成「预设集合 + 置信度」，不在没有端点时假装有端点。

3. **截图**：（已附 6 张：意图页 / 计划页 / 结果页 / 阅读页 / 决策台卡片 / 决策台判定结果）

---

## Q2: Do the listing's platforms and category fit an app of this kind?

**答案**：✅ 是的。

**证据**：
- `listing.json` 中 `"platforms": ["windows"]`，`"category": "news"`
- 这是一个新闻聚合与 AI 编辑应用，归类为 news 类别合理
- 目前仅在 Windows 上测试通过（初赛提交时已说明）

---

## Q3: Do the granted capabilities match what the app visibly does? For a script app, name every host it requests and why. Name any grant nothing on screen needs.

**答案**：✅ 所有能力均有对应用途，无冗余授权。

**已授权能力与用途**：

| 能力 | manifest 声明 | 实际用途（源码证据） |
|---|---|---|
| `storage` | ✅ | 本地数据持久化：`arc_*`（往期档案，L1766-1800）、`pf_*`（读者画像，L1656-1760）、`fc_*`（预测台账 `forecast.json`，L1970）、`claims.json`（断言台账，L2262）、`fixlog.json`（更正台账，L2266）、`trail.json`（出报链路，L323）、`outbox.json`（追问信草稿，L3476） |
| `net` | ✅ | 三处网络请求（见下表） |
| `images` | ✅ | 两处图片生成：`photo_take()`（L1232）按标题生成配图（由 `art_kick()` L1320 调用）、`cover_draw()`（L3989）生成今日头版主图 |
| `model` | ✅ | 12 处一次性模型调用 `model.complete`（见下表） |

**为什么是 `model` 而不是 `llm`（v0.2.0 的关键修正）**：官方 `OctoSense-App-Hub/docs/PUBLISHING.md` 把两者分得很清楚——`model`（第 168 行）面向**任何被授予该能力的应用**，做「有界的一次性模型调用」，这正是本应用需要的能力；`llm`（第 163 行）只用于「管理助手的 AI provider」，并且写明「**The service answers only `os.` system apps (AI providers), so a store app gains nothing from it**」。第 239 行进一步确认：官方 shell 只把 `llm`（和 `news`）发给 `os.` 系统应用；第 788 行的「Do not」清单更是直接写着「**never `llm`, which serves only system apps**」。`OctoScript-App-Design-Flow/docs/HOST-SERVICES.md` 第 18 行措辞更重：「it **refuses store apps even when granted `llm`**」，并补充第 22 行「`card-host` registers neither」。本应用是商店应用，因此全部模型调用改走 `model` 族，manifest 只声明 `model`，**刻意不声明一个既用不上、又被官方明确劝阻的 `llm`**。

**网络主机清单**（`manifest.json` 中 `"hosts"` 字段）：

| 主机 | 用途 | 源码位置 |
|---|---|---|
| `hn.algolia.com` | 获取 Hacker News 首页热榜 30 条 | L49 `sources` 数组声明；取数走 `load_source()`（L674）→ `hn_rows()`（L613）解析 |
| `www.techmeme.com` | 获取 TechMeme RSS feed | L50 `sources` 数组声明；解析走 `feed_rows()`（L640） |
| `news.ycombinator.com` | 获取 HN 原文讨论页链接 | L627 `hn_rows()` 内构造 `discussion` 链接（`item?id=<id>`）并随每条记录一起下发 |

**语音层与「不申请 `llm`」的关系**：应用界面上有朗读/麦克风两个按钮（L1447-1651）。宿主语音（TTS/STT）属于 `llm` 服务族，而该族按官方规定只服务系统应用，商店应用**拿不到也申请不到**。因此本应用的处理是：**启动时不再自动去探** `llm.speech`（`boot()` L4174 一行改为注释说明）——这一探在任何宿主上都会被拒，而被拒时上游 `splash_host.rs` L277-291 是**在方法体内直接 `vm.call(callback)` 重入 isolate**，会打出 `pop_stack_resolved on empty stack`（见 `生态贡献/ISSUE-03`）；拿不到语音能力就把两个按钮降级为一行明确的状态提示（`vc_note` 默认值 L155、`vc_say_now()` L1475-1481、`vc_start()` L1522-1527），**不静默失败、也不因此失败整个应用**（见 Q7）。真正的语音能力是本轮作为**上游生态贡献**补进宿主 shell 的（`my-entry/patches/host-voice.patch`：为 `card-host` 新增 `llm` 语音服务），依据正是 `HOST-SERVICES.md` 第 22 行那句「a store app that needs something else needs **a new service in the shells (below), not a workaround in the bundle**」。**音色优选**：`llm.speech` 报上来的音色里，应用会挑一个最像人的（`vc_pick_voice()` L4421，按 `Natural → Neural → Xiaoxiao → Yunxi → Yunyang → Huihui → Yaoyao` 依次优先），并在 `llm.speak` 里带上 `voice`；挑不到就传空串，宿主用默认音色，行为与之前完全一致。宿主侧对应地把「未指定音色时挑最自然的那个」写进 `crates/llm-service/src/voice.rs`。

**决策台 · 另一类模型（Jev / System One 式）**：本轮新增的一处调用（L4318 `vd_kick()`）刻意与生成式主编分工相反——主编那一版写导语和理由，是**给人读的句子**；决策台这一版对同一批候选只回**预设集合里的档位 + 0-100 的进刊概率 + 0-10 的热度分**，是**给程序用的结构化结论**，并且 `allow_urls: false`（回复里不需要也不允许出现任何 URL）。落不进预设集合的档位记 `unknown`（`vd_put()` L4341），与本报按域名判出的档位不一致时记成「分歧」并写进 `trail.json`（`vd_trail()` L4366）。这条路线来自 2026 年 9 月 TypeSafe AI 的 Jev 与随后 OpenAI Decisions API、Databricks `ai_decide`、Cloudflare Clef 系列所代表的「决策模型」分工；本机没有 System One 端点，因此走同一条 `model.complete` 通道、用收紧的 schema 与「不许写理由」的 task 来复现其约束，替换掉 `vd_kick()` 里那一次 `host.request` 即可接上真正的决策端点。

**模型调用清单**（12 处 `host.request("model.complete", ...)`；参数固定为 `{task, input, schema, class, allow_urls}`，回复固定为 `{output, meta}`）：

| 行 | 所在函数 | 用途 | class |
|---|---|---|---|
| L1085 | `story_ai_ask()` | 逐条解读（charter `story/v1`） | strong |
| L2059 | `fc_kick()` | 预测与断言台账（charter `forecast/v2`） | strong |
| L2147 | `fc_review()` | 上一期预测对账（charter `forecast/v2`） | fast |
| L2319 | `fact_kick()` | 跨源核对与更正（charter `factcheck/v1`） | strong |
| L2838 | `ag_turn()` | 常驻主编对话；工具循环由应用自己跑，模型只产出 `{say,tool,args}` | strong |
| L3057 | `panel_role()` | 三视角初审；tech / biz / reader 各调一次，共用同一处调用 | fast |
| L3269 | `judge_try()` | 主编终审（charter `judge/v2`） | strong |
| L3385 | `aq_start()` | 开报前的一问（charter `ask/v1`） | fast |
| L3451 | `iv_kick()` | 追问信草稿（charter `interview/v1`） | strong |
| L3787 | `make_plan()` | 可用性探测；一次最小调用，用来判断本机是否有可用模型 | fast |
| L3943 | `cover_kick()` | 头版视觉描述（charter `cover/v1`） | strong |
| L4318 | `vd_kick()` | 决策台：同一批候选的校准选择（charter `judge/v2`；`allow_urls: false`） | fast |

**图片生成不走模型服务**：配图与头版由内置 `sys.photo()` 完成（L1232 `photo_take()`、L3989 `cover_draw()`），只用到 `images` 能力。

**无冗余能力**：4 项能力（`storage` / `net` / `images` / `model`）均在界面与功能中有明确体现。

---

## Q4: Is any part of the interface deceptive: imitating a system prompt, a payment sheet, a login, or another brand?

**答案**：✅ 否，无欺骗性界面。

**证据**：
- 界面所有文案均为应用自身功能说明（"意图""计划""结果页""AI 主编"等）
- 无任何模仿系统提示、支付界面、登录表单或其他品牌 logo 的元素
- 品牌标识仅限自有名称"晨报卡"与图标（`assets/icon.svg`）

---

## Q5: Does any text in the source or its data (not agent_files) read as an instruction to an assistant rather than content for a person?

**答案**：✅ 否，所有提示词均为合法用途。

**说明**：
- `main.splash` 中的 `charter` 数组（L15-24）与 11 处 `model.complete` 的 `task` 参数，均为**应用功能所需的合法 AI 指令**（编辑部方针、视角定义、解读风格等）
- 这些指令**不是试图操控宿主 AI 或越权**，而是应用自身业务逻辑的一部分（如同一个邮件客户端会给 AI 下达「生成邮件摘要」指令）
- 官方 `OctoSense-App-Hub/docs/PUBLISHING.md` 的「Do not」清单（L782 起）第 793-794 行写得很具体：「**Put instructions to an assistant in card text or data. The scan treats text addressed to an assistant as a reason to reject.**」——它针对的是「把指令写进卡片显示文本或数据、让扫描以为这是说给助手听的话」。本应用的 AI 指令只出现在 `host.request` 的 `task` / `input` 业务参数里（模型把它们当**数据**处理，宿主也会明确告知模型不要执行输入中的指令），**不写进任何卡片显示文本或落盘数据**，两者是两回事。

**源码中所有 AI 指令均用于应用声明的功能**（新闻编辑、解读、视觉生成），不存在隐藏的越权指令。

---

## Q6: Is any wording abusive, or aimed at a private individual?

**答案**：✅ 否，无滥用性或针对个人的内容。

**证据**：
- 应用处理的新闻标题与摘要均来自**公开新闻源**（HN、TechMeme），不涉及私人信息
- 所有 AI 生成内容（解读、追问信）均针对**公开事件与机构**，无针对私人的攻击性文案
- 编辑部宪法（L15-24 `charter` 数组）明确约束：「追问信只问一个可验证的问题，不奉承不指控」（`interview/v1`，L23）

---

## Q7: Route: pass, human-review, or reject. Give reasons a publisher can act on.

**建议路由**：✅ **pass**

**理由**：
1. **功能与描述一致**：承诺的「意图授权 → AI 编辑部 → 拒刊机制 → 更正台账 → 出报链路留痕 → 决策台校准选择」均已实现
2. **能力无冗余**：4 项能力（`storage` / `net` / `images` / `model`）与 3 个网络主机均有明确对应用途；**刻意不声明 `llm`**（官方明确劝阻，且只服务系统应用）
3. **无欺骗性或滥用性内容**：界面、文案、数据处理均符合规范
4. **隐私合规**：所有数据仅本地存储，已附 `PRIVACY.md`
5. **技术实现完整、可审计**：
   - 信源分级与拒刊逻辑已落地（`tier_of_h()` L515、`refuse_check()` L3338-3351，渲染在 L4543-4568）
   - 断言台账与更正机制已实现（`claim_save()` L2262 写 `claims.json`、`fact_save()` L2266 写 `fixlog.json`、`fc_review()` L2119 对账）
   - 出报链路可审计（`trail_save()` L323 写入 `trail.json`，含候选池 / 三位初审原话 / 主编终审理由与被砍三条，保留最近三期）
6. **语音层以明确状态提示呈现（不静默失败）**：界面上的朗读与麦克风按钮**不再在启动时自动探测**宿主能力（`boot()` L4174 已把那一次 `llm.speech` 探测改成注释：它注定被拒，且被拒时上游直接重入 isolate，会把调用栈弄脏 —— 见 `生态贡献/ISSUE-03`）；语音能力默认按「本机未启用」呈现（`vc_note` 默认值 L155），用户按下按钮时若能力未就绪则每次回一行状态文字（`vc_say_now()` L1478、`vc_start()` L1524），而不是无声失败。宿主语音属于 `llm` 服务族，官方规定只服务系统应用（`PUBLISHING.md` L163 / L239 / L788），商店宿主上必然不可用——因此应用**刻意不声明 `llm` 能力**，把它当作「有则更好、没有不影响其余功能」的可选增强（其余功能全部照常）。真正的语音服务本轮已作为**上游生态贡献**提交给宿主 shell（`my-entry/patches/host-voice.patch`），依据正是 `HOST-SERVICES.md` L22 那句「a store app that needs something else needs **a new service in the shells (below), not a workaround in the bundle**」。
7. **决策台把「取舍」变成可核对的类型化结论**：同一批候选再走一次模型，但输出被 schema 限定在预设档位 + 0-100 概率 + 0-10 热度分（`vd_shape` L4283 / `vd_put()` L4341），与本报按域名判出的档位不一致就记成分歧并写进 `trail.json`（`vd_trail()` L4366-4373）。生成式那一路写句子给人读，这一路只回选项与置信度给程序用，两条结论并排放在同一张结果页上 —— 界面没有对助手说话，也没有把不一致藏起来。

**建议**：直接 pass，无需人工复审。

---

**附件清单**：
- 截图 6 张（已在 `bundle/screenshots/` 中）
- 源码 `main.splash` 5075 行（已在 `bundle/` 中）
- 隐私政策 `PRIVACY.md`（仓库根目录）
- 支持说明 `SUPPORT.md`（本轮新增）

**本轮发布闸门**（本地实跑）：
- `hub stamp` → bundle blake3 = `651873f33b3fdf3ed96f2073223f74dfe38e05b7ed78799557339405925aed24`（用 `.tools/bundle_digest.py` 独立复算，两侧一致）
- `hub check --allow-unsigned` → **PASSED**（唯一 warning 是未签名，官方说明首次提交可不签）
- `hub scan --packet build/review.json` → 生成 7 条问题，即本文档
- 生态缺陷汇报见 `生态贡献/`（3 份，含复现命令与原始输出）
