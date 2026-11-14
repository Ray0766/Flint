# NET-02 · 抓来的每条数据带出处（URL + 时间戳 + 内容哈希）

**卡** `tasks-v041-b2.json#NET-02` · **开工** 机器 UTC 2026-08-04T04:29Z

## 1. 装载清单

卡面 NET-02 · `flint/testing/replay.py` 全文（`RecordedExchange` 五字段、
`fixture_path` 的 E12 布局、`RecordingTransport`）· `flint/sources/registry.py`
的注册面 · `CLAUDE.md#S2` 三条铁律的第二条 · `flint/fav/pin.py` 与
`flint/design/checkpoints.py`（「返回副本」「只增不改」的既有口径）。约 6k tokens。

## 2. 顺序（§4.2）

测试先落盘先跑红（`ModuleNotFoundError: flint.sources.provenance`）→ 实现 →
23 passed。连续第三十二张。

## 3. 采集侧此前没有「出处」这个落点

三条铁律的第二条是「数字必有出处」。那条律**只管生成侧**（Fact / PriceCell /
ProfileRef 三通道）。采集侧没有对应字段——一段抓回来的正文进了库之后，
「它是什么时候、从哪个 URL 抓的、抓到的是不是这一份」**没有任何东西能回答**。

三样缺一即拒，各自挡的是一种具体的坏状态：

| 字段 | 少了它会怎样 |
|---|---|
| 源 URL | 引用它的报告没法回到原处（读者只能选择相信） |
| 抓取 UTC 时间戳 | 源站改版之后，说不清「我们抓的是改版前还是改版后」 |
| 内容 sha256 | 回放时无从确认「这就是当初抓到的那份」——fixture 被改过也看不出来 |

## 4. 三条实现纪律

**① 时间戳必须带时区，且存成 UTC。**
不带时区的在跨时区回放时对不上，而对不上的那一刻**没有任何报错**——
它只是悄悄指向了另一个时刻。带别的时区也收（`astimezone(UTC)` 归一），
因为两种时区的时间戳混在一起没法排序。

**② 哈希由本模块自己算，NEVER 由调用方给。**
`make_provenance` 收的是 `content` 不是 `content_sha256`——调用方给的话，
「哈希与内容对不上」这种状态就存在了，而那正是这个字段要排除的东西。
`test_the_hash_is_computed_here_never_taken_from_the_caller` 直接查签名。

**③ 变了就留两版，NEVER 覆盖。**
同哈希 → 去重（不留第二版，否则每天一版全是同一份东西）；不同哈希 → 两版都留 +
记变化时间。**改回旧内容也算一次变化**——「它变过」与「它现在长什么样」是两件事。

## 5. fixtures 侧走旁挂清单，不改录制件

acceptance③ 要「录进 fixtures 的回放件同样带这三样」。两条路：

| 做法 | 代价 |
|---|---|
| 给 `RecordedExchange` 加三个字段 | **所有既有 fixture 一次性作废**（字段对不上），而它们是别的卡的验收依据 |
| **旁挂清单**（本卡选的） | 多一个文件；但录制件形状一个字不动 |

清单是 `{fixture}.provenance.json`，**同目录同名**——分开放的话，搬一个会忘一个。
`test_the_existing_replay_module_is_untouched` 守着 `flint/testing/replay.py` 没被碰过。

`verify_fixture` 回答的正是那句话：**这就是当初抓到的那份吗**。
它报三类问题：哈希对不上（fixture 被改过）、录了却没记出处、**清单文件不在**——
最后这条尤其重要：「没有清单」与「清单说都对」在返回值上必须分得开，
否则少一个文件就等于全部通过。

