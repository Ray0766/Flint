# AUDIT-01 · 前后端契约全表对账器

**卡** `docs/steward/tasks-v041-b2.json#AUDIT-01` · **cycles 2**（`oneshot=false`）·
**self_review = true** → §7 · **owner_review = false**
**依赖** 无

## 1. 装载清单

卡面 AUDIT-01 · 交付包 `README.md` 的路由表全文 + Interactions 段 ·
`docs/handoff_gap_v04.md` 全文 · `flint/api/` 全部模块的路由装饰器（扫描，不逐个读）·
`web/app/` 页面树 · `web/lib/*.ts` 的客户端 · `web/lib/types.ts` ·
`tools/check_locale_seam.py`（BL-09 那把尺的窄化理由）·
`web/design/mock-identity/mockIdentity.ts`。约 14k tokens，预算 40k 以内。

## 2. 头条发现：**62 条里 51 条是「写好了没挂上」**

```
扫描面：后端路由 62 条 · 前端路由 6 条 · README 期望行 16 行
共 62 条发现
  ① 前端要而后端没有                    0 条
  ② 后端有而前端没接 · 未装配          51 条   ← 全部集中在这里
  ② 后端有而前端没接 · 已装配未调用      0 条
  ③ 字段对不上 · 真漂移                 1 条
  ③ 字段对不上 · 前端没建类型            9 条
  ④ 扫不动 · 本表没核对                 1 条
```

`flint/api/app.py` 至今只挂了 `/categories` 一条。其余 **51 条路由全部够不到**——
包括本批 BE-01~11 新建的十一族端点，也包括 v0.4 就写好的 deref、interventions、
views、compose 那些。

**这件事在任何单卡的验收里都看不见**：每张卡的测试都是拿自己的
`create_*_app` 直接造 `TestClient` 跑的，造得出来 ≠ 挂上了。
我在 BE-01~11 每张 trace 的「登记未做」里都写了一句「没挂进任何 ASGI 应用」——
写了十一遍，也没有任何一条判据会因此变红。**全表对账是第一个会红的地方。**

（`--json` 出机读版；`python tools/check_fe_be_parity.py --write` 重生成表。）

## 3. 卡面要三类，本器出六种

三类里有两类各自分成了两种，因为**混在一起的那两种，修法完全不同**：

| 卡面类 | kind | 分开的理由 |
|---|---|---|
| ② | `backend_not_assembled` | 要**装配**（改 app.py） |
| ② | `backend_unused_by_frontend` | 要**接线**（改前端） |
| ③ | `field_mismatch` | 前端建了类型却少字段 → 要**对齐** |
| ③ | `frontend_untyped_response` | 前端根本没建类型 → 要**新建** |

第六种 `dynamic_path_not_checked` 不属任何一类，它是**本器扫不动的那部分**：
`/projects/${id}/${kind}` 这种动态派发，静态扫描判不出它最终打到哪条路。
**扫不动就说扫不动**——悄悄丢掉的话，这张表会被读成「全都核对过了」，而它没有。

## 4. 把尺子调窄的三次（每次都有理由）

第一版跑出 74 条，其中 22 条是「前端要而后端没有」——**全是误伤**：

| 误伤 | 真相 | 修法 |
|---|---|---|
| `/plaza`、`/topics`、`/projects` | 页面 `href` **导航**，不是 API 调用 | 只扫 `web/lib/` 的客户端层 |
| `/jobs/job-9/events`、`/deliverables/del-9` | 测试与 mock 里的**样例数据** | 跳过 `*.test.*` 与 `mock/` |
| `/gate/{}` | README 那句「仓库路由习惯亦可用 /gate/[jobId]」说的是**页面路由** | 只取跟在 HTTP 动词后面的路径 |

窄完之后 ①=0，而那是**真结果**：README 点名的端点这批全补齐了。

这三次调整照的是 BL-09 那把尺自己的话：**「判据必须窄，否则没人再看它」**。
一把报 22 条假缺口的尺子，第二天就会被当成噪音关掉。

另外两处精度修正：
- 路径三方言归一时 `${encodeURIComponent(jobId)}` 的右括号必须留在匹配里，
  否则归一不掉，这条调用会被报成「后端没有」；
- 响应字段**按 handler 取**，不按模块合成——合成之后 `views.py` 的五条路由
  共用一套键，于是「字段对不上」报的是哪条路都对不上，那种报告没法拿来改代码。

