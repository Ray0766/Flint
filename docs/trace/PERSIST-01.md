# PERSIST-01 · 收藏 · 分享 · 偏好三表建齐，三族接真存储

**结论**：迁移 `0023` 建三张表；三族从 `store=None` / 内存件换成 SQL 实现；
`verify_cmd` 21 条全绿；`ruff` / `mypy --strict flint` 全绿。
真栈实测：三族**跨进程重启还在**。

装载：`docs/steward/tasks-v041-b9.json#PERSIST-01` · `docs/steward/连跑工单-v041-第9批.md#2 #5` ·
`flint/fav/store.py` · `flint/api/{favorites,share,settings,app}.py` ·
`flint/profile/prefs.py` · `flint/profile/store.py`（Pg store 房规）·
`migrations/versions/0022_project_version.py`（迁移体例）· `tests/conftest.py` ·
`tests/v041/test_authz_matrix.py`（compose 夹具体例）
（实测装载 ≈ 33k tokens，预算 40k）

---

## 1 开工前核过的两件事

**① 八张表实查**（不照抄工单）：`asyncpg` 直连 `flint` 库——库里 38 张表，
`favorites` / `share_links` / `prefs` / `templates` / `workbenches` /
`graph_nodes` / `graph_edges` / `cluster_verdicts` **八张一张不差地都不存在**。
本卡负责前三张。

**② `:8000` 的 PID 与启动时间**：`PID=54640 Start=04:54:36`——
**早于本卡的任何改动**，所以它跑的是旧代码。本卡的真栈实测在**重起之后**做
（新 `PID=42632 Start=05:50:56`，第二次重起 `PID=11480 Start=05:51:59`），
逐条记在 §5。

## 2 本卡最硬的一处：**同步 store 接口 × 只有异步驱动**

三族的 store 接口是**同步**的（`get` / `put` / `drop` / `all` / `for_owner`），
而本仓**只有 asyncpg 一个 Postgres 驱动**：

```
psycopg   MISSING
psycopg2  MISSING
asyncpg   0.31.0      ← 只有它
```

而本批 rules 写死 **NEVER 新增依赖**。所以两者之间必须有一座桥。

### 走过的三条路，为什么取第三条

| 方案 | 为什么不 |
|---|---|
| **甲** 把 store 接口改成 `async` | 会一路传染到 `flint/fav/{store,stale,batch}.py` 与 `flint/api/favorites.py`，**然后传染到 `tests/v04/fav/` 下那些已经 verified 的判据**——而 `DEC-021` / `worker.md` §9.2 写死那些 NEVER 再改。**为了让实现顺手去改判据，正是那条纪律要挡住的动作。** |
| **乙** 每请求把库里的行装进内存 store、写回去 | 不阻塞循环，但要重写 `flint/api/favorites.py` 的五个处理函数（归属判定那一段尤其绕），改动面远大于卡上 outputs |
| **丙（取此）** 一条专用事件循环线程 + 同步处理函数 | store 接口一字不动，`flint/fav/*` 的五个域函数一行不动，`tests/v04/fav/` 一个字不动 |

### 丙的两半，缺一不可

**上半**：`flint/db/sync_bridge.py` 起一条守护线程跑长活的事件循环，
同步侧用 `run_coroutine_threadsafe(...).result()` 等它。
（`asyncio.run()` 每次建新循环，而 asyncpg 的连接绑在建它的循环上，那条路走不通。）

**下半**：`.result()` 会**阻塞调用它的那条线程**。所以

- FastAPI 的 `async def` 处理函数跑在**事件循环线程**上 → 在那里阻塞会把
  **所有并发请求一起卡住**，症状只是「服务偶尔很慢」，**没有任何一条错误日志**；
- FastAPI 的 `def`（同步）处理函数跑在**它自己的线程池**里 → 阻塞只影响这一个请求。

所以三族的处理函数从 `async def` 改成 `def`——**函数体一行未动**，
它们本来就没有 `await`（建族时的默认写法是「async 但从不 await」）。

**唯一留在 async 的那条**是 `GET /public/shares/{token}`（它下面要 `await load_content`），
那里的 `store.get` 用 `starlette.concurrency.run_in_threadpool` 包了一层。

**桥自己会喊**：`run_sync` 检测到自己在一条正在运行的事件循环上被调用就当场抛
`BlockingCallOnEventLoop`。**NEVER 让它悄悄地慢下去**——
一个响亮的错误第一次跑判据就会被发现，而一条被停住的事件循环要等到有并发的那天
才现形，那天没人会想到是这里。

