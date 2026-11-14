# FIX-02 · demo 报告正文引用的九个实体从未入库

**卡** `docs/steward/tasks-v041-b3.json#FIX-02` · **cycles 1（oneshot）** ·
**self_review = true** → §5 · **owner_review = false** · **依赖** `WIRE-02`

## 1. 装载清单

卡面 FIX-02 · `docs/blocked/DEMO-REPORT-REFS-NOT-SEEDED.md` 全文 ·
`harness/demo_seed_report.py` 全文 · `flint/api/deref.py` 的六段 SQL 与
`chart_specs` / `DEFAULT_GAP_HINTS_SOURCE` / `DerefApiDeps` ·
`flint/ledger/store.py` 的 `derive` / `_apply_changes` ·
`flint/evidence/docstore.py`、`flint/pricebook/seed.py`、`flint/topic/store.py` 的写面 ·
`contracts/models.py` 的 `Fact` / `Doc` / `Citation` / `Project` / `QualityCard` ·
`docs/trace/FB-08.md` §8-1。约 18k tokens，预算 40k 以内。

## 2. 缺陷：树种下了，树引用的东西没种

`harness/demo_seed_report.py` 只写 `deliverables` 与 `blocks` 两张表，
而它写的 Block 树引用了**九个实体**。装配后实测（真栈 HTTP）：

```
/facts/fact-demo-vecdb-cost            404  no such fact
/facts/fact-demo-infer-cost            404
/price-entries/pe-demo-vecdb-2026      422  （缺 quantity 参数）
/price-entries/pe-demo-gpu-2026        422
/citations/cit-demo-arxiv-2506-06962   404  no such citation
/citations/cit-demo-gh-lightrag        404
/charts/chart-demo-cost-trend          404  no such chart
/cards/qc-demo-fixture-01              404  no such evidence card
/hints/sec-04-gap-hints                404  no gap hints stored for this ref
```

**前端的显示一直是对的**（FB-09：如实标注 + 显示原 id），坏的是数据面。

## 3. 补种六条，**三条 NEVER 顺手修绿**

补种（全部走生产 store，NEVER 在夹具里另写一份写库口径）：
`PgProjectStore` → `PgLedgerStore.derive` → `PgDocStore` → `seed_pricebook_on`。

| 引用 | 现况（真栈实测） |
|---|---|
| 两条 fact | 200 · 记账口径 + 数值 + 单位 + 出处 |
| 两条 price | 200 · `9600–18000 CNY` / `4320–10080 CNY`（后端按 quantity 算） |
| `cit-demo-arxiv-2506-06962` | 200 · 公开文献 + 钉住段落 |
| `cit-demo-gh-lightrag` | 200 · **失锚态**照实标记 |
| `chart` / `质量卡` / `gap hints` | **照旧 404** → `docs/blocked/DEMO-REFS-NO-STORAGE-FACE.md` |

**质量卡那条是本卡最该被看见的判断。** 它是三条里唯一「往 `evidence_cards`
塞一行就能当场变 200」的——我没塞。理由：冻结件写着
`QualityCardContent.card_ref` **→ `QualityCard`**，而 `QualityCard` 现算不落库
（FB-08 §8-1 已登记）；`/cards/{id}` 服务的是**另一个实体** `EvidenceCard`。
塞进去之后屏上「质量卡」那一格里显示的是一张证据卡：
**404 变成了一个看起来对的答案，而那个类型不符从此没人看得见**。
一个诚实的 404 比一个似是而非的 200 更接近真相。

三条留着还有一个作用：补完那六条之后，**它们是这一屏上仅剩的 FB-09 活样本**——
九条全绿的屏幕反而看不出「端点不可用时长什么样」。

## 4. 三处 NEVER 编造

1. **fact 说的是记账口径，不是市场行情**。编一条「2026 年主流报价 800–1500 元」
   会被读成一个有出处的数字。钱在 PriceCell 那条通道——三通道 NEVER 混用（S2-2），
   这里说数量、那里说单价，正是那条铁律在这张表上的样子；
2. **价目的 `source` 自报家门**：「夹具数据 · harness/demo_seed_report.py 写死，
   NEVER 当作真实报价」。只写在脚本注释里的话，屏幕上那两个金额与真实报价长得一模一样；
3. **LightRAG 那条引用 `quote_span=None`**，走失锚态。编一句 README 原文把它填满，
   屏幕上与真引文长得一模一样。

另：两条 fact 的出处指向第三篇 doc——**那篇 doc 就是本脚本自己**
（`kind="user_upload"` / `origin="user_provided"` / `access="private"`）。这是实话，
且顺带把 `access="private"` 那条诚实态（禁外链 + 强制标注）也带上了这一屏。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_demo_refs_seeded.py -q → 9 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3862 passed（FIX-01 收卡时 3853，本卡 +9）
            vitest deref 两文件      → 19 passed（FB-09 组件行为未受影响）
