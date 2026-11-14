# v0.4.1 第 1 批 · 完成态报告（worker）

日期：2026-08-03。工单：`docs/steward/连跑工单-v041-第1批.md`。
机读任务真相：`docs/steward/tasks-v041.json`（7 卡 / Σ10 cycles）。
台账：`docs/progress-v041.jsonl`。

## 一句话

**断了的主链接上了**：提交 → 入队 → worker 消费 → 组稿产出真正文 → 过导出闸门 →
渲染出 markdown，这条链第一次真正跑通了一次，并且是**机器可验**的（`pytest` 里跑，
不是手工点一遍）。

## 卡况

| 卡 | 状态 | cycles | 产出 |
|---|---|---|---|
| ASM-01 组稿生成器注入 | verified | 1 | `flint/jobs/compose_deps.py` + 11 用例 |
| ASM-02 JobKind 分派表 | verified | 1 | `flint/jobs/dispatch.py` + 14 用例 |
| ASM-03 arq worker 装配 | verified | 2 | `flint/jobs/worker_main.py` + 13 用例 |
| ASM-04 定时批 cron 装配 | verified | 1 | `flint/jobs/cron.py` + 11 用例 |
| ASM-05 端到端冒烟 | verified（owner_review 待补审） | 2 | `harness/e2e_smoke.py` + 7 用例 |
| LEDGER-01 台账守门扩面 | verified | 1 | `tests/v041/test_ledger_pairing_v041.py` + 11 用例 |
| GOLD-01 金标采集脚手架 | verified | 1 | `harness/gold_collect.py` + 9 用例 |

**7 卡全 verified，Σ9 cycles**（工单估 Σ10）。新增用例 76 条。
另有 1 张按工单 §4 刻意不执行的留卡：`docs/blocked/E2E-REALSOURCE.md`。

## 全局门（收卡后跑，红态未停留）

```
$ python -m ruff check . --no-cache
All checks passed!
$ python -m mypy --strict flint
Success: no issues found in 273 source files
$ python -m pytest -q
1916 passed, 7 warnings in 158.57s
```

## 触碰边界（工单 §3：本批 NEVER 修改任何既有 .py）

**守住了。** 本批全部产出为新增文件：

- 新增产品代码 4 个：`flint/jobs/compose_deps.py`、`flint/jobs/dispatch.py`、
  `flint/jobs/worker_main.py`、`flint/jobs/cron.py`
- 新增 harness 2 个：`harness/e2e_smoke.py`、`harness/gold_collect.py`
- 新增测试 7 个：`tests/v041/*.py`
- 新增文档：`docs/trace/{ASM-01..05,LEDGER-01,GOLD-01}.md`、
  `docs/blocked/E2E-REALSOURCE.md`、本报告、`docs/progress-v041.jsonl`

`flint/jobs/compose.py`（含 `build_offline_compose_deps` 与 `_default_generator`）、
`flint/jobs/runner.py`（含 `EnqueueHook`）、`flint/jobs/sched.py`、
`eval/ledger_pairing.py`、`tests/m4/test_ledger_pairing.py`、`requirements.lock`
——**全部一字未动**，且各有一条测试直接断言它们没被改。

押后四项（候选③⑤⑥ + E1 观察项）**一件都没碰**。

## 需要 owner 知道的四件事

### 1. ASM-05 的 test-first 顺序偏离（我自己报的）

ASM-05 先写了 `harness/e2e_smoke.py` 再写测试文件，首跑即绿，**没有先看到红**——
违反 `worker.md` §4.2。原因是冒烟脚本本身就是这张卡的产出之一。补偿措施是每条 acceptance
都配了反例用例（详见 `docs/trace/ASM-05.md#断点与决策`）。**这条留给 owner / supervisor 判**，
我没有自行开脱。

### 2. LEDGER-01 的实测数与卡面数差 1

卡面写「实测 71 个事件、涉 60 张卡」，本次采集得到 **70 个事件 / 59 张卡 / 67 个去重对**。
台账是 append-only（只会长不会缩），差异来源没查到。**白名单以实测为准**，没有为了对上
卡面数字去凑。采集命令写在 `docs/trace/LEDGER-01.md` 里，可复跑核对。

### 3. 五个 JobKind 至今没有消费者（已显式声明，不是遗漏）

`revalidation` / `pricebook_scan` / `translate` / `design_generate` / `template_solidify`
——仓里确实没有它们的 per-job 消费者。分派表给每个都留了一行，被调到时**抛错并说明
现有代码在哪**（`flint/jobs/dispatch.py:UnwiredKindReason`），NEVER 静默排队。
接不接、什么时候接，是 owner 的排期决定。

同理，`gate1_analysis` / `daily_ingest` / `spec_export` 三个 handler 需要外部注入件
（真 searcher / source+embedder / 包清单），没注入时点名抛错。这三件里 gate1 的真 searcher
落在红线内——见下条。

### 4. 真实源冒烟需要 owner 在场点一次

`docs/blocked/E2E-REALSOURCE.md`。要的只是一次授权：允许本机对 `api.github.com` 与
`export.arxiv.org` 发只读检索。装配点已就位，无需改代码；跑完建议把结果录制进 `fixtures/`，
以后 CI 就不必再联网。

## 这批之后主链的真实状态

| 环节 | 之前 | 现在 |
|---|---|---|
| 提交报告 | 端点在，作业进表 | 同左 |
| 入队 | **没有钩子接到队列** | `build_enqueue_hook` 实接 arq，队列真实状态可断言 |
| 消费 | **没有任何进程消费** | `build_worker` burst/常驻均可，断点续跑已验 |
| 组稿 | **只产占位 heading（正文是 section_id）** | 生产生成器接上，产真段落 |
| 导出闸门 | 代码在，没被端到端触发过 | 409/200 两条用例都真跑过 |
| 定时批 | 批次定义在，**没人按它触发** | cron 注册面接上 worker，幂等复用既有锁 |
| 台账守门 | 只守 `progress.jsonl` 的 `M?-NNN` 卡 | v0.4 / v0.4.1 两本台账都被守住 |
| 金标备料 | 无 | 采集脚手架就绪（只采不判，可复现） |

## 停机依据

`worker.md` §7 / 工单 §5 的停机条件①：7 张卡全部 verified。收工四步已执行：
本报告 → `docs/FLINT-V041-DONE` → 删 `docs/WORKER.lock` → 结束回合。