## 3 改前 / 改后 / 为什么非改不可

### 3.1 新增（8 个文件）

| 文件 | 是什么 |
|---|---|
| `migrations/versions/0023_favorites_shares_prefs.py` | 三张表 + 两个归属索引 |
| `flint/db/__init__.py` · `flint/db/sync_bridge.py` | §2 那座桥 |
| `flint/fav/pgstore.py` · `flint/share/pgstore.py` · `flint/profile/pgprefs.py` | 三个 SQL 实现 |
| `tests/v041/test_persist_fav_share_prefs.py` | 21 条判据 |
| `docs/blocked/FOUR-REDS-ALREADY-ON-THE-FLOOR-BEFORE-PERSIST-01.md` | §6 那四条 |

### 3.2 既有文件（每处「改前 / 改后 / 为什么非改不可」）

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `flint/api/app.py` | favorites `store=None`；share / prefs 注**内存件** | 三族注 `PgFavoriteStore` / `PgShareLinkStore` / `PgPrefsStore`（`dsn` 直给，连接延到请求期） | 这就是本卡的 acceptance 第 3 条。`not_provided` 那一态**留着**（见 §4） |
| `flint/api/favorites.py` | 5 个 `async def` 处理函数；`store: FavoriteStore \| None` | 5 个 `def`；`store: FavoriteStoreLike \| None` | 前者见 §2 下半；后者见下一行 |
| `flint/api/share.py` | 3 个 `async def`；`store: ShareLinkStore`；无 `run_in_threadpool` | 3 个 `def`；`store: ShareLinkStoreLike`；`public_read` 里包一层线程池 | 同上 |
| `flint/api/settings.py` | 2 个 `async def`；`store: PrefsStore` | 2 个 `def`；`store: PrefsStoreLike` | 同上 |
| `flint/fav/store.py` | 三个域函数形参写死 `FavoriteStore`（内存件本体） | 加 `FavoriteStoreLike` 协议，形参放宽 | `mypy --strict` 当场报 `incompatible type`。**这个文件 35 行自己写着「SQL 实现随 favorites 表接入」**——形参本来就该是**形状**而不是那一个类，是当时没有第二个实现所以没人写下来 |
| `flint/fav/stale.py` · `flint/fav/batch.py` | 形参 `FavoriteStore` | 形参 `FavoriteStoreLike` | 同上，纯类型放宽 |
| `flint/profile/prefs.py` | `get_prefs` / `set_prefs` 形参写死 `PrefsStore` | 加 `PrefsStoreLike` 协议并放宽 | 同上（该文件 39 行同样写着「SQL 实现随表接入」） |
| `tests/v041/test_no_fake_empty.py` | 缝的判据打**装配后的应用**（`/favorites` + `/design/templates`） | `/favorites` 从名单毕业；缝的两条改**直接打缝**（`store=None` 的应用） | 见 §4 |
| `tests/v041/test_project_optimistic_lock.py` | `assert numbers[-1] == 22` | 改成「22 在号段里 + 全段无断档」 | 见 §4 |

**放宽形参是严格兼容的改动**：既有调用点一个都没坏，`tests/v04/fav/` 一个字未动
（内存件仍然满足这个协议）。

## 4 两处动了既有判据——各自为什么不是「为过测而改判据」

`worker.md` §4.4 写死 NEVER 为过测而改测试语义。这两处改的**都不是语义**：

### 4.1 `test_no_fake_empty.py`（WIRE-12 的缝）

**改前**它这样量缝：拿装配后的应用去打 `/favorites`，断言回 `not_provided`。
本卡把 `favorites` 表建出来之后，那三条当场红——
**红的是「今天这一族还没接库」这个事实过去了，不是缝坏了**。

而卡面 acceptance 第 4 条写的正是这件事：
「**`not_provided` 那一态保留但不再触发**」。

**改后**：`FAKE_EMPTY_PATHS` 里 `/favorites` 毕业（`/design/templates` 留着，
它由 `PERSIST-03` 建表，建完也会毕业）；缝的两条改成**直接构造 `store=None` 的应用**去量。

**为什么这个改法更硬**：改前那两条判的其实是「今天哪一族还没接库」，
而缝是**永久的**——装配面会一族一族地接上库，缝不会消失。
挪到缝本身之后，将来八张表全建齐、名单空了，缝仍然有人看着。
本卡的判据里另有一条 `test_the_not_provided_seam_is_still_in_the_code`
从源码那一侧钉同一件事。

