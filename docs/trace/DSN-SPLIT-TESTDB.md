# DSN-SPLIT-TESTDB trace — 演示库/测试库分家 @2026-08-02

> 目标：根治「demo 库与测试库共用一个 PG」。已咬六次。

## 0 结论先行

**根因是两条，不是一条。** 监管盘的 11 处硬编码 DSN 是其中一条；
真正把 demo 数据整张表删掉的是**另一条**，本次才挖出来：

| # | 路径 | 破坏力 |
|---|---|---|
| ① | 11 处硬编码 DSN + 54 处默认值都指 demo 库 | 各用例 wipe fixture `DELETE FROM projects/topics/deliverables/snapshots ...` |
| ② | **三处 alembic 子进程没传 `DATABASE_URL`** | `migrations/env.py` 的 `DEFAULT_URL` 指 demo 库 → `tests/m3/test_m3_001.py::test_downgrade_upgrade_round_trip` 每跑一次全量就对 **demo 库** `alembic downgrade 0007` = **DROP TABLE** deliverables / blocks / projects / topics / topic_seeds / origins / claims / facts / facts_ledgers / pricebook / profiles / generation_records / edit_events / task_specs / cluster_centroid_daily |

②才是「报告夹具没了、combo 项目要重建」的主因——DELETE 只删带前缀的行，
DROP TABLE 是整张表连数据一起没。只修①不修②，等于没修。

## 1 第一步：机械收口 + 防回归（零行为变更）

**先写失败的测试**（`tests/harness/test_dsn_isolation.py`），再动实现。

扫描器口径（NEVER 用会误伤假 DSN 的粗正则）：只认**连本机 compose 端口 55432** 的串，
且必须带 `@`。判「有 env 兜底」按 **AST 结点身份**比对，不靠行文本猜（跨行写法也认得出）。

排除项各自有理由，且写成了反向断言 `test_scanner_excludes_deliberate_fake_dsns`：

