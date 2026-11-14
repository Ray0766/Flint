# SEED-01 · trace

**卡**：种子——demo 库种一条主题（`DEC-041`）
**verify_cmd**：`pytest tests/v041/test_demo_topic_seeded.py -q` → **14 passed**
**cycles**：1（卡面估 2）
**owner_review**：true —— 按 `DEC-000` 事后补审

---

## 装载清单（实际）

| 来源 | 用途 |
|---|---|
| `docs/blocked/DEMO-TOPIC-SAMPLE-ID-IS-A-PLACEHOLDER.md` 全文 | 三选一与关单条件 |
| `harness/demo_seed_report.py` 全文 | 夹具脚本的既有形态（幂等 / `--drop` / dsn 注入 / 前缀标记） |
| `harness/fe_smoke.py` 的 `SAMPLE_IDS` 段 | 改点 |
| `tests/v041/test_mobile_sweep.py` 的 `CONSOLE_BASELINE` | 撤额度 |
| `contracts/models.py` 的 `Topic`/`WhyNow`/`TopicSeed`/`Origin`/`Doc`/`Citation` | 字段与不变量（只读） |
| `flint/topic/store.py`（`PgOriginStore`/`PgTopicSeedStore`/`PgTopicStore`） | 走生产 store 写库 |
| `web/app/topics/[id]/page.tsx` · `web/lib/{topicClient,screenClient,useScreenData}.ts` | 那条被 404 挡着的红 |
| demo 库实查（topics / projects / origins / citations / FK） | 实况 |

估算约 24k tokens，未超 40k 预算。

---

## 断点与决策日志

### 一、开工第一件事：**单据标题那句话已经不成立了**

单子写「demo 库里一条 `topics` 行都没有」。实查：

```
topic-demo14bf9d94b0-1 · -2 · -3 · -5 · -6 · -9        共 六条
seed-demo14bf9d94b0，各 speculative=false、2 条 why_now 证据（带 citation_id）
归在 proj-demo14bf9d94b0 名下
```

**它们是模型产出**（某次 demo 跑留下的）。所以 `/projects/[id]/topics` 那一屏
**早就有真数据**，缺的只有详情屏的样例 id。

### 二、既然有真主题，为什么还是种了一条夹具

这是本卡唯一一处需要判断的地方。理由：**取证样例要的是可复现。**

那六条是一次过去运行的痕迹，**没有任何脚本能把它们重造出来**。
demo 库重建一次，样例 id 又变成死链——**而那正是这张单要终结的失败**
（`fe_smoke.py` 里那条注释上一版就是这么踩的）。

夹具由脚本写死、幂等、`--drop` 能撤干净，才是探针该指的东西。

**两者互不相扰**：脚本只写 `-demo-fixture-` 前缀那几行，
`_drop` 的每条 DELETE 按夹具 id 限定。三条判据钉这件事：
`test_the_seeder_never_deletes_without_a_where_clause` ·
`test_the_seeder_only_touches_its_own_prefixed_rows` ·
`test_the_six_real_topics_are_not_in_the_seeders_blast_radius`。

**留给 owner 的一行选择**（写在 `fe_smoke.py` 的注释里、也写在单子上）：
更希望取证屏上是真产出的话，把 `"/topics/[id]"` 换成 `topic-demo14bf9d94b0-1`，
代价是它依赖一次没人复跑的历史运行。

### 三、`speculative=false` 是因为它真有两条证据

不是为了让屏好看。冻结件 `[C2]` 的规则是「`evidences` 为空 → `True`」，
所以本条一并种了两条真 citation（pgvector 那条 `quote_span=None`
**照实标失锚**，NEVER 编一句 README 原文把它填满）。
`test_every_evidence_carries_a_citation_that_really_exists` 到库里查那两个
`citation_id` 解不解得开——只判「字段非空」的话，编一个 `cit-xxx` 也能过，
而屏上那条引用点开是空的。

### 四、判据第一版：又一次把「解释」判成了「问题」（本仓第十次）

`test_the_six_real_topics_are_not_in_the_seeders_blast_radius` 第一版扫整份源码，
当场把三处**说明文字**判成违规：

1. 模块 docstring 里写着那六条的 id（在解释「为什么还要种夹具」）；
2. `_drop` 的函数 docstring 里写着「那六条一个字节都不碰」；
3. 收尾 `print` 那句「demo 库里那六条真主题未受影响」。

第一版修法是「剥模块 docstring」——**还是不对**，函数 docstring 与 `print` 都在。

