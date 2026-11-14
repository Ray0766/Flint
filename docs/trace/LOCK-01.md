# LOCK-01 · trace

**卡**：并发——`projects` 全行 upsert 没有乐观锁，`change_log` 会被静默覆盖
**verify_cmd**：`pytest tests/v041/test_project_optimistic_lock.py -q` → **17 passed**
**cycles**：1（卡面估 2）
**owner_review**：true —— 按 `DEC-000` 事后补审

---

## 装载清单（实际）

| 来源 | 用途 |
|---|---|
| `docs/steward/连跑工单-v041-第7批.md#3` | 缺陷的由来（steward 复核 `ENTRY-02` 越界时查出） |
| `flint/topic/store.py#PgProjectStore` 全文 | 改点 |
| `flint/ledger/store.py`（`_current` / `_conflict` / `derive`） | **既有乐观锁口径**，本卡照它的形状 |
| `contracts/models.py#LedgerVersionConflict` | 异常携带什么、为什么 |
| `migrations/versions/0021_cluster_region.py` 全文 | 迁移的既有形态与接号 |
| `flint/api/topics.py` 的 `chosen-topic` 段 | 唯一一条更新路径 |
| `flint/api/schemas.py#ErrorCode` | 加码的先例（`EMPTY_HYPOTHESIS` / AUTH-03 两码） |
| `tests/v041/test_cluster_region.py` 迁移那一节 | 迁移判据的既有写法 |

估算约 22k tokens，未超 40k 预算。

---

## 断点与决策日志

### 一、版本记号放哪里：**不能放进 `Project`**

`Project` 是冻结件（`contracts/models.py:971`），加字段由 `S2-1` 禁止。
而且从设计上也不该放：**版本是存储层的并发记号，不是 project 的业务属性**——
放进去，它会出现在每一个域函数的签名里（`choose_topic` 首当其冲）。

落法：`load_with_version(project_id) -> tuple[Project, int]`，
`save(project, *, expected_version: int | None = None)`。
两个都是**加法**，`load` / `save` 的既有签名一字未改（旧调用方照常编译）。

### 二、`expected_version=None` 的语义：**「我在新建」**，撞车就抛

这是本卡唯一一处需要定语义的地方。三种选法：

| 选法 | 后果 |
|---|---|
| `None` → 不带锁的 upsert（维持现状） | **缺陷原样留着**。唯一一条更新路径正是不带版本的那个调用 |
| `None` → 纯 INSERT，撞主键 500 | 退回 `ENTRY-02` 之前那个「大声但错」的行为 |
| **`None` → INSERT，撞车抛冲突** | 选这个 |

理由：**不带版本的写，语义只能是「我在新建」**。那一行已经在库里时，
调用方的前提就是错的——静默覆盖会把它现有的 `change_log` 整段抹掉。
`test_creating_something_that_already_exists_is_loud` 钉住这一条
（并断言已有的 `change_log` 没被抹）。

代价是 `flint/api/topics.py` **必须**改成带版本写（见下），不改的话每次选主题都 409。

### 三、条件更新落在 SQL 的 `WHERE` 里，不是「先读一次再判断」

先读后判有竞态窗口：两个写者都读到 `version=1`、都判「相符」、然后都写。
`WHERE project_id = $1 AND version = $9` 把互斥交给行锁——**那个窗口不存在**。

`test_the_lock_is_a_conditional_update_not_a_read_then_write` 判 SQL 字面量
（**剥注释**：改因注释里逐字写着这段话本身）。

### 四、与账本那一套：**语义同源，手段按数据形状选**

`facts_ledgers` 的锁靠 `(project_id, version)` 唯一索引 + 先读后比——
因为那边**每个版本是一行新记录**，需要唯一索引兜住竞态。
`projects` 的版本是**同一行上的一列**，条件更新已经由行锁保证互斥，
不需要唯一索引。

**语义完全一致**（版本不符 → 抛一个携带当前状态的冲突，败者看得见胜者写了什么），
所以这不是两套锁。`test_the_conflict_mirrors_the_ledger_conflict_shape` 判形状同构；
`test_the_store_did_not_invent_a_second_locking_scheme` 反向守住
（NEVER 出现 `pg_advisory` / `FOR UPDATE` / 重试循环）。

### 五、错误码：**NEVER 借 `LEDGER_CONFLICT`**

`LEDGER_CONFLICT` 说的是「这个项目的**事实账本**变了」，
它的重试策略按来源分派（`inject_evidence` 自动重放 / `dispute` 提示用户 /
`revalidation` 整个 job 重跑，冻结件 docstring 写着）。
本卡这个说的是「这个 **project 行**被别人改了」，重试就是重读一次再选。

借一个已经有主的码去说另一件事——`DEC-034` / `DEC-038` 反复禁的同一条。
所以新加 `PROJECT_CONFLICT`（先例：`EMPTY_HYPOTHESIS`、AUTH-03 那两个 401 码）。

### 六、迁移那一列**非空 + 有默认值**，与 0021 刻意相反

`region` 可空，因为「还不知道这个簇属于哪个区」是一种真实状态。
版本不是这样：**一行记录永远有一个版本**，`NULL` 在这里没有含义——
它只会让 `WHERE version = $n` 静静地匹配不到任何行，
而那个症状读起来是「冲突」，真相是「这一行从来没有版本」。

`server_default="1"` 是必需的：库里已经有 project 行，不给起点迁移会当场违约。
**默认值只在建行时生效**，之后由条件更新推进——NEVER 让数据库自己去加（触发器之类）：
那样版本会在没人预期的时候前进，而调用方拿着刚读到的版本去写就会莫名冲突。

---

## 迁移双向实跑（工单纪律 3）

