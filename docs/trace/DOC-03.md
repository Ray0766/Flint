# DOC-03 · 证据卡吃正文（卡真变厚）+ 引文端点把正文两位给出去

**卡** `docs/steward/tasks-v041-b2.json#DOC-03` · **cycles 2** ·
**self_review = true** → §7 · **owner_review = true** → §8
**依赖** DOC-02（verified）· FB-06（verified）

## 1. 装载清单

卡面 DOC-03 · `flint/evidence/enrich.py` 全文 · `flint/evidence/quote.py` 的
`extract_quote_span` 与 `_SENT_END` · `flint/api/deref.py` 的模块 docstring、
`_CITATION_SQL`、`citation_json`、`citation_detail` · `contracts_v04/models_v04.py#Fact`
与 DOC-01 的正文增量段 · `tests/v041/test_deref_citation.py` 的判据清单 ·
`docs/trace/DOC-02.md`（正文落库形态）。约 13k tokens，预算 40k 以内。

## 2. 顺序（§4.2）

判据先落盘先跑红（`ImportError: cannot import name 'ExtractedFact'`）→
写抽取器 → 两条实测红（§3）→ 修 → 十八条绿 → 接引文端点两位 →
补 acceptance② 的七条判据 → **25 passed**（补判后 27）。

## 3. 抽取器写坏了两处，判据当场逮住

### 3.1 ASCII 句点无条件切 → 小数被切成两句

第一版句子边界照抄 `quote.py#_SENT_END` 的字符类，里面**有 ASCII `.`**。
于是 `托管月成本是 12.5 美元。` 被切成「…12.」与「5 美元。」两句，
一个金额变成两条事实，第二条的数值是 **5**。

改成 `(?<=[。．!?！？])|(?<=\.)(?!\d)`——ASCII 句点只在后面不跟数字时才切。

### 3.2 一句只取第一个数值 → 那句话在说的事被丢掉

第一版用 `.search`（每句一条）。`固态电池的量产成本在 2026 年降到每千瓦时 78 美元。`
里第一个数是 **2026**（年份），而 **78** 才是那句话在说的事。
改成 `.finditer`：一句里的每个数值各成一条事实。

**两处都是判据先红的**，不是我读代码读出来的。

## 4. 卡面与实况对不上一处（如实登记，不阻塞）

acceptance② 原话：「FB-06 引文端点**预留**的 `content` / `content_sha256` /
`content_truncated` 三个位**填上真值**，不再是 null + 「接口未提供」」。

**实查 FB-06 的产物**：`flint/api/deref.py#citation_json` **从来没有过这三个位**——
它回的是 citation 四字段 + doc 的六项（title / url / kind / published_at / origin / access）
+ 两条纪律位（`external_link_allowed` / `share_note`）。全仓搜 `content_sha256`
在 FB-06 的产物里零命中。

所以本卡是**新增**，不是「填上预留位」。**做出来的东西与卡的意图一致**
（引文能说出正文的指纹与截断态），只是卡对现状的描述不准。
如实记在这里与判据的注释里，NEVER 假装那三个位本来就在。

**三个位里只落两位**：`content` 本身不进引用响应——那个端点回的是「一条引用」，
不是「一篇文章」。塞进去的话，前端每展开一条引用就要下载一篇文章。
正文的读取面是另一件事，登记在 §10。

## 5. 三通道纪律怎么钉的（acceptance③）

| 通道 | 来源 | 正文能不能产它 |
|---|---|---|
| `Fact` | 陈述 + 数值 + 引用 | **能**——本卡抽的就是它，产物一律 `channel="fact"` |
| `PriceCell` | PriceBook 的价目行 | **NEVER**——价格要有价目出处，从正文里读一个数当价格就是编造出处 |
| `ProfileRef` | 用户档案字段 | **NEVER**——正文里没有「这个用户的档案」 |

判据两条：产物的 `channel` 集合恒为 `{"fact"}`；**源码级**——
`inspect.getsource(extract_facts_from_content)` 里出现 `PriceCell` / `ProfileRef` 即红。
第二条挡的是「以后有人在这里顺手造一个价格」。

正文里的「12.5 美元」看起来最像价格，判据专门有一条钉它**仍然只是 Fact**。

## 6. 改既有文件：两处

### 6.1 `flint/evidence/enrich.py`（卡上 outputs 第一项）

- **改前**：只有 B-4/B-5 的抓取富化与喂生成器那一套；卡上能引的只有
  `title` + 短 `quote_span`。
- **改后**：**追加** `ExtractedFact` / `extract_facts_from_content` /
  `citable_fact_count` / `ThickeningReport` / `thickening_report`。既有函数一行没动。
- **为什么非改不可**：卡上 outputs 第一项，acceptance① 的落点。

