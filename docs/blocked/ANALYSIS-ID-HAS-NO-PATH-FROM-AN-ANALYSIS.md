# `POST /projects/{id}/report` 要 `analysis_id`，而今天没有一条「从分析拿到它」的路

**状态** open · 2026-08-12 · `WB-03`（阻断 `WB-03-b`） · owner 已答复 `DEC-061`（2026-10-27） · 后端那一半已落地：`REPORT-SRC-01`（2026-11-14 verified）；屏上那一半（带着作业号去提交）归 `CHAIN-UI-01`，在那之前本单不关

**阻断**。owner 2026-08-12 已实查过同一处并点名「开单时把三种口径各写一条，
NEVER 自己择一」。本单先把实况钉死，再把三种口径各写一条，末尾是我复核时
多查到的两件事（它们改变了「哪一种口径最省」的答案，但**选哪一种仍是 owner 的**）。

## 一、实况（2026-08-12 实测，真栈 + 真库）

| 处 | 原文 | 意味着 |
|---|---|---|
| `flint/api/compose.py:46` | `class ReportSubmit: analysis_id: str` | 提交成文**必填**这一格 |
| `flint/jobs/worker_main.py:131` | `_payload_str(payload, "analysis_id")` → `sources` | 它被当作 `source_deliverable_ids` 用 |
| `flint/compose/freeze.py:29` | `SELECT * FROM claims WHERE deliverable_id = ANY($1::text[])` | 它是**一批 claim 的 `deliverable_id`**，不是某张表的主键 |
| `flint/jobs/gate1.py:111` | `analysis_product_id(job_id) = "analysis-" + job_id` | 分析产物的 id **由分析作业 id 决定** |
| `flint/jobs/gate1.py:199` | `INSERT INTO claims (…) VALUES (…)` | 判定的 claim 就落在那个 id 底下 |

库里对得上（`docker compose exec postgres psql`，2026-08-12）：

```
claims:       1 行，deliverable_id = analysis-job-4c558f32-f8a2-4a25-9215-f76c6781ff91
jobs:         job-4c558f32-… kind=gate1_analysis state=done
deliverables: 3 行，没有一行是分析（del-demo-fixture-report / del-job-4d22… / del-job-85bc…）
```

**没有 `analyses` 表**——这是设计，不是遗漏。`flint/jobs/gate1.py:100-104` 逐字写着：

> 交付物是 `del-{job}`，分析产物是 `analysis-{job}`，两者永远撞不上。
> `claims.deliverable_id` **没有外键**（`migrations/0008`），
> 所以这个 id 不需要、也 NEVER 去 `deliverables` 表建一行假记录——
> 建了的话，交付物列表里会多出一份没人能打开的「报告」。

**缺的是把它送到前端的那一段。** 两条相关端点实测回什么：

```
GET /jobs/{id}       → job_id kind project_id state progress partial_output_ref
                       budget cost_accum error created_at updated_at
                       （partial_output_ref = "snap-{job}-verdict"，是快照 id，不是 claim 的 deliverable_id）
GET /projects/{id}   → project_id owner origin_id topic_ids chosen_topic_id
                       deliverable_ids[] status topics[] jobs[]
                       （deliverable_ids 取自 deliverables 表 → 分析产物**不在里面**）
```

`harness/e2e_smoke.py:84` 那一份 `analysis_id` 是**从配置直接给的**
（`cfg.analysis_id`，第 129 行原样发出去），不是从上一步读回来的——
所以那条冒烟链**从来没有验证过这一段**。

## 二、三种口径，各写一条（owner 点名要的形态）

### 口径甲：它就是 job_id 的一个别名 → 端点自己换算

`POST /projects/{id}/report` 收 `analysis_job_id`，服务端调既有的
`analysis_product_id()` 换成 claim 的 `deliverable_id`。

- 好：前端只需要它本来就有的东西（发起分析回的 `job_id`）；零新表；换算规则仍**只有一处**。
- 坏：既有 `analysis_id` 这一格的语义要改（或并存两格），`harness/e2e_smoke.py` 与
  `tests/m3/test_m3_057.py` 那几处传 `analysis_id` 的调用点要跟着动。
