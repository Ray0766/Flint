# WIRE-03 · 九张屏从「接口未提供」切到真数据

**卡** `docs/steward/tasks-v041-b3.json#WIRE-03` · **cycles 2** ·
**self_review = true** → §5 · **owner_review = true** → §6
**依赖** `WIRE-01`（verified）· `WIRE-02`（verified）

## 1. 装载清单

卡面 WIRE-03 · 工单第 3 批 §3 · 九张屏的 `page.tsx` · 对应组件的入参类型段 ·
装配后应用的端点实响应（**实测**，见 §2）· `web/lib/` 既有客户端的写法
（`viewsClient.ts`）· `web/messages/{zh,en}.json`。约 15k tokens，预算 40k 以内。

## 2. 开工第一件事：探端点。切了四张，五张停下登记

「端点挂上了」不等于「切过去就诚实」。实测装配后的应用：

| 屏 | 端点回什么 | 切过去诚实吗 |
|---|---|---|
| account | `profile: {status:"not_checked"}` | **是**——端点在，它说这项它没查过 |
| billing | `{status:"not_enabled", reason:"计费未配置（…）"}` | **是**，且带后端给的理由 |
| settings | `{"lang":"zh","region":"CN","options":{…九区…}}` | **是**——**声明过的默认值就是真答案** |
| project-overview | `404 {"code":"NOT_FOUND"}` | **是**——带 `code`，与框架的 404 不是一回事 |
| favorites / design / workbench / share | `{"items": []}`，来自**内存件** | **否，是假空态** |
| quality / pack | `503 FAMILY_NOT_CONFIGURED` | 端点诚实，但屏还没有对应渲染 |

**第五行是本卡最要紧的发现**：迁移 34 张表里没有 favorites / templates /
share_links，那几族挂的是内存字典。切过去，屏上会写「还没有收藏」——
而真相是「这个功能还没有库」。`DEC-032` 的原话正是这件事。

停下登记：`docs/blocked/WIRE-03-EMPTY-FROM-A-STORE-THAT-HAS-NO-DATABASE.md`
（owner 三选一；worker 取第 1 种的前半：**先切诚实可切的，其余留原态**）。

判据判**等值**（`test_the_held_back_screens_are_exactly_the_registered_ones`）：
多切一张 = 造了个假空态，少切一张 = 该切的没切，两种都会红。

## 3. 四种结果，四个名字

卡面 acceptance③ 继承第 2 批那条纪律。本卡把它推到取数这一层——
**「正在查」是第四种**，之前不存在：

| `data-screen-state` | 说的是 | 谁给的 |
|---|---|---|
| `loading` | 正在查 | 请求在路上 |
| `not_provided` | 这条路由没挂上 | 框架的 404（`{"detail":"Not Found"}`，**没有 `code`**） |
| `not_configured` | 挂上了，但背后没有库 | 503 `FAMILY_NOT_CONFIGURED` |
| `failed` | 后端回了错误状态 | 其余非 2xx，**原样带出它自己的说明** |

**两处 NEVER 合并**：

1. `not_provided` 与 `not_configured`——前者要人去挂路由，后者要人去配后端；
2. **带 `code` 的 404 与框架的 404**——`BE-09` 的「404 不 403」口径就是带 `code` 发的。
   混起来，「分享链接不存在」会被显示成「这个功能没做」。

## 4. 适配层：后端的「没查过」是对象，组件的是 `null`

实测两边不是一个形状：

| | 后端 | 组件 |
|---|---|---|
| 主体 | `principal: {kind, id}` | `principalId: string` |
| 没查过的列表 | `{"status": "not_checked"}`（**对象**） | `null` |

第二行是要害：**不翻译直接喂**的话，那个对象是真值，
组件会把「没查过」渲染成「查过了、有内容」——正好是本批一路在治的那个错。
`web/lib/screenAdapters.ts` 只改形状：NEVER 补默认值、NEVER 加总
（金额恒是字符串原样转出）。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_ui_wired_live.py -q → 12 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3702 passed（WIRE-02 收卡时 3690，本卡 +12）
            cd web && npm test -- --run → 74 files / 750 passed（第 2 批出口 745，本卡 +5）
            cd web && npx tsc --noEmit  → 只剩 2 条既有错，本卡零新增
            node tools/check_design_constraints.mjs web → 4 处（既有已登记缺口）
            python tools/check_fe_be_parity.py → 54 条
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 九张屏切真端点 | `test_the_wired_screens_actually_call_their_endpoint`、`test_the_held_back_screens_are_exactly_the_registered_ones`（判等值）、`test_the_ticket_explains_each_held_back_screen`。**做到四张**，五张登记，理由见 §2 |
| ② 零 NotProvided、NEVER 藏起来 | 四张切了的屏源码里没有 `={null}`（`test_ui07/08` 两条改判）；未切的五张**不是藏，是登记在案** |
| ③ 三态 NEVER 合并 | `test_the_four_outcomes_have_four_different_state_names`（判等值）、`test_not_provided_and_not_configured_are_never_merged`、`test_a_backend_404_with_a_code_is_not_read_as_not_provided`、`test_loading_is_never_rendered_as_the_empty_or_missing_state` |
| ④ 既有前端测试不倒 | vitest **750 passed / 74 文件**（745 → 750，无一条净减） |