**最终修法是给「引用」一个位置，而不是放宽判据**：只扫 **SQL 字面量**
（`sql_statements()` 走 AST 取以 SQL 动词开头的字符串常量）。
「作用范围」本来就等于这些语句——脚本能碰到库里什么，全在这里。
另配阴性对照 `test_the_sql_scanner_would_catch_a_real_reference`：
一句真去删真主题的 SQL 必须照样被抓到，**否则「只判 SQL」就成了豁免通道**。

---

## 取证跑出来的两条红（都不是卡面预期的）

### ① 主题详情屏抛 `undefined (reading 'evidences')` —— **一条被 404 挡着的红**

样例 id 换过来之后，`/topics/[id]` 第一次拿到 200，探针立刻报：

```
pageerror: Cannot read properties of undefined (reading 'evidences')
```

根因：端点回的是**带信封的** `{"topic": {...}}`，而
`web/app/topics/[id]/page.tsx` 写的是 `useScreenData<Topic>`，
把整个响应体当成 `Topic` → `topic.why_now` 是 `undefined`。

**这个错在库里没有主题时看不见**：那时端点恒回 404，这一屏走的是诚实态分支，
**从来没有真正渲染过一次**。这正是本卡最值钱的产出——
它不是「种了一条数据」，而是**让一屏第一次真的跑起来**。

修法：`useScreenData<TopicEnvelope>` + `topic={data.topic}`。
`fetchScreen` 把响应体原样当 `T` 返回（它**不该**去猜信封长什么样），
所以拆信封是这一屏的事。

`web/app/topics/[id]/page.tsx` 在卡上 outputs 之外（outputs 是 `harness/` +
判据文件），但 **acceptance④ 逐字要求「两屏都不再是 404 且渲染出 why_now 的逐条证据」**
——不修这一条，那条 acceptance 不可能过。
文件属 `CHAIN-03`（v0.4.1 第 5 批），**不在 v0.4 封版面内**，故未触 §9.2。
**在此点名，供 steward 复核。**

### ② `/plaza` 移动端横向溢出 —— **是我 `REGION-11` 引入的回归**

`test_no_screen_overflows_horizontally_on_a_390px_viewport` 报
`('/plaza', 481, 390)`。逐元素量出来是那个 `<select data-testid="region-select">`：
宽 431、右边缘 481。

**`<select>` 会把自己撑到最长那一项的宽度**，而我 `REGION-11` 给未归区写的文案
「未归区（不是一个地理区：源没说产地，或源说的是「全球」）」太长了。

两处一起改，因为只改一处都不够：

- 文案缩成 **「未归区 · 不是地理区」**（仍然满足 acceptance③ 与
  `test_the_option_is_labelled_as_not_a_geographic_region`：含「未归区」与「不是」）；
- `globals.css` 的 `.region-switch select` 加 `max-width: 100%; min-width: 0`。
  **这不是给那一条文案打的补丁**：下一个长选项照样会撑，而那时没人记得这里发生过什么。

重跑取证：`mobile_overflow: 0` · `overflow: 0`。

---

## 视觉取证

`.ui-probe/topics-id-light-desktop.png` **已用 Read 看过**：
【夹具】前缀在第一行、两维 tag、`why_now` 正文、**两条证据各带日期**、关键词映射齐全。
`console_error_count = 0`（额度撤掉之后）。

全量取证：88 屏 · `bad_status: 0` · `overflow: 0` · `mobile_overflow: 0` ·
`console_errors: 12`（全部来自 `/deliverables/[id]` 的 3 × 4，它有活单在）。

---

## 改既有文件

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `harness/fe_smoke.py` | `"/topics/[id]": "tp-placeholder"` | 指向夹具 id，注释写清为什么不指那六条真主题、以及 owner 想换的话改哪一行 | acceptance②。占位串留着的话，这一屏的取证永远是一张 404 截图，而那张截图会被读成「这屏坏了」 |
| `tests/v041/test_mobile_sweep.py` | `CONSOLE_BASELINE` 有 `/topics/[id]: (1, …)` | 整条撤掉，留下撤它的理由与「NEVER 因为反正它绿着就留着」 | `DEC-041` 的硬判据。额度还在的话，这一屏哪天真退回 404，**判据不会响** |
| `web/app/topics/[id]/page.tsx` | `useScreenData<Topic>` / `topic={data}` | `useScreenData<TopicEnvelope>` / `topic={data.topic}` | 见上「① 一条被 404 挡着的红」。**outputs 外，供复核** |
| `web/messages/{zh,en}.json` | `region.unassigned.label` 是长句 | 缩成「未归区 · 不是地理区」 | 见上「② 横向溢出」。这一处是 `REGION-11` 的回归，在本卡取证时才现形 |
| `web/app/globals.css` | `.region-switch select` 无宽度上闸 | 加 `max-width: 100%; min-width: 0` | 同上。**这一条是durable 的那半**：只缩文案的话，下一个长选项照样撑 |

