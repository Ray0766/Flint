# REGION-12 · trace

**卡**：地区面⑤——`SourceColumns` 的原文词面（`PLAZA-02` 唯一的残留缺口）
**verify_cmd**：`pytest tests/v041/test_source_columns_verbatim.py -q` → **15 passed**
**cycles**：1（卡面估 2）

---

## 装载清单（实际）

| 来源 | 用途 |
|---|---|
| `docs/blocked/PLAZA-02-REGION-QUERY-AND-SOURCE-REGION-NOT-BUILT.md` 全文 | 缺口二到底缺什么、结案段的建议 |
| `web/components/source-columns/SourceColumns.tsx` 全文 | `SourceStatement` 契约 |
| `flint/region/by_source_region.py` 全文 | 合成句黑名单（本卡 import，不抄） |
| `flint/api/views.py` plaza 段 | 改点 |
| `flint/jobs/ingest.py` 的 `_day_membership` / `_step_heat` / `_step_cards` | 三跳的**方向**（本卡按同一个方向再走一遍） |
| `flint/region/backfill.py` 头部 | 同一条三跳的既有表述 |
| `flint/norm/canonical.py` · `flint/norm/terms.py` | `canonicalize` 与 term map 的加载法 |
| `web/components/plaza/PlazaCards.tsx` · `clusterToCard.ts` · `web/lib/viewsClient.ts` | 接线点 |
| `tasks-v04.json#HOTSPOT-07` + `docs/progress-v04.jsonl` | 确认 `source-columns/` 是 v0.4 已 verified |

估算约 26k tokens，未超 40k 预算。

---

## 断点与决策日志

### 一、开工第一件事：确认 `SourceColumns` 不能改

`web/components/source-columns/` 是 `HOTSPOT-07` 的 outputs，
`docs/progress-v04.jsonl:106` 记着 **2026-08-02 verified**。
`worker.md` §9.2 / `DEC-021`：**v0.4 已 verified 的实现与判据 NEVER 再改**。

这条约束**决定了整张卡的形状**：

- acceptance③「词面缺失时该列如实标注缺」→ 不能给组件加一个 `text?: string | null`；
- 也不能给 `text` 塞占位串——那个槽契约上是「原文」，
  塞 `—` 进去屏上会写着「微博说：—」，**而微博没说过这句话**。

落法：新建**调用方** `web/components/plaza/ClusterSourceLines.tsx`，
有词面的源进 `SourceColumns`，没词面的源**另起一行**如实说。
`test_the_frozen_component_was_not_touched` 钉住组件没被动过。

### 二、词面从哪来：三跳，与 `backfill.py` 同一个方向

```
cluster → lineage_results 当日成员（keyword_ids） → keywords.canonical
        → canonicalize 后与之相同的 trend_items_raw 条目 → 它们的 keyword 原文
```

第三跳要 canonicalize，因为 `trend_items_raw.keyword` 是原始词面而
`keywords.canonical` 是规范形。这条对应关系由 `_step_heat` 建立，本卡**按同一个方向再走**，
NEVER 反过来猜。

### 三、为什么不 import ingest 那段

`_step_heat` 绑着 `IngestDeps`（DSN、term map、embed、聚类阈值）与它自己的事务。
把它 import 进只读端点 = 把整张作业依赖图拖进来；而且
`flint/jobs/ingest.py` 是 v0.4 已 verified 的文件。

所以新建 `flint/region/source_text.py`：**纯函数**，不碰数据库、不碰配置，输入是已取好的行。
两处做的是同一个 join、不同的聚合（那边求和成热度，这里取词面），
join 本身由 `cluster_of_canonical` 一处表达，
`test_the_canonical_map_matches_the_ingest_shape` 判它与那边同构。

### 四、同一个源当天说了两条：取第一条并记数，NEVER 拼接

拼起来的那句话没有任何一个来源说过——**那就是 `B4` 禁的合成句，只是换了个地方合成**。
`SourceWording.also_said` 记条数，判据
`test_a_second_statement_from_the_same_source_is_counted_not_concatenated` 钉住。

