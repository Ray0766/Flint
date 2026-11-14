# REGION-02 trace — 溯源必填 + 接地原文-only @2026-08-02

## 1 装载
REGION-02 卡 + `docs/grounding_spec_v04.md`（MIGRATE-01 规格全文）+ PRIN-02 的 B9/B10 fixture
+ `flint/grounding.py` 头部（撞名核实）+ contracts_v04 的 Doc/WhyNowEvidence/Citation。
~5,000 字符 ≈ 5k tokens（12.5%）。

## 2 结构冲突：`flint/grounding.py` 挡住了卡上的产出路径（DEC-005）
卡的 outputs 是 `flint/grounding/original_only.py`，而 `flint/grounding.py` 已存在 11,748 B。
Python 里两者**不能共存**——包会盖掉模块，让既有代码变成永不执行的死码。

处置：**逐字节移动**为 `flint/grounding/__init__.py`。
- 内容 md5 `0f994d146a5a976c47f60d00439390db` **移动前后一致**；
- `flint.grounding` 这个 import 路径**逐字不变**，6 处既有 import 全部照常；
- 证据：全量 `pytest -q` **1472 passed**（那 6 处 import 都在被执行的测试里）。

这不是 DEC-003 意义上的「改既有文件」——函数、签名、语义一个字未动。已记 **DEC-005**。

## 3 test-first（真红：两个模块都不存在）
先写两个测试文件 → **2 errors during collection** → 实现 → **16 passed**。

## 4 实现中被测试逼出来的两处真修正
**① 文本判据不能是「逐字包含」**：初版要求 event 的每个片段都逐字出现在原文里，
结果**忠实但改写措辞**的 event 也判不过——直接违反规格 §B「改写措辞可以，
引入原文没有的事实 NEVER 可以」。

改法：判**事实锚点**——
- **数字锚点**（年份、数量）一个都不能是原文里没有的：编造最常见的形态就是换个数字，
  而数字换了句子读起来照样通顺；
- **字符 3-gram 重合率** ≥ 0.6：中日文没有词间空格，按词切要么需要分词器（新依赖）、
  要么整句变成一个词块（初版就是这么错的）。3-gram 确定性、零依赖、对改写宽容对换内容敏感。

语义级判定属后续里程碑（规格 §B 已写明沿用既有 `CitationAligner` 通道），
本模块只做确定性的、**宁可漏过不可错放**的那一半。

**② 日期提取不能只取第一个**：一段来源常同时含**发布日与事件日**
（「２０２７年に稼働。発表は２０２６年８月１日」）——取第一个就会把两者搞混，
然后把对的判成错的。改为提取**全部**日期，`event_date` 命中集合即为一致。

三种情形实测：忠实 → True；编造（2025 不在原文）→ False；
引语里没有该事实（不靠全文兜底）→ False。

## 5 acceptance 映射
| acceptance | 测试 |
|---|---|
| 四溯源字段缺省注入 | `test_four_fields_are_injected_from_the_registry` / `..._default_to_unknown` |
| （不猜区） | `test_unregistered_source_raises_instead_of_guessing_a_region`：注册表查不到即抛 `UnknownSourceRegion`，NEVER 猜——猜错的归属会无声地污染该区热点集合 |
| （不覆盖） | `test_injection_never_overwrites_explicit_values`：采集侧已给的值优先，覆盖它等于让注册表悄悄改写采集事实 |
| （不越界） | `test_existing_doc_fields_are_untouched` |
| 派生槽调用接地 → 报错 | `test_translated_event_slot_raises` / `..._source_text_raises` / `..._display_slot_of_citation_raises` / `test_both_stages_are_guarded`（verdict 与 draft 同规则） |
| 双判据按规格实现 | `test_faithful_..._passes` / `test_fabricated_event_fails_text_criterion` / `test_date_mismatch_...` / `test_source_without_extractable_date_fails`（来源无日期判**不过**）/ `test_quote_span_is_preferred_over_full_doc` |
| 过反例 fixture | `test_b9_and_b10_counterexamples_are_covered`：反例**从 PRIN-02 的 fixture 读**，NEVER 在测试里另编一套——另编就不是在测规范里那条了 |

## 6 self_review（self_review=true）
① 见 §5，红态真实；② 冻结件未动（只读 contracts_v04），`contracts/` md5 未变；
③ 无禁用词；④ 复用：接地判据挂既有 `CitationAligner` 通道的语义、`DegradationNote` 未新写、
反例复用 PRIN-02 fixture；⑤ 装载 5k tokens（12.5%）。

## 7 产出
`flint/region/ingest_fields.py`、`flint/grounding/__init__.py`（移动）、
`flint/grounding/original_only.py`、两个测试文件（16 条）。
全局门：ruff 净、mypy 228 文件净、`pytest -q` 1472 passed。