`docs/blocked/DEMO-TOPIC-SAMPLE-ID-IS-A-PLACEHOLDER.md` 关单，
立单原文一字未改地留在下半部分。

---

## self_review（卡上 `self_review=true`）

**① 测试真实覆盖 acceptance**

| acceptance | 判据 |
|---|---|
| ① 种一条带 `seed_id`/`why_now`(含 `speculative`+逐条证据+`citation_id`)/`keyword_mapping`/两维 tag 的主题 | `test_the_topic_carries_every_field_the_screen_needs` · `test_every_evidence_carries_a_citation_that_really_exists`（到库里查引用解不解得开） |
| ② 取证样例改用它，占位串退役 | `test_the_smoke_sample_points_at_the_seeded_topic` |
| ③ 幂等 · 与 `demo_seed_report` 同形 · 前缀标记 · NEVER 冒充模型产出 | `test_running_the_seed_twice_does_not_create_a_second_row`（连跑三次）· `test_the_drop_takes_everything_back` · `test_the_seeder_only_touches_its_own_prefixed_rows` · `test_the_fixture_says_it_is_a_fixture_in_the_data_itself`（标记在**数据里**，不是只在注释里） |
| ④ 主题两屏第一次有真数据 | `test_the_topic_detail_endpoint_no_longer_returns_404` + 真栈取证（详情屏 0 报错、截图逐项看过；列表屏 967/2495px、0 报错，回的是那六条真主题） |
| ⑤ 撤掉 404 额度，撤掉后仍绿 | `test_the_console_allowance_for_the_topic_screen_is_withdrawn` · `test_the_withdrawal_left_a_note_saying_why` · `test_mobile_sweep` 全绿（实跑取证之后） |
| ⑥ 关闭单据 | `test_the_sheet_is_closed_and_records_which_option_won`（并断言记下了「其实已有六条真主题」这个实况） |
| （安全） | `test_the_seeder_never_deletes_without_a_where_clause` · `test_the_six_real_topics_are_not_in_the_seeders_blast_radius` · `test_the_sql_scanner_would_catch_a_real_reference` |

test-first 顺序有据：判据先跑 **5 failed / 8 passed**，实现后 14 passed。

**② 无冻结件偏离**：未触碰 `contracts/` 与 `flint/domain/`；
夹具全部走生产 store（`PgOriginStore` / `PgTopicSeedStore` / `PgTopicStore` / `PgDocStore`），
NEVER 另写一份写库口径。

**③ 无禁用词**：对本卡新增/改动的文件扫 `适当/合理/必要时/大约/尽量/若干`
与列表尾的「等」——无命中。

**④ 复用断言在位**：脚本形态逐条照 `harness/demo_seed_report.py`
（固定时钟 → 重复跑字节稳定 · 前缀标记 · `--drop` · dsn 注入 · 每条 DELETE 带 WHERE）。

**⑤ 装载未超预算**：约 24k / 40k。

**其它门**：
`ruff check . --no-cache` → All checks passed（`F401` + 两处 `I001`，`--fix` 修掉）；
`mypy --strict flint` → 307 files Success；
`npx tsc --noEmit` → exit 0；
`npx vitest run` → **80 文件 812 通过**（全量）。

**操作步骤（不是代码）**：往 demo 库跑了一次
`python -m harness.demo_seed_topic`——判据本身打的是**测试库**
（`FLINT_TEST_DSN`），往 demo 库写是给人看的那一步，如实记在这里。

---

## 产出文件清单

- `harness/demo_seed_topic.py`（新）
- `harness/fe_smoke.py`（样例 id）
- `tests/v041/test_demo_topic_seeded.py`（新，14 条）
- `tests/v041/test_mobile_sweep.py`（撤 404 额度）
- `web/app/topics/[id]/page.tsx`（拆信封，**outputs 外，供复核**）
- `web/messages/zh.json` · `web/messages/en.json`（未归区文案缩短）
- `web/app/globals.css`（`.region-switch select` 宽度上闸）
- `docs/blocked/DEMO-TOPIC-SAMPLE-ID-IS-A-PLACEHOLDER.md`（closed）
- `.ui-probe/*.png` + `.ui-probe/fe_smoke.json`（88 屏重跑）
- `docs/trace/SEED-01.md`（本文件）
