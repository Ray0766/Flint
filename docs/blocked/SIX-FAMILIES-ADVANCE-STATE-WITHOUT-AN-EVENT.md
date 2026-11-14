# 六个族改 `jobs.state` 而从不写 `StatusChanged`

**状态** open · 2026-08-11 · `DESIGN-STATE`

## 实测

`DESIGN-STATE` 立「推进状态一处真相」时全仓扫了一遍 `UPDATE jobs SET state`，
除 `flint/jobs/state.py#enter_state`（四族共用）之外还有**六处**：

| 落点 | 推到什么 | 写事件流吗 |
|---|---|---|
| `flint/jobs/runner.py:184` | `cancelled` / target | **否** |
| ~~`flint/jobs/worker_main.py:349`（`mark_failed`）~~ | `failed` | ~~否~~ → **写了**（`UIR-02`，2026-11-14） |
| `flint/jobs/ingest.py:176`（`_set_state`） | 各状态 | **否** |
| `flint/jobs/pricebook_scan.py:101,106` | `retrieving` / `done` | **否** |
| `flint/jobs/revalidation.py:152,157` | `retrieving` / `done` | **否** |
| `flint/api/hardening.py:52` | `cancelled` | **否** |

六个文件里 `StatusChanged` 出现次数**都是 0**。

## 它是 `DESIGN-STATE` 那条病的**镜像**

| | 写了哪一半 | 谁看不见 |
|---|---|---|
| `design_generate`（已修） | 只写事件流 | **轮询 `GET /jobs/{id}` 的屏**——转圈不停 |
| 这六处 | 只写 `jobs.state` | **订阅 SSE 的屏**——作业一直没动静 |

最要紧的一处是 `mark_failed`：**作业失败了，而订阅那一头什么都收不到**。
屏上会一直转，直到有人去查库才知道它早就 `failed` 了。

## 为什么没在 `DESIGN-STATE` 里一并改

本卡的射程是 `design_generate` 那一族。六个族一起改要逐个确认：

- 它们有没有事件流句柄（`ingest` / `pricebook_scan` 未必有）；
- 哪些状态该推事件（`retrieving` 这种中间态推不推，是 SSE 契约的事）；
- `hardening.py` 那一处是**条件更新**（`AND state = 'queued'`），
  写事件要先知道它到底改没改到行。

**NEVER 顺手都加上**：给一个没有订阅者的后台作业推事件是白写，
而给一个有订阅者的作业漏推是真 bug——这两件事要分开判。

## 本卡留下的东西

`flint/jobs/state.py#enter_state` 是那一处真相，四族已经共用它。
六处接进来的时候，**它就在那里**，不用再想「该写哪两句」。

## 2026-11-14 · `mark_failed` 这一处接上了（`UIR-02`）

六处里最要紧的那一处已改：`flint/jobs/worker_main.py#make_mark_failed` 不再自己 `UPDATE jobs SET state`，
改走 `flint/jobs/state.py#enter_state`，推之前先追加一条带原因的 `failed` 事件。
`worker_main.py` 因此从 `tests/v041/test_design_state.py` 那份「只写库不写事件」的清单里划掉了。
判据：`tests/v041/test_fail_events.py`。

**本单不关**：另外五处（`runner.py` / `ingest.py` / `pricebook_scan.py` / `revalidation.py` /
`hardening.py`）还是原样。它们各自有没有订阅者、中间态推不推，上面「为什么没一并改」那一节的三条仍然要逐个答。
