# v0.4.1 第 12 批 · 完成态报告

**5 / 5 卡 verified · 0 blocked。** 五条全局门全绿，**pytest 零 failed**。

**七项核心功能全部能用**——⑥热点分析在 `DEC-057` 授权的窗口里跑通了，
`cluster_verdicts` 从全库 0 行变成有行。

---

## 一 这一轮的两条教训（owner 要求逐字进报告）

### 1. 少打几发是省钱，改判定是产品事故——两者绝不能混在一次改动里

`GATE1-DEDUP` 的第一版按 `query.text` 共享取数结果。理由写得很顺：
「两个 URL 构造器只吃 text，同文本的两条 query 问上游的是同一个问题」。

**跑测试时判定从 `B_red_ocean` 翻成了 `C_opportunity`。**

`_offline_searcher` 按 `query.intent` 分支——`landscape` 回竞品清单、其余回论文。
按文本共享之后 `support` 先跑并占住那段文本，随后同文本的 `landscape`
拿到的是论文而不是竞品，竞品数归零。

一个只想「少打几发网络」的改动，改掉了产品最核心的那个输出。

### 2. 前提判据要钉**契约的事实**（协议允许什么），NEVER 钉**实现的事实**（那一个实现今天恰好怎么做）

上面那个错误之所以能写出来，是因为我给它配了一条**错的前提判据**：
我断言「`github_search_url` / `arxiv_search_url` 只吃 text」——
那是**那一个实现**今天恰好怎么做，不是 `Searcher` **协议**允许什么。

协议允许按 intent 分支，而 `_offline_searcher` 正在用这个自由。
判据钉错了层，于是它绿着，而共享逻辑是错的。

**落地**：去重的键从 `query.text` 换成 `query_id_for(query)`——
对任何 `Searcher` 实现都安全。那条前提判据也改成钉住
「协议允许按 intent 分支」：它成立，按文本共享就 NEVER 能做。

### 附：抓住它的是既有判据，不是本卡新写的那些

`tests/m2/test_m2_040` 与 `test_m2_049` 当场把判定翻面抓了出来。
它们是**别人的判据**，写在几个批次之前。

> **新判据守「我这次改对了吗」，旧判据守「我有没有把别人的东西碰坏」——
> 这次是后者救的场。**

---

## 二 五条全局门（逐字贴）

```
$ ruff check .
All checks passed!

$ PYTHONIOENCODING=utf-8 python -m mypy --strict flint
Success: no issues found in 323 source files

$ PYTHONIOENCODING=utf-8 python -m pytest -q
5292 passed, 2 skipped, 12 warnings in 425.64s (0:07:05)

$ npx tsc --noEmit
（无输出，退出 0）

$ npm test -- --run
Test Files  85 passed (85)
     Tests  858 passed (858)
```

### pytest 的红：一条都没有

本批一路上红过的每一条，**逐条点名归属**（NEVER 按族小结）：

| 曾经红的 | 归谁 | 现在 |
|---|---|---|
| `test_cluster_region::…majority_is_never_taken` | **第三例**的前提被 `DEC-058` 推翻（`["global"]*5+["CN"]` 改前该抛） | 翻那一例、留另两例，另补一条更硬的 |
| `test_cluster_region::…two_source_region_semantics…` | 它判的是**字面量** `region="global"` | 改判**语义**（见 §四） |
| `test_decisions_landed::…watermark` | 水位 056 → 058 | 跟着事实改数（第十次） |
| `test_m2_040` · `test_m2_049` · `test_featb_gate1_live` | **我按文本共享把判定改坏了** | 键换成 query 身份 |
| `test_m3_025::…verdict_a_with_refute_evidence` | 它自带**第三份**取数循环，签名没跟上 | 改走同一对函数 |
| `test_read_endpoints` ×2（`fe_views`） | **`m3_025` 崩在前面留下的库状态** | 根因修掉后自愈 |
| `test_gate1_dedup` ×2（我自己新写的） | 它们量的是**被推翻的那个设计** | 改成量真做到的事 |
| `test_design_state::…no_second_advancer…` | **我判过头了**（六处合法状态推进被当成违规） | 改成钉清单不增长 |
| `test_smoke_seven::…stuck_job_state…` | 它钉着「那张单还开着」，而单被 `DESIGN-STATE` 关了 | 翻成「开单 → 修好 → 关单」 |
| `test_smoke_seven::…howto_marks_the_one_that_is_not_green` ×2 | ⑥ 从红翻绿 | 两处**一起**翻（《怎么测》与 trace 同源） |

ruff 一路上红过 3 轮共 12 条，全是本批新写的判据文件与被我改动的 import 块。
**纯机械的 import 整理用了 `--fix`，其余逐条改**——
`--fix` 会顺手删掉「看起来没用」的东西，而有些东西没用是因为我刚写错。

