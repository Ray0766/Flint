# WIRE-02 · demo 栈改用装配后的 app + 修掉报告屏恒 500

**卡** `docs/steward/tasks-v041-b3.json#WIRE-02` · **cycles 1（oneshot）** ·
**self_review = true** → §5 · **owner_review = false**
**依赖** `WIRE-01`（verified）

## 1. 装载清单

卡面 WIRE-02 · `docs/blocked/FE-DEMO-ENV-FLINT-API-BASE.md` 全文 ·
`harness/demo_server.py:176-246` · `start-demo.ps1` 的 `$frontCmd` 段 ·
`web/` 的 `process.env` 读取面（grep）· `.ui-probe/fe_smoke.json` 的报告屏两行。
约 8k tokens，预算 40k 以内。

## 2. 两件事，一个根

**一**：`demo_server.build_app()` 原先各屏各造一个 `create_*_app` 再
`include_router`，七族的清单与 `flint/api/app.py` **各写各的**——两个真相。

**二**：`start-demo.ps1:158` 只设了 `NEXT_PUBLIC_FLINT_API`（客户端那份），
没设 `FLINT_API_BASE`（服务端那份）。服务器组件基址为空 → Node 侧
`fetch("/deliverables/…/blocks")` 是相对 URL → `Failed to parse URL` → 报告屏恒 500。

**根是同一件**：「配齐了没有」这件事**没有任何判据在量**，全靠人记着。
所以本卡的核心判据量的是**覆盖关系**，不是某一行在不在。

## 3. 改法

`build_app()` = `create_app(DSN)`（拿到 42 条）+ demo **独有**的三族
（`combo` / `analysis` / `interventions`）。这三族在可部署应用里挂不上
（缺 `role_resolver` 与模型配置，`WIRE-01` §4），而 demo 有——
`lambda _u, _o: "owner"` 在 demo 里是**明知故犯的口径**，在可部署应用里是安全洞。
**这条界线就画在 `build_app()` 这个函数里**，并由判据钉住
（`test_the_demo_stack_adds_exactly_the_families_it_alone_can_wire` 判等值）。

加的时候走**同一个装配器**（`_Assembler`），撞车照样 raise——
NEVER 因为「这是 demo」就少一道闸。

demo 栈路由数：**54**（装配 42 + demo 三族的 8 条 + `/categories` 等）。

## 4. 判据 NEVER 只断言那行环境变量存在（卡面 acceptance③ 点名）

核心那条判的是**前端读的环境变量 ⊆ 启动脚本设的**：

```
read  = grep process.env.X  in web/app/**.tsx + web/lib/**.ts
read -= {NODE_ENV, VERCEL_URL, PORT}          # Next 自己给的
assert read - declared == set()
```

只断言 `'FLINT_API_BASE' in script` 拦不住下一次：**前端新读一个变量
而脚本没跟上时，那种写法照样绿**。变异②（把变量名改成 `FLINT_API_URL`）
证明覆盖判据咬得住，而字面判据咬不住。

另有**真发请求**两条：in-process `TestClient` 打
`/deliverables/del-demo-fixture-report/blocks`（本机库在跑，实测非 500，未 skip）；
以及 `.ui-probe/fe_smoke.json` 的真栈取证（playwright 跑出来的）。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_demo_stack_wired.py -q → 10 passed（0 skipped，库在跑）
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3688 passed（WIRE-01 收卡时 3676，本卡 +10 +2 修复）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① demo 栈用装配后的 app，NEVER 各造一个 | `test_the_demo_stack_starts_from_the_assembled_app`（判包含）、`test_the_demo_stack_adds_exactly_the_families_it_alone_can_wire`（判等值）、`test_the_demo_stack_no_longer_builds_its_own_copies`、`test_a_demo_family_that_collides_with_the_assembled_app_raises`（阴性对照） |
| ② 修掉报告屏恒 500 | `test_both_halves_of_the_base_url_are_set_because_each_serves_one_side`、`test_the_probe_artifact_shows_the_report_screen_at_two_hundred` |
| ③ 真发请求，NEVER 只断言那行存在 | `test_the_report_screen_endpoint_answers_without_a_five_hundred`（真请求）、`test_the_frontend_reads_no_env_var_the_start_script_forgets_to_set`（覆盖判据） |
| ④ 关闭问题单 | `test_the_ticket_is_closed_with_a_banner_and_a_date`、`test_the_smoke_test_gate_that_watched_this_ticket_lets_go` |

