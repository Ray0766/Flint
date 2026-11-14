# PERSIST-04 · cluster→判定关系表

**结论**：迁移 `0025` 建 `cluster_verdicts`；`topic_id` 打通提交链路；
`run_gate1` 收尾**在判定快照同一个事务里**写关系行；新增 `GET /clusters/{id}/verdict`。
`verify_cmd` 14 条全绿，`ruff` / `mypy --strict flint`（316 文件）全绿。
**八张表 5 / 8**（剩下三张卡在被阻的 `PERSIST-02` 上）。

> 上半段（§1~§3）是**上一轮的调查**，原样留着——它记的是「为什么不能先建表」，
> 而那正是本卡最容易做错的地方。§6 起是本轮的实现。

装载：`docs/steward/tasks-v041-b9.json#PERSIST-04` · `DECISIONS-v04.md#DEC-044` ·
`flint/jobs/gate1.py`（收尾与 snapshot 落盘段）· `flint/jobs/worker_main.py#_gate1_handler` ·
`flint/api/analysis.py`（提交段）· `flint/api/schemas.py#AnalysisSubmitRequest` ·
`flint/api/views.py`（`/jobs/{id}/verdict`）· `docs/blocked/HOTSPOT-03.md` ·
`contracts_v04/models_v04.py#Topic` · `web/app/clusters/[id]/page.tsx`

---

## 1 本轮查清的东西（**实现的人不必再查一遍**）

### 1.1 判定今天怎么落盘

```
flint/jobs/gate1.py         判定 payload → snapshots['snap-{job_id}-verdict']
flint/api/views.py:363      GET /jobs/{job_id}/verdict → 从那个 snapshot 取
```

**键是 job，不是 cluster**。`Job` 没有 `cluster` 字段、`jobs` 表也没有 `cluster_id`
（`DEC-044` 记的就是这件事），所以从一个热点出发**无从查起**——
分析屏对每一个热点永远只会说「还没有过 Gate① 判定」。

### 1.2 **`cluster_id` 今天根本进不到作业里**（本轮最关键的一条）

提交链路逐段实读：

```
web/lib/jobClient.ts            POST /projects/{id}/analysis
flint/api/schemas.py:89         AnalysisSubmitRequest = {keywords, locale, budget_cny, topic_id?}
flint/api/analysis.py:163       payload = {"project_id", "keywords", "locale"}
flint/jobs/worker_main.py:172   只取 keywords 与 locale
flint/jobs/gate1.py             run_gate1(job_id, keywords, locale, deps)
```

**四段里没有任何一段带 `cluster_id`。** 所以卡面 acceptance② 那句
「gate1 作业收尾时**记下它判的是哪个 cluster**」——**今天它不知道**。

这不是漏接线，是这条链路从来没有传过这个东西。**建表之前必须先解决它进得来**，
否则 `cluster_verdicts` 会是一张永远空着的表，而分析屏照旧说「还没有判定」——
**表建了、判据绿了、屏上一个字都没变**，那是本卡最坏的一种收场。

### 1.3 关系是**一对多**，不是一对一

`Topic` 只有 `seed_id`，没有 cluster 字段。而一个 combo 主题由 **2~5 张卡**
凑成（`POST /projects/combo` 的 `card_ids`），每张卡背后是一个热点簇。

所以「这次判定判的是哪个 cluster」的诚实答案是**一组**，不是一个。
`cluster_verdicts` 作为**关系表**天然装得下（一次判定 ↔ N 个 cluster，
每个 cluster 一行），这也正是 `DEC-044` 用「关系表」这个词的原因。

**一对一的写法会当场丢信息**：combo 出来的判定只会记住其中一个热点，
而用户从另外那几个热点点进去，看到的仍然是「还没有判定」——
**而那次判定明明也是为它跑的**。

## 2 下一轮接手时的两条路（**worker 倾向乙，但先把甲写清**）

### 甲：给提交链路加一个显式 `cluster_ids`

`AnalysisSubmitRequest` 加可选 `cluster_ids: list[str] = []` → 进 payload →
`run_gate1` 收尾时按它写关系行。

