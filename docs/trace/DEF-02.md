# DEF-02 · 候选⑤ design_delta 的 ephemeral 语义（§9-P3，owner 已采纳）

**卡** `tasks-v041-b2.json#DEF-02` · **开工** 机器 UTC 2026-08-04T01:26Z

## 1. 装载清单

卡面 DEF-02 · `WORKORDER-v04.md#9` 的 P3 行 · `contracts_v04/models_v04.py` 的
`DesignDelta` 采纳位与 `JobEvent`（逐字）· `flint/domain/models.py#JobEvent`（对照）·
`flint/design/session.py` 全文 · `tests/v04/design/test_stream_events.py` 的 P3 两条断言 ·
`flint/jobs/events.py` 的 `append/emit/replay` · `flint/design/checkpoints.py` 的
`Checkpoint`。约 9k tokens。

## 2. 顺序（§4.2）

测试先落盘先跑红（`ImportError: EphemeralNotCheckpointed`）→ 实现 → 23 passed。连续第十六张。

## 3. 位加在事件上，不加在载荷上——与采纳位注释的写法不同

`contracts_v04` 的 `DesignDelta` 采纳位原话是「采纳时**此处**加 `ephemeral: bool = False`」，
而卡面写的是「**JobEvent** 增 ephemeral 位」。两处不一致，按卡面走，理由是技术的：

**决定落不落库的是事件记录，不是载荷内容。** 加在载荷上，replay 过滤就得认识
`JobEventPayload` 的 11 个联合成员——每新增一个成员都要回来改一次过滤逻辑，
而过滤逻辑与「这条载荷是什么」本来无关。加在 `JobEvent` 上，过滤是一行且与成员数无关。

采纳位那段注释同步改成了指路（改动记录见 §6），**没有删**：那段写着 P3 是什么、
代价是什么，删了下一个人只会看到一个来历不明的布尔位。

## 4. 代价还在检查点上——本卡的主约束

ephemeral 不落日志，**重连时唯一还能拿到它的地方就是检查点快照**。
所以约束是一句话：**检查点 MUST 盖住每一个 ephemeral 事件**。

盖不住的后果很具体：重连后的文字比不断线时**短一截**，而短的那截没有任何错误信号。
用户看到的是一段莫名其妙断掉的话，排查会从「模型是不是没生成完」开始——方向全错。
所以 `resume_text` 在盖不住时**直接抛并逐个点名 seq**，NEVER 静默返回短文字。

`fold` 折的是**全部** delta 而不是只折 ephemeral 的，理由写在函数里：
只折一半的话 `state.seq` 会停在最后一个 ephemeral 上，而它之前的普通事件已经被折进
文字里了——续流按 `seq > state.seq` 取，那些普通事件会被**再拼一遍**。

**守卫只有拿到全量事件才看得见丢失**：ephemeral 不落日志，事后从日志里查不出它
曾经存在。`test_the_guard_needs_the_full_stream_not_the_persisted_one` 把这条现状钉住
（传日志那份 → 静默放行），并写明调用方 MUST 在生产侧检查。

## 5. 三条「不借着加功能松门」

| 既有的门 | 本卡后 |
|---|---|
| `limit <= 0` 拒绝 | 不变（`test_zero_limit_is_still_rejected`） |
| 截断丢弃条数经 `on_truncate` 报出 | 不变（`test_the_truncation_report_still_fires_unchanged`） |
| `REPLAY_DEFAULT_LIMIT = 200` | 不变——**不落库与不封顶两条一起放松，一个没存检查点的长会话会把内存吃光** |

acceptance③ 的阴性对照是 `test_replay_window_is_byte_identical_for_a_plain_stream`：
全是普通事件时，过一遍 `persisted_events` 与不过**结果相同**。
本卡对既有行为的全部承诺就是这一句：**新功能只在打了标的路径上生效**。

## 6. 改既有文件（§4.1，逐处记账）

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `contracts_v04/models_v04.py#JobEvent` | 四个字段 | 末尾加 `ephemeral: bool = False` + 六行理由注释 | acceptance① 要求的字段本体。带默认值 → additive；加在末尾 → 既有位置参数构造不受影响 |
| `contracts_v04/models_v04.py#DesignDelta` | 采纳位注释写「owner 未采纳 → 本轮 NEVER 实现，采纳时此处加」 | 改为「已采纳，位没有落在这里，落在 `JobEvent` 上」+ 理由 | 采纳之后原话是**错的指路**：照它做会把位加到载荷上，而那正是 §3 说明要避免的 |
| `flint/design/session.py` | 模块 docstring 写「真正的解法是 P3……在那之前本模块 NEVER 实现它」 | 换成 ephemeral 的语义 + 代价怎么还 | 同上：实现完了还挂着「本模块 NEVER 实现它」 |
| `flint/design/session.py#delta_events` | 无 `ephemeral` 形参 | 加 keyword-only `ephemeral: bool = False` | 没有构造入口就没法标；默认 False 保证既有构造点行为一字不变 |
| `tests/v04/design/test_stream_events.py` 模块 docstring | 「那要 owner 采纳，本轮 NEVER 实现」 | 「owner 已于 v0.4.1 采纳（DEF-02），行为面归 tests/v041/」 | 同上 |
| `tests/v04/design/test_stream_events.py::test_p3_option_is_not_implemented_here` | 断「`DesignDelta` 没有该字段」+「session.py 里没有 `ephemeral` 这个名字」 | 更名 `test_p3_option_landed_on_the_event_not_on_the_payload`：断落点（`DesignDelta` 仍无 / `JobEvent` 有且默认 False）+ **`ephemeral` 必须出现在 session.py** | 原断言钉的是「未采纳」这个现状，采纳后它替一个不成立的现状站岗。新断言把方向反过来：名字**不**出现说明契约有字段而实现不认它，那比两边都没有更难查 |

