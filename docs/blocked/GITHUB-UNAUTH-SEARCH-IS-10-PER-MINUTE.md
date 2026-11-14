# GitHub 免登录搜索每分钟只有 10 发

**状态** open · 2026-08-11 · `GATE1-REAL`

## 实测（`DEC-057` 那一跑，真响应头）

```
x-ratelimit-limit: 10
x-ratelimit-remaining: 9 → 8 → 7 → 6
```

那一跑只打了 4 发 github（因为 `GATE1-FETCHES-EVERY-QUERY-TWICE` 之外，
plan 里落到 github 的 query 本来就少），**用掉了这一分钟额度的四成**。

## 为什么这条要单独记

这是 `K1-02`（拿不到数据源令牌）**第一份真实证据**。
在此之前那张单说的是「未认证的额度与稳定性都是上游随时可以收紧的」——
今天有了数字：**10 发/分钟**。

一次分析的 plan 有 8 条 query。若两处重复取数那件事修好、
且每条 query 都落到 github，一次分析就是 8 发——**一分钟只够跑一次**。
两个人同时点一下分析，第二个人拿到的是 403。

## 三条路（owner 定）

| | 做法 | 代价 |
|---|---|---|
| 甲 | 保持免登录 | 单用户能跑，多用户或大 plan 必撞；撞了是 403，`resilient=True` 会降级成「只有 arxiv」 |
| 乙 | 配一个 GitHub token | 额度升到 30 发/分钟（搜索 API 认证后）。**token 是凭据**，属 owner 人审节点 |
| 丙 | 把 github 那一路换成不限流的取数方式 | 要重做 searcher 的一条腿 |

**倾向乙**，但那要 owner 给一个 token 并决定它存在哪——
本卡 NEVER 自行读取或存放任何凭据。
