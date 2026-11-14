# SCHEMA-08 trace — I8 图谱三实体 @2026-08-02

## 1 装载
SCHEMA-08 卡 + `WORKORDER#6-H8` + `models_v04.py` 的 I8 区。~1,300 字符 ≈ 1.3k tokens（3.3%）。

## 2 test-first（真红 5 条）
先写测试 → **5 failed**。SCHEMA-00 预落的形状与本卡 acceptance **不符**：
预落的是 `NodeRole` 五值（含 hypothesis/note）+ `source_id: str | None`，
卡要的是 **`source_kind` 三值判别** + **`archived` 默认 False**。按卡校正后 **7 passed**，
additive exit 0，全 schema 套 57 passed。

## 3 三处判断
**① 节点只投影三类既有实体**（`cluster` / `evidence_card` / `topic`）：
图谱节点是既有实体的投影，不是新造的东西（§6-H8）。`source_id` 因此改为**必填**——
一个不指向任何实体的节点，在图上就是个孤立标签。

**② 假设在边上，不在节点上**：假设描述的是两个东西之间的**关系**。做成节点会出现
「一个没有两端的假设」——那正是 combo 通道要求 hypothesis 必填的原因。
预落的 `NodeRole` 里有 `hypothesis` 一值，本卡把它去掉（它是 v04 新增物，非冻结件符号，
additive 校验不受影响），并用 `test_hypothesis_lives_on_edges_not_nodes` 反向钉住。

**③ archived 而不是 delete**：图是用户的思考过程，删掉就没了、归档还能翻回。
`test_archiving_is_the_only_removal_path` 断言 `WorkbenchGraph` **没有**任何删除标记字段
（数据删除是 owner 人审节点，v0.4 内不存在这条路径）。

## 4 acceptance 映射
| acceptance | 测试 |
|---|---|
| source_kind 三值判别 | `test_source_kind_is_exactly_three_values`（集合逐字相等） |
| 有向图字段齐全 | `test_graph_is_directed`：断言 `from_node_id`/`to_node_id` 两字段存在且真构造一条边验证方向 |
| archived 默认 False | `test_archived_defaults_to_false` |
| （§6-H8 复用） | `test_edge_hypothesis_is_required_and_non_empty`：空白假设抛 `ValueError`，与 combo 通道同语义 |

## 5 产出
`tests/v04/schema/test_i8_graph.py`（7 条）+ `GraphSourceKind`/`GraphNode.source_kind`/
`GraphEdge.__post_init__`/`WorkbenchGraph.archived`；`docs/schema_reconcile_v04.md` 的 I8 行同步改名。