| 字面量 | 为什么不是问题 |
|---|---|
| `postgresql://unused`（tests/m3/*） | 无 `@`、离线 deps 从不连库 |
| `postgresql://x`（tests/m4/test_m4_039.py:132） | 同上 |
| `postgresql+asyncpg://flint:flint@localhost:**5432**/flint`（tests/m1/test_m1_005.py:22） | 端口 5432，是 Settings 解析的**配置夹具值**，从不开 socket。监管清单里没提它，但粗正则一定会误伤，故单独排除并写进断言 |

**红前**：扫描器报出的正是监管清单那 **11 处，一字不差**（独立复现了监管的盘点），
外加 3 处自己命中——扫描器自己的正向样例。**没有给本文件开豁免**（那等于在扫描器上留后门），
改成用拼接构造样例，AST 里就不是完整字面量了。

**修后**：11 处改成 `DSN = os.environ.get("FLINT_TEST_DSN", <原默认值>)`，默认值**逐字不变**。
`pytest -q` → **1342 passed / 0 failed**（1339 基线 + 3 条新扫描器用例），行为等价。

## 2 第二步：真正分库

`scripts/provision_test_db.py`（新建）——建库 + 迁移 + **种大类**三步，全幂等，
start-demo.ps1 与 CI 都调它（同一信息只在一处定义）：

1. 先查 `pg_database` 再 `CREATE DATABASE`（PG **没有** IF NOT EXISTS）；
2. `alembic upgrade head`（DATABASE_URL 指 flint_test）；
3. `seed_categories` 12 条。

**第③步不是我加戏**：虚拟库跑第一轮时 6 条用例以 `ForeignKeyViolationError:
Key (category_id)=(cat-ai) is not present in table "categories"` 失败——
`clusters.category_id` 有外键指过去，而 categories 是人工固定资产（assets/categories.yaml），
分库前是靠 demo 库里早就 seed 过的 12 行「蹭」到的。空库不备齐 = 库没建全，不是断言不过。

`docker-entrypoint-initdb.d` **NEVER 依赖**：它只在数据卷首次创建时执行，owner 的 pgdata 卷早就存在。

测试默认值：**66 处**全部 `/flint` → `/flint_test`（新增断言
`test_every_dsn_default_points_at_the_test_database` 先红后绿钉住）。

**防 footgun**（`tests/conftest.py`，新建）：收集到 compose 用例时才连库检查——
库不存在 / PG 不可达 / 库在但没迁移 → **大声退出并打印那一条建库命令**，
**NEVER 回落 flint**；另加一条：`FLINT_TEST_DSN` 要是被指回 demo 库，直接拒绝开跑。
CI 的 `pytest -q -m "not compose"` 一条 compose 用例都不收集 → 这道闸对它是空操作。

## 3 第三步：harness 三处（判断错就等于没修）

| 模块 | 是否写库 | 落法 |
|---|---|---|
| `harness/gate1_live.py` | **写**（`_wipe` 删 jobs/job_steps/job_events/snapshots 再写回） | 模块默认 = **测试库**（被 tests 导入时安全）；`__main__` 里显式切 **demo 库**并打印 `[gate1_live] 写入库：...`。默认值选测试库是因为代价不对称：判断错最坏是测试库被自己的用例覆写，反过来会毁 demo |
| `harness/topic_caliber.py` | **不写**（全文件零 INSERT/UPDATE/DELETE/execute，只有 `conn.fetch` 与只读 `PgCardCatalog`） | **仍连 demo 库**——见下 |
| `harness/drill7.py` / `replay30.py` | 写（CLI） | argparse default 改 env 优先（`FLINT_DEMO_DSN`）、默认值不变；测试从不吃这个 default（`run_drill`/`run_replay` 的 dsn 是必填参数） |

**topic_caliber 为什么不搬去测试库**——这条我偏离了任务书的字面（任务书把它和 gate1_live
并列为"会写库"），理由是实测：

- 它**只读**：写库探测器（AST 扫写 SQL 字面量 + execute 类调用）在它身上 0 命中，
  在 gate1_live 身上有命中（阳性对照，写进断言了）。只读就污染不了 demo。
- 它读的是**数据**不是习惯：`replay_run` 要按录制 asset 里的**真实 card_ids** 还原 seed，
  那批卡是真实抓取入库的行，只在 demo 库；空的 flint_test 里 `create_origin` 会直接
  `OriginValidationError("unknown card_ids")`，TS-011 / TS-014 / grounding 三条回放用例会红。
- 所以对它而言「正确的库」= 有那批真卡的库。要改指向设 `FLINT_CALIBER_DSN`。

两条判断都钉成了断言（`test_gate1_live_writes_to_the_test_database_when_imported`、
`test_topic_caliber_stays_read_only`）：哪天有人给 topic_caliber 加了写操作，测试会红，
逼着重新决定它连哪个库，而不是让污染悄悄发生。

⚠ **代价如实记账**：`pytest -q` 仍会**读** demo 库（那三条回放用例）。只读、不清数据。

**超出清单的两处**（同类问题，顺手收口，默认值不变、零行为变更）：
`eval/lineage.py:109`、`tool/labeling.py:111` 的 argparse `--dsn` 默认值也改成 env 优先。
两者的测试都显式传 DSN，本来就没走 default——收口是为了不留下一个新的洞。

## 4 验收（真实数字，全部本人跑）

| # | 项 | 结果 |
|---|---|---|
| 1 | `ruff check --no-cache .` / `mypy --strict flint` | **All checks passed** / **224 文件净** |
| 2 | `pytest -q`（测试库跑热后） | **1345 passed / 0 failed / 0 skipped / 0 warning**，170.75s |
| 2' | `pytest -q`（**全新**测试库首轮） | **1344 passed / 1 skipped / 0 failed**（skip 见 §5） |
| 3 | 不设任何环境变量 | 全程未设 `FLINT_TEST_DSN` / `FLINT_DEMO_DSN` / `FLINT_CALIBER_DSN` / `DATABASE_URL`（本机只有付费档 key 与单价变量，与 DSN 无关）——上面每一次 pytest 都跑在这个前提下 |
| 4 | **根治证明** | 见下表 |
| 5 | start-demo.ps1 编码 | 首三字节 **239,187,191**（UTF-8 BOM）保持 |

**根治证明（第 4 条）**——`harness.demo_seed_report` 灌夹具 + CLI 恢复判定样本 + 真跑一次
`POST /projects/combo`（18s 本地 qwen）把 demo 填满，然后跑**三轮**完整 `pytest -q`：

| demo 库 | deliverables | **blocks** | projects | topics | snapshots | jobs | cards |
|---|---|---|---|---|---|---|---|
| pytest 前 | 1 | **9** | 1 | 6 | 3 | 59 | 1027 |
| 三轮 pytest 后 | 1 | **9** | 1 | 6 | 3 | 59 | 1027 |

**一行不差。** 夹具 9 个 block 全在。（分家前：跑完 deliverables/blocks 表本身都不在了。）

**footgun 三条分支各自实测触发过**（不是读代码推的）：

1. 真把 `flint_test` **DROP 掉**再跑 → `no tests ran`，退出 1，打印建库命令，**没有回落 flint**；
2. DSN 指不存在端口 → 「连不上 PostgreSQL … compose 栈没起来」；
3. DSN 指回 demo 库 → 「测试会把它清空——拒绝开跑」。

删库之后又用 `provision_test_db.py` **从零重建**跑通（`已新建` 分支真走过，不只是幂等分支）。

## 5 没验证 / 没做 / 要 owner 拍的

**① 全新测试库首轮会 skip 一条**（`tests/topic/test_ts_010_combo_api.py:81`
「local PG has <2 distinct-cluster cards」）。这是该用例**自带的设计守卫**：本机 PG 没有真卡就跳过。
分库前它连 demo 库（1027 张真卡）→ 从不 skip；分库后虚拟库首轮 skip，跑过一轮就不再 skip。
两条修法各有代价（造合成卡=改测试语义／从 demo 拷真卡=把刚断的耦合接回一截），
**我不代拍**；口子与实现位置写在 `scripts/provision_test_db.py` 头部注释里。

**② 既存缺陷，我没动**：`tests/m2/test_m2_040.py` 有个 `autouse=True` 的连库 fixture，
把同文件里一条**没打 compose 标记**的纯单元用例
（`test_no_guess_failed_without_reason_invariant`）一起拖去连 PG。
后果：CI 的 `unit` 阶段（`pytest -q -m "not compose"`，不起 PG）会 error 一条。
这是分库前就有的（那时它连 demo 库，一样要 PG）。补标记会改变**用例选择语义**，
撞 owner 红线，故只报不改。

**③ CI compose-smoke 仍不完整**（既存）：它从来没有对 demo 库跑过迁移，
而 topic_caliber 的三条回放用例要读 demo 库里的真卡。我按任务书加了建库+迁移这一步
（针对**测试库**），但 CI 那三条用例仍不会绿。**CI 目前也不会真的运行**（本目录不是 git 仓库）。

**④ 顺手修的既存红**：`tests/m1/test_m1_040.py` 的 import 排序（I001）。
它一直是红的，只是被 **ruff 缓存**挡着——我改到那个文件才让它现形。
控制实验（把 DSN 改回原样再 `--no-cache` 扫）确认与我的改动无关。
**教训值得 owner 知道：`ruff check .` 带缓存会瞒过未改动文件里的既存问题，
`--no-cache` 才是真话。**本次所有 ruff 结论都是 `--no-cache` 跑的。

**⑤ 顺手修的新警告**：`tests/m1/test_m1_003.py` 的 alembic 子进程 `text=True` 无 encoding，
Windows 下按 GBK 解 UTF-8 的中文迁移消息 → 整套跑时读取线程抛 `UnicodeDecodeError`
（分库后迁移真有输出才现形）。加 `encoding="utf-8", errors="replace"`，与
`tests/m2/test_m2_001.py` 既有写法一致。现在全量跑 0 warning。

**⑥ 没验证**：CI 三个阶段没有真跑过（没有远端）；只在本机 Windows + compose 上验证；
`FLINT_CALIBER_DSN` 这个新 env 名只在代码路径上成立，没实测过用它改指向。

## 6 落盘清单

| 文件 | 改动 |
|---|---|
| `tests/harness/test_dsn_isolation.py` | **新建**——6 条断言：无裸 DSN／统一 FLINT_TEST_DSN／默认指 flint_test／gate1_live 导入时落测试库／topic_caliber 保持只读（带阳性对照）／扫描器不误伤假 DSN |
| `tests/conftest.py` | **新建**——测试库前置闸（缺库/不可达/未迁移/指回 demo 各自大声失败，NEVER 回落） |
| `scripts/provision_test_db.py` | **新建**——建库+迁移+种大类，幂等 |
| 11 个测试文件 | 硬编码 DSN → `os.environ.get("FLINT_TEST_DSN", ...)` |
| 66 个测试文件 | 默认库 `/flint` → `/flint_test` |
| `tests/m1/test_m1_003.py`·`tests/m2/test_m2_001.py`·`tests/m3/test_m3_001.py` | alembic 子进程加 `env={**os.environ, "DATABASE_URL": <DSN 派生>}`（根因②） |
| `harness/gate1_live.py` | 双身份：模块默认测试库、`__main__` 显式 demo 并打印 |
| `harness/topic_caliber.py` | DSN 走 env（`FLINT_CALIBER_DSN`→`FLINT_DEMO_DSN`），默认仍 demo（只读，见 §3） |
| `harness/drill7.py`·`harness/replay30.py`·`eval/lineage.py`·`tool/labeling.py` | argparse default → env 优先，默认值不变 |
| `start-demo.ps1` | 加「测试库 flint_test 就绪」一步（BOM 保持） |
| `.github/workflows/ci.yaml` | compose-smoke 在 `pytest -m compose` 前加 provision 一步 |
| `tests/m1/test_m1_040.py` | 既存 I001 import 排序（只移动 import 行） |

**未动**：`contracts/`、`flint/domain/`、后端端点响应形状、`web/`、`V0 files 前端设计/`、
任何测试的断言内容与默认行为语义。零联网装包、零付费（唯一一次模型调用是本地 qwen 的 combo，免费）。