- 注意：**它不是 job_id 本身**，而是 `"analysis-" + job_id`。写成「别名」时
  MUST 把那个前缀写进去，否则下一个人会直接把 job_id 填进去，
  而 `freeze_ledger` 会查到 0 条 claim —— **不报错，出一份全是 `gap_notice` 的报告**。

### 口径乙：新建 `analyses` 表，分析跑完落一行

- 好：「有哪些分析」第一次成为可查的事实（今天只能靠 `jobs.kind='gate1_analysis'` 反推）；
  `GET /projects/{id}` 可以列出它们，屏上能让用户选「拿哪一份分析去成文」。
- 坏：一张新表 + 一次迁移 + 一条写入路径；而 `gate1.py:100` 那段注释明确拒绝过
  「给分析在 `deliverables` 里建一行」——新表要与那条判断并存，
  两个「分析在哪」的答案会同时存在（新表 vs `analysis-{job}` 前缀约定）。

### 口径丙：`report` 端点改收 `job_id`

- 好：前端更省——发起分析拿到的就是 `job_id`，一路传下去。
- 坏：`job_id` 在这条链上会出现两次含义（这次成文作业自己的 id / 上游分析作业的 id），
  端点内部仍要换算，等于甲但名字更容易被读错。
- 另一处代价：`report` 也能从**别的 report**派生（`worker_main.py:131` 同时读
  `report_id`），改成收 `job_id` 之后这两条来源的形状就不一样了。

## 三、我复核时多查到的两件事（不影响「谁来选」，但影响成本）

1. **换算规则今天已经存在，且已经有一处在用它**：
   `tests/v041/test_e2e_full_stack.py:231` 写的就是 `source = analysis_product_id(analysis_job)`。
   也就是说甲/丙不需要发明任何东西，只是把这一行从测试搬进产品路径。
2. **前端自己拼 `"analysis-" + job_id` 是四条里最坏的一条**，本单点名反对：
   那会让同一条规则在 Python 与 TypeScript 各存一份，
   而它们分叉的那天，症状是「报告里全是 `gap_notice`」——
   一个看起来像模型不给力、实际是 id 拼错了的故障。
   （同形先例：`DEC-012` 判死「猜一个 id 去问」；`web/app/combo/page.tsx:34-41`
   拦下过「按 id 形状推出证据卡 id」的同一种手。）

## 四、绕行现状（`WB-03-a` 已落盘的部分）

中栏不假装这一步能走：提交按钮走**真**端点、屏上印**真**答复；
到这一格时如实说「这条链今天断在哪、单号是什么」，
**NEVER 转圈、NEVER 填一个夹具 id 冒充**（填了的话，屏上写着「用你选的卡生成」，
实际生成的是夹具那一份 —— 那正是本批 `never_html_regex` 那条规则在防的同一类事）。

## 五、需要 owner 的什么

**四选一**（甲 / 乙 / 丙 / 先不做），一句话即可。选定后 `WB-03-b` 解阻，
届时还需要 §六那条的答复才跑得起来。

## 六、连带：这条链上还有两处独立的断点（各有自己的单）

- `docs/blocked/COMBO-FAMILY-HAS-NO-PROVIDER-ANYWHERE.md` —— 链的**第一步**今天 503；
- 发起分析要打**真实** github / arxiv（`harness/run_worker.py` 注的是 `build_live_deps`），
  而 `DEC-057` 那个网络窗口逐字写着「只授权这一次跑通」。
  本批规则第一条是「本批 NEVER 真实网络」，所以这一步我**一次都没提交过**
  （提交了就是在队列里埋一颗地雷：worker 一起就打真实站点）。

## owner 答复（`DEC-061` · 2026-10-27）

选**甲 · 服务端换算**：端点改收 `analysis_job_id`，服务端调 `analysis_product_id()` 换算；前端不拼 id。

选项文本由 Claude 在会话里拟、owner 点选——出处与措辞的处置见 `DECISIONS-v04.md#DEC-061`。