**`StreamState` 改名 `ResumePoint`**（本卡新增件，非既有文件）：首版叫 `StreamState`，
撞上 DESIGN-01 的 `test_session_module_never_opens_a_second_stream`——那条按
「类名含 Stream」判第二条流。**这是一条假红**（`ResumePoint` 是快照里的两个值，不是流），
但**没有去改那把尺子**：名字层面的过严判据只会造假红、不会放过真问题，
而 `ResumePoint`（重连从哪一点接上）本来就是更准的名字。改被测对象比松尺子便宜。

## 7. 变异考：五个全红

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① `persisted_events` 返回全部 | 本卡正题 | **3 failed** ✓ |
| ② 改按 `kind == "design_delta"` 过滤 | 「显式标记，NEVER 按 kind 猜」 | **8 failed** ✓ |
| ③ `fold` 只折 ephemeral 的 | §4 的重复拼接 | **2 failed** ✓ |
| ④ 守卫不守（静默返回短文字） | §4 的主约束 | **1 failed** ✓ |
| ⑤ 续流不接快照文字 | 「快照 + 续流」的快照那半 | **2 failed** ✓ |

变异后源码 sha256 与变异前逐位相同（还原一致 = True）。

## 8. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_delta_ephemeral.py -q → 23 passed
tests/v04/design/ → 157 passed（DESIGN-01 基线未被改坏）
check_frozen_additive: models 通过（新增 17 类、14 字段）/ protocols 通过（0 新增）
ruff check . --no-cache → All checks passed!
mypy --strict flint → 275 files, no issues
全局门 pytest -q → 2171 passed
```

**① acceptance 映射**

| acceptance | 测试 |
|---|---|
| ① 走 additive 通道加位、双通过；标 True 不入 replay 日志 | `test_the_bit_is_on_the_event_not_on_the_payload`、`test_the_frozen_contract_is_untouched`、`test_check_frozen_additive_passes_on_both_files`、`test_an_ephemeral_event_never_enters_the_replay_log`、`test_a_mixed_stream_keeps_only_the_unmarked_ones` |
| ② 重连 = 快照 + 续流，复用既有流程；终态与不断线一致 | `test_the_text_after_a_reconnect_equals_the_uninterrupted_one`、`test_resume_reuses_the_existing_replay_window`、`test_resume_from_an_empty_snapshot_is_the_whole_stream`、`test_dropping_without_folding_would_lose_text` |
| ③ 非 ephemeral 的 replay 行为一字不变（阴性对照） | `test_a_plain_event_is_persisted_unchanged`、`test_the_mark_is_explicit_never_inferred_from_the_kind`、`test_replay_window_is_byte_identical_for_a_plain_stream`、`test_the_truncation_report_still_fires_unchanged`、`test_zero_limit_is_still_rejected`、`test_the_default_limit_is_the_same_number` |

**② 无冻结件偏离**：`contracts/`、`flint/domain/` 一字未动（`test_the_frozen_contract_is_untouched`
把这条写成断言）；零新增依赖；改既有文件六处，逐处记账见 §6。

**③ 禁用词**：产物文件六词 0 命中、本 trace 收尾「等」0 命中。

**④ 复用**：续流直接调既有 `replay_window`（截断上限、丢弃报数、seq 过滤只有一份实现）；
「内存实现在前、SQL 随 E2 接入」与 `CheckpointStore` / `SnapshotPins` 同一房规。

**⑤ 装载预算**：约 9k tokens。

## 8.5 顺手：GAUGE-02 清点表重生成

全局门跑出 1 failed：`test_gauge_map.py::test_disk_copies_are_current`——本卡新增的
尺子文件让落盘清点过期。跑 `python tools/gauge_map.py` 重生成
`assets/gauge_map.json` + `docs/尺子清点-v041.md`。

**在门内 108 / 有尺子但不在门内 61 / 查不到尺子 0**（与上一次相同：本卡的新尺子挂在
v0.4.1 卡号下，不改 v0.4 那 104 张的归属）。

## 9. 登记未做

1. **落库那一侧没接**：`flint/jobs/events.py` 的 `append/emit/replay` 用的是**冻结件**
   `flint/domain/models.py#JobEvent`，那上面没有 `ephemeral`（一字不动）。
   所以本卡交的是**策略 + 构造侧**，真正「少写一条 INSERT」要等 owner 把 additive 副本
   并回冻结件。`test_the_frozen_contract_is_untouched` 会在并回的那天变红，提醒来更新本条。
2. **谁来决定标不标**未定：卡面没写策略（全部 delta 都标？只有超过 N 条之后才标？）。
   本卡把「标记是显式的」钉死，取值交给调用方——`test_the_mark_is_explicit_never_inferred_from_the_kind`
   守着「NEVER 按 kind 替调用方决定」。
3. **检查点没有自动触发**：约束是「检查点 MUST 盖住每一个 ephemeral」，但没有实现
   「推到第 N 条自动存一次检查点」。`unfolded_ephemeral` 提供的是**查**的能力，
   什么时候存属编排面（`flint/design/checkpoints.py` 的调用方）。
4. **SSE 传输层没动**：`Last-Event-ID` 补发仍归 api（M2）。ephemeral 事件在 SSE 上
   照常推给客户端——它只是不落库，不是不推送。