### 五、种子第一版对不上：`keywords.canonical` 是手写的

第一版种子写死 `CANONICAL = "brain computer interface"`，
而两条原始词面 canonicalize 出来的根本不是它，于是 `by_source_text` 回 `{}`。

**这不是实现的错，是种子与真实数据的形状分了家。** 改法不是去凑那个字符串，
而是让种子**用产线那个函数算**（`_canonical_of` 调 `canonicalize` + 同一份 term map），
并且种**两个** keyword（两个源两种说法 → 两个 canonical → 都落进同一个簇），
这正是 ingest 的真实形态。

手写一个的话，判据会绿着，而线上那条链一条词面都对不上——
**而「对不上」的症状是屏上什么都不显示，看起来像没数据。**

顺带修一处：`lineage_results` 九列全 NOT NULL，阈值三列照 `S5` 初值填；
`kind` 用 `continued`（`_day_membership` 认的四种之一）。

### 六、`global` 在这一层也走呈现层合并

`ClusterSourceLines` 把 `global` 与未归区记号都映射成空串，
落进 `SourceColumns` 的未归区那一列（`UNKNOWN_REGION_KEY`，恒排最后）。
**这正是 `DEC-040` 的呈现层合并**，库里两者仍然可分辨。

---

## 视觉取证 —— 并且它抓出了一个真缺陷

重启 demo 后端后实测（`day=2026-07-05`）：

```
簇数：106 | 有词面的：106
两源以上有词面的簇：1
  c-20260629-108  {"ghtrend": "bci", "gtrends": "脑机接口"}
```

那一条正是本卡文档里一路举的例子——**它真的在库里**。

playwright 探到屏上：

```json
{"columns": 1, "labels": ["未归区"],
 "source_ids": ["ghtrend", "gtrends"],
 "texts": ["bci", "脑机接口"],
 "missing_line": 0, "console_errors": []}
```

`.ui-probe/region12-source-columns.png` **已用 Read 看过**：卡面主行是
`brain-computer interface`（**我们**起的名字），下面是两个源**各自**的说法。
这正是 `B4` 要的东西，而它此前在屏上不存在。

### 看屏看出来的缺陷：**屏上看不出谁说的**

两条陈述并排，`data-source-id` 在 DOM 里，**可见文本里没有来源**。
而这个组件自己的文件头写着「读者失去了『谁说的』这个唯一能判断可信度的东西」——
屏上现在正是这个状态。地区那一列顶不住：今天 `global=103 · CN=89 · NULL=1`，
绝大多数簇的源同区或无区，**同一列里两条陈述谁说的完全看不出来**。

改法在冻结组件里 → 按 §9.2 **立单不自行动手**：
`docs/blocked/SOURCE-COLUMNS-DOES-NOT-SHOW-WHO-SAID-IT.md`（四选一，推荐甲）。

**它不阻塞本卡任何一条 acceptance**（那四条问的是词面对不对、有没有被分数顶替、
缺项标没标、合成句有没有），所以 `PLAZA-02` 照常关闭，本单是新发现的另一件事。

---

## 改既有文件

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `flint/api/views.py` | plaza 只回 `by_source` / `by_source_region` | 加 `_term_map()`、`_day_source_wordings()`，每条簇多回 `by_source_text` | acceptance①：端点目前只回分数。词面拿不到，`SourceColumns` 就只能被喂分数——那是 `DEC-034`/`DEC-038` 禁的借槽 |
| `web/lib/viewsClient.ts` | `PlazaCluster` 无 `by_source_text` | 加可选字段 + 契约注释 | 不加的话 `tsc` 拿不到这个字段，前端只能 `as any` 绕过去——而绕过去之后**类型系统就不再守这一格** |
| `web/components/plaza/PlazaCards.tsx` | 网格项 `cards.map(card => …)` | 改 `clusters.map((cluster, index) => …)`，插入 `<ClusterSourceLines>` | `clusterToCard` 只搬卡面六槽（它**该**只搬那些），词面三张表在 `PlazaCluster` 上。要么把三张表塞进卡面属性（污染卡面契约），要么在这里同时拿到两者——选后者 |
| `web/messages/{zh,en}.json` | — | 各 +1 `source.wording.missing` | 缺词面那一态要有话说，且 NEVER 硬编码 CJK |

