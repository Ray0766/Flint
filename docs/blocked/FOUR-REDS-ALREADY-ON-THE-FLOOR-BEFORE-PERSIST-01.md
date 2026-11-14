# 四条红在 `PERSIST-01` 开工之前就在盘上

**状态** open · 2026-08-09 · `PERSIST-01`

**开单人**：worker，第 9 批 `PERSIST-01` 执行中（2026-08-09）。
**状态**：open。**归属**：`PERSIST-02`（前三条）与 `ENTRY-05`（第四条）——两张卡都在本批。

## 为什么单独开一张单，而不是顺手修掉

`PERSIST-01` 的全量 `pytest` 跑出 **10 红**。其中 6 条是本卡引起的（已在本卡修掉，
逐条记在 `docs/trace/PERSIST-01.md` §改前改后），**另外 4 条不是**。

不顺手修的理由有两条，第二条更硬：

1. 它们的正主是本批后面两张卡（`/workbenches` 那一族归 `PERSIST-02`，
   可达性与对账表归 `ENTRY-05`），在那里修才有对应的 acceptance 看着；
2. **本卡的 outputs 里没有 `flint/api/workbenches.py`，也没有那三个判据文件**。
   工单 rules 写死：「改动面大于卡上 outputs → 停下走 `docs/blocked/`」。
   顺手修掉的话，台账上会显示这四条是 `PERSIST-01` 的产物，
   而**下一个人复盘时会以为本卡碰过 workbenches**。

## 怎么确认它们不是本卡引起的

本卡碰过的文件：`migrations/versions/0023_*.py`（新）· `flint/db/`（新）·
`flint/fav/pgstore.py`（新）· `flint/share/pgstore.py`（新）· `flint/profile/pgprefs.py`（新）·
`flint/api/app.py` · `flint/api/{favorites,share,settings}.py` ·
`flint/fav/{store,stale,batch}.py` · `flint/profile/prefs.py`。

**`flint/api/workbenches.py` 一次都没打开过**，而下面三条报的主语就是它。

第四条报的是 `flint/api/app.py` 里**一句注释**，那句注释是 `ENTRY-03` 写的，
本卡读到它时就已经在（原文见下）。

## 四条各自是什么

### ①②③ `/workbenches` 与 `/workbenches/{}/nodes` 没有前端类型

```
tests/v041/test_type_gaps_untyped.py::test_no_endpoint_is_reported_as_untyped
  还有端点没有类型：/workbenches（缺 ['created', 'graph_id', 'seed_cluster_id']）,
                    /workbenches/{}/nodes（缺 ['created', 'graph_id', 'node_id']）
tests/v041/test_types_complete.py::test_the_untyped_count_is_pinned_until_the_ruler_is_fixed
tests/v041/test_fe_be_parity.py::test_the_table_is_generated_from_a_real_run_not_hand_written
tests/v041/test_parity_dynamic_path.py::test_both_kinds_are_genuinely_zero_now
```

（第三、四条是同一个根因的另外两把尺子在报同一件事。）

**这与 `PERSIST-02` 是同一件事的两半**：那张卡的 acceptance 第一条写的就是
「对账器 `frontend_wants_missing_backend = 1`，那一条就是 `POST /workbenches`」。
建端点的时候把响应类型一起建上，这三条一起绿。

### ④ `app.py` 里 `GraphStore()` 出现了两次，而判据要求一次

```
tests/v041/test_workbench_create.py::test_the_app_shares_one_graph_store_between_workbench_and_edges
  AssertionError: 又有人 new 了第二个 GraphStore
  assert 2 == 1
```

两处实况：

```
flint/api/app.py:572    # 改前 edges 那一族自己 new 了一个 `GraphStore()`。再给建工作台 new 第二个的话，
flint/api/app.py:581    graph_store = GraphStore()
```

**第 572 行是一句注释**——`ENTRY-03` 解释「为什么只能有一个」时把那个名字写进了正文，
而判据数的是**整份源码里的字符串出现次数**，分不出代码与注释。

所以这条判据今天判的是「这个字符串出现几次」，而它想判的是
「`GraphStore()` 被**调用**几次」。**NEVER 靠改那句注释去顶绿**：
那是把解释删掉来迎合尺子，而那句解释正是这条判据存在的理由。
正确的修法是让判据走 AST 数调用点（本仓 `tools/check_fe_be_parity.py` 已经是这么做的，
它的原话是「判在 AST 上——注释里写的路径不算数」）。

`ENTRY-05` 收口可达性与对账表时一并修，或由 `PERSIST-02` 顺手修
（它本来就要动 workbenches 那一族）。

## 需要 owner 的什么

**什么都不需要**——两张正主卡都在本批之内，本单只是把「谁在什么时候发现的」
钉住，免得下一个人把这四条算到 `PERSIST-01` 头上，
或者反过来以为它们是 `PERSIST-02` 新引入的回归。

## 绕行现状

四条**保持红**。`PERSIST-01` 自己的 `verify_cmd`
（`pytest tests/v041/test_persist_fav_share_prefs.py -q`）21 条全绿，
全局门 `ruff` / `mypy --strict flint` 全绿。