**② 改既有文件四处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `start-demo.ps1` | `$frontCmd` 里补 `$env:FLINT_API_BASE`（并列既有的 `NEXT_PUBLIC_` 那份） | **卡上 outputs**；这一行就是问题单末尾给出的修法 |
| `harness/demo_server.py` | `build_app()` 从 `create_app(DSN)` 起；不再自造 views/deliverables/categories/deref；三族走 `_Assembler`；清掉 6 个变成未用的 import | **卡上 outputs** |
| `docs/blocked/FE-DEMO-ENV-FLINT-API-BASE.md` | 顶部加关闭横幅（日期 + 修法 + 卡号 + 「另配了一条覆盖判据」），原文一字未改以 `---` 隔开 | **卡上 acceptance④** |
| `tests/v041/test_deref_frontend.py` | `test_the_deref_app_is_mounted_somewhere_reachable` 从「断言 demo 源码里有 `create_deref_app` 这个词」→「问建起来的应用要路由表」 | 本卡的改动让那个词不再出现在 demo 源码里（deref 改由 `create_app` 统一挂），旧判据**恒红**。而它本身就是「只断言语句存在」那一类——对「挂了个空 router」「被遮蔽」全绿。**换成量真路由表是把它修对，不是绕过它** |

**未改**：`flint/api/app.py`。demo 复用装配器是靠 import `_Assembler`，
没有给 `create_app` 加参数——那会让改动面超出本卡 outputs（§五.1）。
**登记**：一个公开的 `extra=` 接缝比 import 私有名干净，见 §6。

**③ 变异考 5 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 删掉补上的那行环境变量 | 红 |
| ② 变量名写错（`FLINT_API_BASE`→`FLINT_API_URL`） | 红——**字面判据咬不住这条，覆盖判据咬住了** |
| ③ demo 退回自己造 app | 红 |
| ④ 三族绕过装配器直接 `include_router` | 红——**但第一轮幸存**，见下 |
| ⑤ 单子横幅去掉关闭标记 | 红 |
| ⑥ 假变异对照：只改一句注释 | 全绿 |

**④第一轮幸存**与 `WIRE-01` 的②同一课：**守卫只在真撞车时说话**，
而 demo 那三族此刻恰好不与谁撞车，两条路径给出的路由表一样。
补了阴性对照 `test_a_demo_family_that_collides_with_the_assembled_app_raises`
（monkeypatch 让 combo 去抢 `/categories`）后咬住。

**④** 装载约 8k tokens；**⑤** 禁用词六词 0 命中。

## 6. 登记未做

1. **`flint/api/app.py` 缺一个公开的「额外族」接缝**。demo 现在 import 私有的
   `_Assembler` 并自己重建 `claimed` 字典。给 `create_app` 加一个
   `extra: Sequence[FastAPI] = ()` 参数更干净，**但那超出本卡 outputs**，
   按 §五.1 登记不做。`WIRE-05` 或 `WIRE-06` 顺手做掉即可。
2. **报告屏仍有 10 条控制台报错**：`docs/blocked/DEMO-REPORT-REFS-NOT-SEEDED.md`，
   由 `FIX-02` 处置。本卡判**等值**（== 10），数字一变就要有人回来确认——
   NEVER 判零（会把别人的活算成本卡失败），也 NEVER 不判（会混进「本卡修好了」）。
3. **`start-demo.ps1` 的另外两处 `$env:` 块**（后端与 worker）本卡未动：
   它们设的是 `FLINT_DEMO_DSN` 等，与前端基址无关。