`web/components/source-columns/` **一个字节都没动**（判据钉住）。
`flint/jobs/ingest.py` **一个字节都没动**。

---

## self_review（卡上 `self_review=true`）

**① 测试真实覆盖 acceptance**

| acceptance | 判据 |
|---|---|
| ① 端点回原文词面（不再只回分数） | `test_the_endpoint_returns_each_sources_own_wording` · `test_the_wording_is_verbatim_not_normalised`（首尾空格 + 全角井号）· `test_the_two_sources_disagree_and_both_are_kept` |
| ② 分列 ≥2 列 · 无合成句 · 既有判据不倒 | `test_no_synthesised_sentence_reaches_the_wire`（**import** 黑名单，不抄）· `test_the_blacklist_would_catch_a_synthesised_sentence`（阴性对照）· `test_the_endpoint_does_not_carry_its_own_blacklist_copy` · `test_the_score_channel_is_untouched` · `test_the_frozen_component_was_not_touched` |
| ③ 词面缺失如实标注，NEVER 用分数顶替 | `test_a_source_without_wording_is_absent_not_empty` · `test_the_caller_never_puts_a_score_into_the_text_slot` · `test_the_caller_reports_missing_wording_on_its_own_line` |
| ④ 关闭 `PLAZA-02` | `test_the_sheet_is_closed_now_that_both_gaps_are_gone`（并断言缺口一的结案记录**还在**） |
| （纯函数） | `test_a_second_statement_from_the_same_source_is_counted_not_concatenated` · `test_an_item_that_maps_to_no_cluster_is_dropped_quietly` · `test_the_canonical_map_matches_the_ingest_shape` |

test-first 顺序有据：判据先跑 **3 failed / 6 passed / 6 errors**（fixture 撞 NOT NULL），
修 fixture 后 **8 failed / 7 passed**，实现后 15 passed。

**② 无冻结件偏离**：未触碰 `contracts/` 与 `flint/domain/`；
另**未触碰两处 v0.4 封版面**（`source-columns/` 与 `jobs/ingest.py`），各有判据钉住。

**③ 无禁用词**：对本卡新增/改动的六个源文件扫 `适当/合理/必要时/大约/尽量/若干`
与列表尾的「等」——无命中。

**④ 复用断言在位**：合成句黑名单**从 `flint/region/by_source_region.py` import**，
NEVER 抄一份（`HOTSPOT-07` 为前端那份副本专门配了漂移检测，后端这一侧本来就能直接 import）；
分组/排序沿用 `SourceColumns` 既有的 `groupByRegion`，本卡不另写一套。

**⑤ 装载未超预算**：约 26k / 40k。

**其它门**：
`ruff check . --no-cache` → All checks passed（`I001` 导入序一处，`--fix` 修掉）；
`mypy --strict flint` → 307 files, Success；
`npx tsc --noEmit` → exit 0；
`npx vitest run components/plaza components/source-columns` → 4 文件 45 通过。

---

## 产出文件清单

- `flint/region/source_text.py`（新，纯函数）
- `flint/api/views.py`（`_term_map` · `_day_source_wordings` · `by_source_text`）
- `web/components/plaza/ClusterSourceLines.tsx`（新）
- `web/components/plaza/PlazaCards.tsx`（网格项接线）
- `web/lib/viewsClient.ts`（`by_source_text` 字段）
- `web/messages/zh.json` · `web/messages/en.json`（各 +1 key）
- `tests/v041/test_source_columns_verbatim.py`（新，15 条）
- `docs/blocked/PLAZA-02-REGION-QUERY-AND-SOURCE-REGION-NOT-BUILT.md`（closed）
- `docs/blocked/SOURCE-COLUMNS-DOES-NOT-SHOW-WHO-SAID-IT.md`（**新开**，看屏看出来的）
- `.ui-probe/region12-source-columns.png`（取证）
- `docs/trace/REGION-12.md`（本文件）