## 5. 变异考：二十一个，一个假变异，零真存活

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 路径不归一 | §4 | **10 failed** ✓ |
| ② 归一归过头 | §4 | **6 failed** ✓ |
| ③ 查询串连路径一起丢 | §4 | **16 failed** ✓ |
| ④ `api_route` 合成一行 | 方法级缺口 | **2 failed** ✓ |
| ⑤ 装配面当成全挂上了 | §2 | **2 failed** ✓ |
| ⑥ 把各卡工厂也算已装配 | §2 | **2 failed** ✓ |
| ⑦ README 表整张丢 | 期望面 | **5 failed** ✓ |
| ⑧ 没写端点的行也造一个 | 期望面 | **2 failed** ✓ |
| ⑨ 连测试与 mock 一起扫 | §4 | **全绿** ✗（`web/lib/` 下本就没有 `mock/` → **假变异**）→ 补判据 + ⑨′（真去掉 `.test.` 跳过）**3 failed** ✓ |
| ⑩ 连注释里的路径也算 | §4 | **2 failed** ✓ |
| ⑪ 字段键按模块合成 | §4 | **3 failed** ✓ |
| ⑫ 两种字段问题混成一类 | §3 | **2 failed** ✓ |
| ⑬ 扫不动的路悄悄丢掉 | §3 | **2 failed** ✓ |
| ⑭ 空报告不说扫描面为空 | 空/未知 | **全绿** ✗（判据被邻居那段解释文字喂饱）→ 改判那句警告本身后 **1 failed** ✓ |
| ⑮ 报告不报条数 | 可核对 | **2 failed** ✓ |
| ⑯ 发现里不带位置 | 可定位 | **1 failed** ✓ |
| ⑰ 包不在时报一个像实测的数 | §6 | **1 failed** ✓ |
| ⑱ 屏数不去重 | §6 | **1 failed** ✓ |

⑨ 是本轮第五个假变异（`web/lib/` 下根本没有 `mock/` 目录，去掉那行不改变行为）；
**但它顺带揭出一个真洞**：当时没有任何判据拦着「把测试文件当成前端调用」。
补了一条合成目录的阴性对照，⑨′（真去掉 `.test.` 跳过）当场红 3 个。

⑭ 是「判据被邻居喂饱」的又一例（本轮第九次）：空报告那段解释文字里
也写着「扫描面为空」五个字，于是判这五个字的判据永远绿。改判那句警告本身
（「不能被当成…证据」）之后才真的钉住。

## 6. acceptance④：更正一处错误登记（**改了既有文件**）

**改前**（`docs/handoff_gap_v04.md` 开头）：

> **本文件是登记，不是实测报告。** `design_handoff_flint_web/` 包**不在本仓库**
> （已核：仓库根目录无该目录）。因此下列数字全部来自工单清单与既往审计，
> 逐条标 `[待核实]`。

**改后**：加了一段 `> **更正（AUDIT-01 @2026-08-05）**`，写明原判是错的、
包实际在 `Claude design Flint 前端设计/Flint 应用 · 20 屏/design_handoff_flint_web/`，
并把四处 `[待核实]` 换成实测值。

**为什么非改不可**：那句话是**事实错误**，而且它正被当作依据使用——
文档里三处「包不在仓库 → 本轮不做」都挂在它下面。留着它，后面每一张
碰这个包的卡都会照着它跳过实测。

实测值（尺子 `measure_handoff_package`，可重跑）：

| 项 | 原登记 | 实测 @2026-08-05 |
|---|---|---|
| 屏数 | `[待核实]` 20 屏两轨 | **22 个屏标记**（`data-screen-label` 去重，4 个批次文件） |
| inline mono | `[待核实]` 456 处 | **1114 处** |
| 带 `tabular-nums` | `[待核实]` 仅 14 处 | **1108 处** |
| ⚠ 图标 | `[待核实]` 23 处 | **0 处** |
| i18n key | `[待核实]` 零 key | **0 处**（与原登记一致） |

三处数字与原登记差得很远（456→1114、14→1108、23→0）。
原登记自己写着「NEVER 把清单数字写成我实测的结果」——那条纪律是对的，
错的只是「包不在仓库」这个前提。

**屏数 22 与 README 自称的「20 屏」都对**，说的是两件事：多出来的两个是
`404` 与 `字段对照表`，它们确实是屏，但不在 20 屏总表里。写清楚，免得下一个人
以为哪边数错了。

判据钉住它：`test_the_measured_numbers_are_reproducible` 断言文档里的三个数
与尺子当场量出来的一致——**数字漂了会红**，不靠人记得回来改。

### 一处**没改**的东西（登记）

