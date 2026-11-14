# DEC-030-032-LANDING · owner 2026-08-05 三条裁决落盘

**来源** owner 口述（口述号 DEC-030 / DEC-031 / DEC-032）·
**落盘号** `DEC-031` / `DEC-032` / `DEC-033`（顺延，见 §2）·
**台账** `docs/progress-v041.jsonl` @ 2026-08-05T06:41Z started

## 1. 装载清单

`DECISIONS-v04.md` 全文（47 行）· `docs/blocked/NET-03-CARD-PREMISE-STALE.md` ·
`docs/progress-v041.jsonl` 全 205 行 · `docs/steward/tasks-v041-b2.json` 的 id 集 ·
`tools/check_fe_be_parity.py` 的 `mounted_paths`/`parity` 段 ·
`tests/v041/test_fe_be_parity.py` · `tests/v041/test_backlog_ledger.py` ·
`docs/积压总账-v041.md` · `docs/V041-BATCH2-COMPLETION.md`。约 14k tokens，预算 40k 以内。

## 2. 编号：owner 口述的 DEC-030 已被占用，顺延

`DECISIONS-v04.md` 里 **`DEC-030` 已经有主**——worker 2026-08-04 在 GAUGE-04
执行中登记的 `WORKORDER-v04.md` 五个 `src/` 过滤器重映射。
它被 `docs/trace/GAUGE-04.md` 引用**三处**（126 行、128 行、130 行）。

本文件自己的 `DEC-002` 就是同一情形的先例，原话：
「owner 口述记为 DEC-001，但该号已被 PRIN-01 的 §3 边界决定占用
（`docs/trace/PRIN-01.md` 已引用），**改号会让既有 trace 指向错误条目**，故顺延为 DEC-002。」

照办：**新的三条顺延为 DEC-031 / DEC-032 / DEC-033，既有 DEC-030 一字不动**。
编号说明写进 `DEC-031` 条目正文，任何人搜 DEC-030 都能就地读到这段消歧。

**若 owner 更愿意让口述号生效**，那要改的是既有 DEC-030 与 GAUGE-04 trace 的三处引用，
属 owner 变更通道；本 worker 不自行择一。

## 3. DEC-031（API 装配）：落地时发现出口判据**不可能达成**，已修

裁决把 `tools/check_fe_be_parity.py` 的 `backend_not_assembled` **归零**定成第 3 批
首卡的出口判据。开工前先量这把尺子——**它量不准**。

### 3.1 洞在哪

`mounted_paths()` 原实现按源码字面量扫 AST：只有 `node.args[0]` 是**字符串常量**
才记一条挂载。而装配的惯用写法是

```python
app.include_router(account.router)
app.include_router(billing.router, prefix="/billing")
```

**这两行里没有任何路径字面量**。实测（合成 app，两条真路由）：

```
识别到的挂载路径 = set()
```

后果是：装配卡把 51 条全挂对、路由真的通了，`backend_not_assembled` **仍然是 51**。
**出口判据在原实现下永远不可能达成**，而它红着的样子与「真的没装配」逐字相同，
读表的人分不出自己看的是缺陷还是尺子瞎了。

### 3.2 为什么不是「也认 `include_router` 这个词」

那正是裁决点名的空转：**挂一个空 router，源码里 `include_router` 明明白白写着，
用户能打到的路由一条都没有**。两种读法各错一半。

### 3.3 改法：问建起来的应用要它的路由表

三处实测逼出来的细节，各留一条判据：

| 实测 | 结论 |
|---|---|
| FastAPI 0.140 的 `app.routes` 里，`include_router` 留下的是 `_IncludedRouter` 惰性节点，`path` 是 `None` | 照直读 `app.routes` 会把整整一个 router 读成 0 条 → 必须递归下钻 `original_router` |
| `include_context.prefix` 携带前缀（实测 `/v2`） | 前缀要拼上，否则路径对不上 |
| `app.openapi()["paths"]` 漏掉 `include_in_schema=False` 的路由（实测只出 `/v2/alpha`，`/v2/hidden` 不见了） | **NEVER 走 openapi**——一条隐藏路由就能把出口判据永远卡住 |

外加一条本批的老纪律：**建不起来 ≠ 一条都没挂**。
`_build_app` 失败时 raise `AppUnbuildable`，`parity()` 报**一条 `app_unbuildable`、
零条 `backend_not_assembled`**。退化成空集合的话，报告会印出一份与
「62 条端点一条都没挂」逐字相同的东西，而两者该让人做的事正好相反。

