# GATE1-VERDICT-IS-NOT-A-COMPOSE-SOURCE · 判定与组稿之间那一跳没有人接

**状态** closed · 2026-08-06 · `CHAIN-01` + `CHAIN-02`
**发现者** worker / E2E-01 端到端串链时 · **发现时间** 2026-08-05
**危害** 中 —— 主链路在**中间断成两段**，而两段各自都是绿的
**改动面** 组稿的取数面或 gate1 的落盘面，**都在 E2E-01 outputs 之外**

## 现象

主链路名义上是「提交 → gate1 判定 → 组稿 → 渲染 → 导出」。实测两段各自跑得通，
**中间不通**：

| 段 | 产出落在哪 |
|---|---|
| gate1（`flint/jobs/gate1.py#run_gate1`） | `snapshots` 表：`snap-{job}-docs` / `-judge` / `-verdict` |
| 组稿（`_compose_handler` → `run_compose`） | 读 `claims WHERE deliverable_id = <analysis_id>` |

`analysis_id` 在组稿这一侧被当成**来源交付物 id**，而 gate1 从来不往 `claims`
写行——它把 support/refute 放在 `judge` 快照的 JSON 里。
所以「拿判定去组稿」这一步，今天**只能靠人手种一条 claim**
（`ASM-05` 与 `E2E-01` 都是这么种的）。

## 为什么此前没人发现

两段各有各的绿：`ASM-05` 从种好的 claim 起跑，gate1 的测试到判定落盘为止。
**没有任何判据横跨那一跳**——而那一跳正是产品的主干。

## 判据钉在哪

`tests/v041/test_e2e_full_stack.py::test_gate1_output_is_still_not_the_claims_source`：
它断言那个来源 id 下**没有**除夹具以外的 claim。哪天有人把这一跳接上，**这条会红**，
红的时候来这里关单，并把端到端判据里的「种一条 claim」那步删掉。

## 要 owner / 下一张卡定的

1. **谁负责那一跳**：是 gate1 收尾时把 support_claims 落成 `claims` 行，
   还是组稿多认一种来源（直接读 judge 快照）？
   前者让 claims 成为唯一真相，后者省一次写库但让组稿知道判定的内部形状。
2. **claim 的 `deliverable_id` 该填什么**：gate1 的产出不是一份交付物，
   而 `claims` 表按交付物索引。这可能要一个「分析产物」的 id 口径。

---

## 关闭（`CHAIN-01` 落盘 + `CHAIN-02` 接端到端 · 2026-08-06）

单子里那两个要 owner / 下一张卡定的问题，都定了：

**1. 谁负责那一跳** → **gate1 收尾落 `claims` 行**（steward 建议，owner 未划掉）。
理由是让 `claims` 成为唯一真相；让组稿多认一种来源会把它绑死在判定的内部形状上。
落盘在 validate 步**与 `job_steps` 同一个事务**——分两次提交的话，
kill -9 卡在中间会留下「步已记完、claim 没写」，续跑跳过那步，那批结论就永远丢了。

**2. claim 的 `deliverable_id` 填什么** → **分析产物 id `analysis-{job_id}`**。
交付物是 `del-{job}`，两个命名空间不相交。`claims.deliverable_id` 没有外键，
所以**不去 `deliverables` 表建假记录**——建了的话，交付物列表里会多出一份
没人能打开的「报告」。这条有判据钉着，变异考里造过那一手，当场红。

**端到端那步种 claim 的代码删掉了**，`test_gate1_output_is_still_not_the_claims_source`
按它自己写的那句话翻成了正向判据 `test_the_chain_now_runs_from_gate1_all_the_way_to_compose`：
来源 id 由判定推导、那批行真在库里、且**没有任何带测试前缀的人手行**。

## 接上之后露出来的下一处（**不是本单的**）

实测那批 claim 是 `speculative` / `supports`，账本里 **0 条 Fact**：
钉引用那一步（`pin_verdict_citations`）**只在 `gate1.main()` 的生产路径跑**，
队列 worker 的 gate1 handler 不跑它。于是队列跑出来的判定有结论、没引用，
`promote_claims` 一条都提不动（要 cited ∧ supports）。

这一条**据实记在** `tests/v041/test_e2e_full_stack.py::test_the_chain_carries_conclusions_but_not_yet_citations`
（等值判据，钉住 `speculative` 与 0），处置方案三选一见 `docs/trace/CHAIN-01.md` §6。

