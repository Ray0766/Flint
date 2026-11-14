# GATE1-REAL · trace

**卡**：`DEC-057` 授权的那一跑——⑥热点分析的出口。
**结果**：verified · 1 cycle · 判据 28 条全绿 · **`cluster_verdicts` 0 → 2 行**。

## 边界先做成代码，再谈跑

`DEC-057` 给了四条边界。**一条都没有靠「我记得」**——
`fixtures/_gate1_real.py` 把它们做成了三道拦得住的闸：

| 闸 | 怎么拦 | 阴性对照实测 |
|---|---|---|
| 授权 | `authorised_by` 必须**逐字**等于 `DEC-057`，默认 `None` | `None` / `""` / `DEC-052` / `dec-057` / `DEC-0570` 全部 `NotAuthorised` |
| 域名 | 后缀匹配落在**点边界**上 | `github.com.evil.example` 拒 · `trends.google.com`（`DEC-052` 的域）拒 |
| 额度 | ≤40 发，**数盘上的回执**不是内存计数器 | 第 41 发抛 `BudgetExhausted`，不重试 |

三道闸**在发出去之前**判（判据用 MockTransport 证明域外那一发根本没到内层）——
闸装在事后就不是闸。

> 额度为什么数盘上：进程重起一次内存计数器归零，**而授权不会跟着归零**。

## 烧额度之前先离线数了一次

`_plan_queries` 离线跑：8 条 query × 2 源 = **预估 16 发**。额度 40，够一次跑加一次重试。
**实测 28 发**——差额的原因见下，那是这一跑最有价值的产出之一。

## 那一跑

```
提交    POST /projects/proj-gate1real/analysis {topic_id, keywords, budget_cny}
        → 200 job-4c558f32-f8a2-4a25-9215-f76c6781ff91
跑      run_gate1(..., topic_id="topic-gate1real")  经录制闸
        28s · plan → retrieve → judge → validate
网络    28 发（额度 40，剩 12）· 全部 200 · 全部落 fixtures/_probe/gate1/
模型    LocalProvider → 本机 qwen3.6:35b-a3b（免费本地档，一个 key 都没读）
```

**worker 先停掉了再跑**：它用的是**没有录制闸**的客户端，
让它抢走这一跑就是一次边界外的真实请求。作业照旧经真提交端点建（job 行是真的），
只是由我在录制闸里执行——`run_gate1(...)` 与 `_gate1_handler` 调的是同一个函数。

## 三条出口逐条核

| 出口 | 实测 |
|---|---|
| `cluster_verdicts` 至少多一行 | **0 → 2 行**（`c-20260810-000` · `c-20260810-002`，同一个 job） |
| `GET /clusters/{id}/verdict` 取得回来 | 200，`all_satisfied: ["D_insufficient"]`，竞品含 `Sentdex/BCI` |
| 分析屏显示判定 | 屏上写「**Gate① 判定 · D_insufficient**」，不再是「还没有判定」（截图在本轮回复里） |

判定是 **D_insufficient（证据不足）**、关键引用 0 条。
**那不是失败，那是一次诚实的判定**：真实证据不足以支撑 A/B/C，引擎照实说 D。
一个在证据不足时仍给出 A 的引擎才是坏的。

## 这一跑最值钱的两个发现（各开一单）

### 一、每条 query 都去取了两遍

28 发里**只有 13 个不同 URL**，每个打了 2 遍（有一个 4 遍）。
根因：`gate1.py` 在两处各调一次 searcher（`:429` 与 `:441`），
两处要的是同一批文档，而 searcher 自己不缓存。

**一次分析的网络开销是它需要的两倍。**
单 `docs/blocked/GATE1-FETCHES-EVERY-QUERY-TWICE.md`——
NEVER 顺手加一层缓存了事：缓存会把「取了两次」变成「看起来取了一次」，
而两处各自要什么这件事仍然没人说得清。

### 二、GitHub 免登录搜索每分钟只有 10 发

真响应头逐字：`x-ratelimit-limit: 10`，这一跑用掉 4（`remaining` 9→6）。

这是 **`K1-02`（拿不到数据源令牌）第一份真实证据**——
在此之前那张单说的是「未认证的额度是上游随时可以收紧的」，今天有了数字。
一次 plan 有 8 条 query；重复取数修好、且每条都落到 github 的话，
一次分析就是 8 发，**一分钟只够跑一次**，两个人同时点第二个人拿 403。
单 `docs/blocked/GITHUB-UNAUTH-SEARCH-IS-10-PER-MINUTE.md`，列了三条路，倾向乙（配 token），
而 token 是凭据，**本卡 NEVER 自行读取或存放任何凭据**。

## 种数据踩的一处

`topics.why_now` 是 `jsonb` 且形状是 `{claim, evidences[], speculative}`，
我第一版塞了一个 list → 提交端点 500（`TypeError: list indices must be integers`）。
**我的种数据错，不是产品缺陷**——照库里既有那一行的形状改好即通过。

## 夹具与判据

`fixtures/gate1/real-2026-08-11.json`：28 发去重成 **13 条**真响应
（github 2 · arxiv 11），另有 `.provenance.json` 记着它从哪一跑来的、
真实请求几发、留痕在哪——**没有出处的夹具，下一个人分不出它是录来的还是编的**。

`tests/v041/test_gate1_real.py` **一发真实请求都不发**（`DEC-057` 逐字 + `S2-7`）：
三道闸各有阴性对照 · 留痕齐且没超额 · 真响应离线重放解析得动 ·
读端点 NEVER import 生成通道 · 录制器里 NEVER 出现调度器
（一个能自己再跑一次的录制器，就是把「一次授权」变成「长期授权」的东西）。

> 判据第一版有一条红在「读端点 import 了 `flint.jobs`」——
> 而那个文件的文件头**正是在解释它为什么不 import 生成通道**。
> 改成先剥 docstring 与注释再扫。**本仓这一坑第八次**。
