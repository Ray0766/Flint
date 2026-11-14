# DESIGN-11 trace — 版本历史检查点（VFS+图谱同快照；恢复=新检查点）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-11`；
- context_refs：`WORKORDER-v04.md#5-G`（G16 一行）；
- 前置产物：`flint/graph/store.py`（图谱状态的形状）、`flint/fav/store.py`
  （FAV-01 的深拷贝/副本读口径）、`tests/v04/_source_scan.py`（本卡新抽）。
- 实测装载 ≈ 8k tokens，未超 40k。

## 2 关键设计判断

**两份必须在同一个检查点里**：设计产物与它所依据的图谱是一起才说得通的——
同一份页面配上另一张图谱，讲的就是另一件事。分开存两条历史，恢复时就要回答
「用哪一版图谱配哪一版页面」，那个问题没有正确答案，只有猜。故缺一半直接拒绝。

**恢复 = 新检查点**：「恢复到三步前」若把后面几步删掉，用户就再也回不到当前这一版——
而他常常是回去看一眼、再回来。所以恢复把旧内容抄成一个新点并记 `restored_from`：
时间线永远往前走，且看得出这一版是从哪一版抄回来的。

**存储层也不留口子**：同 id 二次写入抛 `HistoryImmutable`，免得哪天有人
「更新一下历史」。历史一旦会变，它就不再是历史。

**快照与现场彻底断开**：存时深拷贝、读时回副本（与 FAV-01 同一条纪律）。
浅拷贝的话现场改一下嵌套结构，「历史」里那份跟着变。

**只存图谱状态，不碰活的图谱**：本模块不 import `GraphStore`、不调 `add_node/add_edge`——
快照是当时的样子，现场是现在的样子，接在一起就会出现「回看历史顺手改了当前图」。

## 3 一次语法错 + 一次判据修（后者顺手抽了共享工具）

**语法错**：`Checkpoint` 里误留了一个裸 `/`（本想写位置参数分隔符），Python 直接
SyntaxError。改为一行注释说明 `restored_from` 的含义。

**判据修（第 7 次同款坑，Python 侧第 2 次）**：`test_module_never_reaches_into_the_graph_store`
按字符串扫源码，把模块 docstring 里那句「NEVER import GraphStore」判成了违规。
前端侧这个坑第 6 次时抽了 `web/test-utils/source.ts#codeOnly`；本卡在 Python 侧
抽出对应物 **`tests/v04/_source_scan.py`**（`code_names` / `code_strings`，按 **AST** 判——
注释与 docstring 根本不进 AST，所以「解释」永远不会被误判成「实现」）。
后续 Python 卡直接用它，不再各写一遍。

## 4 自审报告（§4.6，本卡 self_review=true）

**①** acceptance ↔ 测试：

| acceptance | 测试名 |
|---|---|
| 检查点含 VFS+图谱双份 | `test_checkpoint_carries_both_vfs_and_graph`、`test_checkpoint_rejects_a_half_snapshot`（两侧各一） |
| 恢复产生新检查点 | `test_restore_appends_a_new_checkpoint_and_keeps_the_old_ones`（新 id + 内容相等 + `restored_from` + 时间线三点） |
| 历史不可变 | `test_restore_never_deletes_or_rewrites_history`、`test_history_is_append_only_at_the_store_level` |
| （快照语义） | `test_snapshot_is_deep_copied_from_the_live_state`、`test_reading_a_checkpoint_returns_a_copy` |
| （边界） | `test_restore_unknown_checkpoint_raises`、`test_history_is_scoped_per_session`、`test_history_is_ordered_by_time_then_creation` |
| （不碰现场） | `test_module_never_reaches_into_the_graph_store`（AST 判据） |

**②** 无冻结件偏离：新增模块，零触碰 `contracts/` 与 `contracts_v04/`。
**③** 无禁用词：三份产出 `BANNED_HITS= 0`。
**④** 复用断言在位：深拷贝/副本读沿用 FAV-01 口径；源码扫描抽成共享 `_source_scan`。
**⑤** 装载 ≈8k tokens，未超 40k。

## 5 verify

```
$ pytest tests/v04/design/test_checkpoints.py -q  → 11 passed
$ pytest tests/v04/design -q                       → 32 passed
$ ruff check . --no-cache                          → All checks passed!
$ mypy --strict flint                              → 259 source files, no issues
```

卡上 cycles=2，实际 1。

## 6 产出

- `flint/design/checkpoints.py`
- `tests/v04/design/test_checkpoints.py`（11 条）
- `tests/v04/_source_scan.py`（Python 侧共享源码扫描口径）