`docs/handoff_gap_v04.md` 第 54 行有一句「代码里的 ⚠ **等**图标字符」，
「等」在这里是列表尾用法，命中 S2-8 禁用词。它是 **DESIGN-05 那一节的既有文字**，
不在本卡 outputs 内，本卡**不顺手改**（§六.1）。登记在此，由碰那一节的卡处理。

## 7. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_fe_be_parity.py -q → 31 passed
            （基线：collection error，收集期就红）
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: no issues found in 299 source files
            pytest -q               → 3497 passed（BE-11 收卡时 3466，本卡 +31）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 以 README 全表为期望面，与实况双向比对 | `test_the_readme_table_is_parsed_into_expectations`、`test_a_row_that_says_the_endpoint_is_not_built_is_kept_not_dropped`、`test_the_parser_never_invents_an_endpoint`、`test_backend_routes_are_read_from_the_decorators`、`test_frontend_routes_are_read_from_the_page_tree`、`test_frontend_calls_are_read_from_the_source`、`test_the_three_path_dialects_normalise_to_one`、`test_two_different_paths_never_collapse` |
| ② 报三类 | `test_a_wanted_but_missing_endpoint_is_reported`（合成仓库）、`test_an_unmounted_route_is_reported_as_idle_capacity`、`test_a_field_mismatch_is_reported_with_both_sides`、`test_a_drift_and_an_untyped_response_are_two_different_findings`、`test_an_aligned_pair_is_not_reported`、`test_a_page_that_does_not_exist_is_not_invented`、`test_test_files_are_not_mistaken_for_frontend_calls` |
| ③ 对当前仓库跑一次并把结果写进表 | `test_the_table_is_generated_from_a_real_run_not_hand_written`、`test_the_table_lists_every_finding`、`test_the_renderer_marks_an_empty_report_as_empty_not_as_passing`、`test_a_report_with_a_real_scan_surface_carries_no_such_warning`、`test_the_renderer_never_swallows_a_finding`、`test_the_tool_is_runnable_from_the_command_line` |
| ④ 更正错误登记 + 换掉 `[待核实]` | `test_the_handoff_gap_note_no_longer_claims_the_package_is_absent`、`test_the_placeholder_numbers_were_replaced_with_measured_ones`、`test_the_measured_numbers_are_reproducible`、`test_the_measurement_counts_nothing_when_the_package_is_missing` |

**② 无冻结件偏离**：新增两个文件 + 改一个既有登记文档（§6 记了改前/改后/为什么）；
`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
未触碰；零新增依赖（纯标准库）。

**③ 禁用词**：六词在本卡三个产物里 0 命中；一处既有「等」登记未改（§6 末）。

**④ 复用**：路径归一/AST 扫描的写法与 `tools/check_locale_seam.py`、
`tools/check_payment_safety.py` 同形；`--json` 出机读版的约定与 PAY-03 一致。

**⑤ 装载预算**：约 14k tokens，未超 40k。

**⑥ cycles**：卡面 2，实际 1 个连跑回合内完成（含三次窄化返工与变异考）。

## 8. 登记未做

1. **本卡不改 `app.py`**。装配是 51 条发现的**修法**，不是本卡的 outputs
   （本卡 outputs 是尺子 + 表 + 测试）。硬接进来会让这张卡同时改动
   十一个模块的挂载方式，改动面远大于卡面——按 §六.1 登记，另开一张装配卡。
   **这是本批最值得下一步做的一件事**：51 条闲置里有 11 族是本批刚建的。
2. **字段比对只覆盖静态可见的那部分**。后端取 `*_json()` 里字面量 dict 的键，
   前端取 `types.ts` 的接口成员；`{**base, ...}` 这种动态拼键、
   运行期才知道的字段，**量不到**。量不到的不报——报一个量不准的差异
   比不报更糟，它会让人去改本来对的代码。
3. **openapi 实况没用上**。卡面写的是「与 openapi 实况比对」，
   本器读的是**路由装饰器**（AST）。理由：openapi 要先把应用装起来才生成得出来，
   而 51 条根本没装上——**拿一个装不起来的东西当实况面，量到的会是空**。
   装配卡落地后可以补一条「openapi 与 AST 两个面互相印证」的判据。
4. **v2 屏总表（18 屏）没并进期望面**。本器的期望面只用了交付包 README
   那 16 行。`docs/前端功能说明-v2.md` 的 18 屏总表是**另一份**期望
   （v2 新屏，如收藏图书馆、图谱工作台），两份表的口径不同（一份按路由、
   一份按屏号），合并需要一次口径对齐——登记，属另一张卡。
5. **`backend_unused_by_frontend` 当前恒为 0**，因为已装配的只有 `/categories`
   一条而它正被前端用着。装配卡落地后这一类才会真正开始报东西。