### 3.4 改既有文件两处

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `tools/check_fe_be_parity.py` | `mounted_paths()` 从「AST 扫字面量、文件不在则返回 `set()`」→「`_build_app()` 建应用 + `_walk_routes()` 递归展开路由表；失败 raise `AppUnbuildable`」。`parity()` 的 ②③ 两节包进 `if mounted is None` 分支，新增 `app_unbuildable` 发现类型与标题 | **owner 把这个计数定成了出口判据**。不改，第 3 批首卡做对了也永远读不到 0，而红着的样子与真缺陷同形 |
| `tests/v041/test_fe_be_parity.py` | 新增 **9 条**（31 → 40：含阴性对照、`parity()` 层判据、CLI 实跑判据）；`test_every_finding_says_where_to_look` 的 kind 闭集 6 → 7 项 | 前者是新行为的判据；后者是等值判据，多一种发现类型必须来这里确认 |

**未改**：`docs/前后端对账表-v041.md`（发现数仍 62，本仓实际挂载面没变——
`/categories` 一条，两种读法结果相同；`test_the_table_is_generated_from_a_real_run_not_hand_written` 实跑仍绿）。
冻结件与四份「一字不动」清单未触碰；`requirements.lock` 未动（`importlib.util` 是标准库）。

### 3.5 顺带量出来的第二处：CLI 跑法下整块塌成「没量到」

改完在命令行实跑 `python tools/check_fe_be_parity.py`，⑤ 节报了一条：

```
应用建不起来，装配面本次没有核对：import 失败：No module named 'flint'
```

`app.py` 里 `from flint.repo.categories import ...` 要求仓库根在 `sys.path` 上。
pytest 会替你放（所以判据全绿），**`python tools/...` 不会**——
于是 owner 拿去当出口判据读的那份 CLI 报表，装配面**整块是空的**。

新读法把这一处**暴露**了出来（旧的 AST 读法不 import，永远碰不到这个问题，
但它给的答案本来就是错的）。已在 `parity()` 开头补一句 `sys.path.insert`，
判据 `test_the_command_line_run_measures_the_assembly_too` 守住。
**该判据判的是 ⑤ 节的条数，不是「应用建不起来」这几个字在不在**——
那一节是恒印的空节（本工具「空报告要写扫描面为空」那条设计），
判在不在会被自己的空节骗过去，第一版就是这么错的。
抽掉那句 `sys.path.insert` → 判据红（已实测）。

CLI 实跑现况：**共 62 条发现 · 未装配 51 条 · 建不起来 0 条**。

### 3.6 变异考 6 条，全咬住

| 变异 | 判据 |
|---|---|
| ① 不下钻 `_IncludedRouter` | `test_a_router_mounted_without_a_path_literal_is_seen` 红 |
| ② 改走 `app.openapi()` | `test_a_prefixed_and_hidden_route_still_counts_as_mounted` 红 |
| ③ 建不起来时吞异常返回空应用 | `test_an_app_that_cannot_be_built_is_never_reported_as_empty` 红 |
| ④ 丢掉 prefix 拼接 | 同 ② 红 |
| ⑤ 不滤 FastAPI 自带文档路由 | `test_the_real_app_is_measured_by_its_route_table` 红 |
| ⑥ 建不起来时退化成空集合往下算 | `test_an_unbuildable_app_reports_one_gap_not_sixty_two_false_ones` 红 |
| ⑦ **假变异对照**：只改一个局部变量名 | 39 passed 全绿（对照成立） |

脚本带 `assert old != new` 自检拦假变异；跑完源码逐字还原（脚本末尾断言）。

### 3.7 留给装配卡的两句话

1. 本尺子量的是**「挂上了」**（应用会去派发这条路径）。
   **「能通」要一条条探活**——那是卡上 acceptance 的活，本尺子不代劳。
2. `test_the_exit_criterion_is_a_number_this_tool_can_actually_report`
   现在断言该计数 **> 0**。装配做完后它会因为「不再大于 0」而红，
   **那正是提醒你来这里把判据改成 `== 0` 并记下出口的机制**。

## 4. DEC-032（未装配期间显示「接口未提供」）：确认既有实现，零代码改动

裁决与 UI-01~11 十一张卡已经采取的做法**逐字一致**（`NotProvided` 与空态各带自己的
`data-*-state`；`UI-11` 照 `BE-01` 的一次查齐、不照蓝本 P14；`UI-09` 未查证时不挂横幅）。
故本条**不产生代码改动**，只结掉 11 张卡的 `owner_review` 共同问题。

裁决自带失效条件——**随装配落地自动失效**。已在完成态报告 §五 写明：
装配卡做完后须回来把这 11 屏切到真数据路径（组件里两条路都留着，切换成本一行）。

## 5. DEC-033（NET-03 拆两半结案）

owner 的答案是问题单三选一里的 **「甲 + 乙 各一半」**，不是三取一。

- **①（甲）**：`NET-03` 记 `skipped_by_owner`，**理由逐字进台账**（裁决明文要求），
  且 **NEVER 按「已登记未执行」写判据**——那句话今天是假的。
  台账行 @ 2026-08-05T06:47Z 把 owner 原话整段引在 `note` 里。
