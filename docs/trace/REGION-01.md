# REGION-01 trace — 分区源选集 + 准入标准 + 空表降级 @2026-08-02

V2 首卡，**第一次真写 `flint/` 运行期代码**（DEC-003 触碰边界从此生效）。

## 1 装载
REGION-01 卡 + `PRINCIPLES#B4/#B5` + `flint/sources/degradation.py` 真件（复用对象）
+ `flint/sources/registry.py` 头部（撞名核实）+ `contracts_v04` 的 I3 区。
~3,000 字符 ≈ 3k tokens（7.5%）。

## 2 test-first（真红：整包不存在）
先写测试 → **collection error**（`flint.region` 不存在）→ 实现 → 落准入文档 →
**11 passed**；`ruff --no-cache .` 全绿、`mypy --strict flint` 226 文件净。

## 3 本卡最重要的一处设计：两个 select 不是一回事
- `sources_for_ingest(region)` —— **采集**选集，按区取（热点集合本就分区，`PRINCIPLES#B5`）。
- `sources_for_retrieval(region)` —— **检索**选集，**NEVER 按国别排除**：
  本区以 `region_match` 加权排前，他国源权重照常 > 0（`PRINCIPLES#B4`）。

**把这两件事写成同一个函数，就等于让「本国优先」悄悄变成「本国隔离」**——
跨国立场分歧会在检索阶段就被过滤掉，后面 REGION-08 的 by_source 分列再怎么做也拿不回来。
测试里 `test_retrieval_ranks_home_region_first_without_excluding` 断言
**他国源权重 NEVER 归零**（归零＝变相隔离）。

## 4 DEC-003 边界内的既有文件改动（本卡唯一一处）
`flint/sources/degradation.py` 的 `DegradationReason` **只加不删**加一个值：

```diff
-DegradationReason = Literal["rate_limited", "fetch_failed", "parse_drift", "disabled"]
+DegradationReason = Literal[
+    "rate_limited", "fetch_failed", "parse_drift", "disabled",
+    # —— v0.4 只加不删（E6 降级矩阵注册点，DEC-003 允许的既有文件增量）——
+    "no_region_sources",   # 该地区无可用源（K1 未决或全部停用）
+]
```

E6 降级矩阵是 DEC-003 明列的允许注册点；既有四值一个未动、既有函数语义未动。

## 5 名字撞车（登记项，无法消除）
`flint.sources.registry.SourceRegistry`（M1-010 **热点源工厂注册表** + feature flag 启停）
与 v04 契约 I3 的 `SourceRegistry`（**分区源选集表**）**同名不同物**。
两个名字各由自己的规格钉死，改哪个都越界。处置：`flint/region/registry.py`
**NEVER 引用** M1-010 那个，并由 `test_v04_registry_does_not_shadow_the_m1_source_registry`
双向断言（源码里无该 import + 两个类不是同一对象）。

## 6 self_review（self_review=true）
① acceptance 映射见下表；② 冻结件未动（本卡只读 contracts_v04）；③ 无禁用词；
④ 复用 `flint/sources/degradation.py` 的 `DegradationNote` 与 `DegradationStore` 协议，
**NEVER 新写降级机制**；⑤ 装载 3k tokens（7.5%）。

| acceptance | 测试 |
|---|---|
| 空表 select 走 E6 缺数据行 | `test_empty_registry_emits_degradation_note`（reason/day/detail 逐项断言）+ `test_degradation_is_per_region_not_global`（一个区没源其余照常）+ 阴性对照 `test_non_empty_registry_emits_no_note`（有源时不落降级，否则「降级」信号会被噪音淹没） |
| 他国强证据保留在选集 | `test_retrieval_keeps_foreign_sources` + `test_retrieval_ranks_home_region_first_without_excluding` |
| 真实源清单 NEVER 内置 | `test_seed_registry_is_empty` + `test_no_real_site_baked_into_implementation`（扫实现里的 URL/域名字面量） |
| 准入标准成文 | `test_admission_doc_states_the_undecided_items`：文档 MUST 指明 K1/K2 未决且含四项字段口径 |

## 7 产出
`flint/region/__init__.py`、`flint/region/registry.py`、`docs/source_admission_v04.md`、
`tests/v04/region/test_registry.py`（11 条）；`flint/sources/degradation.py` 加一个降级原因。
