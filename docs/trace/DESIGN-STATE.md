# DESIGN-STATE · trace

**卡**：`design_generate` 跑完了而 `jobs.state` 停在 `queued`——「作业跑完没有」有两个真相。
**结果**：verified · 1 cycle · 判据 11 条全绿 · 真栈两跑对照就在库里。

## 病是什么

`SMOKE-01` 实测：那一跑**真的产出了 192 个片段的设计稿**，
事件流最后一条是 `{"kind":"status","state":"done"}`——而 `jobs.state` 是 `queued`。

| 看哪里 | 说什么 | 谁在看 |
|---|---|---|
| `job_events` | 已完成 | 订阅 SSE 的屏 |
| `jobs.state` | **排队中** | 轮询 `GET /jobs/{id}` 的屏 |

> 用户侧：「点了生成，转圈不停，而内容其实已经出来了」。

## 修法照 owner 逐字：走同一条路，NEVER 另写一套

扫全仓发现 `_enter_state` 在**三处**各有一份（`compose` · `gate1` · `spec_export`），
**逻辑逐字相同**（只有换行不同），而 `design_generate` **一份都没有**。

三份并存时没人看得出「谁在推进状态」有统一口径；
第四族接进来时最省事的写法就是自己再写一套——
**两套推进器会让「作业跑完没有」再长出第三个真相**。

落点：`flint/jobs/state.py#enter_state` 一处真相，三处改成别名引用
（既有调用点一个都不用改），design 接上同一条。

## 它当初为什么写不了那一半

`DesignGenerateDeps` 里**没有任何库句柄**——手上没有连接，那一半就写不了。
这不是谁偷懒，是结构。本卡加了 `dsn`。

`dsn is None` 时**只写事件流那一半，并且照实不推 `jobs.state`**：

> **NEVER 假装推过了。** 假装的话，离线判据会以为这一半被覆盖到了，
> 而真栈上它其实没跑。

## 真栈两跑对照（同一台机器）

```
job-51ba152f…（本卡之后）  jobs.state = done   · 270 条事件，末尾 {"kind":"status","state":"done"}
job-dc0d4001…（本卡之前）  jobs.state = queued · 事件流早就说 done
```

**改前那一跑仍留在库里没动**——对照不用转述，它就在那儿。

## 顺带发现：这条病还有一个**镜像**，另有六处

立「一处真相」时扫全仓 `UPDATE jobs SET state`，除 `state.py` 外还有六处，
而这六个文件里 `StatusChanged` 出现次数**都是 0**：

| 落点 | 推到什么 |
|---|---|
| `runner.py:184` | `cancelled` / target |
| `worker_main.py:349`（`mark_failed`） | `failed` |
| `ingest.py:176` | 各状态 |
| `pricebook_scan.py:101,106` | `retrieving` / `done` |
| `revalidation.py:152,157` | `retrieving` / `done` |
| `hardening.py:52` | `cancelled` |

**它们是本卡这条病的镜像**：design 只写事件流（轮询的屏看不见），
这六处只写库（**订阅 SSE 的屏看不见**）。
最要紧的是 `mark_failed`——**作业失败了而订阅那一头什么都收不到**。

没在本卡一并改（射程是 design 那一族，且六处各有各的前提：
有没有事件流句柄、中间态推不推、`hardening` 那一处是条件更新）。
**NEVER 顺手都加上**：给没有订阅者的后台作业推事件是白写，
而给有订阅者的作业漏推是真 bug——两件事要分开判。
单据 `docs/blocked/SIX-FAMILIES-ADVANCE-STATE-WITHOUT-AN-EVENT.md`。

## 我第一版判过头了

`test_no_second_advancer_exists_anywhere` 第一版写的是
「除 `state.py` 外一处 `UPDATE jobs SET state` 都不许有」——**当场红，而红得对**：
那六处是**合法的状态推进**（failed / cancelled / 中间态），
它们的问题不是「存在」，是不写事件流。

改成钉**清单不增长**：多出一个就红。
那个新出现的，会在没人注意时又长出一个「作业跑完没有」的答案。

> 一条判据把「不该有的」和「已知且另有单据的」混成一堆时，
> 它逼着人要么删掉合法代码、要么把它整条关掉——**两条都比现状坏**。

## 连带翻面的三处

| 落点 | 为什么 |
|---|---|
| `test_smoke_seven::…stuck_job_state…` | 它钉着「那张单还开着」——单关了它就该红。翻成「开单 → 修好 → 关单」，且关单要说得出是什么关的 |
| 《怎么测》⑤ | 写着「进度条会一直转」，已过期；改成实况并留下**排障口径**（转圈不停时先看两处对不对得上） |
| 《怎么测》⑥ 与两条同源判据 | `GATE1-REAL` 跑通之后 ⑥ 从红翻绿——**两处一起翻**，各翻各的话 owner 手上那页与记录会各说各的 |

## 判据与门

`pytest tests/v041/test_design_state.py -q` → **11 passed**（含卡面要的阴性对照：
摘掉收尾那一步 → 两块表分家，且红的话点名是哪两处）。
全量门在 `SHIP-12` 一并跑。