- **②（乙）**：队列链路缺的是 `gate1_deps` 注入而非网络授权 →
  **普通卡、respx 回放、不再挂红线**，带**回退闸**（回放下若暴露真实网络请求，
  立即回退红线并停下上报）。新卡登记进 `docs/积压总账-v041.md`，由 steward 编进第 3 批。
  **本 worker 未新建该卡的机读条目**——`tasks-v041-b2.json` 是第 2 批冻结的 89 卡，
  往里加一张会改掉分母；建卡是 steward 的活。

### 改既有文件四处

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `docs/blocked/NET-03-CARD-PREMISE-STALE.md` | 顶部加「已关闭 · DEC-033」段（含两半对照表与回退闸）；**关闭前的原文一字未改**，以 `---` 隔开 | 挂着的问题单 = 「还等 owner 答复」。已答复还挂着，下一个 worker 会再停一次 |
| `docs/积压总账-v041.md` | 候选① 那行「真实源那一半属红线」→「已做（07-31 payoff 已跑并录制）」，卡在谁 `红线`→`—`；D1 那行保留红线但注明**与 NET-03 不是同一批源**；新增 DEC-033② 一行；顶部 `共 42 行 / 红线 2` → `共 43 行 / 红线 1`，`已做 21`→`22` | 候选① 那行现状**今天是假的**；顶部计数由 `test_the_summary_counts_match_the_table` 逐行数出来核，不改就是两个真相。D1 的红线**独立成立**（weibo/news 首次抓取），不随 NET-03 解除——合并读会误以为红线全清 |
| `docs/V041-BATCH2-COMPLETION.md` | §一 `88/89 · 1 blocked · 停机条件②` → `89/89 = 88 verified + 1 skipped · 停机条件①`（保留一句「原记②」的更正说明）；§四 NET-03 单标已关闭；§五 11 张 UI 卡的共同问题标为已裁、余 26 张待复核；§七.1 补 DEC-031 的采纳与尺子硬伤 | 完成态报告是这批的对外真相，停机条件变了不改就过期 |
| `docs/FLINT-V041-B2-DONE` | `88/89 verified，NET-03 blocked（等 owner 三选一）` → `89/89 = 88 verified + 1 skipped_by_owner`，注明原记② | 同上；且这行是下一轮 worker 的第一眼 |

`docs/blocked/E2E-REALSOURCE.md` **仍未改**——它记的是当时的实况，
且 DEC-033 没有点它；改它要么由 steward 建卡时一并处理，要么等 owner 一句话。

## 6. 全局门（本轮实跑）

```
ruff check . --no-cache          → All checks passed!
mypy --strict flint              → Success: no issues found in 299 source files
pytest -q                        → 3661 passed（落地前 3652，本轮 +9）
cd web && npm test -- --run      → 74 files / 745 passed（未动前端源码）
cd web && npx tsc --noEmit       → 2 条既有错（WorkbenchSwitch 的 ?raw），零新增
node tools/check_design_constraints.mjs web → 4 处（既有已登记缺口 S1-COMMON-STATES-MISSING）
python tools/check_fe_be_parity.py          → 62 条发现 · 未装配 51 · 建不起来 0
```

**中途红过一次，非本轮改出来的**：`test_v041_ledger_has_no_unpaired_event` 报
`('V041-BATCH2-DONE', 'verified')` 未配对——第 2 批收工时那张收工卡**只写了
`verified`、漏了 `started`**，而收工前最后一次全局门跑在那行落盘**之前**，
所以它从没被量到。按 2026-08-03T21:47:30Z 那次同因同修法补配对行
（append-only，历史行一字未改），补后 11 绿。
**这是同一个坑的第二次**：收工四步（报告→标记→删锁→结束）里没有「补 started」这一步，
也没有「补完再跑一次门」这一步。已登记在 §7。

禁用词自检：六词逐个扫过本文件，0 命中。

## 7. 登记未做

1. **DEC-033② 的机读卡未建**（steward 的活，理由见 §5）；
2. **`DEC-032` 的失效条件没有机器守卫**——「装配落地后这 11 屏要切到真数据」
   目前只写在文档里。装配卡完成时若没人记得回来切，屏上会**永远显示「接口未提供」**，
   而后端明明已经通了。建议装配卡带一条判据：`backend_not_assembled == 0` 时，
   若 UI 组件仍走 `NotProvided` 默认路径则红。这条**本轮没做**，因为它属装配卡的验收面。
3. **`docs/前后端对账表-v041.md` 未重生成**（数没变，见 §3.4），
   但装配卡做完后**必须重跑** `python tools/check_fe_be_parity.py` 刷新它。
4. **收工四步缺一步，已第二次踩**（见 §6）：收工卡自己的 `started` 行没人补，
   且最后一次全局门跑在收工行落盘之前，于是台账配对判据**恒在下一轮才红**。
   两种修法（收工时一次写两行 / 收工行落盘后再跑一次门）都要改 `worker.md` 的
   收工步骤，**改动面大于本轮任何一张卡的 outputs**，故按 §六.1 停下登记，不自行改。
