# REGION-04 trace — 聚类 region 分桶 + 簇血缘 region 维度 @2026-08-02

## 0 归属声明

`tests/v04/region/test_cluster_bucketing.py` 的**前 146 行（红测部分）由并发会话写**，
它写完红测后停在半途：`flint/region/bucketing.py` 未落地，
所以我接手时 `pytest tests/v04/region -q` 是 **collection error**（那是它的中间态，不是缺陷）。

本会话做的是：读其红测 → **按红测补实现转绿** → 补齐卡 outputs 的两处缺口。

## 1 采纳其红测的理由

它的红测口径与我要写的一致，且覆盖到位：
2 簇 0 合并、成员 region 单一性、三区三簇、同区不相似分簇、空输入、
以及一条**参数面断言**（`bucket_and_cluster` 的签名里 NEVER 有
`auto_merge`/`cross_region`/`allow_cross` 之类开关）。最后这条抓得好——
留一个开关，就等于留一条「打开它就自动跨区合并」的路。

故**不重写**，按它的 API 契约实现。

## 2 我补的两处缺口（卡 outputs 与标题要求，红测没覆盖）

**① 双区样本没落成文件**（卡 outputs 明写 `fixtures/US/…,fixtures/JP/… 双区样本`）：
红测用的是内联 Python 数据——内联的没法被别的卡复用。
按 **E12 目录口径** `fixtures/{region}/{source_id}/{yyyy-mm-dd}.json` 落了两份：
`fixtures/US/demo-wire/2026-08-02.json`、`fixtures/JP/demo-wire/2026-08-02.json`
（同一事件的两国报道 = B5 的反例场景；`source_id` 用占位名，**K1 未决前 NEVER 写真实站点**；
日文原文 NEVER 翻译）。新增三条测试：文件存在、**用文件里的样本复跑 acceptance ①**、
日文原文未被翻译。

**② 卡标题的「簇血缘 region 维度」红测没覆盖**：补 `link_lineage()` —— **跨区父子直接拒绝**
（`CrossRegionLineageError`）。理由写进 docstring：血缘跨了区等于**从另一头绕过 B5**——
簇没合并，但血缘把两国的簇连成一条线，下游按血缘取「同一事件的历史」时又拿到两国混合的东西。
测试另断言**拒绝之后 NEVER 留下半挂的血缘**（`parent_cluster_ids == []`）。

## 3 实现里的一处判断
分桶**必须在聚类之前**，不是聚完再拆：先聚后拆是拆不干净的——一旦两国报道被合成一簇，
簇心已是两国报道的平均，再按 region 拆开时每一半的簇心都不是它自己的，
产出的是**哪国都不存在的假热点**。

## 4 验收
| 项 | 结果 |
|---|---|
| verify_cmd `pytest tests/v04/region/test_cluster_bucketing.py -q` | **13 passed**（原 8 + 本会话补 5） |
| `pytest tests/v04/region -q`（owner 指定的收尾门） | **52 passed** |
| `ruff check --no-cache .` | All checks passed |
| `mypy --strict flint` | 230 文件净 |

## 5 产出归属一览
| 文件 | 谁写的 |
|---|---|
| `tests/v04/region/test_cluster_bucketing.py` 前 146 行 | 并发会话 |
| 同文件后半（fixture 驱动 3 条 + 血缘 2 条） | 本会话 |
| `flint/region/bucketing.py` | 本会话（按并发会话的红测 API 实现） |
| `fixtures/{US,JP}/demo-wire/2026-08-02.json` | 本会话 |