**② 改既有文件八处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `web/app/{account,billing,settings/locale,projects/[id]}/page.tsx` | 传 `null` → `useScreenData` 取数 + `ScreenFetchState` 分四态 | **卡上 outputs**，本卡主体 |
| `web/messages/{zh,en}.json` | +5 个 `screen.*` 词条（两侧对称、中英不同串） | 新的「正在查 / 没配 / 出错」三态要有文案，裸中文会被 i18n 判据拦下 |
| `web/__tests__/app/ui{07,08,11}.test.tsx` | 「一个请求都不发」→「发且**只发一个**，四态各显示各的」 | 那几条判的是**未装配期间**的正确行为（`DEC-032`），装配落地后自动失效。`ui11` 那条保留了「**只发一个**」这半条——它比「发了」更要紧 |
| `tests/v041/test_ui07.py` · `test_ui08.py` | 同上的 pytest 侧 | 同上 |
| `tools/check_fe_be_parity.py` | `frontend_calls` 先剥掉 `import` 里的模块路径 | **本卡撞出的纯误报**：`from "../components/account-billing/AccountPanel"` 被当成端点，报「前端要 `/account-billing/AccountPanel` 而后端没有」。模块路径与端点路径长得一样，一个是磁盘上的文件、一个是 HTTP 上的资源。这把尺子自己的 docstring 写着「报一个量不准的差异比不报更糟」 |
| `docs/前后端对账表-v041.md` | `--write` 重生成（54 条） | 表是跑出来的，不是手写的 |

**未改**：`web/components/`（不在本卡 outputs）。因此
`ScreenFetchState` 放在 `web/lib/` 而不是 `components/shell/`——
**`UIX-01` 正要在那里建 S1 通用件**，现在放同名同职的东西必然撞车。见 §7。

**③ 变异考 5 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 取数中折进「接口未提供」 | 红 |
| ② 带 `code` 的 404 也当「接口未提供」 | 红 |
| ③ 503 折进 `failed` | 红 |
| ④ 适配层不翻译「没查过」对象 | 红 |
| ⑤ 一张该切的屏退回不取数 | 红——**但第一轮幸存**，见下 |
| ⑥ 假变异对照：只改一句注释 | 全绿 |

**⑤第一轮幸存**：判据写的是 `"useScreenData" in code`，而把屏改成
`const state = {kind:"not_provided"}` 之后 **`import` 那行仍然含这个词**，
判据照样绿——取数没了，判据不知道。改成判**调用点**
（`useScreenData<` / `useScreenData(`）后咬住。
这是本批第三次撞上同一类问题：**扫标识符 ≠ 判行为**。

**④** 装载约 15k tokens；**⑤** 禁用词六词 0 命中。

## 6. owner_review

1. **只切了四张**，五张停在原态。三选一在
   `docs/blocked/WIRE-03-EMPTY-FROM-A-STORE-THAT-HAS-NO-DATABASE.md`。
   **我取的是「先切诚实可切的」**——若你要一次切完（接受假空态），
   说一声即可，改动很小（每屏一行）。
2. **`quality` / `pack` 两屏还没有 `not_configured` 的渲染**：
   端点已诚实回 503，但那两屏本卡未切。它们归 `UIX-01` 的 `ErrorState` 一起做更省。

## 7. 登记未做

1. **`ScreenFetchState` 是临时接缝**。`UIX-01` 建完 S1 五件
   （`LoadingSkeleton` / `EmptyState` / `ErrorState` / `NotFound404` /
   `SseDisconnectNotice`）之后，它应当被替掉，`web/lib/` 只留取数与适配。
   **`EmptyState` 的语义 MUST 写清它只用于「查过了确实为空」**，
   NEVER 兼职「没查过」——本卡整张单说的都是这件事。
2. **`WIRE-04` 取证**：四张切了的屏要重跑 `.ui-probe`；未切的五张取证仍是原态，属预期。
3. **PUT `/settings/locale` 没接**：本卡只接了读。写要处理乐观更新与失败不回滚
   （组件里 `status="saving"/"failed"` 已备好），属下一张卡。
