# DOC-02 · 迁移 + 抓取管线写正文

**卡** `docs/steward/tasks-v041-b2.json#DOC-02` · **cycles 2** ·
**self_review = true** → §6 · **owner_review = false**（但 §7 有一条要 owner 知道）
**依赖** DOC-01（verified）

## 1. 装载清单

卡面 DOC-02 · `flint/evidence/docstore.py` 全文 · `migrations/versions/0006_evidence_layer.py`
的 `docs` / `citations` 建表段 · `migrations/versions/0018_*.py`（迁移体例）·
`contracts_v04/models_v04.py#Doc` 的 DOC-01 增量段 · `tests/conftest.py` 全文（测试库闸）·
`flint/sources/throttle.py#check_metadata_only` 与两处白名单 ·
`tests/m1/test_m1_016.py` / `tests/m2/test_featb_b1_docstore.py` 的合规判据。
约 14k tokens，预算 40k 以内。

## 2. 顺序（§4.2）

判据先落盘先跑红（`ImportError: cannot import name 'build_doc_with_content'`）→
写迁移 0019 → 写 `prepare_content` / `build_doc_with_content` /
`save_doc_with_content` / `load_doc_with_content` → 离线十条绿 → 迁测试库 →
真库十条绿 → 撞上两条旧合规判据（§4）→ **23 passed**。

## 3. 正文为什么单独一张表

acceptance④ 要的是「同一篇文章多源抓到**只存一份**，引用关系保留」。

只留 `docs.content` 一列做不到：第二个源那行只能填 `NULL`，而 DOC-01 把
`content IS NULL` 的语义**写死**成「还没提取」。两件事挤进同一个值，
重跑提取时就不知道该跳过谁。

所以：

```
doc_contents(content_sha256 PK, content, content_truncated, byte_length)   ← 一份正文一行
docs(..., content_sha256, content_truncated, source_file_ref)              ← N 个来源 N 行
```

**`docs` 表本身仍然没有正文列**——§3.5 那句「Doc 无 content 字段」逐字还成立
（判据 `test_the_docs_table_itself_still_has_no_fulltext_column` 钉着）。
每行 doc 各自的 `doc_id` / `source_id` / `url` 原样保留，那就是「引用关系保留」。

`docs.content_truncated` 与 `doc_contents.content_truncated` **有意冗余**：
读一行 doc 不必 join 就知道自己拿到的是不是全文。

**没给 `docs.content_sha256` 加外键**：抓取管线可能先落元数据、后补正文
（DOC-03 的重跑路径），加外键那一步会因正文还没写而失败——而「先有 doc、后有正文」
是正常的采集顺序。一致性由 `save_doc_with_content` 的单事务保证。

## 4. 撞上两条旧合规判据——用**白名单**解，不反转任何判据

`pytest -q` 红了两条：

```
tests/m1/test_m1_016.py::test_live_schema_has_no_fulltext_columns
tests/m2/test_featb_b1_docstore.py::test_compliance_no_fulltext_column_introduced
```

它们钉的是 §3.5 的老口径「外站全文一律不落库」，而**那条口径已被 owner 2026-08-04
的方案 A 裁决覆盖**（DOC-01 卡面原话）。

**没有反转任何一条判据**：`check_metadata_only` 本来就带一个
`SYSTEM_GENERATED_ALLOWLIST`（`blocks.content` 早就在里面，带着「系统自产内容」的理由）。
本卡按同一机制加一条 `("doc_contents", "content")`，并把**放行出处**写进注释
（谁、哪天、哪个方案、覆盖了哪条口径）。

- **改前**：白名单一项。
- **改后**：两项，第二项带裁决出处与射程说明。
- **为什么非改不可**：不加的话，本卡的正文表会被这把尺子判成违规——
  而它是被裁决放行的，不是漏网的。
- **强度对比**：尺子**一个字没改**。别的表再长出 `content` / `full_text` / `raw_html`
  照旧判红（判据 `test_the_ruler_still_reds_on_any_other_table` 把压力直接打在判定函数上，
  而不是只数白名单里有几项）。**放行一处与拆掉尺子是两件事。**
- **越界登记**：`flint/sources/throttle.py` 不在本卡 outputs 里。改动面 1 项 + 一段注释，
  语义只窄不宽。**这一条列进 §7 请 owner 过目**——它碰的是合规面。

另加一条绊线：`test_the_compliance_allowlist_names_exactly_two_places` 判**等值**，
再多一处就该有人来确认「那也是被裁决放行的」。

## 5. 改既有文件：三处

### 5.1 `flint/evidence/docstore.py`

- **改前**：只有元信息 API（`save_doc` / `load_doc` / citation 三个），
  模块 docstring 第一句是「门 1=C：Doc 只落元信息，**无 content 字段、NEVER 全文**」。
