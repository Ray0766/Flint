# GRAPH-07 trace — 连线交互 + 强制假设（前端空不落盘 + 服务端 422）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#GRAPH-07`；
- context_refs：`WORKORDER-v04.md#4-I8`（图谱三实体）、`WORKORDER-v04.md#6`（H8 行）、
  `WORKORDER-v04.md#5-F`（F7/F8 行）、`contracts_v04/models_v04.py#GraphEdge`（第 1361~1376 行）；
- 前置产物：`flint/graph/store.py#add_edge`（H8 链条：它 import combo 的 `_require_str`）、
  `flint/topic/create.py#_require_str` 与 `OriginValidationError`、
  `flint/api/schemas.py#ErrorCode`、`flint/api/views.py`（`create_*_app(deps)` 的既有写法）、
  `tests/m2/test_m2_041.py`（错误码注册表的既有断言口径）。
- 实测装载 ≈ 15k tokens，未超 40k。

## 2 一处既有文件的注册点增量（DEC-003 允许的形态）

`flint/api/schemas.py` 的 `ErrorCode` 加了一个成员 `EMPTY_HYPOTHESIS`（只加不删，
错误码注册表即注册点）。**单列一码而不是并进 `VALIDATION_FAILED`** 的理由写在代码注释里：
「边上没写假设」与「请求体格式不对」的修法完全不同，前端要据此把光标送回假设输入框，
而不是弹一句通用报错。既有断言 `tests/m2/test_m2_041.py` 复跑通过（新码为 UPPER_SNAKE）。

新增 `flint/api/graph_edges.py`（新文件）承载 `POST /workbenches/{id}/edges`：
acceptance 要的是**绕过前端直发得到 422**，那是一次真实 HTTP 往返，函数级测试出不了状态码。

## 3 关键设计判断

**两道拦截彼此独立，不是回声**。前端那一半只保证「正常用界面的人不会建出空假设边」；
curl 一发、或哪天多一个批量导入入口，空假设边就进库了——而一条没有假设的边
说不出两端为什么被连起来：它在画布上是一根线，在生成时是一条**没有理由的关联**，
会被当成用户的判断写进文书。

**前端为什么要拦住而不是让 422 弹回来**：请求飞出去再被拒，用户看到的是一次失败，
而他其实只是还没写；更糟的是画布上那根线该不该留——发出去了就要处理
「服务端拒了但线还在」的中间态。不发，就没有这个中间态。

**校验只有一份（H8）**：API 层不写任何非空判断，照常走 `add_edge`（它 import 的是
combo 的 `_require_str`），再把共享校验器抛的 `OriginValidationError` 映射成 422。
两份实现就是两种口径，用户会遇到「在 combo 里能提交、在图谱里被拒」这种事。

**失败不清空草稿**：清掉等于让用户重写一遍，而他多半只需要改一个词。

## 4 test-first 顺序 + 两次返工（都改判据不改语义）

1. 后端 10 条先写 → 红（模块不存在）→ 实现 → **1 条红**：
   `test_api_layer_never_reimplements_the_hypothesis_check` 按字符串扫源码，
   把模块 docstring 里那句「本层不做 `hypothesis.strip()`」判成了违规。
   改判据为 **AST**（属性名集合里无 `strip`、名字集合里无 `_require_str`）——
   断的是代码不是文字。同一个坑此前在 SCHEMA-09 / REGION-05 / I18N-06-b / FAV-04
   出现过四次，这次是第五次，形态是「解释自己不做某事的那句话被当成做了」。
2. 前端 9 条先写 → 红（组件不存在）→ 实现 → **1 条红**：CJK 扫描把三行**行尾**
   `//` 注释判成界面文案。改判据为与 `tools/i18n_scan.mjs` **同口径**
   （块注释 + 整行 `//` + 行尾 `//` 都剥掉）——比扫描器更严没有意义，
   严出来的红是假的，而假红会训练人去忽略红。

## 5 自审报告（§4.6，本卡 self_review=true）

**① 测试真实覆盖 acceptance**

acceptance①「松手弹假设框；空值前端不发请求；绕过前端直发 → 422 EMPTY_HYPOTHESIS」：

| 测试名 | 覆盖点 |
|---|---|
| `松手即弹假设框，且此刻还没有边被建出来`（前端） | 弹框 ≠ 落盘 |
| `空假设不发请求` / `只有空白同样不发`（前端） | 提交被拦在本地，`onCreate` 零调用 |
| `写了假设才发，且原样带上两端与文本`（前端） | **阴性对照**：这条路是通的（否则「不发」毫无意义） |
| `test_empty_hypothesis_is_422_with_the_named_code[3 组]`（后端） | 空串 / 空格 / 制表换行 三种空白都 422 且码正确、库里零边 |
| `test_missing_hypothesis_field_is_also_422`（后端） | 字段不给走同一条路 |
| `test_valid_edge_is_created_once_and_is_idempotent`（后端） | 阴性对照 + 同 (from,to) 幂等（GRAPH-02 口径） |
| `test_dangling_edge_is_rejected_with_a_different_code`（后端） | 悬空边也拒但**码不同**：两种错的修法完全不同 |
| `test_empty_hypothesis_code_is_registered`（后端） | 新码进注册表且 UPPER_SNAKE |

acceptance②「校验复用 H8 函数（import 断言）」：

| 测试名 | 覆盖点 |
|---|---|
| `test_api_layer_never_reimplements_the_hypothesis_check` | AST：无 `strip`、无 `_require_str`、import 自 `flint.graph.store` |
| `test_the_shared_validator_is_what_rejects_it` | 映射键的是共享校验器的**异常类型**（import 自 `flint.topic.create`） |
| `test_store_still_routes_through_the_combo_validator` | H8 链条另一端未被绕开 |

另有四条边界在前端：方向不可互换（有向边）、取消不留半根线、服务端拒了不谎报成功
且草稿保留、连点两下只发一次。

**② 无冻结件偏离**：`contracts/` 与 `contracts_v04/` 零触碰（md5 未变）；
`GraphEdge` 的字段与 `__post_init__` 语义原样使用。唯一改动的既有文件是
`flint/api/schemas.py` 的错误码注册表（只加不删，见 §2）。

**③ 无禁用词**：本卡五份产出扫描 `BANNED_HITS= 0`。

**④ 复用断言在位**：H8 三条（见上表）；错误响应体走既有 `ErrorBody`，未新写错误结构。

**⑤ 装载未超预算**：实测 ≈15k tokens（上限 40k）。

## 6 verify（卡上 verify_cmd 是合取，两段分别在各自 cwd 跑）

```
$ cd web && npm test -- --run components/graph-edge          → 9 passed
$ pytest tests/v04/graph/test_edge_hypothesis.py -q           → 10 passed
```

回归：`pytest tests/v04 tests/m2/test_m2_041.py` 377 passed；`tests/v04/graph` 39 passed；
前端全套 **206 passed / 31 files**；typecheck 干净；`i18n_scan web/components` exit 0；
`ruff` 全绿（`--fix` 归位三处 import 排序）；`mypy --strict flint` 257 文件净。

## 7 产出

- `flint/api/graph_edges.py`、`flint/api/schemas.py`（+1 错误码）
- `tests/v04/graph/test_edge_hypothesis.py`（10 条）
- `web/components/graph-edge/GraphEdgeDraft.tsx`、`GraphEdge.test.tsx`（9 条）
- `web/messages/{zh,en}.json`：各 +5 key（45 键，键集一致）
