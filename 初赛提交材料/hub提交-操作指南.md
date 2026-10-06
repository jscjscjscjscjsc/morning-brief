# 提交到 OctoSense App Hub · 操作指南

> 依据：官方仓库 [OctoSense-org/OctoSense-App-Hub](https://github.com/OctoSense-org/OctoSense-App-Hub)
> `docs/PUBLISHING.md` §Submitting（读取版本 `78dfda5`，2026-10-06 拉取）
> 适用作品：morning-brief 0.1.0　|　队伍：共创

---

## 一、官方规定的提交方式（当前唯一路径）

官方原文：

> **The route maintainers accept now:**
> 1. Push the signed bundle to your app's public repository and tag the commit (for example `v1.0.0`).
> 2. Open an issue in [OctoSense-org/OctoSense-App-Hub](https://github.com/OctoSense-org/OctoSense-App-Hub/issues) titled `Submit <app id> <version>`.
> 3. Do not open a pull request that edits `catalog.json`, `index/` or `artifacts/`.

**要点：**

| 项 | 说明 |
| --- | --- |
| 提交位置 | **在 App Hub 仓库开 issue**（不是 PR，不是上传文件） |
| issue 标题格式 | `Submit morning-brief 0.1.0` |
| 必须提供 | 仓库 URL、tag、完整 commit SHA、bundle 路径、publisher id 与公钥（或声明 unsigned）、`hub check` 完整输出、`hub scan` 问题的回答 |
| 禁止 | 提 PR 去改 `catalog.json` / `index/` / `artifacts/`（目录未被 hub 密钥签名，商店会拒绝） |

官方还说：

> **Not yet available.** There is no separate index repository and no `octosense-org/publish-app` GitHub action. Do not add a release workflow that uses them.

即：**目前没有自动发布流水线**，只能走 issue。

---

## 二、签名：首次提交可选（重要）

官方原文：

> **Signing is optional for a first submission** and required for updates once a key is on record.

**我们的选择：首次提交不签名。**

原因（实测踩到的）：

- 官方 `card-host` 内置的签名验证器是 `RefuseAllSignatures`（`crates/card-host/src/host.rs:105`）。
- 因此**一旦 manifest 带签名，本地用 `card-host` 就跑不起来**，报
  `refused: no signature verifier is installed, so the signature from key "gongchuang" cannot be checked`
  ——即使加了 `--allow-unsigned` 也一样（该开关只影响「未签名」是否放行）。
- 而「可运行」既是初赛硬要求，也是评审复现的前提。

**结论**：仓库里的 bundle 保持**未签名**（`hub check --allow-unsigned` PASSED，且能实机运行）。
提交时向官方声明 `unsigned` 即可；等首次发布后要更新时，再用私钥签名并复用同一个 publisher id（`gongchuang`）。

> 私钥位置（不在仓库里）：`C:\Users\Admin（无密码）\.octosense-keys\morning-brief-gongchuang.key`
> 若要用签名版提交，流程是：`hub stamp` → `hub sign-manifest --key <key> --key-id gongchuang` → `hub check --publisher-key "gongchuang=<pubkey>"`。

---

## 三、提交前的完整检查清单（逐条已跑通）

```bash
export HUB=/path/to/hub
export B=my-entry/morning-brief/bundle
export KEY=$HOME/.octosense-keys/morning-brief-gongchuang.key
export PUB=$(hub pubkey "$KEY")     # cf84dce7…4b
```

| # | 命令 | 期望 | 我们的结果 |
| --- | --- | --- | --- |
| 1 | `hub stamp $B` | 写入新摘要 | ✅ `fead4b8c…95` |
| 2 | `hub check $B --allow-unsigned` | PASSED | ✅ PASSED（仅 unsigned 警告） |
| 3 | `hub scan $B --packet build/review.json` | 写出审核包，7 个问题 | ✅ 已生成，问题已逐条回答 |
| 4 | （可选）`hub sign-manifest … --key-id gongchuang` | 签名成功 | ✅ 已验证可通过 `--publisher-key` 检查 |
| 5 | `hub check $B --publisher-key "gongchuang=$PUB"` | PASSED | ✅ PASSED（签名版时） |

**逐项核对结果：**

```
morning-brief 0.1.0 — PASSED
  [warning] publisher-signature: unsigned: accountability rests on the hub alone
  grants: capabilities {"images", "llm", "net", "storage"},
          hosts {"hn.algolia.com", "news.ycombinator.com", "www.techmeme.com"},
          storage 16777216 bytes, agent none
```

---

## 四、要提交的 issue 内容（可直接复制）

**标题：**

```
Submit morning-brief 0.1.0
```

**正文：**

```markdown
App: morning-brief 0.1.0
Team: 共创 (Gongchuang)

- Repository: https://github.com/jscjscjscjscjsc/morning-brief
- Tag: prelim-2026-10-06
- Commit SHA: <填入 git rev-parse prelim-2026-10-06>
- Bundle path: my-entry/morning-brief/bundle/
- Publisher id: gongchuang
- Publisher public key: cf84dce74275adb1bdaf8484f30f65a4c5a4ca765954ecb819b42edb340fe34b
- Signature: **unsigned** (first submission; the bundle in the repository is
  unsigned on purpose so that reviewers can run it with the stock `card-host`,
  which ships `RefuseAllSignatures`)

### hub check output

<paste the full output of `hub check my-entry/morning-brief/bundle --allow-unsigned`>

### hub scan answers

<see the attached answers below / link>

Full answers: https://github.com/jscjscjscjscjsc/morning-brief/blob/prelim-2026-10-06/初赛提交材料/hub提交-审核问题回答.md
```

---

## 五、7 个审核问题（官方 hub scan 提出，已逐条回答）

完整回答见同目录 `hub提交-审核问题回答.md`。摘要：

| # | 问题 | 结论 |
| --- | --- | --- |
| 1 | 应用是否做到名称/副标题/描述所声称的？ | 是，逐条给出源码位置 |
| 2 | listing 的平台与分类是否合适？ | 是；`platforms` 只写实机验证过的 windows |
| 3 | 授权是否与可见行为相符？ | 完全相符；**主动删除了多余的 `web`**；3 个域名逐个说明用途 |
| 4 | 界面是否有欺骗性（仿系统弹窗/支付/登录/他牌）？ | 无；无登录无支付，来源如实标注 |
| 5 | 源码或数据中是否有「对 AI 的指令」而非给人看的内容？ | 无；`charter` 提示词只驱动应用自身流程，不上界面 |
| 6 | 有无辱骂或针对个人的措辞？ | 无；传闻类条目有「未证实」强制标注 |
| 7 | 路由建议 | pass（附可核查证据清单） |

---

## 六、提交后会发生什么（官方说明）

1. 维护者 checkout 该 commit，对**完全相同的字节**跑 `hub check` 和 `hub scan`。
2. 两者都过 → 维护者运行 `hub publish`，写入 `catalog.json` / `artifacts/` / `index/`，并用 hub 自己的密钥签名新目录。
3. issue 以「应用出现在哪个 catalog 序列」或「需要修的问题」关闭。
4. **首次提交或需要人工复核的扫描，会等人**。

**发布之后：**
- hub 保留自己的 bundle 副本；每个商店用内置锚点验证目录签名。
- 应用在自己的隔离区运行，只有 manifest 声明的授权；越权请求会被拒绝并告知用户。
- 已安装的应用**不会**自动更新到新版本；用户可自行选择。
- 已安装 bundle 存在应用存储之外（`<app data>/.bundles/<id>/`），应用无法写入。
- 版本可用理由撤回（withdraw）；被撤回版本的已安装副本在下次拉取目录后停止运行。

---

## 七、我们现在离提交还差什么

| 项 | 状态 |
| --- | --- |
| bundle 通过 `hub check` | ✅ PASSED |
| bundle 能实机运行（评审可复现） | ✅ 已实测 |
| `hub scan` 审核包与 7 问回答 | ✅ 已完成 |
| 仓库 public + tag | ✅ `prelim-2026-10-06` |
| 许可证 / 隐私政策 / 图标 / 截图 | ✅ 齐备 |
| 提交 issue | ⬜ 待开（可随时执行，见第四节模板） |

**说明**：初赛阶段官方明确「无需等待 Hub 上架」（见赛事 `docs/app-hub-submission.md`），
所以这份 issue 属于**提前占位**——一旦发出，就是我们正式向官方提交上架申请。
