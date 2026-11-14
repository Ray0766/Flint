# PERSIST-02 · 工作台三表 + 图落库 + `GET /workbenches/{id}`（`DEC-051` 解阻）

**结论**：迁移 `0027` 建齐最后三张表，**八张表 8/8**；图从内存件换成 `PgGraphStore`；
新建 `GET /workbenches/{id}`；那一屏从写死 `graph = null` 换成真去取。
`verify_cmd` 20 条全绿；`ruff` / `mypy 319` / `tsc 0` / `vitest 858` 全绿。

装载：`docs/steward/tasks-v041-b9.json#PERSIST-02` · `DECISIONS-v04.md#DEC-051` ·
`docs/blocked/PERSIST-02-TWO-DIFFERENT-THINGS-ARE-BOTH-CALLED-WORKBENCH.md` ·
`docs/blocked/GRAPH-HAS-NO-STORAGE-FACE.md` · `flint/api/workbenches.py` ·
`flint/graph/store.py` · `flint/fav/pgstore.py`（Pg 件房规）· `migrations/versions/0023_*.py`
（实测装载 ≈ 34k tokens，预算 40k）

---

## 1 先把卡面那三处与实况的差别钉住

| 卡面 | 实况 | 谁改的 |
|---|---|---|
| 「`POST /workbenches` 没挂，入台永远拿不到 ok」 | **早就挂了**（`ENTRY-03`）。对账器 `frontend_wants_missing_backend = 0` | owner 2026-08-09 已按实测改口径 |
| `frontend_wants_missing_backend = 1` | **0** | 同上 |
| —— | `GET /workbenches/{id}` **要新建** | 同上 |

**缺的不是挂载，是表。** 入台今天拿得到 `ok`，只是那张工作台**活不过一次进程重启**。
这与「拿不到 ok」是两种不同的坏：后者用户当场就知道没成，
前者他以为存下了，下次打开发现没了。

## 2 `DEC-051`：两个都叫「工作台」的东西

| | 甲（本卡建） | 乙（等 K6） |
|---|---|---|
| 表 | `workbenches` | `workbench_graphs`（**本批不建**） |
| 主键 | `graph_id`（由 `(user_id, cluster_id)` 决定） | `graph_id` |
| 带项目 | 否（`project_id` 先留空列） | 是 |
| 谁在用 | `ENTRY-03` 那条入台链 | `flint/graph/multi.py` |

`project_id text NULL`，语义**逐字写死在迁移注释里**（owner 原话）：

> `NULL =「这张图还没有归属任何项目」`，且 **NEVER 往这一列写一个编出来的项目 id**。

今天这一列**没有任何写入方**。到 K6 交互稿落地时它由一次 `UPDATE` 填上，
**不是由一次迁移回填**——两者的区别是：迁移回填要现在就编出一批项目 id 来。
判据两头都钉：注释里那两句逐字在、库里那一列真的可空。

## 3 `workbenches` 是**第三张**表，而不是「有节点就算有图」

改前「这张图在不在」判的是 `nodes(graph_id)` 非空。那把两件事合成了一件：

- **图不存在**（没人建过）
- **图存在但空了**（建过，节点删光）

第二种今天还不会发生，而它一旦发生，入台会回 404「没有这张工作台」——
**而那张工作台明明在**。所以图有了自己的一行，端点两处存在性判断都改问那一行。

## 4 换实现的四条纪律

1. **域函数一行没改**：`add_node` / `add_edge` / `set_node_role` 照旧。
   判据 `test_a_dangling_edge_is_still_refused_through_sql` 就是拿这件事当证据——
   悬空边在 SQL 上仍然被 `add_edge` 拦下。
2. **Protocol 而不是继承**：新增 `GraphStoreLike`（`flint/graph/store.py`）。
   继承会把内存件那三个字典也带过去——一个连着库、同时揣着一份永远为空的
   进程内副本的对象，读它的人分不清哪一份是真的。
3. **内存件同形补两个方法**：只给 SQL 那边加的话，注内存件的调用方
   （既有测试、冒烟脚本）会在端点里撞 `AttributeError`——那是**换实现换出的新故障**。
4. **幂等落到库里**：`ON CONFLICT DO NOTHING` + 唯一索引。域函数那层是
   「读一次、判一次、写一次」，改前落在进程内字典上、GIL 顺手挡住并发；
   落到库上之后没人挡。

`DO NOTHING` 而不是 `DO UPDATE`：`owner_id` 与 `seed_cluster_id` 是这张图
**怎么来的**，NEVER 因为第二次点击而被改写。

## 5 三条外键 + 两条索引，各有各的理由

孤儿节点占着 `node_id`，下一次同名节点入台时**撞主键**——报的错与「重复入台」
一模一样，于是排查的人会去查幂等逻辑，而问题根本不在那里。

