# v0.4.1 第 7 批 · 完成态报告

**12 / 12 verified**（`SHIP-07` 本身在内）· 2026-08-08 · worker 单会话连跑

> 本批定位：**清尾**。三条裁决落地 + 一处并发缺口 + 八张问题单。
> 清完之后，`docs/blocked/` 里 open 的还剩 **7 张**——比工单预计的 5 张多两张，
> 两张都是本批**看屏 / 连跑时新发现的**，逐条点名在 §4。

---

## 1 五道全局门（逐字贴出）

```
$ ruff check . --no-cache
All checks passed!

$ mypy --strict flint
Success: no issues found in 307 source files

$ pytest -q
4648 passed, 12 warnings in 369.15s (0:06:09)          ← 零 failed

$ cd web && npx vitest run
 Test Files  82 passed (82)
      Tests  831 passed (831)

$ cd web && npx tsc --noEmit
exit=0
```

**一条环境事实，下一个人务必带上**：`pytest` 要带 `PYTHONIOENCODING=utf-8`。
不带的话约 27 条走 subprocess 的判据会以
`TypeError: argument of type 'NoneType' is not iterable` 失败——
子进程输出 GBK、父进程按 UTF-8 解码，读线程抛 `UnicodeDecodeError`，
`subprocess` 于是把 `stdout` 交成 `None`。**那不是代码红**。
本批实测：不带时 35 红，带上后 8 红（那 8 条是真的，已全部清掉）。

## 2 出口判据三条

### ① 对账器两类计数均为 0

```
{'backend_unused_by_frontend': 20, 'frontend_wants_missing_backend': 1}
field_mismatch: 0        frontend_untyped_response: 0
```

总发现 36 → **21**。剩下两类**不属本批范围**：20 条是「后端有前端没用」
（已由第 6 批 `GAUGE-11` 逐条分诊，表在 `docs/端点分诊-v041.md`），
1 条是 `/workbenches/{}/nodes`（前端要而后端没有，登记在第 6 批的单里）。

### ② 九区加未归区等于全量（真栈实测）

```
day=2026-07-05   全量=106
  CN=18   unassigned=88   其余七区当日无数据
覆盖=106   漏=[]   多=[]
```

全表口径：`clusters` 193 行 = `CN` 89 + `global` 103 + `NULL` 1 = 89 + 104。
广场按天，所以屏上是 18 + 88——**口径差如实记在 `docs/trace/REGION-11.md`**，
NEVER 为了对上卡面那两个数去改判据。

### ③ 主题两屏在真栈上有真数据

```
GET /topics/topic-demo-fixture-vecdb          200
GET /projects/proj-demo14bf9d94b0/topics      200
```

详情屏截图 `.ui-probe/topics-id-light-desktop.png` 已逐项看过：
【夹具】前缀、两维 tag、`why_now` 正文、**两条证据各带日期**、关键词映射齐全，
控制台 0 报错（404 额度已撤）。

---

## 3 十二张卡各做了什么

| 卡 | 一句话 | 最值钱的那一点 |
|---|---|---|
| `DEC-039-041-LANDING` | 三条裁决进 `DECISIONS-v04.md` | 三句**禁令**各挂一条判据——转述时最先掉的就是禁令 |
| `STALE-01` | 全仓禁「据时间戳算陈旧」 | **边界比禁令更要紧**：`novelty`/`dormant`/`age_days` 三处正当算术 NEVER 误伤 |
| `REGION-11` | `global`+`NULL` → 未归区 | 判的是**闭合**：九区之和加未归区 == 全量**且互不重叠** |
| `REGION-12` | `by_source_text` 原文词面 | `SourceColumns` 是 v0.4 封版件，缺词面那一态落在**新建的调用方** |
| `SEED-01` | demo 库种夹具主题 + 撤 404 额度 | 它让主题详情屏**第一次真的渲染**，当场抛出一条被 404 挡着的红 |
| `LOCK-01` | 迁移 0022 + 乐观锁 | 阴性对照断言**先写者的 `change_log` 还在**，不只是「抛了异常」 |
| `UIX-04` | 作业屏第五态「无权查看」 | 不劝重试，**并且明说重试没用**——只是不劝的话用户自己会去刷新 |
| `UIX-05` | `useScreenData` 出 `refetch` | 阴性对照：**不调它，屏上仍是旧值** |
| `TYPE-05` | `field_mismatch` 7 → 0 | 七条里**六条不是漂移，是尺子认错了接口** |
| `TYPE-06` | `frontend_untyped_response` 8 → 0 | 卡面写八条**实做五条**，差额如实记进单子 |
| `FIX-15` | 间歇红第三轮连跑 | 30 次全绿 → **单据 NEVER 关**：三轮合计 60 次仍低于 `FIX-04` 的复现门槛 |
| `SHIP-07` | 本报告 + 出口门 | — |