```
$ DATABASE_URL=postgresql+asyncpg://…/flint_test python -m alembic upgrade head
  Running upgrade 0021 -> 0022, 迁移 0022：`projects` 加 `version` 列（LOCK-01，乐观锁）

$ python -m alembic downgrade -1
  Running downgrade 0022 -> 0021, …
  → information_schema 里 projects.version 计数 = 0     ← 真撤掉了

$ python -m alembic upgrade head        # 再上来
  Running upgrade 0021 -> 0022, …
```

demo 库也跟上了（`DATABASE_URL=…/flint`）：两条既有 project 的 `version` 都是 **1**。

**一处环境坑记下来**：`alembic` 必须带 `postgresql+asyncpg://` 前缀。
写成 `postgresql://` 时它去找 `psycopg2`（本仓没装，也 NEVER 新增依赖），
报的是 `ModuleNotFoundError: No module named 'psycopg2'`——
**那句话读起来像缺依赖，真相是 URL 少了驱动段**。
`migrations/env.py:16` 的 `DEFAULT_URL` 本来就带着它。

---

## 改既有文件

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `flint/topic/store.py` | `save(project)` 无锁全行 upsert；行→Project 的转换逐字写在 `load` 里 | `save(project, *, expected_version=None)` 两种语义 + `_conflict` + `load_with_version`；转换抽成 `_to_project` | 卡面 outputs。抽 `_to_project` 是因为三条路径（`load` / `load_with_version` / `_conflict`）要同一份转换——**抄三份的话，哪天多一列只有一处会跟上** |
| `flint/api/topics.py` | `store.load` → `store.save(updated)` | `load_with_version` → `save(..., expected_version=version)`，接 `ProjectVersionConflict` → 409 | **不改就坏**：不带版本的 `save` 语义是「我在新建」，而这一行已在库里 → 每次选主题都 409。它是唯一一条更新路径。**outputs 外，供复核** |
| `flint/api/schemas.py` | `ErrorCode` 无 project 冲突码 | 加 `PROJECT_CONFLICT` + 写明为什么不借 `LEDGER_CONFLICT` | acceptance② 要「可被端点转成 409 的冲突」。**outputs 外，供复核** |

`contracts/` 与 `flint/domain/` 未触碰。`ENTRY-02` 定下的两条（`save` 能更新、
`created_at` 不在更新列里）**原样保留**，各有判据。

---

## self_review（卡上 `self_review=true`）

**① 测试真实覆盖 acceptance**

| acceptance | 判据 |
|---|---|
| ① 缺陷描述（九列无版本列，`change_log` 在被覆盖列里） | `test_the_column_really_exists_in_the_database`（打真库）+ 迁移 docstring |
| ② **把响亮的错找回来**：版本列 + 条件更新 + 抛可转 409 的冲突 | `test_the_second_writer_hits_a_conflict` · `test_the_lock_is_a_conditional_update_not_a_read_then_write` · `test_the_endpoint_turns_the_conflict_into_a_409` |
| ③ 口径与 `LedgerStore` 同源，NEVER 另发明 | `test_the_conflict_mirrors_the_ledger_conflict_shape` · `test_the_store_did_not_invent_a_second_locking_scheme` |
| ④ **阴性对照：后写者 409 且先写者的条目还在** | `test_the_first_writers_entry_survives_the_conflict`（**回库读一次**，断言 `change_log == [A 那条]`）· `test_the_conflict_carries_the_winners_state` |
| ⑤ 迁移接 0021、两向跑通 | `test_the_migration_continues_the_numbering` · `test_the_migration_chains_onto_0021` · `test_both_directions_are_implemented` + 上面的实跑记录 |
| ⑥ 单写路径行为不变 | `test_creating_a_project_still_works` · `test_a_single_writer_updates_and_the_version_advances` · `test_created_at_is_still_excluded_from_the_update` |

acceptance④ 那条**是这一组的核心**，理由写进了它的 docstring：
只断言「抛了异常」不够——一个抛了异常但**已经写下去了**的实现在那条判据下是绿的，
而它把这张卡要修的东西（静默丢失）原样留着。

test-first 顺序有据：判据先跑 **16 failed / 1 passed**，实现后 17 passed。

**② 无冻结件偏离**：未触碰 `contracts/` 与 `flint/domain/`。
版本记号刻意**不进** `Project`（理由见断点日志一）。

**③ 无禁用词**：对本卡新增/改动的四个文件扫 `适当/合理/必要时/大约/尽量/若干`
与列表尾的「等」——无命中。

**④ 复用断言在位**：乐观锁语义照 `flint/ledger/store.py` 的既有形状
（先比版本 → 抛携带当前状态的冲突），判据钉住同构；
NEVER 新写一套（判据反向守住五个关键词）。

**⑤ 装载未超预算**：约 22k / 40k。

**其它门**：
`ruff check . --no-cache` → All checks passed；
`mypy --strict flint` → 307 files Success；
`pytest tests/v041/test_topic_choose.py tests/v041/test_empty_hypothesis_one_code.py -q`
→ 23 passed（`ENTRY-02` 与 `FIX-10` 的既有判据未被本卡碰坏）。

---

## 产出文件清单

- `migrations/versions/0022_project_version.py`（新）
- `flint/topic/store.py`（`ProjectVersionConflict` · 两种 `save` 语义 · `_conflict` · `load_with_version` · `_to_project`）
- `flint/api/topics.py`（带版本读写 + 409，**outputs 外，供复核**）
- `flint/api/schemas.py`（`PROJECT_CONFLICT`，**outputs 外，供复核**）
- `tests/v041/test_project_optimistic_lock.py`（新，17 条）
- `docs/trace/LOCK-01.md`（本文件）
