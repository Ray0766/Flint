# DEF-01 · 收藏快照 pin（§9-P1，owner 已采纳）

**卡** `tasks-v041-b2.json#DEF-01` · **开工** 机器 UTC 2026-08-04T01:10Z

## 1. 装载清单

卡面 DEF-01 · `flint/fav/store.py` 的 P1 采纳位那段注释（逐字）· `flint/fav/stale.py`
（`SnapshotHistoryStore` 与「历史保留每一个旧值」的理由）· `flint/store/snapshot.py`
（`RETENTION_DAYS` 与 `cleanup_expired`）· `contracts/protocols.py#SnapshotStore` 的
「唯一例外 RedactionRecord」· `WORKORDER-v04.md#9` 的 P1 行。约 8k tokens。

## 2. 顺序（§4.2）

测试先落盘先跑红（collection ERROR）→ 实现 → 15 passed。连续第十五张。

## 3. pin 是**多**一条路，不是**换**一条路

`flint/fav/store.py` 的采纳位原话：「P1 的做法: 把内嵌换成 snapshot_id 引用……
在那之前它只是注释, NEVER 成为真实现」。owner 已采纳，所以它成了真实现——
**但内嵌那条路一个字都不动**。

理由写进代码：基线的冻结靠**内嵌**（收藏时抄一份带走），所以
「源被改了 / 被删了 / 被 180 天周删清了」都影响不到它——**冻结是结构性的，
不依赖任何人记得去保护被引对象**。而 pin **依赖有人记得钉**：忘了钉，快照到期照样没。

所以两条并存：pin 让「引用 snapshot_id」这条更省空间的路也能安全走。
`test_the_embedded_freeze_path_is_untouched` 守着内嵌那条（深拷贝还在、采纳位注释还在——
**那段写着为什么内嵌不能换**，删了下一个人就会以为 pin 可以取代它）。

## 4. 两条豁免，方向正好相反

`SnapshotStore` 承诺「保留 180 天」（F2）。之上两条例外：

| 例外 | 方向 | 出处 |
|---|---|---|
| `RedactionRecord` | **提前删**，不等 180 天 | 审9，owner 删除权 |
| `pinned` | **留过 180 天**，周删跳过 | 本卡 |

**把两者混成一个「豁免」概念，迟早会写出「pinned 的也一并删掉」这种代码。**
所以它们分开测，还专门有一条 `test_the_two_exemptions_point_in_opposite_directions`：
同一个 id，pin 让它活、redact 让它死。

**撞上时删除权赢**：反过来（pin 挡住 owner 的删除权）等于用一个便利功能架空了一项权利。

## 5. 时间靠构造（acceptance③）

`now` 注入，`OLD = now - (180+1) 天`。**靠真实等待验 180 天的保留期是验不了的**——
那种测试要么永远不跑，要么被人改成 1 天然后忘了改回来。
边界也写死：整整 180 天那天还在保留期内，第 181 天才删——省得下一个人按「大概半年」重新猜。

## 6. 变异考：第四个活了下来，补了一条断言

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① GC 不跳过 pinned | 本卡正题 | **2 failed** ✓ |
| ② pin 能挡住删除权 | 「删除权赢」 | **2 failed** ✓ |
| ③ `pinned_ids` 返回内部集合 | 返回副本 | **1 failed** ✓ |
| ④ `RETENTION_DAYS = 30`（在 pin.py 里另写一个） | 「两处同一个数」 | **14 条全绿地活了下来** ✗ |

**变异 ④ 暴露的是一种很难自己发现的洞**：上面所有用例都从 `pin.RETENTION_DAYS`
推导时间，改常量时两侧一起动，**自洽得看不出问题**——而自洽不等于正确。
真实后果是：pin 以为自己保住了，周删按另一个数把它清了，谁都不会发现。

补 `test_the_retention_window_is_the_store_s_own_number`：断言
`pin.RETENTION_DAYS == snapshot.RETENTION_DAYS == 180`，把两个模块钉在一起。
重考变异 ④ → 红。

