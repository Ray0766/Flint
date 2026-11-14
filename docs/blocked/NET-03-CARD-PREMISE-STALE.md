# NET-03-CARD-PREMISE-STALE · 「真实源冒烟留卡未执行」这个前提与盘上的事实对不上

**状态** closed · 2026-08-05 · `DEC-033`

> **已关闭 · owner 2026-08-05 裁决 `DEC-033`**（见 `DECISIONS-v04.md`）。
> 三选一的答案是**「甲 + 乙 各一半」**，不是三取一：
>
> | 卡面的哪一半 | 裁决 | 落在哪 |
> |---|---|---|
> | 跑一次真实 github/arxiv 检索 | **读法甲：卡面过期**——07-31 payoff 已执行并录制 → `NET-03` 记 `skipped_by_owner`，理由逐字进台账，**NEVER 按「已登记未执行」写判据** | `docs/progress-v041.jsonl` @ 2026-08-05T06:47Z |
> | 经作业队列（`jobs` 表 → `worker_main` 消费）跑通 gate1 | **读法乙：缺的是 `gate1_deps` 注入而非网络授权** → 单开**普通卡**，走 respx 回放，**NEVER 继续挂红线** | `docs/积压总账-v041.md`（待 steward 编进第 3 批） |
>
> 本单提出的「读法乙也说不通一处：那条链路缺的是注入、不缺网络授权，可以走回放」
> 正是 owner 采纳的那一点。**新卡带一条回退闸**：若该链路在回放下暴露出真实网络请求，
> **立即回退为红线卡并停下上报**。
>
> 以下为关闭前的原文，一字未改。

---

**发现者** worker / 取 NET-03 时 · **发现时间** 2026-08-05
**危害** 中 —— 不是缺陷，是**卡面描述的状态已经不成立**，而它是一张红线卡
**为什么停下**：worker.md §1.4「发现两处矛盾：以 contracts/ 与任务真相为准，
同时**必须**写问题单上报，NEVER 自行择一后不留痕」。红线话题上更要停。

## 卡面怎么说

`docs/steward/tasks-v041-b2.json#NET-03`：

- 标题：「真实源冒烟（红线卡 · **留卡不执行**，需 owner 在场）」
- acceptance②：「测试断言这张卡处于**「已登记未执行」**态——防止它被静默跳过或被当成做完了」

`docs/blocked/E2E-REALSOURCE.md` 同口径：「**没做的只有一件事**：`gate1_analysis`
那条支线接真实 github/arxiv 检索跑一次」。

## 盘上的事实

**真实源检索已经跑过，而且录下来了。** 逐条证据：

| 证据 | 内容 |
|---|---|
| `docs/生产Gate1-真实源切换-payoff.md` | 抬头写着「owner @2026-07-31」；正文：「live 路（owner payoff）：真实 qwen 判官 + 真实 github/arxiv，24s 跑完，检索 **14 篇真实 arxiv**」 |
| `fixtures/gate1_live/scripted/search.json` | `api.github.com` **4 条** + `export.arxiv.org` **13 条**（真实交换，非 `.example`） |
| `fixtures/gate1_live/qwen/search.json` | `api.github.com` **4 条** + `export.arxiv.org` **25 条** |

也就是说：**「跑一次真实 github/arxiv 检索」这件事，2026-07-31 就在 owner 的 payoff
授权下做完并录制了**，`harness/gate1_live.py` 的 `record` / `record-qwen` 两条路都跑过。

所以 acceptance② 要断言的那个状态（「已登记未执行」）**今天是假的**。
按它写判据，等于把一句不成立的话钉成回归。

## 两种读法，我不替 owner 选

**读法甲：卡面已过期。** 真实源冒烟在 v0.4 的 payoff 里做完了，NET-03 该被标成
`skipped_by_owner` 或改写成「已执行，记录见 payoff 文档」。

**读法乙：卡面说的是另一条路，仍然没跑。** 两条路径确实不是同一条：

| | 已跑过的（07-31 payoff） | NET-03 可能指的 |
|---|---|---|
| 入口 | `harness/gate1_live.py` 直接调 `run_gate1` | 提交作业 → `jobs` 表 → `worker_main.py` 消费 |
| 依赖注入 | `build_live_deps(...)` 在 harness 里现造 | `WorkerDeps.gate1_deps` 注入（现为 `None` → 抛 `HandlerDepsMissing`） |
| 覆盖面 | Gate① 四步 + 真实检索 | 整条队列链路（ASM-05 的 e2e 那半条） |

`E2E-REALSOURCE.md` 原文说的是「`gate1_analysis` 那条支线」——
`gate1_analysis` 正是 **worker 的 handler 名**（`flint/jobs/worker_main.py:161`），
不是 harness 的函数名。这一点**支持读法乙**：没跑的是「经作业队列的那一条」。

但读法乙也说不通一处：那条链路缺的是 `gate1_deps` 注入，**不缺网络授权**——
注入之后它会用同一个 `GithubArxivSearcher`，而那个的录制已经在盘上了，
**可以走回放，不必真联网**。若真如此，NET-03 就不该是红线卡。

## 需要 owner 给一句话

三选一：

1. **卡面过期** → NET-03 记 `skipped_by_owner`，理由指向 payoff 文档；
2. **指的是队列那条链路，且允许走回放** → 它不是红线卡，重写 acceptance，本批可做；
3. **指的是队列那条链路，且要求真联网再跑一次** → 保持红线，待 owner 在场。

## 我做了什么、没做什么

- **没有执行任何真实抓取**（红线，且本轮压根没到那一步）；
- **没有按 acceptance② 写判据**——那条要断言的状态今天是假的，
  写出来就是把一句不成立的话钉成回归。写到一半的判据文件已删除；
- **没有改** `docs/blocked/E2E-REALSOURCE.md`：它记的是当时的实况，
  改它要先有上面那句裁决；
- NET-03 在台账记 `blocked`，连跑继续取下一张就绪卡（worker.md §4.4）。
