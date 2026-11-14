# REGION-05 trace — same_event_group 显式建解 @2026-08-02

## 1 装载
REGION-05 卡 + `PRINCIPLES#B5` + REGION-04 的 bucketing 结论。~1,200 字符 ≈ 1.2k tokens（3%）。

## 2 test-first
先写测试 → **collection error**（`flint.region.same_event` 不存在）→ 实现 → 9 passed。

## 3 「不存在」比「默认关闭」强
acceptance ② 要的是**模块导出面断言**。留一个 `auto_group(threshold=…)` 而默认不调用是不够的——
留一条路就等于允许它被走，而 B5 要防的正是 embedding 把两国报道合成一簇。
所以断言的是**导出面上根本没有这条路**：`dir(module)` 与 `auto_group`/`group_by_similarity`/
`embedding`/`cosine`/`threshold` 等名字零交集；`establish_group` 的入参集合逐字断言
（只有 store/group_id/cluster_ids/actor/now，没有任何「按什么自动找」的参数）。

## 4 一次自纠：断言把散文当成了实现
`test_no_embedding_symbol_in_source` 初版扫全文，结果 docstring 里解释
「B5 要防的正是 embedding 自动合并」这句**说明文字**被判成实现，红在一个正确的模块上。
改成 **AST 只扫标识符**（Name/Attribute/def/arg/alias），docstring 自然不在其中。
这是 SCHEMA-09 踩过的同一个坑，第二次遇到已按同一口径处理。

## 5 显式 = 有主体
每组记 `established_by` / `established_at`，空 actor 直接拒绝——
**没有主体的组就是「系统自动建的」**，那正是要禁的东西。
另拒单簇建组：一个簇自己不构成「同一事件」的关联。

## 6 幂等（acceptance ①）
建组：同 id 同内容重放返回同一个组，NEVER 产出第二个；
解组：不存在时返回 `False` 而 NEVER 抛错（端点重放、用户连点都不该炸）；
解后重建：从干净状态开始（`test_establish_after_dissolve_starts_clean`）。

## 7 产出
`flint/region/same_event.py`、`tests/v04/region/test_same_event_group.py`（9 条）。
API 端点（POST/DELETE `/clusters/same-event-group`）的形状由本模块的两个函数定义，
挂路由属后续 api 卡；本卡不接库（SQL 实现随 E2 的 `same_event_groups` 表）。
