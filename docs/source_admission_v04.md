# 源准入标准 v04（REGION-01）

> 依据 `WORKORDER-v04.md#5-B` 与 `PRINCIPLES#B4`。校验：`tests/v04/region/test_registry.py`。
> **本文件定的是「一个源要满足什么才能进注册表」，不是源清单本身。**
> 九区源清单待 **K1**、各国抓取合规结论待 **K2**——两者未决前，注册表是**空表种子**，
> 实现与文档里 NEVER 内置任何真实站点。

## 一、每个源必须给出的四项

| 字段 | 口径 | 缺了会怎样 |
|---|---|---|
| `region` | 该源归属的九区之一 | 归不了区就进不了任何区的采集选集；归错区会污染该区热点集合（`PRINCIPLES#B5`） |
| `name_native` | 源名**原文**，NEVER 翻译 | 原文是权威（`PRINCIPLES#B7`）；用译名做 embedding/去重会把同一个源认成两个 |
| `authority_tier` | 四级 + `unknown` 缺省 | `unknown` 证据 NEVER 满足判 A/B 的必要条件（REGION-03 前置门） |
| `fetch_legal_status` | `allowed` / `unknown` / `restricted`，缺省 `unknown` | `restricted` 拒绝抓取任务（REGION-07）；缺省 `unknown` 意味着**默认不当作可抓** |

`country`（ISO 3166-1 alpha-2）与 `region` 可以不同：一个源的注册地与它服务的地区并不总是一致，
两者分开记录，NEVER 用其中一个推断另一个。

## 二、准入判断（K1 落地时逐源过一遍）

1. **可定位**：有稳定主页与稳定的条目 URL 形态——否则抓取无法复现（S2-2 第三条铁律）。
2. **可归区**：能确定 `region`。**不确定就不收**，NEVER 先塞进一个「差不多」的区。
3. **可定权威度**：能对上四级中的一级。定不了就是 `unknown`——`unknown` 是**如实标注**，
   不是「先给个中等」。
4. **合规态明确**：`fetch_legal_status` 由 **K2 的结论**填。K2 未决前一律 `unknown`，
   而 `unknown` 在 REGION-07 的门里**不放行抓取**。

## 三、本国优先，但 NEVER 隔离（`PRINCIPLES#B4`）

- **采集**选集按 region 取：热点集合本就是分区的。
- **检索**选集**不按国别过滤**：本区源以 `region_match` 加权排前，他国源权重照常 > 0。
  他国强证据留在选集里——跨国立场分歧沿 `by_source` 分列独立呈现（REGION-08），
  NEVER 合成为单一结论句。

**过滤器 NEVER 写成 `[s for s in sources if s.country == region]`**——
这行代码就是 B4 的反例，`tests/v04/principles/fixtures/B4.json` 里存着它。

## 四、空表期间（现状）

注册表为空 → 采集侧对每个区落一条 `DegradationNote(reason="no_region_sources")`（E6 缺数据行），
当日该区无数据，**其余区照常**。空是明确状态，不是故障。
