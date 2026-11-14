# 项目总览列不出它自己产出的交付物：`deliverable_ids` 是建项时写死的一列

**状态** closed @2026-11-14 · `OVERVIEW-01`（`DEC-063`） · 开单 2026-08-12 `WB-06`（连带 `WB-03-b`）

## 一、实测（2026-08-12，真栈 + 真库）

```
GET /projects/proj-demo-fixture
→ "deliverable_ids": ["del-demo-fixture-report"]        # 一条

库里同一个项目底下实际有 **四份**：
  del-demo-fixture-report                       version 1
  del-job-4d22d6be-…                            version 1   ← 第 12 批真跑的 report
  del-job-85bc6baa-…                            version 1   ← 同批的 proposal
  del-job-4d22d6be-…-r-job-acbe737c-…           version 2   ← WB-06 这次重写的产物
```

## 二、根因

`projects.deliverable_ids` 是 `projects` 表里的一个 **jsonb 列**（迁移里就有），
**建项时写一次，此后无人回写**：`flint/jobs/compose.py#run_compose` 存
`Deliverable` 时只写 `deliverables` 表；重写那条路（`run_regenerate_job`）同理。
`flint/api/project_overview.py:50` 如实把那一列读出来——**端点没错，数据是旧的**。

## 三、这条为什么要紧

它是「用户从哪儿找到自己生成的东西」的唯一一条路：

- 项目总览屏列不出真正的产出 → 用户在界面上**找不到自己刚生成的报告**；
- `WB-06` 本来打算靠它做「重写完把预览换到新版本」（提交前后比清单，
  新出现的那一份就是产物）——**那条绕行因此不成立**，
  已在 `docs/blocked/REGENERATE-JOB-WRITES-NO-EVENTS.md` 里改口径；
- 与那张单合起来看：从「我提交了一次生成/重写」到「产物是哪一份」，
  今天**三条路全断**：作业不写状态与事件 · 端点不回产物 id · 项目总览列不出新产出。

## 四、两种修法

| 口径 | 做法 | 代价 |
|---|---|---|
| 甲 · 落库时回写 | `save_deliverable` 同事务把 `project_id` 那一行的 `deliverable_ids` 追加一条 | 一处写入两张表，要在同一事务里（否则会出现「交付物在、清单里没有」的半态） |
| 乙 · 总览改查 | `project_overview` 不读那一列，改 `SELECT deliverable_id FROM deliverables WHERE project_id = $1 ORDER BY created_at` | 那一列从此是死数据（要么删列，要么写明它不再是真相）；顺带能带上 `version`/`supersedes`，`WB-06` 想要的「哪一份接替了哪一份」也就有了 |

**乙更贴近「一处定义他处引用」**：交付物属于谁，`deliverables.project_id` 本来就是真相，
`projects.deliverable_ids` 是它的第二份副本——而两份副本今天已经不一致了。

## 五、需要 owner 的什么

甲 / 乙 二选一。选乙时顺带定一条：总览要不要一并回 `version` 与 `supersedes`
（`WB-06` 的「换到新版本」与 `WB-03-b` 的「作业产出了哪一份」都要这两格）。

## owner 答复（`DEC-063` · 2026-10-27）

选**乙 · 总览改查**：`project_overview` 改查 `deliverables` 表并回 `version` / `supersedes`；`projects.deliverable_ids` 列保留、不再读（删列属数据删除，未授权）。

选项文本由 Claude 在会话里拟、owner 点选——出处与措辞的处置见 `DECISIONS-v04.md#DEC-063`。

## 关闭（2026-11-14 · `OVERVIEW-01`）

`DEC-063` 落地的是「总览改查表」那一半：`GET /projects/{id}` 不再回 `deliverable_ids`，
交付物只认 `deliverables[]`（现查 `deliverables` 表，带 `version` / `supersedes`）。

**本单开单时的一句要更正**：「项目总览列不出新产出」只对那条旧列成立。`deliverables[]`
从 `BE-01` 起就在响应里，也一直列得出新版本（`docs/trace/B17-PLAN.md` 的 stale_premise 一节）。
断的是读的人——取证脚本 `tools/ui_probe_wb_annotate.py` 读的是旧列。它已改读 `deliverables[]`。

`projects.deliverable_ids` 那一列**留在库里，没有删也没有清**（删列是数据删除，`DEC-063` 不授权）。
屏上「提交之后去总览找产物」那一步归 `CHAIN-UI-01`，不在本单。

判据：`tests/v041/test_overview_deliverables.py`。
