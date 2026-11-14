# REGEN-EVT-01 · 单块重写作业推状态、写事件（`DEC-063`）

**状态**：verified @2026-11-14。第 17 批第三张，卡单 `docs/trace/B17-PLAN.md`。

## 一、装载清单

`flint/jobs/regenerate_job.py`（全文）· `flint/jobs/state.py`（全文）· `flint/jobs/events.py:66-110` ·
`flint/jobs/compose.py:140-212,308-326`（`run_compose` 推状态的写法）· `flint/jobs/worker_main.py:100-170,336-400` ·
`flint/domain/models.py:709-823`（`JobState` 与事件判别联合，只读）· `harness/demo_server.py:138-170` ·
`docs/blocked/REGENERATE-JOB-WRITES-NO-EVENTS.md` · `tests/fe_core/test_regen_job_e2e.py`（既有搭法）·
`tests/v041/test_design_state.py:60-125` · `DECISIONS-v04.md:375-391`。

## 二、决定

1. **走 `enter_state` 那一处真相**，不另写 `UPDATE jobs`。`tests/v041/test_design_state.py` 守着
   「全仓不出现新的一套推进器」，本卡没有让那份清单增长。
2. **三个状态**：开工 `drafting` → 落库后 `done`；失败 `failed`。`drafting` 取自冻结件 `JobState`
   既有的值——重写干的就是起草那一步。没有它的话屏上从提交到完成之间一个字都没有。
3. **失败写两条，先原因后终态**：先追加 `JobFailedEvent(reason="类型名: 文本")`，再 `enter_state(failed)`。
   订阅的屏按到达顺序读，最后一条必须是终态。然后**异常原样抛回**：worker 的 `dispatch_job`
   还要靠它往 `jobs.error` 落文本（`flint/jobs/worker_main.py:343-356`）。
4. **作业行不在就不写事件，也不造作业行**。`run_compose` 的做法是 `_ensure_job` 补一行
   （发起人写死 `u-owner`）。重写这里没有照抄这一点：补出来的那一行的归属只能是编的。
   经 API 提交的作业恒有那一行；没有的只会是判据与脚本的直调，那时没有屏在读。
5. 拆成两个函数：`run_regenerate_job` 管状态与事件，`_regenerate` 管产物（原函数体一字未动）。

## 三、判据先行

`tests/v041/test_regen_events.py`（7 条）先写，实现前 `5 failed, 2 passed`
（已经绿的两条是「失败不留半写产物」与「直调照常产出」，它们是改前就成立、要保住的性质）。
实现后 7 passed。搭法复用 `tests/fe_core/test_regen_job_e2e.py` 的种子与回放 provider。

变异验红（每次还原）：

| 变异 | 结果 |
|---|---|
| 成功后不推 `done` | 2 failed |
| 失败时不写 `failed` 事件 | 1 failed |
| 失败时不推 `failed` | 1 failed |
| 开工不推 `drafting` | 1 failed |
| 作业行不在也硬写事件 | 1 failed |

## 四、验证

- `pytest tests/v041/test_regen_events.py -q` → `7 passed`
- `ruff check .` → All checks passed · `mypy --strict flint eval harness` → 371 文件零条
- 全量 `pytest -q`（单跑，309 秒）→ `5426 passed, 422 skipped`，零红

## 五、没有做的

- **真栈上没有量**：`2026-08-12` 那次实测用的是本机模型真跑。这台机器上没接模型，
  本卡的证据全部来自回放 provider 打测试库。「真栈上 `jobs.state` 走到 `done`」这一句没有核过；
- **屏上还没接**：`WorkbenchAnnotate` 仍停在「已提交」、不订阅作业（`WB-06` 的绕行）。
  撤绕行是 `CHAIN-UI-01` 的事；
- 单据 `REGENERATE-JOB-WRITES-NO-EVENTS` **没有关**：块级 `revision` 那一格 `DEC-063` 写明不在范围。
  状态行与文末各补了一段落地记录；
- `harness/demo_server.py#_run_regenerate` 把作业丢进线程池跑，异常在那里没人接。
  现在状态与事件由 `run_regenerate_job` 自己写，这条路上失败也会落 `failed`；`jobs.error` 那一格
  在 demo 这条路上仍是空的（只有 worker 那条路会落）。没有动。