### 4.2 `test_project_optimistic_lock.py`（LOCK-01 的迁移号）

**改前** `assert numbers[-1] == 22`。它的 docstring 写着意图是「**NEVER 跳号**」，
而「22 是最后一个」只是当时表达它的一种方便写法。

**改后**判「22 在号段里 + 全段无断档」。**意图一字未动**，
而钉住最大值等于让每一张新迁移卡都回来改 LOCK-01 的判据，
且每改一次都要重新判断「这次红是真的吗」——那正是判据该替人做的事。

## 5 真栈实测（**在重起过的进程上**）

新进程 `PID=42632 Start=05:50:56`（本卡改动之后）：

```
GET  /favorites                → {"items":[]}              ← 改前是 not_provided
POST /favorites  fav-live-1    → 200，回整条
GET  /favorites                → 一条，就是刚写的那条
GET  /favorites  (stranger)    → {"items":[]}              ← 别人的不出现在我的列表里
DELETE /favorites/fav-live-1 (stranger) → 404              ← 越权与不存在同一行
DELETE /favorites/fav-live-1 (主人)      → 204
PUT  /settings/locale {"region":"JP"} → lang 仍是 zh        ← A3 两条轴
POST /shares                   → 回 token
库里三张表逐行看过：favorites 1 行 / prefs 1 行 / share_links 1 行
```

**再重起一次**（`PID=11480 Start=05:51:59`）之后三族**都还在**——
这就是 owner 那句「选择要存得住」的可观测形式，也是内存件在这一条上必红的地方。

探针写的 `region=JP` **已复位成 CN**（`DEC-045`：本版只做中国区，JP 无内容，
留着会让 owner 点进去看到一片空）。留了一条收藏与一条分享链接在 demo 库里，
owner 点进去看得见。

## 6 全量跑出 10 红：6 条是本卡的，4 条不是

```
pytest -q   →  10 failed, 4799 passed, 4 skipped
```

**本卡引起的 6 条，已全部修掉并说明**（3 条 `test_no_fake_empty` · 1 条
`test_project_optimistic_lock` · 1 条 `test_persist_fav_share_prefs` 自己的
源码串判据（协议改名之后串对不上——**判据抓到了我这次的改动**，这正是它该做的）
· 见 §4）。

**另外 4 条不是本卡引起的**，单独开单
`docs/blocked/FOUR-REDS-ALREADY-ON-THE-FLOOR-BEFORE-PERSIST-01.md`：

- `/workbenches` 与 `/workbenches/{}/nodes` **没有前端类型**（三把尺子在报同一件事）
  ——主语是 `flint/api/workbenches.py`，**本卡一次都没打开过**它。
  与 `PERSIST-02` 是同一件事的两半（那张卡的 acceptance 第一条就是它）。
- `app.py` 里 `GraphStore()` 出现两次而判据要求一次——第二次是 `ENTRY-03`
  写的**一句注释**，本卡读到它时就已经在。修法是让那条判据走 AST 数调用点，
  **NEVER 靠删那句注释顶绿**（那是删掉解释来迎合尺子）。

**为什么不顺手修**：本卡 outputs 里没有 `flint/api/workbenches.py` 也没有那三个判据文件，
工单 rules 写死「改动面大于卡上 outputs → 停下走 `docs/blocked/`」；
且顺手修掉之后，台账上会显示这四条是 `PERSIST-01` 的产物，
下一个人复盘时会以为本卡碰过 workbenches。

## 7 自审（`self_review=true`）

**① 判据真实覆盖 acceptance**

| acceptance | 判据 |
|---|---|
| 三张表实测都不存在 → 本卡就是那个接入 | `test_the_three_tables_exist_now`（实查 `pg_tables`，不是查迁移文件） |
| 迁移接 0022 不跳号；upgrade 与 downgrade 都跑通 | `test_the_migration_number_continues_without_a_gap`、`test_the_migration_goes_down_and_up_again`（**走子进程真跑 alembic** 降级再升级） |
| 收藏能存能读能删 | `test_a_favorite_survives_a_new_store_object`、`test_dropping_a_favorite_is_idempotent`、`test_reading_a_favorite_gives_back_a_copy_not_a_handle` |
| 分享能生成能失效 | `test_a_share_link_survives_a_new_store_object`、`test_revoking_keeps_the_row_so_the_holder_gets_410_not_404`、`test_the_password_hash_round_trips_and_the_plaintext_never_lands` |
| 偏好能存能回读 | `test_prefs_round_trip_across_store_objects`、`test_an_unset_user_gets_the_declared_default_not_an_empty_row`、`test_setting_one_axis_leaves_the_other_alone_through_sql` |
| `not_provided` 保留但不再触发 | `test_favorites_no_longer_answers_not_provided` + `test_the_not_provided_seam_is_still_in_the_code`（两侧各一条） |
| `snapshot_stale` 只由 Revalidator 置 | `test_a_new_favorite_is_not_stale_and_the_store_never_decides_that`（两个方向：新建是 `False`；被置成 `True` 的读回来仍是 `True`，存储层没把它抹平） |
| 鉴权照 AUTH-03，越权 403/404 | `test_someone_else_can_neither_see_nor_delete_my_favorite` + 真栈实测（§5） |