### 6.2 `flint/api/deref.py`（**超出卡上 outputs**，单独交代）

- **改前**：`_CITATION_SQL` 取 citation 四字段 + doc 六项；`citation_json` 照此序列化。
- **改后**：SQL 多取 `d.content_sha256, d.content_truncated`；
  `citation_json` 的 `doc` 子对象多三位（指纹、截断态、一句人话说明）。
  既有字段**一个没动、一个没改名**，FB-06 的 13 条判据全绿。
- **为什么非改不可**：acceptance② 点名的就是这个端点。卡上 `inputs` 列了它，
  `outputs` 没列——但不改它，acceptance② 一条都做不到。
- **强度对比**：只增不减。FB-06 原有的失锚纪律、私有材料纪律、404 口径全部原样。
- **越界登记**：`flint/api/deref.py` 是 FB-06 的 outputs，不是本卡的。改动面
  2 处（SQL 一行、序列化三行 + docstring）。**列进 §8 请 owner 过目。**

**未改**：`flint/cards.py`（卡上 inputs 列了它，实查后确认卡的组装面不需要动——
抽取器吃的是 `Doc`，不是 `EvidenceCard`）、`contracts/` · `contracts_v04/` ·
`flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`。零新增依赖。

## 7. 变异考：二十一个，一个先活了下来

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 没数值的句子也产事实 | 「事实」不是「分句」 | **12 failed** ✓ |
| ② 一句只取第一个数值 | §3.2 | **1 failed** ✓ |
| ③ ASCII 句点无条件切 | §3.1 | **1 failed** ✓ |
| ④ 读不到单位就安一个默认单位 | NEVER 猜单位 | **1 failed** ✓ |
| ⑤ `content` 缺失时回落到标题 | acceptance① | **37 passed** ✗ → 补判后 **2 failed** ✓ |
| ⑥ 截断的正文不标记 | acceptance④ | **3 failed** ✓ |
| ⑦ 没截断也标一遍 | 反向 | **1 failed** ✓ |
| ⑧ 截断标记只给布尔、不给人话 | 可读 | **1 failed** ✓ |
| ⑨ 通道改成 price | acceptance③ | **2 failed** ✓ |
| ⑩ 抽取器里构造 PriceCell | acceptance③ | **1 failed** ✓ |
| ⑪ 事实不带 doc_id | 数字必有出处 | **1 failed** ✓ |
| ⑫ `ExtractedFact` 不再 frozen | 产物不可改写 | **1 failed** ✓ |
| ⑬ 对照的「前」直接用「后」 | acceptance① | **2 failed** ✓ |
| ⑭ 没正文的卡也报一个增量 | 诚实 | **1 failed** ✓ |
| ⑮ 报告不数截断条数 | acceptance④ | **1 failed** ✓ |
| ⑯ 引文响应不给指纹 | acceptance② | **2 failed** ✓ |
| ⑰ 引文响应不给截断态 | acceptance② | **2 failed** ✓ |
| ⑱ 截断了也不留那句话 | 可读 | **1 failed** ✓ |
| ⑲ 没截断也留那句话 | 反向 | **1 failed** ✓ |
| ⑳ 把整篇正文塞进引用响应 | §4 的边界 | **1 failed** ✓ |
| ㉑ SQL 不取那两列（响应静默变 `None`） | 只判序列化不够 | **11 failed** ✓ |

**⑤ 为什么能活，以及它暴露的真洞**：第一版变异是 `if not content:` → `if False:`——
`content=None` 时 `str(None)` 是「None」，里面没有数字，抽不出东西，**行为面零变化**。
那是个**假变异**（与 DOC-02 的⑧ 同型：一个杀不掉的变异，要先问它是不是真的在变异）。

换成真的回落 `content or title` 之后**仍然活着**——这次是**判据的真洞**：
我的测试用例里标题是「固态电池成本」，**不带数字**。抽取器就算真的回落到标题，
也会因为标题里没有数值而交白卷，判据照样绿。

补了两条：`content=None` 与 `content=""` 各配一个**带数字的标题**。
docstring 里那句「NEVER 从标题里凑一条」从此有判据管着。

**㉑ 值得单说**：只判序列化函数的话，把 SQL 里那两列删掉，
响应里两位会静默变成 `None`（`row.get` 不报错），而判据照样绿。
所以另有一条判据直接读 `_CITATION_SQL` 的文本——**查询给了什么，决定序列化读得到什么**。

二十一次变异后两个被改文件与变异前逐字相同（baseline 38 passed）。

## 8. verify、全局门与 owner_review

```
verify_cmd: pytest tests/v041/test_cards_thickened.py -q → 27 passed
            （基线：ImportError，收集期就红）
连坐面:     + tests/v041/test_deref_citation.py → 40 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: no issues found in 288 source files
            pytest -q               → 3117 passed（DOC-02 收卡时 3091，本卡 +26）
```

