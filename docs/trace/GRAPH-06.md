# GRAPH-06 trace — 角色菜单 + 主唯一运行时（旧主降级 + toast）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#GRAPH-06`；
- context_refs：`WORKORDER-v04.md#5-F`（F5/F6 行）、`WORKORDER-v04.md#4-I12`（三条不变量）、
  `contracts_v04/models_v04.py` 的 `set_primary`（第 1233~1242 行）与 `GraphNode.primary`（第 1358 行）；
- 前置产物：`tests/v04/schema/test_i12_invariants.py`（SCHEMA-12 已验的规则语义）、
  `flint/graph/store.py`（GRAPH-02 的 store 面）、`web/lib/i18n/t.ts`。
- 实测装载 ≈ 12k tokens，未超 40k。

## 2 一处卡片 outputs 与 acceptance 不齐（已按 §4.3③ 记决定，非阻塞）

卡片 outputs 只列 `web/components/graph-roles/` 与 `tests/v04/graph/test_primary_unique_runtime.py`，
但 acceptance② 要的是**服务端并发双写下 primary ≤1**——契约里的 `set_primary` 是一个作用在
列表上的**纯规则函数**，没有任何运行时落点可供并发测试打。只用它写测试，测到的是
「规则在单线程下成立」，而那正是 SCHEMA-12 已经验过的东西。

故新增 `flint/graph/roles.py` 作为运行时落点（DEC-003 的口径：以新增文件为主，
既有文件不动）。记 `DECISIONS-v04.md#DEC-014`。

## 3 关键设计判断

**规则成立 ≠ 并发下成立**：两个写入方各自「读全图 → 改自己那一个 → 写回」时两次都会成功，
图里于是有两个 primary——UI 只显示其中一个是主，另一个悄悄也是主，
「这张图在讲哪件事」就没有答案了。故写入在**一个临界区**内完成「清旧主 → 立新主」。
内存实现用锁；SQL 实现的等价物是同一事务 + `UNIQUE (graph_id) WHERE primary` 部分唯一索引
（语义相同：同一时刻只有一个写入方能改这张图的主）。这一条写进了模块 docstring，
免得接 SQL 时有人以为锁是内存实现的特产。

**并发测试最容易变成摆设**（线程太少、跑得太快、恰好没撞上），故配**反例探针**
`naive_set_primary_unsafe`：同样的压力打在不加锁的写法上必须让断言变红。
探针的 docstring 写死「NEVER 用于生产路径」，它存在的唯一理由是让尺子证明自己认得出违规。
屏障对齐也写了理由：不对齐的话线程前后脚各跑各的，测试退化成串行调用。

**图可以没有主**：把主降成 secondary 之后不自动挑一个顶上——自动顶上等于系统替用户
决定「这张图在讲哪件事」，而那正是他要自己回答的问题。

**前端不自判降级**：谁被降是服务端在临界区里定的，组件只呈现回值。
本地推断在并发下必然与服务端不一致，而用户看到的是本地那份。
`currentPrimaryId` 只用于标出当前态，一条源码断言禁掉它参与判断
（`not.toMatch(/currentPrimaryId\s*(!==|===)/)`）。

**NEVER 确认对话框**：用户点第二个节点设主，意思已经很明确；再问一句「确定要替换吗」
是把系统的洁癖变成用户的负担。但降级必须**如实告诉他**：悄悄换掉主而不吭声，
他下次看这张图时会以为自己记错了。

## 4 自审报告（§4.6，本卡 self_review=true）

**① 测试真实覆盖 acceptance**

acceptance①「设第二主 → 旧主自动降 secondary + toast（NEVER 确认对话框）」：

| 测试名 | 覆盖点 |
|---|---|
| `test_setting_a_second_primary_demotes_the_first_and_says_so`（后端） | 旧主降级且**报出**被降的是谁；图内 primary 恰 1 且就是新主 |
| `test_resetting_the_same_node_reports_no_demotion`（后端） | 对当前主再设一次：无人被降（NEVER 报自己降了自己） |
| `旧主被降级 → 出 toast 并点名是谁；NEVER 弹确认对话框`（前端） | toast 带 `data-demoted-node-id`；`window.confirm` 未被调用；无 dialog/alertdialog |
| `没有谁被降级就不出 toast`（前端） | 回值 null → 无 toast |
| `降级与否只看服务端回值`（前端） | 传了 `currentPrimaryId` 但服务端说没人被降 → 仍不出 toast |
| `设次要/辅助也走同一条路`（前端） | 三项同一条调用路径，且不产生降级提示 |
| `角色集恰是三项` + `test_roles_module_never_reimplements_the_contract_rule` | 前后端角色集与契约同集 |

acceptance②「服务端并发双写下 primary ≤1 仍成立」：

| 测试名 | 覆盖点 |
|---|---|
| `test_primary_stays_unique_under_concurrent_writes` | 8 线程 × 40 轮屏障对齐并发写 → primary 恰 1 |
| `test_the_concurrency_check_can_actually_fail` | **反例探针**：同样压力打在无锁写法上必须 >1（证明尺子不空转） |
| `test_demoting_the_primary_leaves_the_graph_without_one` | 主可被降空，NEVER 自动顶一个 |
| `test_unknown_node_and_unknown_role_are_rejected` | 未知节点/未知角色拒绝 |

另有两条边界在前端：`设主失败不谎报成功`（出错误态且无 toast）、`文案 key 化`。

**② 无冻结件偏离**：本卡零触碰 `contracts/` 与 `contracts_v04/`；`NodeRole` 三值与
契约 `GraphNode.primary` 语义一致，`set_primary` 规则函数仍在原处未被取代（有测试断言）。
冻结件 md5 `380d7b5a7dae…` / `eb19b73e176e…` 未变。

**③ 无禁用词**：本卡四份产出扫描 `BANNED_HITS= 0`。一处自纠：屏障那行注释初版写了
S2-8 的一个禁用词，已改写为说清理由的句子（不对齐 → 线程前后脚 → 测试退化成串行）。

**④ 复用断言在位**：`test_roles_module_never_reimplements_the_contract_rule`
断言角色集与契约同集且契约规则函数仍在；运行时模块 import 自 `flint.graph.store`
（GRAPH-02 的既有 store），未新建第二套图存储。

**⑤ 装载未超预算**：实测 ≈12k tokens（上限 40k）。

## 5 verify（卡上 verify_cmd 是合取，两段分别在各自 cwd 跑）

```
$ cd web && npm test -- --run components/graph-roles              → 9 passed
$ pytest tests/v04/graph/test_primary_unique_runtime.py -q         → 7 passed
```

回归：前端全套 **197 passed / 30 files**、typecheck 干净、`i18n_scan web/components` exit 0；
`pytest tests/v04/graph` 29 passed；`ruff` 全绿（`--fix` 归位两处 import 排序）；
`mypy --strict flint` 256 文件净。

## 6 产出

- `flint/graph/roles.py`（运行时落点，DEC-014）
- `tests/v04/graph/test_primary_unique_runtime.py`（7 条）
- `web/components/graph-roles/GraphRoles.tsx`、`GraphRoles.test.tsx`（9 条）
- `web/messages/{zh,en}.json`：各 +5 key（40 键，键集一致）
