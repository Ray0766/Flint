# OVERVIEW-01 · 项目总览的交付物只剩一份清单（`DEC-063`）

**状态**：verified @2026-11-14。第 17 批第二张，卡单 `docs/trace/B17-PLAN.md`。

## 一、装载清单

`flint/api/project_overview.py`（全文）· `DECISIONS-v04.md:375-391`（`DEC-063` 与影响面）·
`docs/blocked/PROJECT-DOES-NOT-LIST-ITS-OWN-DELIVERABLES.md` · `tests/v041/test_be_project_overview.py:1-125`
（既有搭法）· `tools/ui_probe_wb_annotate.py:85-160` · `web/components/workbench/WorkbenchAnnotate.tsx:28-60` ·
`flint/topic/store.py:254-290` · `docs/trace/B17-PLAN.md` 的 stale_premise 一节。

## 二、改前实况

`GET /projects/{id}` 回两样：`deliverable_ids`（`projects` 表的一列，建项时写一次）与
`deliverables[]`（现查 `deliverables` 表）。后者从 `BE-01` 起就在、一直是对的。
读前者的只有一处代码：`tools/ui_probe_wb_annotate.py:95,134`。
`web/` 下没有任何代码读它——`WorkbenchAnnotate.tsx:39` 那一处是注释。

## 三、改动

| 位置 | 改了什么 |
|---|---|
| `flint/api/project_overview.py` | `_PROJECT_SQL` 不再取 `deliverable_ids`；`_JSONB_COLUMNS` 去掉这一项；文档串加一节说明 |
| `tools/ui_probe_wb_annotate.py` | 新增 `_listed()`，前后两次清单都改读 `deliverables[]` |
| `flint/topic/store.py` | 写入点加三行注释：那一列照冻结件落库，但不是清单的真相 |
| `docs/blocked/PROJECT-DOES-NOT-LIST-ITS-OWN-DELIVERABLES.md` | 状态行改 closed，文末加关闭节 |

**没有动的**：`projects.deliverable_ids` 列本身（`DEC-063` 原话「列保留、不再读」，删列不授权）；
冻结件 `Project.deliverable_ids`；`harness/demo_seed_report.py:321` 仍往那一列写一条——它是在按冻结件造
`Project`，不是在列产物。

**「列上写明它不再是真相」落在代码注释，没有落成库里的列注释**：`COMMENT ON COLUMN` 要一条迁移，
而 `B17-PLAN` 给 `CONTRACT-REV-01` 预留的迁移号 0028 已经被 `REGION-CN-HK` 占了。
为一句注释开一条迁移不值，写在了写入点与读取模块两处。

## 四、判据先行

`tests/v041/test_overview_deliverables.py`（6 条）先写，改前 `4 failed, 2 passed`。
种子里那一列故意放一个库里没有的 id，响应里出现它即红。

**判据自己错过一次**：第一版用正则剥掉全部三引号串再搜列名，把 SQL（也是三引号串）一起剥掉了，
「查表那一句得在」那条自证当场红。改成用 AST 取文档串之外的字符串常量。

变异验红：把那一列加回 `_PROJECT_SQL` → `2 failed`；还原 → `6 passed`。

## 五、验证

- `pytest tests/v041/test_overview_deliverables.py -q` → `6 passed`
- `ruff check .` → All checks passed · `mypy --strict flint eval harness` → 371 文件零条
- 全量 `pytest -q`（单跑，301 秒）→ **`5419 passed, 422 skipped`，零红**。
  这是这台机器上第一遍全绿。跑完 `git status` 里的生成物只剩 `MAC-07` 登记的那 4 个。

## 六、留给后面的

- `WorkbenchAnnotate.tsx:36-47` 那段注释还写着「三条路全断」。其中总览这一条现在是通的；
  屏上真去读它、注释跟着改，是 `CHAIN-UI-01` 的事，本卡 outputs 不含 `web/`；
- `tools/ui_probe_wb_annotate.py` 改了读法之后**没有在真栈上重跑**（要 playwright 环境与模型）。
  `projectListChanged` 这一格在重写产物落库后预期变成 true，这句是推的，不是量的。
