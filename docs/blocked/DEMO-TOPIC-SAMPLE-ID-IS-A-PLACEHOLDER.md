# 主题详情屏的取证样例 id 是个占位串——库里一条主题都没有

**状态** closed（owner 2026-08-08 挑**甲**，落为 `DEC-041`，由 `SEED-01` 执行）

## 开工时查到的实况：**标题那句话已经不成立了**

单据说「库里一条 `topics` 行都没有」。实查 demo 库：

```
topic-demo14bf9d94b0-1 · -2 · -3 · -5 · -6 · -9      共 六条
seed-demo14bf9d94b0，各 speculative=false、2 条 why_now 证据（带 citation_id）
```

**它们是模型产出**（某次 demo 跑留下的），归在 `proj-demo14bf9d94b0` 名下——
所以 `/projects/[id]/topics` 那一屏**早就有真数据**，缺的只是详情屏的样例 id。

### 那为什么还是种了一条夹具

取证样例要的是**可复现**。那六条是一次过去运行的痕迹，
**没有任何脚本能把它们重造出来**——demo 库重建一次，样例 id 又变成死链，
而那正是这张单要终结的失败。

夹具（`harness/demo_seed_topic.py`）由脚本写死、幂等、随时能撤，
才是探针该指的东西。两者互不相扰：脚本只写 `-demo-fixture-` 前缀那几行，
`_drop` 的每条 DELETE 都按夹具 id 限定，**那六条一个字节都没碰**
（判据 `test_the_six_real_topics_are_not_in_the_seeders_blast_radius` 钉住）。

**owner 若更希望取证屏上是真产出**：`harness/fe_smoke.py` 里把
`"/topics/[id]"` 换成 `topic-demo14bf9d94b0-1` 即可，一行。
代价是那条 id 依赖一次没人复跑的历史运行。

## 交付

| 产出 | 是什么 |
|---|---|
| `harness/demo_seed_topic.py` | 夹具主题 + seed + origin + 2 doc/citation（另一条标明夹具身份）；幂等、`--drop` 撤干净、dsn 可注入 |
| `harness/fe_smoke.py` | 样例 id 换成夹具；`tp-placeholder` 退役 |
| `tests/v041/test_mobile_sweep.py` | `/topics/[id]` 的 **404 额度撤掉**，并留下撤它的理由 |
| `tests/v041/test_demo_topic_seeded.py` | 15 条判据 |

**额度撤掉后判据仍绿才算数**（`DEC-041` 的硬判据）——留着额度的话，
这一屏哪天真退回 404，**没有一条判据会响**。

---

## 以下为立单时的原文（一字未改）

**状态**（原）open

> 发现者：worker，v0.4.1 第 6 批（清 `SPEC-01` 的连带红时顺出来的）。
> **这不是产品坏了**，与 `DEMO-JOB-NOT-OWNED-BY-THE-PROBE-USER` 同一形状：
> 红的是取证样例，不是被取证的那一屏。

## 现象

`harness/fe_smoke.py` 扫 `/topics/[id]` 时用的样例 id 是个占位串。
demo 库（`flint`）里**一条 `topics` 行都没有**，于是
`GET /topics/{id}` 回**带 `code` 的 404**——那正是 `TS-007` 要的正确行为。

屏上如实显示「没有这一条」，控制台留下一条 404 报错。
`tests/v041/test_mobile_sweep.py` 的 `CONSOLE_BASELINE` 因此给这一屏留了 1 条额度。

## 这张单子为什么现在才立

那条基线原先引的是 `docs/blocked/TOPIC-HAS-NO-NAME-TRIPLE.md`。
**引错了**：那张单说的是「规格要主题屏上名称三元组而冻结件 `Topic` 没有那两个字段」，
与「库里没有主题」是两件事。`DEC-036`（owner 2026-08-08）把那张单关掉之后，
基线指向了一张已关的单——**而基线要求每一条额度都指着一张活单**，
那条判据当场红。

这是一次有用的红：它逼出了「基线的理由从一开始就写错了」。

## 修法三选一（owner）

| 选项 | 做什么 | 代价 |
|---|---|---|
| **甲** | **给 demo 库种一条主题**（连同它的 `seed_id` / `why_now` / `keyword_mapping`），取证样例改用它 | 一次种子脚本改动。**推荐**：它同时让主题两屏第一次有真数据可看 |
| 乙 | 取证样例改用一个**明说不存在**的 id，并把这条 404 登记成「预期的诚实态」 | 0，但主题两屏在取证里永远是空的 |
| 丙 | 维持现状，基线指向本单 | 0，**当前就是这一条** |

种主题属**种子数据**（工单 §7 的 owner 面：「广场数据是合成的」同一族），
所以甲需要 owner 点头。在那之前走丙。

## 关单条件

`GET /topics/{sample}` 不再回 404（甲），或 owner 明确选乙并落地。
**NEVER 因为「那条判据绿了」就关**——判据绿只说明基线指对了单子。
