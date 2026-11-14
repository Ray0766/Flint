# 单块重写作业**不写事件、也不推状态**：屏上没有任何办法知道它结束了

**状态** open · 2026-08-12 · `WB-06`（不阻断：本卡按实况绕行，绕法与代价写在下面） · owner 已答复 `DEC-063`（2026-10-27），待落地

## 一、实测（2026-08-12，真栈 + 真库 + 本机 Ollama）

```
POST /deliverables/del-job-4d22d6be-…/sections/market/regenerate?project_id=proj-demo-fixture
     {"block_id": "b-del-job-4d22d6be-…-market-1", "guidance": "把这一段写得更具体一点…"}
→ 200 {"job_id": "job-ed52221b-c91e-418c-a96a-6eef2c2e0841"}
```

**作业真的跑完了**（本机 qwen3.6:35b-a3b），产物在库里：

```
deliverables  del-job-4d22d6be-…-r-job-ed52221b-…   version=2  supersedes=del-job-4d22d6be-…
blocks        那一块的正文换了（"本市场判断基于以下成本核算口径与边界：…"）
generation_records  {"action":"regenerate_block","block_id":"…market-1",
                     "guidance":"把这一段写得更具体一点…"}  model=qwen3.6:35b-a3b
```

**而这两处一个字都没动**：

```
jobs        state = 'queued'（提交后 10 分钟仍是 queued，作业早已跑完）
job_events  0 行
```

## 二、为什么这是个病

前端知道作业结束的唯一两条路都断着：

- `GET /jobs/{id}` 永远回 `queued` —— 轮询它的屏会**一直转**；
- `GET /jobs/{id}/events` 一条事件都没有 —— 订阅它的屏**永远收不到终态**。

这正是本仓登记过的那一族：**「失败不写事件、屏上一直转圈」**
（`docs/blocked/SIX-FAMILIES-ADVANCE-STATE-WITHOUT-AN-EVENT.md` 同类）。
这一条更进一步：**成功也不写**。

`harness/run_worker.py` 里 `design_generate` 那一族的注释逐字写着同一个坑的解法：

> `DESIGN-STATE`：收尾要把 `jobs.state` 也推到 `done`，那要库连接。
> 不给的话事件流说 `done` 而作业表停在 `queued`——
> 用户侧就是「点了生成转圈不停，而内容其实已经出来了」。

regenerate 这一族**连事件流都没有**。

## 三、根因位置

`flint/jobs/worker_main.py#_run_regenerate` → `flint/intervene/…#run_regenerate_job`：
它写 `deliverables` / `blocks` / `generation_records`，
**不碰 `jobs`，也不 `append` 任何 `job_events`**。
对照 `run_compose`：那条链每一步都 `_enter_state` + `events.append`。

## 四、绕行现状（`WB-06` 落盘的那一版）

屏上**不轮询那个作业**（轮了就是转圈）。

**我先写的绕行是「轮项目的交付物清单，新出现的那一份就是产物」——实测那条路不通**：
`GET /projects/{id}` 的 `deliverable_ids` 是 `projects` 表里一个建项时写死的列，
组稿与重写落库都不回写它（库里已有四份交付物，那一列仍只有一条）。
单：`docs/blocked/PROJECT-DOES-NOT-LIST-ITS-OWN-DELIVERABLES.md`。

于是今天从「我提交了重写」到「产物是哪一份」**三条路全断**：
作业不写状态与事件 · 端点不回产物 id · 项目总览列不出新产出。

**落盘的那一版因此只说到「已提交」为止**：屏上写清改的是哪一块、批注是什么，
作业 id 留在 `data-*` 上；「好了没有」一个字都不说——
说不出来的事 NEVER 编一句像样的话糊过去。
产物在库里是真的（本单 §一那三行就是它），只是这一屏够不着。

**NEVER 由 `{原id}-r-{作业id}` 拼一个出来**：那个形状在库里确实成立，
但它是实现细节。拼出来的那天它变了，屏上会去问一个不存在的东西（`DEC-012` 同形）。

## 五、修法（三条，各自代价）

| 口径 | 做法 | 代价 |
|---|---|---|
| 甲 | `run_regenerate_job` 收尾推 `jobs.state=done` + 写一条终态事件 | 要给它库连接（与 `DESIGN-STATE` 同款处置）；改的是 `flint/`，本卡 outputs 之外 |
| 乙 | 端点回 `{job_id, deliverable_id}`（产物 id 是**确定的**：`{原}-r-{job}`） | 前端从此不用猜；但那个 id 形状是实现细节，写进契约要 owner 点头 |
| 丙 | 新增 `GET /deliverables/{id}/successor` | 一条新端点 + 一次路由装配 |

甲最贴近既有形状（`run_compose` 就是那么做的），且顺手把
「失败了」与「还在跑」重新分开。

## 六、需要 owner 的什么

三选一。选甲的话可以顺带把 `blocks.revision` 那一格一起看了：
重写产物里那 22 块的 `revision` **全是 1**，
而工单 `WB-06` acceptance 要的是「未受保护的改得动且 **revision +1**」——
今天版本号涨在**交付物**那一层（v1 → v2 + `supersedes`），块级 `revision` 没有涨。

## owner 答复（`DEC-063` · 2026-10-27）

选**甲**：`run_regenerate_job` 照 `run_compose` 推 `jobs.state=done` 并写终态事件。`blocks.revision` 那一句不在本次答复范围，原样待议。

选项文本由 Claude 在会话里拟、owner 点选——出处与措辞的处置见 `DECISIONS-v04.md#DEC-063`。