- **好处**：来源明确，谁发起谁负责说清判的是哪几个热点；
- **坏处**：**今天没有任何一屏会填它**。`DEC-042` 写死「打开分析界面只是查看，
  NEVER 顺手跑一次分析」，所以 `/clusters/[id]` 那一屏不发起分析；
  而真正发起分析的是主题族那几屏（`NAV-05` 接的九条边），
  那里手上拿着的是 `topic_id` 不是 cluster。
  → 结果仍然是一张空表，只是空得更隐蔽。

### 乙：收尾时**从 topic 反查**（倾向这条）

`run_gate1` 收尾时按已有的 `topic_id` 反查它的种子卡、再由卡查回热点簇，
每个簇写一行。**这条链本轮已经实查过了**（`information_schema.columns`，测试库）：

```
topics        -> topic_id, seed_id, one_liner, target_user_tag, form_factor_tag,
                 why_now, keyword_mapping, embedding
topic_seeds   -> seed_id, origin_id, keywords, hypothesis, context_text
origins       -> origin_id, kind, owner, payload, created_at
evidence_cards-> card_id, cluster_id, keyword_ids, flags, top_links
```

**`topic_seeds` 没有 `card_ids` 列**——本来以为有，实查发现没有。
`card_ids` 在 **`origins.payload`（jsonb）**里（combo 建 Origin 时写进去的）。
所以完整链路是**四跳**：

```
topic.seed_id → topic_seeds.origin_id → origins.payload->'card_ids'
              → evidence_cards.cluster_id
```

链是通的，但**最后一跳穿过 jsonb**。两条要当心：
① `origins.kind` 不只 combo 一种，别的 kind 的 payload 里**没有** `card_ids`——
取不到时就是取不到，**NEVER 回退去猜**；
② 走 jsonb 取数要写清 kind 过滤，否则一个形状不同的 payload 会静静地回空，
而「这条 origin 不是 combo」与「这个 combo 没有卡」在结果上长得一样。

- **好处**：不需要任何一屏改，今天就能有数据；关系天然是一对多，对得上 §1.3；
- **坏处**：`payload` 里今天连 `topic_id` 都没有（只有 `project_id` / `keywords` /
  `locale`）——**所以乙也要动提交段**，把 `topic_id` 放进 payload。
  那是一处**加字段**的改动，比甲小得多，且 `topic_id` 本来就是提交时就有的东西。

**查不到就不写行**（缺就是缺）：不带 `topic_id` 的旧路径照旧不产生关系行，
分析屏对那些热点仍然如实说「还没有判定」。**NEVER 为了让表不空而猜一个 cluster**——
猜错时用户看到的是**另一个热点的判定**，并会把它引进计划书
（`DEC-044` 原话，也是「猜 job id 那条路」当初被判死的同一个理由）。

## 3 迁移号

接盘上当时最高的那一号（`PERSIST-03` 已占 `0024`，所以本卡是 `0025`）。
**不留号**——`PERSIST-02` 被阻不影响号段连续，理由见 `docs/trace/PERSIST-03.md` §2。

## 4 本轮还做了什么

开工同时在后台重跑了一次**全量 `pytest`**——那是 `PERSIST-03` 收尾时欠下的确认
（那一卡改了 6 个既有判据文件的基线，收尾后没有复跑）。结果记在台账里。

## 5 交接一句话

**下一轮接手的人**：`cluster_verdicts` 的表结构不是难点，
难点是 §1.2 那条「`cluster_id` 今天进不到作业里」。
先按 §2 乙实查三张表的列确认链路通，再动手；
**NEVER 先建表再想数据从哪来**——那样会得到一张永远空着的表和一屏没变的界面。


---

# 本轮（实现）

## 6 走的是「乙」，落地形态