真栈取证:   python -m harness.demo_seed_report（demo 库）→ 10 条端点逐条 curl
视觉取证:   ui_probe /deliverables/del-demo-fixture-report
            → 控制台 error **8 → 3**（剩下的 3 条正是没有存储面的那三个）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 补种或改指向 | `test_every_reference_with_a_storage_face_resolves`（**引用清单从 `build_tree()` 现取**，NEVER 手抄——手抄的那份在有人加第十条引用时不会跟着变） |
| ② 判据是真栈上逐条解引用 | 全文件走 `create_app(dsn)` + `TestClient` 发 HTTP；`test_the_content_is_real_content_not_an_empty_shell`（判**内容**：空 statement / 空 source 照样绿的话，屏上那句话仍然是空的）、`test_an_unseeded_id_still_returns_the_honest_404`（阴性对照：没有它，那些 200 可能是「对谁都回 200」换来的） |
| ③ FB-09 既有行为保留 | `test_the_three_without_a_storage_face_stay_honest`（三条照旧 404 + `code == "NOT_FOUND"`，**有了存储面就红**）、`test_the_seed_script_still_declares_its_fixture_boundary`（夹具身份写进**数据本身**：价目 source 回给前端、私有材料禁外链） |
| ④ 关闭问题单 | `test_the_ticket_is_closed` |
| （自加） | `test_the_fixture_facts_never_claim_to_be_promoted`、`test_seeding_twice_is_idempotent`、`test_every_kind_of_reference_in_the_tree_is_accounted_for`（树里加了新的一支 `BlockContent` 而提取器没跟上时，那条新引用会**悄悄不在任何判据下**） |

**② 改既有文件一处**（卡上 outputs 之内）：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `harness/demo_seed_report.py` | ①只写 deliverables/blocks → 连引用实体一起种（`_seed_referenced` + 四个 `fixture_*()`）；②`_drop` 按夹具 id 逐表撤（**NEVER 出现不带 WHERE 的 DELETE**）；③`seed()` 加 `dsn` 参数、`main()` 加 `--dsn` | **卡上 outputs**，本卡主体。`dsn` 那处是判据要求的：acceptance② 要在真栈上验，而真栈判据 MUST 跑在**测试库**上（§五.8），demo 库地址写死在模块里就没法验 |

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；未新增依赖。

**③ 变异考 7 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 退回缺陷态（不种引用实体） | 红 |
| ② 只种一半（价格不种） | 红 |
| ③ 空壳（fact 的 statement 留空） | 红 |
| ④ 冒充 `promoted_claim`（连 `source_claim_id` 一起给足，能过冻结件校验） | 红 |
| ⑤ **把质量卡塞进 `evidence_cards`**（数据侧变异，不是改代码） | 红 · `card qc-demo-fixture-01 有存储面了：200` |
| ⑥ 价目 `source` 不再自报夹具 | 红 |
| ⑦ 树里加第十条引用（未种） | 红 · 证明「现取清单」不是摆设 |
| ⑧ 假变异对照：只改一句注释 | 全绿 |

⑤ 是本卡最该有的那条：它演的正是**下一个人顺手把 404 修绿**的那一手。

**④** 装载约 18k tokens；**⑤** 禁用词六词 0 命中。

## 6. 登记未做

1. **屏上看不出那两个金额是夹具数据**。`source` 在响应里（判据守着），
   但 `web/components/DerefValue.tsx` 只在 `stale` 时显 `price_data_note`，
   不显 `source`。改它在本卡 outputs 之外。
   缓解：同一行的 fact 正文以「夹具口径：」开头，**就在金额旁边**。
   要不要让每个价格都显出处，是产品口径，不是夹具的事。
2. **`qc-demo-fixture-01` 的口径之争没解**：`card_ref` 到底指 `QualityCard`
   还是 `EvidenceCard`。已在 `DEMO-REFS-NO-STORAGE-FACE.md` 列成 owner 待定项。
   **先定口径，再谈补种**——反过来做就是拿数据把口径问题盖住。
3. **黄标（价格过期）那条诚实态没覆盖**：两条价目都写成 2026 年、未过期。
   造一条过期的能把 `yellow_flag` 也带上屏，但那要动 `check_stale` 的时钟口径，
   本卡没碰。
4. **证据卡那行 INSERT 在 `flint/jobs/ingest.py` 里是内联写的**（没有可复用的函数）。
   本卡最终没有写卡，所以没有复制那段 SQL；哪天真要种证据卡，
   先把它提成函数，NEVER 抄第二份。
5. **claim（`clm-demo-01`）与 profile（`research.publications[0]`）两条引用不在本卡**：
   它们不属于解引用六族，各有自己的读取面。判据把它们显式列成 `OUT_OF_FAMILY`，
   NEVER 静默跳过。