### 关掉六张单

`SLOT-02` · `REGION-08` · `PLAZA-02` · `DEMO-TOPIC-SAMPLE-ID` ·
`JOB-SCREEN-HAS-NO-DENIED-STATE` · `SCREEN-DATA-HOOK-HAS-NO-REFETCH` ·
`PARITY-WIDER-SCAN-REVEALS-FIFTEEN-TYPE-GAPS`（七张，其中 `PLAZA-02` 是两条缺口一起清完）。

每一张的原文**一字未改**地留在下半部分——那四选一的选项是裁决唯一的推理过程，
删掉等于把推理擦掉只留结论。

---

## 4 还开着的 7 张，逐条点名卡在谁那里

### owner 面（5 张，工单 §8 预告过）

| # | 单 | 卡在什么 |
|---|---|---|
| 1 | `DEMO-REFS-NO-STORAGE-FACE.md` | chart / 质量卡 / gap hints **没有存储面**。质量卡那条要先定口径 |
| 2 | `E2E-REALSOURCE.md` | 真实源端到端冒烟——**红线**，需 owner 在场 |
| 3 | `K1-02-SOURCE-CONTRACTS-MISSING.md` | 三条候选新源的响应契约，要开发者账号或商务协议 |
| 4 | `K2-COMPLIANCE-BEFORE-LAUNCH.md` | 上线前合规手续，有到期日的欠条 |
| 5 | `LINEAGE-GOLD-REPLAY-MISSING.md` | 血缘金标 30 天回放，根因是库里只有 7 天 |

### 本批新增 / 保留的 2 张

| # | 单 | 为什么还开着 |
|---|---|---|
| 6 | `ONE-UNNAMED-FRONTEND-RED-NOT-CAPTURED.md` | **第三轮 30 次全绿，未复现**。三轮合计 60 次，仍低于 `FIX-04` 那次的复现门槛（40 次里第 29 次）。**「跑不出来」与「不存在」不是一回事**，所以 NEVER 关 |
| 7 | `SOURCE-COLUMNS-DOES-NOT-SHOW-WHO-SAID-IT.md` | **`REGION-12` 看屏时新发现**：两条来源说法并排，而屏上**看不出谁说的**（source id 只在 `data-*` 属性里）。改法在 v0.4 封版组件内，按 §9.2 停下立单，四选一等 owner |

---

## 5 未解决的、逐条列名（NEVER 一句「其余无异常」收口）

**① `docs/blocked/SOURCE-COLUMNS-…` 是一个真产品缺陷，不是登记。**
那个组件自己的文件头写着「读者失去了『谁说的』这个唯一能判断可信度的东西」——
屏上现在正是这个状态。地区那一列顶不住：今天 `global=103 · CN=89 · NULL=1`，
绝大多数簇的源同区或无区，同一列里两条陈述谁说的完全看不出来。
**推荐甲**（每条陈述前加一行可见的来源名，改 4 行冻结组件 + 4 个文案 key）。

**② `TYPE-06` 卡面写八条，实做五条。** `/settings/locale` 与两条 deref
由 `TYPE-05` 顺带建了（前者中途换了类别、后两条同住一个通道）。
差额记在单子与判据里——照卡面那个八去找，会有三条怎么也找不到。

**③ `FIX-15` 没有定位到那条红。** 本批把 `globals.css` 又改过、dev server 全程在跑，
环境比上一轮更接近第一次那条红的条件，仍然没有复现。
这让「与那个环境有关」这条猜想的可信度**下降了一点**，**但不是证明**。

