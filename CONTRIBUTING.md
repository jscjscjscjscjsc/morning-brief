# 贡献指南（给想改这个项目的人）

> AI Agent 请先读 [`AGENTS.md`](AGENTS.md)；这里给的是人类最短路径。

## 一句话

**不用申请成为成员，不用等任何人批准。** fork（或直接开分支）→ 推 PR → 语法体检变绿 → **自动合并**。

## 最短流程

```bash
# 1) 拿到代码：fork 后 clone 你自己的 fork；或者有权限就直接 clone 本仓库
git clone <你的 fork 或本仓库地址>
cd morning-brief

# 2) 开分支（一个分支只做一轮的事）
git checkout -b round-30/你的主题

# 3) 改代码 + 自查
python tools/brace.py            # 语法体检，改了 main.splash 必做

# 4) 提交推送
git add -A
git commit -m "第30轮：做了什么"
git push -u origin round-30/你的主题

# 5) 在 GitHub 上开 Pull Request（模板会自动带出来）
```

## 会发生什么

| 情况 | 结果 |
| --- | --- |
| 语法体检**变绿** | `auto-merge.yml` 自动把你的 PR squash 合并进 master，**没人需要点按钮** |
| 语法体检**变红** | 机器人在 PR 下留言指出问题；修好再 push 会自动重跑 |
| 你的改动动了 `.github/` | **不会自动合并**——工作流文件能提权，需维护者人工过目（机器人会留言说明） |

## 提交前请自查

- [ ] `python tools/brace.py` 通过
- [ ] 实机跑过新功能，截图存到 `my-entry/evidence/`
- [ ] 没破坏既有功能 —— 尤其 **「联网必须用户明确批准」** 这条底线不能破
- [ ] 写了 `项目复盘/日期_第N轮_主题.md`，并把 `进度交接_第N+1轮前.md` 更新到下一轮
- [ ] 若改过 bundle 内容：上传官方 hub 前需要重新 `hub stamp` + `hub sign-manifest`
      （**本地开发保持未签名**，否则 card-host 起不来）

## 改代码前必读

- [`AGENTS.md`](AGENTS.md) —— 背景、技术栈、**splash 语法红线**（踩过就会崩的那些坑）
- [`进度交接_第30轮前.md`](进度交接_第30轮前.md) —— 当前进度与操作手册
- [`07_官方仓库下载说明.md`](07_官方仓库下载说明.md) —— 官方运行环境怎么下（本仓库不含）