| 环节 | 做了什么 |
|---|---|
| `flint/api/analysis.py` | 提交 payload 里加 `"topic_id": body.topic_id`——**数据从哪来那一半** |
| `flint/jobs/worker_main.py` | `_gate1_handler` 取出它并传给 `run_gate1`（payload 里有而 handler 不取的话，链路在这一行静静地断掉） |
| `flint/jobs/gate1.py` | `run_gate1` 加 `topic_id: str \| None = None`（**放最后且带默认值**，既有调用点一个都不用改）；`validate` 步内、**判定快照同一个事务里**写关系行 |
| `flint/jobs/cluster_verdict.py`（新） | `clusters_for_topic` 四跳反查 · `record_cluster_verdicts` 幂等写 · `latest_verdict_job` 取最新 |
| `flint/api/views.py` | 新增 `GET /clusters/{cluster_id}/verdict` |
| `migrations/versions/0025_cluster_verdicts.py`（新） | 关系表，PK `(cluster_id, job_id)`，两个外键，按 `(cluster_id, created_at DESC)` 建索引 |

**`run_gate1` 的新形参为什么带默认值**：这条链路上「不知道判的是哪个热点」
**本来就是一种真实状态**（不带 `topic_id` 的旧提交路径）。
必填会逼出一个占位值，而占位值会写出**一行指向错误热点的关系**。

## 7 `GET /clusters/{id}/verdict`：`HOTSPOT-03` 那张单等的就是它

那张单当初判死的正是「自己补一个 cluster 键端点」，**理由是那时没有真相可查**——
从热点出发只能猜一个 job id 去试，猜错时用户看到的是**另一个热点的判定**。
`DEC-044` 之后前提变了，关系表就是那个真相，所以补它不是自作主张。

**加一条读法，不是换一条**：`GET /jobs/{id}/verdict` 一行没动
（判据 `test_the_job_keyed_endpoint_still_works` 钉住）——
两条服务的是两种问法：「这次作业判了什么」与「这个热点判过什么」。

端点分**三态**，NEVER 合并：

| 情况 | 答复 |
|---|---|
| 没判过（关系表里没有） | 404 `NOT_FOUND` +「no Gate verdict for cluster …」 |
| 判过、快照读不回来 | 404 + **点名是哪个 job** +「这个热点判过，而那份判定读不回来」 |
| 判过且读得到 | 200 `{cluster_id, job_id, verdict}` |

第二态单独留着的理由：它与第一态**该让人做的事完全不同**——
前者去发起一次分析，后者去查快照哪儿去了。

## 8 上一轮欠的全量跑完了，抓到两条本可以溜掉的东西

```
7 failed, 4816 passed, 6 skipped, 16 errors      ← 本卡开工前
```

除去 `PERSIST-02` 被阻那一档（`test_workbench_persist` 整个文件 + 16 errors，
迁移没写是预期红）与 `FOUR-REDS` 那张单上的 5 条，**剩下三条是新的，且都是我的**：

### 8.1 `templates.html` 撞上「不许有全文列」的合规尺子

```
tests/m1/test_m1_016.py::test_live_schema_has_no_fulltext_columns
  full-text columns found: [('templates', 'html')]
tests/m2/test_featb_b1_docstore.py::test_compliance_no_fulltext_column_introduced
```

那把尺子（`flint/sources/throttle.py`）的射程写得很清楚：
**§3.5 针对采集数据（外站全文不落库），系统自产内容不在管辖**。

`templates.html` 存的是**固化后的模板**——由用户自己的样板经 `to_slots` 变换而来，
标记区换成插槽、水印剥掉、**示例正文与示例数字一律拒绝放行**（残留即
`SolidifyBlocked`）。落进去的东西**只剩形状**，与外站全文没有任何关系。

所以它走 `blocks.content` 那一档（系统自产），**不**需要像 `doc_contents.content`
那样援引 owner 的 `DOC-01` 裁决——那一条放行的是「外站正文进库」，是另一件事。
白名单加了这一处并把上面这段理由写进注释；那份注释自己写着
「放行一处与拆掉尺子是两件事」，本次照此办理。

### 8.2 改迁移号留下的一枚哑弹

```
tests/m1/test_m1_004.py  ERROR: alembic upgrade failed
  Can't locate revision identified by '0025'
```