**④ `LOCK-01` 只补了 `projects` 一张表的乐观锁。** 库里别的全行 upsert 有没有
同样的问题，本批**没查**——`LOCK-01` 的触碰面是 steward 复核 `ENTRY-02` 时查出的那一处。

**⑤ 主题两屏的真数据里，详情屏用的是夹具。** demo 库里有**六条真主题**
（模型产出，各带 2 条证据），取证样例仍指夹具，理由是**可复现**
（那六条是一次过去运行的痕迹，没有脚本能重造）。
owner 想换成真产出的话，`harness/fe_smoke.py` 改一行。

---

## 6 改了 outputs 之外的文件，逐处点名待 steward 复核

| 卡 | 文件 | 一句话 |
|---|---|---|
| `STALE-01` | `tests/v041/test_plaza_stale.py` | 「单据仍 open」前提过期，改判「关单必须留下答复」 |
| `REGION-11` | `tests/v041/test_plaza_filters.py` | 同上，并把它 docstring 里那句「别把 global 叫成全球」的担心**从注释变成断言** |
| `REGION-12` | — | 全部在 outputs 内 |
| `SEED-01` | `web/app/topics/[id]/page.tsx` · `web/messages/*` · `web/app/globals.css` | 拆信封（acceptance④ 必需）；未归区文案缩短 + select 宽度上闸（`REGION-11` 的移动端溢出回归） |
| `LOCK-01` | `flint/api/topics.py` · `flint/api/schemas.py` | 带版本读写 + 409；新增 `PROJECT_CONFLICT` 码（**NEVER 借 `LEDGER_CONFLICT`**） |
| `UIX-04` | `web/__tests__/app/screens.test.tsx` · `tests/v041/test_probe_job_owned.py` | 桩补 `access`；第 6 批那条反向判据照它自己的话翻成正向 |
| `TYPE-05` | `docs/前后端对账表-v041.md` · `test_types_complete.py` · `test_fe_be_parity.py` | 表重跑；两条判据的前提第三次过期 |
| `TYPE-06` | `tools/check_fe_be_parity.py` | **单键响应**精确匹配（那道「两个字段重合」的门在单键上结构性迈不过去） |
| `SHIP-07` | `tools/check_design_constraints.mjs` · `test_parity_dynamic_path.py` | A3 不再把**纯类型声明文件**当成渲染件；两类计数第三次换值 |

---

## 7 这一批反复撞到的两个形状

### ① 判据把「说明问题的那句话」当成问题本身 —— **本批第 12 次**

规格 `#2.4` · `backfill.py` · 噪声基线 · `check_fe_be_parity` 旧白名单 ·
`FIX-12` 枚举扫描 · `test_endpoint_triage` 读缓存判据 · `GAUGE-14` 首段清单 ·
`STALE-01` 时间戳禁令 · `REGION-11` 迁移回填 · `SEED-01` 种子 SQL ·
`UIX-04` 的「重试」二字与 `SseDisconnectNotice` 那句解释 · `SHIP-07` 的 A3。

**每一次的修法都是给「引用」一个位置，而不是把判据放宽**：
剥注释 / 剥 docstring / 只判 SQL 字面量 / 只判 messages 而不判组件源码 /
禁「劝进」的话术而不禁那个词。

### ② 判据的前提会过期，而过期的判据看起来与回归一模一样 —— 本批 9 处

`test_plaza_stale`（单据 open）· `test_plaza_filters`（同）·
`test_cluster_region`（迁移水位 21 / 单据 open）· `test_mobile_sweep`（404 额度）·
`test_screens_live_probe`（噪声登记）· `test_types_complete`（清单四次换值）·
`test_fe_be_parity`（两类非零）· `test_parity_dynamic_path`（7/8）·
`test_probe_job_owned`（反向判据）。

**每一处都在原地写清「改前判的是什么、为什么它红了、意图哪一条没变」**——
钉死一个过期的世界，只会让下一次真正的修复被判成错。
其中两处（`test_fe_be_parity` 与 `test_parity_dynamic_path`）已经**第三次换值**，
所以这一次彻底改判**能力本身**，不再钉真仓库的取值。
