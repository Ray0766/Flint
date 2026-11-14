# 六个族改 `jobs.state` 而从不写 `StatusChanged`

**状态** open · 2026-08-11 · `DESIGN-STATE`

## 实测

`DESIGN-STATE` 立「推进状态一处真相」时全仓扫了一遍 `UPDATE jobs SET state`，
除 `flint/jobs/state.py#enter_state`（四族共用）之外还有**六处**：

| 落点 | 推到什么 | 写事件流吗 |
|---|---|---|
| `flint/jobs/runner.py:184` | `cancelled` / target | **否** |
| `flint/jobs/worker_main.py:349`（`mark_failed`） | `failed` | **否** |
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
