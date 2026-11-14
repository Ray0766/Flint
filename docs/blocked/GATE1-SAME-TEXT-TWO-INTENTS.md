# 同一段检索文本被两条 intent 各问一次

**状态** open · 2026-08-11 · `GATE1-DEDUP`

## 实况

`GATE1-DEDUP` 把调用层那一层去掉之后，一次分析的往返数从 **28 → 14**。
而不同 URL 只有 **13** 个——差的那一发是这条：

```
support   / "brain-computer interface"
landscape / "brain-computer interface"
```

两条 query **intent 不同、文本相同**。`GithubArxivSearcher` 的两个 URL 构造器
（`github_search_url` / `arxiv_search_url`）**只吃 text**，
所以它们打出去的是同一个 URL——**同一个问题问了两遍**。

## 为什么没有在 `GATE1-DEDUP` 里一并解决

第一版就是按文本共享的，**而它当场把判定改了**：

`Searcher` 是一个**协议**，不是那一个实现。`flint/jobs/gate1.py#_offline_searcher`
按 `query.intent` 分支——`landscape` 回竞品清单、其余回论文。
按文本共享之后 `support` 先跑并占住那段文本，随后 `landscape` 拿到论文而不是竞品，
竞品数归零，判定 `B_red_ocean` → `C_opportunity`
（`tests/m2/test_m2_040` / `test_m2_049` 当场抓住）。

> 一个「只是少打几发网络」的改动**改变了判定结论**。
> 少打几发是省钱，改判定是产品事故——两者绝不能混在一次改动里。

所以 gate1 那一层的键改回 **query 身份**（对任何 Searcher 实现都安全）。

## 它该在哪一层解决

**在知道 URL 怎么算出来的那一层**，也就是 `GithubArxivSearcher` 自己：
只有它说得出「这两条 query 打的是同一个 URL」。gate1 那一层猜不出来，
猜错的代价刚刚已经付过一次。

难点是**记忆的作用域**：

- 记在 searcher 实例上 → `harness/run_worker.py` 的 `build_deps()` **只造一次**，
  实例活整个 worker 生命周期，跨作业、跨天复用同一份结果——那是错的；
- 记在一次分析里 → 要么 searcher 变成每跑一个新的，要么给它一个显式的
  「这一跑」句柄。**两条都是接口改动**，不在 `GATE1-DEDUP` 的范围里。

## 值多少

一次分析 **14 → 13 发**，github 那一路 **2 → 1 发**。

今天离天花板（免登录 10 发/分钟，见
`docs/blocked/GITHUB-UNAUTH-SEARCH-IS-10-PER-MINUTE.md`）还很远，
所以这一条**不急**。它值得记下来，是因为**下一个人会以为已经修干净了**。


## 它要动的是 **searcher 的实例生命周期**（owner 2026-08-11）

**NEVER 在调用点再补一层去凑那个数。** 「往返数 = 不同 URL 数」这条指标
`GATE1-DEDUP` 够不着——URL 在 searcher 内部算，那张卡的射程是调用点。
在调用点补一层，等于让 gate1 去猜 searcher 会打什么 URL，而**猜错的代价已经付过一次**
（按 `query.text` 共享 → 判定 `B_red_ocean` → `C_opportunity`）。

真正要改的是：

```
harness/run_worker.py#build_deps()   只造一次 GithubArxivSearcher
                                     → 实例活整个 worker 进程
                                     → 记在它身上的任何记忆都会跨作业、跨天
```

记忆的作用域 MUST 是**一次分析**：开始时开一个、结束时丢掉。

## 收口卡：`SEARCHER-SCOPE`（下一批）

owner 2026-08-11 定：并进下一批，与下面这条一并收口。

### 另一半：`now` 是定死的时间戳，出处日期在说假话

steward 读码确认：`build_deps()` 构造 `GithubArxivSearcher` 时传的 `now` 是
**一个定死的时间戳**（不是 callable），而 `flint/evidence/search.py:91,116`
拿它写 `meta.fetched_at`——

> **worker 开着三天，今天抓的文档在出处里写的是三天前。**

同一个文件里 `design_generate_deps` 传的是 `lambda: datetime.now(UTC)`——
**两种写法并排放着**。

### 两件一件都不许省（owner 逐字）

**① 记忆的作用域 MUST 是一次分析，NEVER 是 searcher 实例。**
同文本不同 intent 的两条 query 在这一次分析内共享结果；
**键含 intent，NEVER 只用 text**（`GATE1-DEDUP` 那次判定翻面就是只用 text 翻的）。

四条 NEVER，**每条各有判据**：

| NEVER | 为什么 |
|---|---|
| 跨分析复用 | 同一个 job 重跑 MUST 得到同样的往返次数——可复现（`S2-2`） |
| 跨租户复用 | 隔离面（`D7`） |
| 自造第二套新鲜度口径 | stale 只有 Revalidator 那一个口径 |
| 让第二次取数不进录制层 | 夹具缺一块，CI 就回放不出来（`S2-7`） |

**② `now` 从定死的时间戳改成 callable**（与同文件 `design_generate_deps` 一致）。
判据：让 searcher 活过一段时间后再抓一次，断言两次的 `meta.fetched_at` **不同**；
阴性对照 = 改回定死的时间戳则判据红。

**①② MUST 同卡**：它们是同一个生命周期问题的两半。
分两次改的话，第二次的人会看着已经改好的那一半以为整件事做完了。

### 关单条件

`SEARCHER-SCOPE` 做完之后按新规矩关这张单
（状态行三样齐 + `## 关闭` 节点名本卡）。
**「往返数 = 不同 URL 数」这条指标到那一层才真的够得着——在那里断言它。**
