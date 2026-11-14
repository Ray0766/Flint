# MIGRATE-05 trace — design_handoff 差距登记 @2026-08-02

## 1 装载（05/06/07 三卡共用一次装载）

MIGRATE-05/06/07 三卡 + `WORKORDER-v04.md#2-J6/J7/J9` 三节 + 三处真件核实，
合计 ~3,200 字符 ≈ 3.2k tokens（占 8%）。三卡共用 `tools/check_impact_doc.py`，
**NEVER 写三个校验器**。

## 2 test-first

`tools/check_impact_doc.py` 先写 → 三条 verify_cmd 全跑 → 三条全红（文档不存在）→ 逐份落盘 → 全绿。

## 3 关键判断：包不在仓库

`design_handoff_flint_web/` **实测不在本仓库**（根目录无该目录）。
按 acceptance 第三条，所有数字逐条标 `[待核实]` 并写明来源是清单与既往审计，
**NEVER 写成我实测的结果**。包挂载后由 DESIGN-05 出实测值替换。

一处**我没有擅自扩写**的地方：v2 有六类新屏，但 J6 点名的「缺 4 类」是设置/收藏/图谱/设计台。
热点卡片广场与外链查看页不在这份清单内——差额属登记口径差异，照 J6 写 4 类并在文档里注明，
NEVER 自己改成 6 类。

## 4 self_review

① acceptance 映射：缺 4 类新屏（表格逐行 + 对应 v2 编号）／tabular-nums 与 ⚠ 两问题各自指向
DESIGN-05／`[待核实]` 标记齐全。反证：**h1**（把 `## known-issues` 改名）→ `缺小节`；
**h2**（把 `## i18n-hardcode` 正文清空）→ `小节是空的（只有标题不算登记）`。
② 无冻结件偏离：本卡不碰 contracts/，也不碰包（包不在仓库）。
③ 无禁用词：文档与校验器均无命中。
④ 复用：三卡共用同一校验器。
⑤ 装载 ~3.2k tokens，占 8%。

## 5 产出

`docs/handoff_gap_v04.md` + `tools/check_impact_doc.py`（后者为 05/06/07 共用，ruff 净）。
