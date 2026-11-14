# ENTRY-05 · 孤岛清零 + 三个空表

**结论**：**孤岛 6 → 0** · 「路接上了而走不通」1 → 0 ·
`frontend_wants_missing_backend` 0 · `UnwiredKindReason` 空 ·
`field_mismatch` 1 → 0 · `frontend_untyped_response` 3 → 0 ·
图与代码**双向一致**（两个方向都是 0）。
`verify_cmd` 16 条全绿；全局门全绿。

装载：`docs/steward/tasks-v041-b9.json#ENTRY-05` · `docs/trace/NAV-01.md` ·
`assets/screen_graph.json` · `tools/check_reachability.py` · `tools/check_fe_be_parity.py` ·
`flint/jobs/dispatch.py` · `docs/端点分诊-v041.md`
（实测装载 ≈ 26k tokens，预算 40k）

---

## 1 清零靠的是**两张卡真的把功能做出来了**

| 原来红在哪 | 谁做掉的 |
|---|---|
| `/plaza -> /workbenches/[id]` 标着 `blocked`（`POST /workbenches` 拿不到 ok） | `PERSIST-02`：三张表 + 端点落库 + 新建 `GET /workbenches/{id}` |
| `/combo` 是孤岛（「广场上没有多选建组合这个能力」） | `ENTRY-04`：**建的正是那个能力** |
| 项目族四屏 + `/topics/[id]` 是二级孤岛 | 同上——**头一通，整条链跟着通** |

那五屏**自己一行都没改**：孤岛从来不是它们的病。
本卡做的是把两件已经发生的事**如实声明进图**。

**NEVER 靠往 `exempt` 里塞**——判据钉着豁免名单只许有 `/share/[token]` 那一条外链屏。

## 2 只写一边的边，等于没接

补了 `/combo` 的 `reached_by` 之后尺子**照样报它是孤岛**——遍历走的是 `goes_to`。
只写一边的边在图里看起来是接上了，而它一条路都走不通。
这句话已写进 `screen_graph.json` 的 `_never`，下一个人先读到它。

## 3 三条判据翻面，**能力一条都没少**

| 原判据 | 原来量什么 | 现在 |
|---|---|---|
| `..._is_red_today_and_that_is_the_point` | 退出 1（「红着才说明在量」） | 退出 0，**并且**喂一座人造孤岛时它当场变 1 |
| `a_second_level_island_is_not_counted_as_reachable` | 指着一座真的二级孤岛 | 喂**人造图**（删掉头边）→ 那一座立刻退回孤岛；真图里它可达 |
| `every_island_has_a_reason_and_an_open_sheet` | 六座各有理由与开着的单 | 断言清零；**那条循环留着空跑**——下次长出孤岛它就是闸 |

第一条是本卡最要紧的一处：**一把永远绿的尺子与一把被人注释掉的尺子，
从退出码上看一模一样**。只翻成「断言 0」的话，下一个人把 `check()` 改成
`return Report()` 也是绿的。所以加了阴性对照。

## 4 对账器两处真发现（**尺子在读一份虚构的形状**）

### 4.1 `payload=` 不是响应

`PERSIST-04` 往 `POST /projects/{}/analysis` 的 `runner.submit(payload={...})`
里加了 `topic_id`，尺子当场报 `field_mismatch`——而那条端点的响应
**只有 `job_id` 一个字段**，前端类型一点没漂。
照那份报告去改代码的人，会去给一个正确的类型加一个它不该有的字段。

### 4.2 更坏的那一处：`/projects/combo` 的三个「后端字段」**一个都不在响应里**

`card_ids` / `hypothesis` 来自 job payload，`n` 来自一个局部计数器 `counter = {"n": 0}`。
而前端的 `ComboSubmitEcho` **恰好照着这三个字段建了类型**——
于是两边对着一份虚构的形状达成了一致，**尺子报绿**。

这比报错更坏：它把「没人核对过」伪装成了「核对过、没问题」。

**修法**：把取字段的范围收到 `return` 语句能到达的 dict
（`return {...}` 与 `return JSONResponse({...})` / `content={...}` 都算）。
这正是工具文件头一直写着的口径——「后端字段取自 `*_json()` 里字面量 dict 的键」，
而实现是对**整个函数体**做 `ast.walk`。**改的是让实现追上它自己写的契约。**