`PERSIST-03` 把 `0025_templates.py` 改名成 `0024_templates.py` 之前，
**demo 库已经被某条判据 stamp 到了 `0025`**——而那个 revision 从此不存在了，
于是任何一次 `alembic upgrade` 都当场失败。

顺带查明了它**怎么被 stamp 上去的**：`migrations/env.py:20` 的 `DEFAULT_URL`
指向 **demo 库**，所以任何不设 `DATABASE_URL` 就跑 alembic 的判据都在动 demo 库。
把两个库的 `alembic_version` 从 `0025` 修回 `0024` 后恢复。

**这一条是改号那次决定的余波**：改号本身是对的（§2），
而「改号会让已经 stamp 过的库指向一个不存在的 revision」是当时没想到的。
记在这里，下一次改号的人 MUST 顺手核一次两个库的 `alembic_version`。

## 9 自审（`self_review=true`）

**① 判据真实覆盖 acceptance**

| acceptance | 判据 |
|---|---|
| ① 表不存在 → 分析屏永远说没判定 | `test_the_cluster_verdicts_table_exists_now` |
| ② 建关系表；gate1 收尾记下判的是哪个 cluster；**contracts/ 一字不动** | `test_the_four_hop_chain_resolves_every_cluster_of_a_combo`、`test_the_submit_payload_now_carries_the_topic_id`、`test_the_handler_passes_the_topic_id_through`、`test_the_contract_was_not_touched`（两侧都判：源码里 `Job` 无 cluster 字段 + `jobs` 表无 `cluster_id` 列） |
| ③ 按 cluster_id 查最新一条；猜 job id 那条路删掉 | `test_the_endpoint_answers_with_the_latest_verdict_for_a_cluster`、`test_the_job_keyed_endpoint_still_works` |
| ④ 多次判定取最新一条 | `test_the_latest_verdict_wins_when_a_cluster_was_judged_twice` |
| ⑤ 四态不倒 | `test_a_cluster_never_judged_reads_as_none_not_as_an_error`、`test_a_cluster_without_a_verdict_says_so_instead_of_pretending` |
| 「NEVER 猜」那条纪律 | `test_a_non_combo_origin_resolves_to_nothing_instead_of_guessing`、`test_an_unknown_topic_resolves_to_nothing` |
| 幂等（续跑不翻倍） | `test_recording_links_is_idempotent` |

**先红后绿**：写完判据、未建表未写实现时 14 条全红；实现完 `14 passed`。

**② 无冻结件偏离**：`contracts/` 与 `contracts_v04/` 四件一字未动，
且**有一条判据专门盯着它**（见上表 ②）。

**③ 无禁用词**：六个词 0 命中。

**④ 复用断言在位**：判定语义、`decide`、快照落盘一行未改——
本卡只在既有事务里多写一组关系行，并在读侧加一条端点。

**⑤ 装载未超预算**：≈34k / 40k。

## 10 门

```
pytest tests/v041/test_cluster_verdict_link.py -q   14 passed
ruff check . --no-cache                            All checks passed!
mypy --strict flint                                Success: no issues found in 316 source files
两库 alembic_version = 0025，八张表 5/8（缺的三张归被阻的 PERSIST-02）
```

## 11 留给下游

1. **屏那一半不在本卡 outputs 里**（`web/` 没列进去）。后端真相与端点都齐了，
   热点分析屏改成读 `GET /clusters/{id}/verdict` 需要 `web/`——
   要么给 `PERSIST-04` 扩 outputs，要么单开一张卡。**在那之前屏上仍是「还没判定」**，
   但**原因变了**：从前是「查不到」，现在是「屏还没接这条读法」。
2. **`AnalysisView.tsx` 是 v0.4 封版件**，`FIX-19` 拿到的许可**只限加类名与样式**。
   改它的取数路径**不在那条许可里**——接屏时走承载屏 `web/app/clusters/[id]/page.tsx`，
   NEVER 动封版件的判定语义。
3. 下一次改迁移号的人：**顺手核一次两个库的 `alembic_version`**（§8.2）。