---

## 三 五张卡各做了什么

| 卡 | 病 | 现在 |
|---|---|---|
| `DEC-057-058-LANDING` | — | 两条原文一字未改追加，水位 056→058，既有 68436 字节逐字节未动 |
| `GATE1-REAL` | `cluster_verdicts` 全库 0 行——链修好了而没在真网络上跑过 | **0 → 2 行**，判定取得回来，分析屏显示 `D_insufficient` |
| `REGION-SPAN` | 一条簇成员跨区，判不出区、留 `NULL` | 源常量不参与定区；那一条 `NULL → HK` |
| `GATE1-DEDUP` | 一次分析取两遍数（28 发 / 13 个不同 URL） | **28 → 14**；全仓三份取数循环退役 |
| `DESIGN-STATE` | 跑完了而 `jobs.state` 停在 `queued` | 两块表说同一句话；推进状态立一处真相 |

---

## 四 本批的第二组教训：判据自己判错了三次

**三次都是我写的判据错，不是代码错。** 逐条记下来：

1. **判据的名字与它断言的东西对不上。**
   `test_the_payload_carries_what_the_consumer_reads` 名字写着
   「payload 带的是**消费方读的那个**」，而它断言的是 `payload["brief"]`——
   **消费方读的是 `payload["prompt"]`**。
   一条名叫「两边对得上」的判据，钉住的正是那个对不上的键，**而它一直是绿的**。
   翻面时不只改字面，还把消费方那一侧**一起读进来**：两边从此对着同一个名字。

2. **判据的报错信息叫我去关一张单，而那张单不该关。**
   `test_the_two_source_region_semantics_are_still_different` 断言
   `'region="global"' in ghtrend`，报错写着「ghtrend 不再写死 global 了——去关那张单」。
   **它的触发条件对，触发原因错**：`ghtrend` 并没有不再写源常量，
   它只是从自带字面量改成了引用那一处真相。
   > 一条判据叫我去关一张单时，**先核它触发的原因是不是它说的那个**。
   > 照着关掉的话，一张仍然成立的单就从盘上消失了。

3. **判据判过头，把合法的东西也拦了。**
   `test_no_second_advancer_exists_anywhere` 断言「除 `state.py` 外
   一处 `UPDATE jobs SET state` 都不许有」，而库里另有**六处合法的状态推进**。
   改成钉**清单不增长**（多出一个就红）。
   > 一条判据把「不该有的」和「已知且另有单据的」混成一堆时，
   > 它逼着人要么删掉合法代码、要么把它整条关掉——**两条都比现状坏**。

---

## 五 要你定的四件

1. **`SEARCHER-SCOPE`（你已定：并进下一批）**——记忆的作用域改成一次分析、
   `now` 从定死的时间戳改成 callable。两件同卡，卡面已写进
   `docs/blocked/GATE1-SAME-TEXT-TWO-INTENTS.md`。
   顺带：那条「往返数 = 不同 URL 数」的指标到那一层才够得着，**在那里断言它**。

2. **六个族改 `jobs.state` 而从不写 `StatusChanged`**
   （`docs/blocked/SIX-FAMILIES-ADVANCE-STATE-WITHOUT-AN-EVENT.md`）——
   `DESIGN-STATE` 那条病的**镜像**。最要紧的是 `mark_failed`：
   **作业失败了而订阅那一头什么都收不到**。

3. **GitHub token 本版不配**（你已定）——`K1-02` 记上了真实数字
   （`x-ratelimit-limit: 10`，那一跑用掉 4），代码里留了空的认证接缝。
   重启条件：第二个并发用户，或一次分析的 github 请求数达到两位数。

4. **`REGION-CN-HK-COUNT-SAYS-SEVEN` 保持 open**（你已定）——
   等你改完纸面清单 A2。

---

## 六 收工纪律的落地检查

- **顺序**：先写五张 trace 与台账 → 再跑五条门 → 最后只改本报告的数字。
  门跑完之后**没有再动任何被判据读的文件**；
- 台账落行后**单独重跑了它的读者判据**（`test_ledger_pairing_v041` + `test_blocked_sheets_state`）；
- **每张卡的 `started` 与终态成对**；
- pytest 的红**逐条点名归属**（§二），NEVER 按族小结；
- **真实网络只发生在 `GATE1-REAL` 那一次**，28 发、全部 200、全部留痕，
  `DEC-057` 的 40 发额度**剩 12**，后三张卡一发都没用；
- 组稿、判定、设计生成一律走**免费本地档**（`LocalProvider` → 本机 Ollama），
  **一个 key 都没读过**。
