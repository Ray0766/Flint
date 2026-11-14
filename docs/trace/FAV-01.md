# FAV-01 trace — 收藏写路径 + 快照冻结 @2026-08-02

## 1 装载
FAV-01 卡 + SCHEMA-09 的 `Favorite`（内嵌快照形状）+ `§9-P1` 提案。~1,400 字符（3.5%）。

## 2 test-first
先写测试 → collection error → 实现 → **10 passed**；ruff 净、mypy 238 文件净。

## 3 「冻结」在基线里靠内嵌，不靠保护
SCHEMA-09 定的基线是**内嵌** `evidence_snapshot`：收藏时把内容抄一份带走。
于是「源被改了/被删了/被 180 天周删清了」都影响不到它——**冻结是结构性的**，
不依赖任何人记得去保护被引对象。

**抄必须是深拷贝**：浅拷贝会漏——顶层键抄了，嵌套的 `list`/`dict` 还是同一个对象，
调用方 `append` 一下就改了「冻结」的快照。**读出去的也是副本**，
否则拿到返回值改一下就改了库里的东西。

## 4 acceptance 映射
| acceptance | 测试 |
|---|---|
| 收藏后改源 → 快照字节不变 | `test_mutating_the_source_dict_does_not_touch_the_snapshot`（改名、往 list 里 append、加新字段三种改法后 `json.dumps(sort_keys)` 比对）+ `test_snapshot_is_byte_identical_after_source_deletion`（源整个 `clear()` 后快照照常可读） |
| （最容易漏的两处） | `test_nested_structures_are_deep_copied`（浅拷贝会漏嵌套）+ `test_reading_back_does_not_expose_the_stored_object`（读出去的必须是副本） |
| P1 采纳位以注释标记、基线不实现 | `test_p1_pin_path_is_comment_only`：注释里有 P1 与 pin 接法；导出面上 `pin_snapshot`/`freeze_snapshot`/`protect_snapshot` **一个都不存在** |
| （写路径） | add/remove 幂等各一条；`test_list_is_scoped_to_owner`（越权读 NEVER 发生）；`test_snapshot_stale_starts_false`（stale 只能由 Revalidator 置，§6-H1）；`test_empty_snapshot_is_rejected`（空快照 = 指向空处的壳，正是内嵌要避免的） |

## 5 self_review（self_review=true）
① 见 §4；② 冻结件未动（只读 contracts_v04 的 `Favorite`）；③ 无禁用词；
④ H1 复用：stale 判定不在本卡实现，注释指向 `Revalidator` 统一口径；
⑤ 装载 1.4k tokens（3.5%）。

## 6 产出
`flint/fav/__init__.py`、`flint/fav/store.py`、`tests/v04/fav/test_snapshot_freeze.py`（10 条）。
API 三端点（POST/GET/DELETE `/favorites`）的形状由这三个函数定义，挂路由属后续 api 卡。