## 7. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_fav_pin.py -q → 15 passed
ruff check . --no-cache → All checks passed!
mypy --strict flint → 275 files, no issues
```

**① acceptance 映射**

| acceptance | 测试 |
|---|---|
| ① pin/unpin + GC 跳过 pinned；豁免面扩为「RedactionRecord + pinned」 | `test_pinning_is_idempotent_and_reversible`、`test_a_pinned_snapshot_survives_the_gc`、`test_a_redacted_snapshot_goes_early_even_inside_the_window`、`test_a_redaction_beats_a_pin`、`test_the_two_exemptions_point_in_opposite_directions` |
| ② 收藏存 snapshot_id 引用；NEVER 回填 | `test_a_favorite_can_reference_a_snapshot_id`、`test_referencing_never_backfills_the_original_value`（源码面扫 UPDATE/backfill/回填/赋值）、`test_the_embedded_freeze_path_is_untouched` |
| ③ 180 天后 pinned 仍在（构造时间） | `test_a_pinned_snapshot_survives_the_gc`、`test_the_boundary_day_is_inclusive_of_retention`、`test_the_retention_window_is_the_store_s_own_number` |

**② 无冻结件偏离**：`contracts/`、`flint/domain/` 只读消费；零新增依赖；
**未改任何既有文件**（`flint/fav/store.py` 的采纳位注释原样保留——它现在是这条路的说明书）。

**③ 禁用词**：两个产物文件六词 0 命中、收尾「等」0 命中。

**④ 复用**：`RETENTION_DAYS` 直接 import `flint/store/snapshot.py` 的那个（§6 的教训）；
「返回副本」口径复用 `SnapshotHistoryStore` / FAV-01；内存实现在前、SQL 随 E2 接入
也是这两处的既有房规。

**⑤ 装载预算**：约 8k tokens。

## 7.5 顺手修的既有文件：GAUGE-05 把「引用」当成了「自述」

全局门跑出 1 failed：`test_outputs_declared.py::test_the_repo_has_no_new_difference`
——本卡新建的 `flint/fav/pin.py` 被报成「少声明」。

**又是一条假红，而且是我自己在 GAUGE-05 埋的**：那把尺子的 C 类判据是
「docstring 自述某张 v0.4 卡号，却不在任何卡的 outputs 里」，实现上扫的是**整段** docstring。
而 `pin.py` 的首行写的是 `DEF-01`（v0.4.1 卡，不在那 104 张里），
正文里引了 `FAV-01` / `FAV-02` **讲理由**（为什么内嵌那条不能换、历史为什么保留每个旧值）。

**「引用某张卡」与「是某张卡的产物」是两件事。** 混起来的后果很具体：
它会逼着后人把「为什么这么写」从注释里删掉，好让尺子闭嘴——
而那正是本批一路在守的东西（第七次同型：判据不该与留痕互相取消）。

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `tools/check_outputs_declared.py` | 扫整段 docstring 找卡号 | **只扫首行**（房规是 `"""CARD-ID：标题`） | 不改则每个引用旧卡讲理由的新模块都会被误报，而修法只有「删注释」或「加白名单」两条烂路 |

**没有走白名单**：白名单是 v0.4 历史差异的冻结闭集，把一个 v0.4.1 新文件塞进去，
正是 GAUGE-05 自己警告过的「谁都能钻的口子」。

**改完之后规则没被削弱**，有现成的证据：GAUGE-05 那条反向断言
（`test_every_whitelisted_row_is_still_a_real_finding`：白名单里每一条今天仍必须是真发现）
**照常通过**——8 条历史发现全部仍由首行判据检出。

## 8. 登记未做

1. **没接进 `PgSnapshotStore.cleanup_expired`**：本卡交的是**策略 + 内存实现**，
   接线要改 `flint/store/snapshot.py`（超出 outputs）。
   `test_pin_is_not_wired_into_the_pg_store_yet` 把这条现状钉住——
   **NEVER 让「策略写好了」被读成「周删已经会跳过 pinned 了」**；哪天接上了这条会红，
   提醒那时的人来更新登记。
2. **pin 没有持久化**：内存实现，进程重启即失效。与 §8-1 是同一件事的两半
   （E2 建表 + 周删读表）。
3. **收藏侧没有真的改成引用**：`snapshot_reference()` 只提供引用记录的形状；
   把 `Favorite.evidence_snapshot` 从内嵌改成引用要动 schema 与 FAV-01 的写路径，
   属 owner 面（而且 §3 说了内嵌那条本来就该留着）。
4. **谁来钉、什么时候钉**未定：收藏时自动钉？还是用户显式钉？属产品口径，卡上未要求。