**owner_review 三件**：

1. **改了 FB-06 的产物**（§6.2）。`flint/api/deref.py` 不在本卡 outputs 里，
   但 acceptance② 点名的就是它。只增不减，FB-06 判据全绿。
2. **卡面与实况对不上那一处**（§4）：卡说「填上预留位」，实况是「新增」。
   我按意图做了，没有停下走 blocked——若 owner 认为这类描述偏差一律该停机，请写死。
3. **抽取器的口径**：一句里的每个数值各成一条事实、带单位就记单位、读不到就留空。
   这是我按「可引用事实 = 陈述 + 数值 + 出处」定的。owner 若要更严
   （比如只收带单位的数值、或过滤掉年份），改的是 `_NUMBER_WITH_UNIT`
   与那一段循环，判据钉的是关系不是具体正则。

## 9. self_review

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 从正文抽事实与数值、卡显著变厚、用前后对照证明 | `test_a_sentence_with_a_number_becomes_a_citable_fact`、`test_the_statement_is_the_sentence_it_came_from`、`test_a_sentence_without_a_number_yields_nothing`、`test_every_fact_carries_the_doc_it_came_from`、`test_a_doc_without_content_yields_nothing_rather_than_guessing`、`test_an_empty_body_does_not_fall_back_to_the_title_either`、`test_units_are_read_off_the_sentence_not_invented`、`test_the_before_and_after_counts_are_measured_not_asserted_by_hand`、`test_the_card_really_gets_thicker`、`test_a_card_whose_docs_have_no_content_does_not_pretend_to_thicken` |
| ② 引文端点的正文位填真值 | `test_the_citation_response_carries_the_content_fingerprint`、`test_the_citation_response_says_when_the_body_was_truncated`、`test_an_untruncated_citation_carries_no_scary_note`、`test_a_doc_that_was_never_extracted_reports_null_not_a_fake_hash`、`test_the_body_itself_stays_out_of_the_citation_response`、`test_the_citation_sql_actually_selects_the_two_columns`、`test_the_citation_channel_is_still_the_citation_channel` |
| ③ 三通道纪律不破 | `test_everything_extracted_lands_in_the_fact_channel`、`test_the_extractor_never_builds_a_price_cell_or_a_profile_ref`、`test_a_currency_amount_is_still_a_fact_not_a_price_cell` |
| ④ 截断标记一路传到产物 | `test_facts_from_a_truncated_body_are_marked`、`test_facts_from_a_whole_body_are_not_marked`、`test_the_truncation_mark_has_a_reader_facing_note`、`test_the_report_names_the_card_and_carries_the_truncation_tally`、引文端点那三条 |

**② 无冻结件偏离**：`contracts/` · `contracts_v04/` · `flint/domain/` 未触碰
（v04 契约仍按仓里既有形态惰性 import）；`requirements.lock` 未动；零新增依赖。

**③ 禁用词**：六词 + 列表尾「等」在三个产物文件里 0 命中。

**④ 复用**：句子边界口径对齐 `quote.py`（注释写明为什么不能照抄那个字符类）；
截断态直接读 DOC-02 落下的 `content_truncated`（NEVER 在这里重新判一次截断）；
引文端点就地扩展（NEVER 另开一个「引文+正文」端点）。

**⑤ 装载预算**：约 13k tokens，未超 40k。

## 10. 登记未做

1. **抽取器还没被任何生产路径调用**。`enrich_card` 那条抓取链仍走
   `title` + `quote_span` 的老路——把 `extract_facts_from_content` 接进去
   需要抓取管线先写正文（DOC-02 §10 第 1 条：那一步也还没接）。
   所以**线上的卡目前还没有真的变厚**，变厚的是**能力**与它的判据。
2. **抽出的事实没有落库、没有变成 `Fact`**。`ExtractedFact` 是抽取结果，
   不是账本里的 `Fact`——提升成 `Fact` 要走 ClaimPromoter 那条不变量
   （S2-4：`alignment=="partial"` 的 claim NEVER 提升）。本卡 NEVER 绕过它。
3. **正文本身没有读取面**。`GET /docs/{id}/content` 一类端点没有建
   （见 §4 的边界）。前端要看全文时该怎么走，是另一张卡。
4. **抽取是正则，不是模型**。「陈述 + 数值 + 单位」按句子形态抽，
   抽不出「这句话在讲什么」。语义抽取要过 LLM，属另一条线。
5. **单位表是有限枚举**：`%` / 拉丁字母串 / 常见中文货币与量词。
   表外的单位会被留空（而不是被猜），这符合「NEVER 猜单位」，
   但也意味着一部分数值的单位信息丢失。