`is_primary` 而不是 `primary`：后者是 SQL 保留字，每条碰它的语句都要加引号，
而**总有一条会忘**，那一条报的是语法错、看起来与这一列毫无关系。
`UNIQUE (graph_id) WHERE is_primary` 是冻结件那句「图内计数恒 ≤1 (I12-1)」
在库这一层的写法——**放在库里而不是只放在代码里**：
两个并发请求各自读到「现在没有 primary」再各自写一个，代码那层拦不住，索引拦得住。

## 6 撞上的四件事，两件是真缺陷

### 6.1 同步 store × 异步处理函数：护栏当场生效（**它是对的**）

六条端点判据一起 500。原因是 `PgGraphStore` 底下走 `run_sync`，
而它**在已经跑在事件循环上时会抛** `BlockingCallOnEventLoop`——
那是 `PERSIST-01` 刻意立的护栏，拦的是「在事件循环上阻塞住整个进程」。

**NEVER 把护栏拆掉**。做法是把同步调用挪出循环：七处包 `run_in_threadpool`，
与 `flint/api/favorites.py` 那族用 `def` 处理函数（FastAPI 自动丢线程池）
是同一条路的两种写法。

### 6.2 整机身份三拒是**裸 500**（既有缺陷，本卡第一次照出来）

`test_app_assembly.py#test_no_mounted_route_answers_500_out_of_the_box`
把 `GET /workbenches/{graph_id}` 报成「无脑 500」。查下去不是本卡的错：

`_Assembler.add` **只搬 `APIRoute`——子应用的异常处理器一个都不跟过来**。
每个模块里那句 `install_identity_handlers(app)` 只在它自己那个 `create_*_app()`
造的 TestClient 上生效；并进整机之后，任何一条从处理函数里抛出的身份异常都变成 500。

**它一直是这样，只是一直没有一条路把它照出来**：身份类端点大多要请求体，
探针不带体时先被 422 挡住，走不到抛异常那一步。本卡建的 GET 是这一族第一条不要体的路。

修法：`create_app` 里补一句 `install_identity_handlers(app)`。实测：

```
GET /workbenches/probe  -H X-User-Id: probe  → 401 IDENTITY_UNKNOWN
GET /workbenches/probe  （不带头）            → 401 IDENTITY_MISSING
```

500 说的是「坏了」，真相是「你没带身份」——两者该让人做的事完全相反。

### 6.3 判据缺一步：`flint_test` 的 `users` 是空的

端点会去 `users` 表查身份，编一个 id 会被拦成 401——**那与本卡要量的东西无关，
只会让判据红得没有意义**。补 `_seed_people()`，幂等，且**不在收尾时删**：
`demo-user` 是这套栈自己用的演示身份，别的判据也在用，谁先跑谁把后面的人的前提拆了。

### 6.4 本轮**第六次**「尺子读了注释」

我自己新写的那条：`assert "GraphStore()" not in code` 撞上装配处两段
**记录改动理由**的注释（逐字写着「改前它是 `GraphStore()`」）——
解释得越清楚它越红。改成先剥注释再数。前五次记在
`SHELL-01` / `SHELL-02` / `ENTRY-04` / `FIX-19` 的 trace 里。

## 7 -b：那一屏今天打得开

`GET /workbenches/{id}` + `web/lib/workbenchClient.ts` + 那一屏真的去取。

**别人的图回 404 而不是 403**：`graph_id` 由 `(user_id, cluster_id)` 算出来，
**谁都能算**——知道对方的 user_id 就能算出他那张图的 id。
读路径不比一次归属的话，那个 id 就是一把公开的钥匙。
而 403 等于用状态码告诉对方「这张图存在」：403 与 404 一对照，谁有哪张图就被数出来了。

**四态各画各的**（`A6` 尺子逼出来的，见 §8）：加载中 / 画布或空图引导 /
「没有这张工作台」/「接口未提供」。

## 8 `A6` 说我并了格——**它是对的**

第一版把「还在取」与「取不到」并进 `null` 那一格，理由写的是
「两者都还没有依据画任何一张图」。`tools/check_design_constraints.mjs` 的 A6
当场把这一屏报成「缺加载态、错误态」。

**并格省下的是四行代码，代价是屏上写着一件没发生的事**：正在取的那一秒
屏上说「接口未提供」，而用户会照着它去找运维。改成四态各占一格。

## 9 改前 / 改后 / 为什么非改不可

