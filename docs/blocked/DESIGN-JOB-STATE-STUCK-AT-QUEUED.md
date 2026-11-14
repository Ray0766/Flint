# design_generate 跑完了，而 `jobs.state` 还停在 `queued`

**状态** closed · 2026-08-11 · `DEC-058` 那一批 / 卡 `DESIGN-STATE`（开单人 `SMOKE-01`）

## 实测

`SMOKE-01` 第一次真跑设计生成（`job-dc0d4001-1abe-4843…`，本地 `qwen3.6:35b-a3b`）：

| 看哪里 | 说什么 |
|---|---|
| `job_events`（SSE 那一路） | 192 条事件，末尾 `{"kind":"status","state":"done"}` |
| `jobs.state`（轮询那一路） | **`queued`** |

两处对同一件事说了两句相反的话：订阅 SSE 的屏看到「已完成」，
轮询 `GET /jobs/{id}` 的屏**永远**看到「排队中」。

## 为什么这不是小事

「作业跑完了没有」是 `D6` 作业状态机的核心，而它今天有两个真相。
用户那一侧的症状是「点了生成，转圈不停，而内容其实已经出来了」——
**看起来像卡死，实际是两块表没对上**。

## 本卡没有改它

`SMOKE-01` 的 outputs 是 `harness/` + 文档 + 判据，不含作业状态机。
改它要动 `run_design_generate` 的收尾路径（谁负责把 `jobs.state` 推到 `done`），
那是 `DESIGN-01` 那一族的事。

## 对照

`compose`（⑦计划书）那一族**是对的**：`jobs.state` 走到 `done`。
所以这不是「状态机整体没接」，是设计生成这一条路径漏了收尾那一步。


## 关闭

`DESIGN-STATE`（2026-08-11）修好并在真栈上验过。

**修法照 owner 逐字：走与 compose 同一条收尾路径，NEVER 另写一套推进状态的代码。**

- 推进状态搬到**一处真相** `flint/jobs/state.py#enter_state`——
  改前它在 compose / gate1 / spec_export **三处**各有一份、逐字相同，
  而 `design_generate` **一份都没有**；
- `DesignGenerateDeps` 加 `dsn`——**它当初写不了那一半的结构原因就是手上没有库句柄**；
  `dsn is None` 时只写事件流并**照实不推 `jobs.state`**，NEVER 假装推过了；
- `harness/run_worker.py` 把 `dsn` 注进去。

### 真栈实测（同一台机器，两跑对照）

```
job-51ba152f…（本卡之后）  jobs.state = done   · 270 条事件，末尾 {"kind":"status","state":"done"}
job-dc0d4001…（本卡之前）  jobs.state = queued · 事件流早就说 done
```

**改前那一跑仍留在库里没动**——对照不用转述，它就在那儿。

### 顺带发现（另开一单）

立「一处真相」时扫全仓，发现**另有六处**改 `jobs.state` 而从不写 `StatusChanged`——
本条的**镜像**（这六处是订阅 SSE 的屏看不见）。
最要紧的是 `mark_failed`：作业失败了而订阅那一头什么都收不到。
单据 `docs/blocked/SIX-FAMILIES-ADVANCE-STATE-WITHOUT-AN-EVENT.md`。
