# SCHEMA-13 trace — 事件与作业增量 @2026-08-02

## 1 装载
SCHEMA-13 卡 + `WORKORDER#9-P3` + `models_v04.py` 的事件增量区 + `protocols_v04.py`
的 JobEventStream docstring（SCHEMA-00 已增补）。~1,600 字符 ≈ 1.6k tokens（4%）。

## 2 test-first（真红 3 条）
先写测试 → **3 failed**：预落的 `DesignCheck` 是 `passed: bool`（两态），
且 `DesignDelta` 处没有 P3 采纳位注释。按卡校正后 **8 passed**，additive exit 0，全套 88 passed。

## 3 design_check 为什么必须三态
`passed: bool` 只有过与不过——**「没跑过自检」被迫伪装成其中一个**：
报 False 是冤枉（没跑不等于不合格），报 True 是撒谎。
第三态 `unreported` 让「这次没自检」能如实说出来，前端才可能显示「未自检」而不是绿勾或红叉。
测试同时反向断言 **`passed` 字段已不存在**——它正是逼「没自检」撒谎的那个字段。

## 4 P3：delta 入 replay 是基线，ephemeral 只留注释
设计台流式增量若不入 replay，断线重连后用户看到的是**残缺的一半**——
SSE 的 `Last-Event-ID` 补发机制拿不到没存的东西。所以基线是入 replay（`seq` 是补发定位依据）。
`§9-P3` 的 ephemeral（不落库、只走内存）是**提案**，采纳位只留 `#` 注释，
`test_p3_ephemeral_is_comment_only` 两侧都断：注释在、字段不在。

## 5 acceptance 映射
| acceptance | 测试 |
|---|---|
| 事件名全集唯一 | `test_event_names_are_unique_across_the_whole_union`：遍历 11 个成员取各自 `kind` 单值 Literal，断言无重复（撞名 = 解析出错的对象却看不出错） |
| payload 判别可解析 | `test_payload_discriminator_resolves_to_exactly_one_member`：按 kind 唯一定位到成员类 |
| 3 JobKind | `test_three_new_job_kinds_added_without_losing_old_ones`：新三值在 + **既有七值一个不丢** + 总数 10 |
| design_check 三态含 unreported | `test_design_check_has_three_states_including_unreported` + `..._unreported_is_constructible` |
| P3 delta 入 replay | `test_delta_enters_replay_by_baseline` |
| P3 ephemeral 注释位 | `test_p3_ephemeral_is_comment_only` |
| （§6-H4 不另开流） | `test_new_job_kinds_reuse_the_existing_stream`：断言**不存在**第二条事件流的联合类型 |

## 6 产出
`tests/v04/schema/test_i13_events.py`（8 条）+ `DesignCheckState` 三态 + `DesignDelta` 的 P3 注释位。