| 文件 | 改前 | 改后 | 为什么 |
|---|---|---|---|
| `migrations/versions/0027_workbench_graph.py` | 不存在 | 三张表 | 卡面 + `DEC-051` |
| `flint/graph/pgstore.py` | 不存在 | SQL 件 | `store.py:34` 自述的那个接入 |
| `flint/graph/store.py` | 内存件四方法 | +`GraphStoreLike` +两方法 +域函数吃面 | §4-②③ |
| `flint/graph/roles.py` · `flint/fav/batch.py` · `flint/api/graph_edges.py` | 吃内存件 | 吃面 | 同上；SQL 件不是 `GraphStore` 的子类 |
| `flint/api/workbenches.py` | 两条写端点，存在性判「有没有节点」 | +`GET`，存在性判那一行，七处 `run_in_threadpool` | §3 §6.1 §7 |
| `flint/api/app.py` | `GraphStore()`，无整机身份处理器 | `PgGraphStore(dsn=dsn)` + `install_identity_handlers(app)` | §6.2 |
| `web/lib/workbenchClient.ts` · `web/lib/types.ts` | 不存在 / 无工作台类型 | 新增 | -b；类型**必须是 `export interface`**（尺子只认这个） |
| `web/app/workbenches/[id]/page.tsx` | 写死 `graph = null` | 四态 | §7 §8 |
| `web/messages/{zh,en}.json` | — | 各 +2 | 加载中 / 没有这张工作台 |
| `tests/v041/test_ui03.py` · `web/__tests__/app/ui03.test.tsx` · `test_workbench_create.py` · `test_be_settings_locale.py` | 断言「一屏不发请求」「`GraphStore()` 只有一个」「响应三样」 | 逐条翻面并写明为什么 | 前提被本卡与 `SHELL-02` 推翻 |

## 10 卡面 outputs 窄了一格（**据实上报**）

卡面 outputs 是 `["migrations/versions/", "flint/api/", "tests/v041/…"]`，
而同族三张（`PERSIST-01/03/04`）都是 `flint/`。本卡实际动到
`flint/graph/` · `flint/fav/batch.py` · `web/`。

**没有停下开单**，理由与 `SHELL-02` 那次停下**恰好相反**：
那次卡住的是一条**口径**（主题按人存还是按设备存），只有 owner 能定；
这次 `DEC-051` 已经把表结构与语义逐字定死了，剩下的只是
「`PgGraphStore` 这个类放在哪个文件里」——**一个位置问题，不是一次裁决**。
而 owner 的退出条件①（八张表 8/8）没有这些改动就到不了。

**建议 steward 把 `PERSIST-02` 的 outputs 对齐同族三张改成 `flint/`。**

## 11 自审（`self_review=true`）

**① 判据覆盖 acceptance**（五条）：①实况已按 owner 口径改正并钉住（§1）；
②三表 + 端点 + `graph_id` 这个名字（前端只认它）；③幂等**两层各有判据**
（同一个人重复入台 → 一张图；同一个热点重复入台 → 一个节点）；
④`GET` 真的取到刚入台那个热点（**不是只断言回 200**）+ 那一屏真去取；
⑤可达性那条「路接上了而走不通」**已消失**——由 `ENTRY-05` 同轮交付（见其 trace）。

**先红后绿**：实现前 20 条里 20 条 error（表不存在）。

**② 无冻结件偏离**：四件一字未动。`GraphNode` / `GraphEdge` 从 `contracts_v04`
延迟 import，**NEVER 在 pgstore 里新定义一个**。
`WorkbenchRow` 是本地行对象，**不是**冻结件里的 `WorkbenchGraph`（那是乙，`DEC-051`）。
**③ 无禁用词**：0 命中。
**④ 装载未超预算**：≈34k / 40k。

## 12 门

```
pytest tests/v041/test_workbench_persist.py -q     20 passed
pytest tests/v041 -q                               3171 passed（余 1 红 = SHIP-09 台账）
ruff check . --no-cache                            All checks passed!
mypy --strict flint                                Success: 319 source files
npx tsc --noEmit                                   0
npm test -- --run                                  858 passed
两库 alembic_version = 0027 · 八张表 8/8
```

## 13 留给下游

1. 单据 `GRAPH-HAS-NO-STORAGE-FACE.md` 与
   `PERSIST-02-TWO-DIFFERENT-THINGS-ARE-BOTH-CALLED-WORKBENCH.md` 由本卡关掉。
2. **`workbench_graphs`（乙）到 K6 必须回来定一次**（`DEC-051` 原话：
   「到 K6 交互稿落地时必须回来定一次，NEVER 到那时才发现」）——
   「我的工作台列表」今天有两个来源，合并语义未定。
3. `POST /workbenches/{id}/edges` 那条端点仍然**没有前端在调**（分诊表 B1）。
4. `/clusters/{}/verdict`（`PERSIST-04` 建）也还没有人调，已进分诊表 B2。