- **改后**：**追加** `PreparedContent` / `prepare_content` / `build_doc_with_content` /
  `save_doc_with_content` / `load_doc_with_content`；docstring 改写为两条 API 并存，
  并写明老口径被哪条裁决覆盖（**不是执行侧自己松的**）。
  既有四个方法**一行没动**，判据 `test_the_old_metadata_only_api_still_works` 钉着。
- **为什么非改不可**：卡上 outputs 第二项就是它。

### 5.2 `migrations/versions/0019_doc_content.py`（新增）

见 §3。回滚**真回滚**：三列 + 一表 + 一索引全清，`docs` 既有行一行不动。

### 5.3 `flint/sources/throttle.py`

见 §4。

**未改**：`contracts/` · `contracts_v04/`（DOC-01 已定，本卡只读）· `flint/domain/` ·
`requirements.lock` · `assets/heldout_questions.yaml`。零新增依赖。

## 6. 变异考：十七个，两轮

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 哈希改成算截断后那份 | DOC-01 的字段语义 | **2 failed** ✓ |
| ② 截断按字符数而不是字节 | 上限口径 | **1 failed** ✓ |
| ③ 恰好等于上限也标成截断 | 边界 | **1 failed** ✓ |
| ④ 截断时不标记 | acceptance③ | **3 failed** ✓ |
| ⑤ 切在字符中间（不按 UTF-8 边界回退） | 坏 UTF-8 | **2 failed** ✓ |
| ⑥ 空正文当成「还没提取」 | 两态可分 | **32 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑦ 分两次写（不在一个事务里） | acceptance② | **1 failed** ✓ |
| ⑧ 去重关掉：正文按 doc_id 存 | acceptance④ | **4 failed** ✓ |
| ⑨ 读回时正文缺失用空串顶上 | 两态可分 | **1 failed** ✓ |
| ⑩ `build_doc_with_content` 忘了填截断标记 | 三件套同生 | **1 failed** ✓ |
| ⑪ build 时顺手改了别的字段 | 只填正文 | **2 failed** ✓ |
| ⑫ 迁移把正文列加到 `docs` 上 | §3 的分表 | **3 failed** ✓ |
| ⑬ downgrade 什么都不做 | acceptance① | **3 failed** ✓ |
| ⑭ downgrade 少清一列 | acceptance① | **4 failed** ✓ |
| ⑮ 白名单被放宽到整张 `docs` 表 | §4 的射程 | **2 failed** ✓ |
| ⑯ 白名单不写放行出处 | 可追溯 | **4 failed** ✓ |
| ⑰ 把合规尺子改成恒返回空 | §4 的强度 | **2 failed** ✓ |

**⑥ 为什么能活**：写入路径原本判 `if doc.content is not None`，变异改成 `if doc.content:`
——空正文被静默跳过，读回来成了 `None`，于是重跑提取时它被当成没提过，
**永远重跑下去**。判据当时只覆盖了「有正文」与「没写过正文」两种，
漏了「提取过、结果是空」这一种。补了一条真库往返判据。

**⑧ 第一版变异是个假变异**：原本把 `DO NOTHING` 改成 `DO UPDATE SET content=...`
——主键还是哈希，最终仍是一行，**行为可见面一个字没变**。那不是判据的洞，
是变异体本身没打到东西。换成「正文按 `doc_id` 存」才真的把去重打掉（4 failed）。
如实记下来：**一个杀不掉的变异，要先问它是不是真的在变异。**

### 6.1 变异考本身踩的坑：改迁移文件会在盘上留 DDL

⑫⑬⑭ 三个变异改的是**迁移文件**，而 `test_downgrade_then_upgrade_keeps_the_existing_rows`
会**真跑 alembic**。它们的 downgrade 被我故意改坏，于是跑完之后测试库停在半路：
`alembic_version` 说 0018，而 `doc_contents` 还在、`docs` 上还多出一列 `content`。
整轮跑完 baseline 当场变红——**红得对**，那是盘上真的脏了。

修法（记在这里，下一个改迁移的人会再撞一次）：手工 `DROP` 掉残留的列与表、
把 `alembic_version` 压回 `0018`、再 `alembic upgrade head`。
动的是 `flint_test`（测试库，每轮本来就会被清），**NEVER 碰 demo 库**。

## 7. 要 owner 知道的一条

**本卡碰了合规面**（§4）：`flint/sources/throttle.py` 的白名单加了
`("doc_contents", "content")`。依据是 owner 2026-08-04 的方案 A 裁决，
但那条裁决说的是「证据正文进库」，**没有逐字说「§3.5 的 metadata-only 尺子该怎么改」**——
是我按「裁决覆盖旧口径 + 用既有白名单机制放行一处」推出来的。

三件事请 owner 确认：