代价说清楚：响应是 pydantic 模型的那几条现在抽不到键（本来就抽不到，
`return JSONResponse(XxxResponse(...).model_dump())` 里没有字面量 dict）。
`test_types_complete.py` 那条「扫描面塌了」的守卫因此改成
**名单外抽不到才算塌**，名单写死两条并写明理由。

`ComboSubmitEcho` 描述的形状不存在这件事**留着**——真响应是
`{project_id, topic_ids, degraded}`。本卡没有改它（不在 outputs，也不在本卡射程），
它现在不再假绿，而是**不再被这把尺子看见**。**建议给它一张卡。**

## 5 分诊表补一条

`/clusters/{}/verdict`（`PERSIST-04` 新建的读端点）进 B2，写明它**不是没接线的旧账，
是本批新长出来的一条**。B 类 16 → 17，标题与判据里的数字一起改。

## 6 改前 / 改后 / 为什么非改不可

| 文件 | 改前 | 改后 | 为什么 |
|---|---|---|---|
| `assets/screen_graph.json` | 6 座孤岛 + 1 条 blocked | 声明 `/plaza -> /combo`（两个方向）· 去掉 blocked · 六处孤岛标记退场 | §1 §2 |
| `tests/v041/test_reachability.py` | 钉旧数字 | 三处常量翻面 + 三条判据翻面（带阴性对照） | §3 |
| `tools/check_fe_be_parity.py` | 全函数体 `ast.walk` | 只数 `return` 到得了的 dict，且排除 `payload=` | §4 |
| `tests/v041/test_types_complete.py` | 「一个键都抽不到 = 塌了」 | 名单外抽不到才算塌 | §4 代价 |
| `docs/端点分诊-v041.md` · `tests/v041/test_endpoint_triage.py` | B 类 16 | 17 | §5 |
| `docs/前后端对账表-v041.md` | 旧的一份 | `--write` 重跑 | 表是跑出来的，不是手写的 |
| `tests/v041/test_shell_nav.py` · `test_main_chain_walk.py` · `test_add_to_workbench_nav.py` | 断言 `/combo` 无入口 / 孤岛非空 / 那条边 blocked | 逐条翻面并写明谁做掉的 | §1 |

`tools/check_fe_be_parity.py` 在卡面的 **inputs** 里而不是 outputs。
改它的理由：它报的那两条**是它自己的 bug**，而按那份报告去改代码会把对的改坏。
不改的话本卡交出去的是一张「看起来清零、其中两条是假的」的表。

## 7 自审（`self_review=true`）

**① 判据覆盖 acceptance**（四条）：①实况已在 §1 逐条记；②三个空表**同时成立**
（孤岛 0 · `frontend_wants_missing_backend` 0 · `UnwiredKindReason` 空）；
③今天没有走不到的屏，**而「写理由不顶红」那条规矩留着空跑**；
④主链路那条判据在 `test_main_chain_walk.py`，本卡没有削弱它。

**② 清零不是做小分母**：入口数没变（6），豁免名单没变（1 条），
`exempt` 判据钉死；23 屏一屏没删。
**③ 无禁用词**：0 命中。
**④ 装载未超预算**：≈26k / 40k。

## 8 门

```
pytest tests/v041/test_reachability.py -q   16 passed
pytest tests/v041 -q                        3171 passed（余 1 红 = SHIP-09 台账）
ruff / mypy 319 / tsc 0 / vitest 858        全绿
可达性：孤岛 0 · 走不通 0 · 两个方向的边差都是 0 · 单向边 0 · 过期声明 0
对账器：field_mismatch 0 · frontend_untyped_response 0 · frontend_wants_missing_backend 0
分派表：UnwiredKindReason = {}
```

## 9 留给下游

1. `backend_unused_by_frontend` 仍有 **21 条**——**这不是本卡的射程**
   （它量的是「后端有、前端没接」，逐条在 `docs/端点分诊-v041.md` 里有主）。
2. `ComboSubmitEcho` 描述了一份不存在的响应形状（§4.2）。**建议给它一张卡。**
3. `MAIN-CHAIN-HAS-NO-LIVE-ENTRANCE.md` 那张单可以关了——它要的入口
   由 `ENTRY-04` 建出来了。本卡没有动它（不在 outputs），留给收尾卡。