## 6. 变异考：十个全红

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 空 url 也收 | acceptance① | **2 failed** ✓ |
| ② 无时区也收 | §4-① | **1 failed** ✓ |
| ③ 不转 UTC | §4-① | **1 failed** ✓ |
| ④ 内容变了直接覆盖 | acceptance② | **2 failed** ✓ |
| ⑤ 相同内容也留一版 | 去重 | **2 failed** ✓ |
| ⑥ 不记变化时间 | 「源站改版可查」 | **2 failed** ✓ |
| ⑦ `versions` 返回内部列表 | 返回副本 | **1 failed** ✓ |
| ⑧ 清单缺失当成没问题 | §5 | **1 failed** ✓ |
| ⑨ 哈希对不上不报 | acceptance③ 正题 | **1 failed** ✓ |
| ⑩ 录了没记出处不报 | §5 | **1 failed** ✓ |

十次变异后 `flint/sources/provenance.py` 的 sha256 与变异前逐位相同。

## 7. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_source_provenance.py -q → 23 passed
ruff check . --no-cache → All checks passed!
mypy --strict flint → 282 files, no issues
```

**① acceptance 映射**

| acceptance | 测试 |
|---|---|
| ① 三样缺一即拒绝入库 | `test_a_complete_record_is_accepted`、`test_an_empty_url_is_refused`、`test_a_naive_timestamp_is_refused`、`test_a_non_utc_timestamp_is_normalised_to_utc`、`test_the_hash_is_computed_here_never_taken_from_the_caller`、`test_bytes_and_text_hash_the_same_way`、`test_the_provenance_is_frozen`、`test_an_incomplete_record_never_enters_the_log` |
| ② 按哈希去重；变化时保留两版并标出变化时间 | `test_the_first_fetch_is_new`、`test_the_same_content_again_is_deduped`、`test_changed_content_keeps_both_versions`、`test_the_change_time_is_recorded`、`test_going_back_to_an_old_content_is_still_a_change`、`test_two_urls_never_share_a_history`、`test_versions_returns_a_copy` |
| ③ fixtures 同样带三样，回放可验证 | `test_a_manifest_round_trips`、`test_the_manifest_stores_the_timestamp_as_iso_utc`、`test_verify_fixture_passes_when_the_body_still_matches`、`test_verify_fixture_catches_a_tampered_body`、`test_verify_fixture_catches_a_missing_manifest_entry`、`test_a_missing_manifest_file_is_a_problem_not_a_pass`、`test_the_manifest_path_sits_next_to_the_fixture` |

**② 无冻结件偏离**：`contracts/`、`flint/domain/` 未触碰；零新增依赖
（`hashlib` / `json` 标准库）；**未改任何既有文件**（§5 的旁挂清单就是为此选的）。

**③ 禁用词**：两个产物文件六词 0 命中、本 trace 收尾「等」0 命中。

**④ 复用**：「返回副本」与 `SnapshotPins` / FAV-01 同款；「只增不改」与
`flint/design/checkpoints.py#HistoryImmutable` 同一条纪律；
fixture 布局沿用 `flint/testing/replay.py#fixture_path` 的 E12 约定。

**⑤ 装载预算**：约 6k tokens。

## 8. 登记未做

1. **没有接进任何抓取路径**：`flint/sources/` 的四个源模块还没有调 `ProvenanceLog`。
   接线要改那四个既有文件（超出本卡 outputs），且一接就会改变落库内容——
   属另一张卡。本卡交的是**机制 + 判据**。
2. **既有 fixtures 没有补清单**：仓里现有的 fixture 都没有旁挂清单，
   `verify_fixture` 对它们会报「清单不在」。**这是对的**——它们确实无从确认。
   补清单要重抓（真实源，红线）或按当前内容倒推（那等于自证，没有意义）。
3. **`ProvenanceLog` 是内存实现**：SQL 实现随 E2 接入（同 `SnapshotHistoryStore` 房规）。
4. **不查响应头**：只记 URL / 时间 / 正文哈希。`ETag` / `Last-Modified` 这类源站
   自己的版本信号没有采集——那能让「变没变」判得更省事，属后续增强。