1. **这个推法认不认**（用白名单放行一处，而不是改判据语义）；
2. **`docs` 表仍无正文列**这条口径要不要写进 DECISIONS——它是本卡分表设计的直接后果，
   也是让 §3.5 原文继续成立的原因；
3. **上线前合规手续不受影响**：正文进库改变的是**存什么**，改不了**准不准抓**，
   后者仍由 `docs/上线前合规手续清单.md`（COMP-01）管。这一条我写进了白名单注释。

## 8. verify 与全局门

```
verify_cmd: pytest tests/v041/test_doc_content_store.py -q → 23 passed
            （基线：ImportError，收集期就红）
连坐面:     + tests/m1/test_m1_016.py + tests/m2/test_featb_b1_docstore.py → 33 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: no issues found in 288 source files
            pytest -q               → 3091 passed（DOC-01 收卡时 3067，本卡 +24）
迁移真跑:   alembic upgrade head（flint_test）→ 0018 → 0019
            判据内 downgrade 0018 → 数据行仍在、doc_contents 已消失 → upgrade 0019 复原
```

## 9. self_review

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 迁移加三列；正向与回滚都测过（回滚后既有数据不损） | `test_the_migration_file_is_on_disk_with_the_right_chain`、`test_the_migration_has_a_real_downgrade`、`test_the_columns_and_the_content_table_are_really_there`、`test_downgrade_then_upgrade_keeps_the_existing_rows` |
| ② 提取正文 → 算哈希 → 一次事务写入 | `test_metadata_and_body_are_written_in_one_transaction`、`test_saving_and_loading_a_doc_round_trips_the_body`、`test_building_a_doc_fills_all_three_fields_together`、`test_building_a_doc_keeps_every_other_field_untouched` |
| ③ 超 2 MB 截断并置标记，NEVER 让下游以为拿到全文 | `test_the_hash_is_of_the_original_not_of_the_truncated_copy`、`test_truncation_cuts_at_the_byte_cap_not_the_character_count`、`test_truncation_never_splits_a_character_in_half`、`test_exactly_at_the_cap_is_not_truncated`、`test_a_truncated_body_keeps_its_mark_through_the_round_trip` |
| ④ 同哈希去重，引用关系保留 | `test_two_sources_of_the_same_article_store_the_body_once`、`test_different_bodies_are_stored_separately`、`test_resaving_the_same_doc_is_safe`、`test_a_doc_without_content_loads_as_never_extracted`、`test_an_empty_body_round_trips_as_empty_not_as_never_extracted` |
| （§4 附带）合规尺子不被拆 | `test_the_docs_table_itself_still_has_no_fulltext_column`、`test_the_compliance_allowlist_names_exactly_two_places`、`test_the_ruler_still_reds_on_any_other_table` |

**② 无冻结件偏离**：`contracts/` · `contracts_v04/` · `flint/domain/` 未触碰
（v04 契约按仓里既有形态**惰性 import**，同 `flint/region/registry.py`）；
`requirements.lock` 未动；零新增依赖。

**③ 禁用词**：六词 + 列表尾「等」在四个产物文件里 0 命中。

**④ 复用**：`PgDocStore` 就地扩展（NEVER 另起一个 store）；上限直接读
`contracts_v04.models_v04.DOC_CONTENT_MAX_BYTES`（NEVER 在这里再写一个 2MB）；
合规放行走既有白名单机制（NEVER 另写一个例外通道）；
`_to_doc` 复用既有行→对象转换。

**⑤ 装载预算**：约 14k tokens，未超 40k。

## 10. 登记未做

1. **抓取管线还没接上**。本卡给的是 `prepare_content` / `build_doc_with_content` /
   `save_doc_with_content` 这条**入口**；真正在 `flint/sources/*` 里调用它、
   从 HTML 抽正文的那一步，属 **DOC-03**（卡上写的是「证据卡吃正文」，
   而抽取器落在 `flint/evidence/enrich.py`）。所以现在库里一条真正文都没有。
2. **demo 库（`flint`）没迁**。只迁了 `flint_test`。demo 库归 owner 的演示栈，
   迁它属数据面动作——等 DOC-03 真要写正文时一并处理，或由 owner 点头。
   现在不迁不影响 demo：新方法没有任何调用点，老方法一行没改。
3. **`source_file_ref` 只留位没落地**。PDF 原件的存放（对象存储还是相对路径）
   没有实现，字段先留着（DOC-01 §7 第 1 条已请 owner 确认形态）。
4. **`byte_length` 只写不读**。`doc_contents.byte_length` 现在没有任何查询用到它，
   留着是为了「不 join 正文就能知道这篇多大」——真用到它的是 DOC-03 的抽取预算。
5. **没有跨库去重的迁移**：已有的历史 doc 行没有正文，也就没有回填。
   回填要跑一遍抓取，属 DOC-03 之后的事。
