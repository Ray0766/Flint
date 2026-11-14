# DEMO-REFS-NO-STORAGE-FACE · chart / 质量卡 / gap hints 全库没有存储面

**发现者** worker / FIX-02 补种 demo 引用实体时 · **发现时间** 2026-08-05
**状态** open
**待办归属** owner 定要不要建面 · **危害** 低（当前显示是诚实的，不是错的）

## 一句话

`FIX-02` 把 demo 报告正文引用的九个实体补种了六个；剩下三个**不是漏了，是没有地方可种**：

| 引用 | 出现在 | 端点 | 为什么种不了 |
|---|---|---|---|
| `chart-demo-cost-trend` | `bf-05` (`ChartContent`) | `GET /charts/{id}` | `ChartSpec` **只在模板里定义**，`assets/templates/` 那四份当前全是 `charts: []`。而 `flint/api/deref.py` 自己写着「**NEVER 去改 assets/ 里的模板凑数据**」——为一份 demo 夹具往产品模板里塞一个图表，等于让产品模板承担夹具的需求 |
| `qc-demo-fixture-01` | `bf-06` (`QualityCardContent`) | `GET /cards/{id}` | 冻结件写着 `card_ref` **→ `QualityCard`**，而 `QualityCard` 由 `flint/gate/quality_card.py` **现算不落库**（FB-08 §8-1 已登记）。端点服务的是另一个实体：`EvidenceCard`。往 `evidence_cards` 塞一行 `qc-demo-fixture-01` 能让它当场变 200——**代价是屏上「质量卡」那一格里显示的是一张证据卡**，而且从此没人看得见这个类型不符 |
| `sec-04-gap-hints` | `bf-08` (`GapNoticeContent`) | `GET /hints/{ref}` | 全库**没有** `section_states` / `gap_hints` 表。`DEFAULT_GAP_HINTS_SOURCE` 如实回 `None`（原话：「NEVER 回一个空列表：空列表读起来是『这一节没有缺口』，那是一句结论」） |

三条都要动 `FIX-02` **outputs 之外**的面（产品模板 / 现算的卡如何落面 / 新建表 + 往 `DerefApiDeps` 注取数函数），
按第 3 批 §五.1「改动面大于卡上 outputs → 停下走 `docs/blocked/`」开此单。

## 当前行为是对的，NEVER 当成缺陷去「修绿」

三条照旧回 `404 NOT_FOUND`，报告屏按 FB-09 如实标注并显示原 id。
补种完那六条之后，**这三条正是这一屏上仅剩的 FB-09 活样本**——
九条全绿的屏幕反而看不出「端点不可用时长什么样」。

**质量卡那条尤其不能顺手修绿**：它是三条里唯一「塞一行就能变 200」的，
也正因为如此，它是三条里唯一**会被误当成完工**的。

判据 `tests/v041/test_demo_refs_seeded.py::test_the_three_without_a_storage_face_stay_honest`
把这个状态钉住：**它们哪天有了存储面，这条会红**，红的时候来这里改单、
并把那一条移出 `NO_STORAGE_FACE`。

## 要 owner 定的

1. **图表**：`ChartSpec` 是否需要一个与产品模板分开的夹具模板目录
   （`DerefApiDeps.template_dir` 本来就可注入，demo 栈注一个 `assets/templates-demo/` 即可）？
   代价是 demo 栈与可部署应用的图表来源不同——这条差异要有人认。
2. **质量卡**：`card_ref` 到底指 `QualityCard` 还是 `EvidenceCard`？
   冻结件注释与 FB-08 卡面不一致（FB-08 §8-1 原样登记过）。
   这是**口径问题，不是数据问题**——先定口径，再谈补种。
3. **缺口提示**：`SectionState.gap_hints` 至今没有持久面。这是 M3 干预层的事，
   不是 demo 夹具的事；此处只登记「报告屏上有一个引用通道全系统无人写过」。