**本卡最容易做假的那一条单独说**：把 `store=None` 换成一个**内存** store，
`GET /favorites` 立刻从 `not_provided` 变成 `{"items": []}`——判据会转绿，
而用户看到的仍然是一句系统没有依据说出口的话。
所以 `test_my_list_is_empty_because_it_was_queried_not_because_it_was_never_stored`
判的不是「回了空列表」，是**这个空列表来自一次真的查询**：
先往库里写一条**别人的**收藏，再断言我的列表是空的——
一个假 store（对谁都回空）给不出这个区别。

**先红后绿**：写完判据、未建表未写实现时跑一次 → `21 errors`（autouse 的清库夹具
在「表不存在」上就炸了，那正是根因）；实现完 → `21 passed`。

**② 无冻结件偏离**：`contracts/` 与 `contracts_v04/` 四件一字未动
（本卡只加表、加实现、放宽形参）。`Favorite` / `ShareLink` 的字段逐字对齐冻结件，
`PgFavoriteStore` 造对象走的是 `contracts_v04` 的 `Favorite` 本体（`_contract()`，
与 `flint/api/favorites.py` 同一种加载法），**NEVER 在本模块再抄一份字段清单**。

**③ 无禁用词**：新增与改动处 `适当` / `合理` / `必要时` / `大约` / `尽量` / `若干` 0 命中。

**④ 复用断言在位**：三个 SQL 实现**没有重写任何域逻辑**——
`add_favorite` / `remove_favorite` / `list_favorites` / `evaluate_snapshot_stale` /
`refresh_snapshot` / `get_prefs` / `set_prefs` / `resolve_share` 一行未动，
判据 `test_my_list_is_empty_because_it_was_queried…` 与
`test_setting_one_axis_leaves_the_other_alone_through_sql`
都是**经由既有域函数**去打 SQL store 的（不是直接调 store），
这就是「复用在位」的可执行形态。

**⑤ 装载未超预算**：≈33k / 40k。

## 8 门

```
pytest tests/v041/test_persist_fav_share_prefs.py -q     21 passed
ruff check . --no-cache                                  All checks passed!
mypy --strict flint                                      Success: no issues found in 313 source files
pytest -q                                                4799 passed / 10 failed → 修掉本卡那 6 条后
                                                          剩 4 条见 §6（另开单，非本卡引起）
```

## 9 留给下游的四句话

1. **`PERSIST-02`**：`create_workbench_app` **已经装配上了**（`flint/api/app.py:573`，
   `ENTRY-03` 挂的），今天用的是**内存** `GraphStore`。卡面写的「`POST /workbenches`
   也没挂」与实况有出入——**缺的是表与 SQL 实现，不是挂载**。
   另：§6 那四条红全归你（`/workbenches` 的前端类型 + `GraphStore()` 那条判据）。
2. **`PERSIST-03`**：`templates` 表建完之后，`test_no_fake_empty.py` 的
   `FAKE_EMPTY_PATHS` 就该空了——**名单空了不等于缝可以删**，
   缝的两条判据已经挪到「直接打缝」，你不用再动它们。
3. **`SHELL-01` / `SHELL-02`**：`prefs` 表已经在了，右上角下拉与主题三态都存得住。
   **主题那一列本卡刻意没建**：`Prefs` 今天只有 `lang` / `region` 两个字段，
   现在加一个没有任何代码读写的列等于把猜测写进 schema——
   列由 `SHELL-02` 用迁移 `0027` 加，与它一起加进 `Prefs`。
4. **所有人**：`flint/db/sync_bridge.py` 的 `run_sync` **在事件循环线程上会抛错**。
   看到 `BlockingCallOnEventLoop` 时 NEVER 去掉那道检测——
   把调用点改成同步处理函数，或用 `run_in_threadpool` 包住整段同步调用。
