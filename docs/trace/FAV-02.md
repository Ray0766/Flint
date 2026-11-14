# FAV-02 trace — snapshot_stale 打标 + 双动作（查看当时版本 / 更新到最新）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#FAV-02`；
- context_refs：`WORKORDER-v04.md#5-D`（D3 一行）、`WORKORDER-v04.md#6`（H1 行）、
  `contracts_v04/models_v04.py#Favorite`（第 1392~1414 行：内嵌快照基线、
  `snapshot_stale` 只能由 Revalidator 置 True、P1 采纳位注释）；
- 前置产物：`flint/analysis/stale_adapter.py`（HOTSPOT-06，本卡直接转调）、
  `flint/fav/store.py`（FAV-01 的深拷贝与 owner 过滤口径）、
  `flint/fav/batch.py#_owned`（FAV-05 的越权口径）。
- 实测装载 ≈ 13k tokens，未超 40k。

## 2 关键设计判断

**旧快照放哪**：冻结件 `Favorite` 没有历史字段，且 S2-1 禁止改冻结件。故历史落在
模块内的 `SnapshotHistoryStore`（与 `FavoriteStore` 同款内存实现，SQL 随 E2 接入），
**零触碰冻结件**。

**「更新到最新」不能是覆盖**：两个动作是一对，覆盖之后「查看当时版本」就没有数据可看，
而用户按下更新时并不知道那是一次不可撤销的擦除。且历史保留**每一次**旧值——
只留上一次的话，「当时版本」最远只能回到昨天，可用户想回的是**他收藏那天**看到的东西。

**stale 只由统一口径置 True**：转调 HOTSPOT-06 适配器，本模块一行比对逻辑都不写；
另加一条源码断言禁掉时间戳推断（`timedelta` / `days=` / `utcnow` / `time.time`）。
按时间戳推断的坏处是它**看起来总是对的**：三个月前的收藏「显然」旧了，可事实一个字
没变时那个标记只让用户白重跑一次；而昨天的收藏也可能因一次事实移除而彻底失效。

**快照缺账本版本 → 抛 `StaleNotEvaluated` 且状态保持原样**，NEVER 猜、NEVER 悄悄
标成不陈旧：悄悄放过的话，界面会告诉用户「这份收藏是最新的」，而我们根本没能力知道。

**内容相同的刷新不写历史**：没有旧值可留，历史里多一条只会误导。

## 3 test-first 顺序 + 一处 API 收敛

1. 先写 15 条测试 → 跑 → 红（模块不存在）；
2. 实现 `flint/fav/stale.py` → 15 passed；
3. `ruff --fix` 清掉 3 处无效 `# noqa: E402`；
4. 一处 API 收敛：`refresh_snapshot` 原本收 `model` 入参（对齐 `add_favorite` 的写法），
   但它是**派生**而非构造，`dataclasses.replace` 不需要模型类——留一个立刻被丢弃的参数
   会让调用方以为它有用。故从签名与测试里一起去掉（语义未变，不是为过测改测试）。
   顺带把「为什么用 replace 而不是重建」写进注释：重建会丢掉 `created_at` 这种
   收藏时点字段，而「查看当时版本」正靠它说明那是哪一天的东西。

## 4 acceptance ↔ 测试映射

**① stale 判定复用 H1 适配器（import 断言）**

| 测试名 | 覆盖点 |
|---|---|
| `test_stale_module_imports_the_h1_adapter` | AST 断言 import 面含 `flint.analysis.stale_adapter` |
| `test_stale_module_never_infers_freshness_from_time` | 无自定义 diff 函数；源码无 `timedelta`/`days=`/`utcnow`/`time.time` |
| `test_marks_stale_when_the_channel_says_a_cited_fact_moved` | 版本对 `(7, 9)` **取自快照**（通道内断言），结果落库而不只是返回值 |
| `test_unrelated_change_leaves_the_favorite_fresh` | 零污染：未被引用的事实变动不标陈旧 |
| `test_snapshot_without_ledger_version_is_not_guessed` | 缺版本 → 抛错 + 状态保持 False + 通道 NEVER 被调 |
| `test_evaluate_rejects_another_owners_favorite` | 越权抛 PermissionError（NEVER 静默跳过） |

**② refresh 生成新快照且旧值保留历史**

| 测试名 | 覆盖点 |
|---|---|
| `test_refresh_replaces_snapshot_and_keeps_the_old_one` | 新值就位、旧值逐字进历史、`replaced_at` 为传入时钟 |
| `test_history_keeps_every_old_value_in_order` | 两次刷新 → 两条历史且顺序为时间序；`original_snapshot` 仍是最初那份 |
| `test_original_snapshot_before_any_refresh_is_the_current_one` | 没刷新过时「当时版本」是现在这份，NEVER 空 |
| `test_refresh_clears_the_stale_mark` | 刷新后陈旧标记归 False（先用通道标 True 再刷，两段连着验） |
| `test_history_entries_are_copies` | 改返回值不影响库（深拷贝，FAV-01 同源） |
| `test_identical_refresh_records_no_history` | 内容未变不写历史 |
| `test_refresh_rejects_empty_snapshot` | 空快照拒绝 |
| `test_refresh_rejects_another_owners_favorite` | 越权拒绝**且原快照未被改动** |
| `test_refresh_unknown_favorite_raises` | 未知收藏抛 KeyError |

## 5 端点落法（与卡片 outputs 的对应）

卡片 outputs 写 `api: POST /favorites/{id}/refresh-snapshot`。仓库现状：
`flint/api/` 下**没有 favorites 路由文件**，FAV-01（`POST /favorites`）与
FAV-05（`POST /favorites/batch`）都是「函数即端点语义、路由随 E2 接线」的落法。
本卡沿用同一惯例：`refresh_snapshot` 的 docstring 写明端点路径，路由文件不在本卡新建
——新建一个只挂一条路由的文件会与 FAV-01/05 的接线方式分叉。

## 6 verify

```
$ pytest tests/v04/fav/test_snapshot_stale.py -q  → 15 passed
$ pytest tests/v04 -q                              → 350 passed
$ ruff check . --no-cache                          → All checks passed!
$ mypy --strict flint                              → 255 source files, no issues
```

禁用词扫描：本卡两份产出 0 命中。

## 7 产出

- `flint/fav/stale.py`
- `tests/v04/fav/test_snapshot_stale.py`（15 条）
