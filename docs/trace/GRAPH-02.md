# GRAPH-02 trace — 图谱数据层 @2026-08-02

## 1 装载
GRAPH-02 卡 + SCHEMA-08 的 `GraphNode`/`GraphEdge` + `flint/topic/create.py` 的
`_require_str`（H8 复用对象）。~1,600 字符（4%）。

## 2 test-first
先写测试 → collection error → 实现 → **9 passed**；ruff 净、mypy 242 文件净。

## 3 入台幂等按什么判
按 **(graph_id, source_kind, source_id)**。
- 按 `node_id` 判不够：用户第二次拖入时**不会带着上次的 node_id**
  （`test_second_admission_of_same_source_returns_existing_node` 就是用两个不同 node_id 进的）；
- 作用域是**一张图**：同一个热点当然可以出现在两张图里，那是两个独立的思考；
- `source_kind` 也进键：同 id 不同类（cluster `c-1` 与 topic `c-1`）不是同一个东西。

## 4 悬空边 NEVER 入库
一条指向不存在节点的边，在画布上就是**一根断线**；存进去之后每个读图的人
都要自己判断「这根线算不算数」。两端必须都在（`test_edge_requires_both_endpoints_to_exist`）。

## 5 H8 复用（acceptance ②）
边上的 hypothesis 与 combo 的关联假设是**同一个东西**——都是「为什么把这两样连起来」。
校验 import 自 `flint/topic/create.py` 的 `_require_str`，**NEVER 新写一份**：
两份实现就是两种口径，用户会遇到「在 combo 里能提交、在图谱里被拒」这种事。

三条测试守着：源码里有 `from flint.topic.create import`；空/空白假设被拒；
以及 `test_shared_validator_matches_combo_semantics` —— 直接拿 combo 的校验器跑一遍，
断言两侧判据一致。

## 6 self_review（self_review=true）
① 见上；② 冻结件未动；③ 无禁用词；④ H8 由三条断言守着；⑤ 装载 1.6k tokens（4%）。

## 7 产出
`flint/graph/__init__.py`、`flint/graph/store.py`、`tests/v04/graph/test_store.py`（9 条）。
