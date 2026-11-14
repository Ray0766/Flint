# v4 写着「两版互链（`sibling_deliverable_id`）」，而冻结件里没有这个字段

**状态** open · 2026-08-12 · `AUD-PACK-01` · owner 已答复 `DEC-064`（2026-10-27），待落地

不阻断本卡其余部分（v4 的说明文案照落）。阻断的只有「两版互链」这一件。

## 一、设计稿那一句

`前端设计/应用前端设计需求/design-handoff/Flint v4.dc.html`（受众选择那一屏）：

> 任一受众生成后可再生成另一版本 · 钉同一 ledger 版本 · **两版互链（`sibling_deliverable_id`）**

## 二、实查：冻结件里没有这个字段

```
grep -c 'sibling' contracts/models.py        → 0
grep -c 'sibling' contracts/protocols.py     → 0
grep -c 'sibling' contracts_v04/models_v04.py→ 0
```

`Deliverable`（`contracts/models.py:393`）今天的字段是：

```
deliverable_id · project_id · type · version · supersedes · inputs ·
ledger_version · generation_record_id · stale_reasons · created_at · reproducible
```

**关系只有一条 `supersedes`**（这一份接替了哪一份，纵向），
没有任何一格表达「这一份与那一份是同一材料的两个受众版本」（横向）。

## 三、`S2-1` 说了停在这里

> `contracts/models.py` 与 `contracts/protocols.py` 是**唯一真相**。NEVER 修改冻结件；
> 类型不够用 → 停止实现，按 `S9` 写问题单。

所以本卡**NEVER 在前端编一个 `sibling_deliverable_id` 出来**——
前端编出来的关系没有落点：它既不进库，也没有第二个读它的人，
而屏上会显示成「两版已互链」这样一句**没有任何东西在支撑的话**。

## 四、两种口径（**没有自己择一**）

| 口径 | 做法 | 代价 |
|---|---|---|
| 甲 · 加字段 | `Deliverable` 加 `sibling_deliverable_id: str \| None` | **动冻结件** = 一次修订窗口（`S2-1`/`S9-1`），且要定清写入方（组稿收尾时两边互写）与它与 `supersedes` 的关系 |
| 乙 · 由现有字段推 | 同一 `project_id` + 同一 `ledger_version` + `type` 不同的两份互为对方的另一受众版 | 不动冻结件；代价是这条关系**每处各推一遍**，且同一项目同一账本版本下生成过三份时会推出多对 |

乙的可行性今天可查：`Deliverable` 有 `project_id` 与 `ledger_version` 两格，
按它们分组即可。**但那是一条推导规则，不是一条记录下来的事实**——
两者的差别在于：推导规则改一次，历史产物的关系跟着变。

## 五、v4 那一句里另外两半**今天已经成立**

- 「任一受众生成后可再生成另一版本」：`POST /projects/{id}/proposal` 与
  `/report` 各自独立，互不排斥；
- 「钉同一 ledger 版本」：`Deliverable.ledger_version` 就是这一格，
  组稿时由 `freeze_ledger` 定死（`flint/jobs/compose.py`）。

**只有「互链」这一半没有落点。**

## 六、需要 owner 的什么

甲（开冻结件修订窗口）或乙（定成推导规则并写明它是推导的）。
在此之前，受众那一屏**不显示任何互链信息**——NEVER 印一句系统答不上来的话。

## owner 答复（`DEC-064` · 2026-10-27）

选**甲 · 加字段**：`Deliverable.sibling_deliverable_id: str | None`（带默认值），组稿收尾两边互写；与 `GapNoticeContent` 两件合一个修订窗口。

选项文本由 Claude 在会话里拟、owner 点选——出处与措辞的处置见 `DECISIONS-v04.md#DEC-064`。
