# UIR-02 · 失败的作业屏上不再一直转（@2026-11-14）

卡单：`docs/trace/UIR-PLAN.md` 问题 8。同时是 `docs/blocked/SIX-FAMILIES-ADVANCE-STATE-WITHOUT-AN-EVENT.md`
六处里最要紧的那一处。

## 一、装载清单

`flint/jobs/worker_main.py:336-400` · `flint/jobs/dispatch.py:130-170` · `flint/jobs/state.py` ·
`flint/jobs/events.py:66-110` · `tests/v041/test_design_state.py:60-135` · 那张单据全文 ·
`web/lib/jobClient.ts:86-122` · `web/app/jobs/[id]/page.tsx`。

## 二、看到的

`CHAIN-UI-01-a` 验证时在真栈上发起一条成文作业，没接模型，它在 `draft` 这一步失败。
库里 `jobs.state = failed`、`error` 有文本；作业屏停在 `drafting`，没有任何失败提示，会一直这样下去。

## 三、两处改动

**后端**（`flint/jobs/worker_main.py#make_mark_failed`）：原来是一句直接把状态改成 `failed` 的 UPDATE，
不写事件流。现在：落 `error` 文本 → 追加一条带原因的 `failed` 事件 → 经 `enter_state` 推到 `failed`。
已经 `done` / `cancelled` 的不动；已经 `failed` 的只补 `error`，不再说一遍；没有那一行就什么都不写。

**前端**（`web/lib/jobClient.ts#applyEvent`）：这一处是改完后端、回到浏览器里才发现的。
归约器收到 `failed` 就置 `done`，流随即关掉，后面那条 `status/failed` 读不到——
屏上是「状态 drafting」底下印着「作业失败」，两句话打架。改成收到 `failed` 时同步把状态置为 `failed`。

## 四、判据先行

| 判据 | 条数 | 实现前 | 实现后 |
|---|---|---|---|
| `tests/v041/test_fail_events.py` | 8 | 4 failed（另 4 条是改前就成立、要保住的） | 8 passed |
| `web/lib/jobClient.test.ts` 新增一条 | 1 | `expected 'drafting' to be 'failed'` | passed |

变异验红（`make_mark_failed`，每次还原）：不写 failed 事件 → 2 failed · 不推状态 → 2 failed ·
已 failed 也再说一遍 → 1 failed · done/cancelled 也照改 → 2 failed · 不落 error 文本 → 3 failed。

**我自己撞了一次本仓那个老坑**：给 `make_mark_failed` 写的文档串里逐字提了那句旧 SQL，
`tests/v041/test_design_state.py` 与我自己的判据都读到了它，各红一条。改掉文档串里的字面量。

`tests/v041/test_design_state.py` 的「只写库不写事件」清单从六处减到五处，单据里那一行划掉并补了落地记录，单子不关。

## 五、验证

五条门单跑：`tsc --noEmit` 无输出 · `vitest` 86 文件 871 条 · `ruff` All checks passed ·
`mypy --strict flint eval harness` 371 文件零条 · `pytest` `5434 passed, 422 skipped`。

真浏览器（重起演示栈后）：从项目总览对一条跑完的分析点「生成报告」，9 秒后作业屏上
`data-job-status` 是 `failed`，`data-job-failed` 是
`LocalProviderUnavailable: local endpoint unreachable for qwen3.6:35b-a3b: [Errno 61] Connection refused`，
带 `role="alert"` 的那一块也在；Gate 入口与回总览入口都没有出现（失败的作业不该有）。
验证用的行与账本副产物已从演示库删净。

## 六、留着的

- 状态那一格印的是枚举原值 `failed` / `drafting`，不是人话（`UIR-05` 一并处理）；
- 另外五处只写库不写事件的仍是原样。
