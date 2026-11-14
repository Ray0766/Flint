# UIX-01 · S1 三件通用件 + 四个页面接入

**卡** `docs/steward/tasks-v041-b3.json#UIX-01` · **cycles 2** ·
**self_review = true** → §5 · **owner_review = false** · **依赖** 无

## 1. 装载清单

卡面 UIX-01 · `docs/blocked/S1-COMMON-STATES-MISSING.md` ·
`tools/check_design_constraints.mjs` 的 A6 规则与 `scanTree` ·
`tests/v041/test_design_constraints.py#KNOWN_GAPS` ·
四个页面与 `web/components/DemoFlow.tsx` 的取数段 ·
`web/components/shell/{Screen,NotProvided}.tsx`。约 14k tokens，预算 40k 以内。

## 2. 三件建出来，四态互不相同

| 情形 | 组件 | `data-screen-state` | 该做什么 |
|---|---|---|---|
| 请求在路上 | `LoadingSkeleton` | `loading` | 等 |
| 查过了，一条都没有 | `EmptyState` | `empty` | 去创建内容 |
| 出错了 | `ErrorState` | `failed` | 去查日志 |
| 接口没挂 / 没有后端 | `NotProvided`（既有） | `not_provided` | 去挂路由或配后端 |

两处**NEVER 由组件编**：空态的 `hint`、错误态的 `detail`。
不给就不画，而不是填「暂无数据」「未知错误」——那两句既不真也没用，
且会盖住调用方本来能给出的那句真话。

`EmptyState` 的注释里写死了它**只用于「查过了确实为空」**（`WIRE-03` 登记的那条），
并列出与 `LoadingSkeleton` / `NotProvided` 的分工——不写清楚，
下一个人会拿它去画「还没查」。

## 3. 四个页面各按**自己的机制**接，不套模板

| 页面 | 加载态在哪 | 为什么 |
|---|---|---|
| `deliverables/[id]/export` | 已有 `pending`，换成通用件 | 它本来就有真加载态，只是自造的一行提示 |
| `deliverables/[id]` | **同目录 `loading.tsx`** | 它是 **async 服务器组件**：`await` 完才返回 JSX，**内部没有「正在加载」那一刻可渲染** |
| `demo` | `DemoFlow` 里补 `run()` 包壳 | 取数在那儿，不在 page |
| `jobs/[id]` | `status === null` = 还没收到第一个事件 | SSE 屏 |

第二行是本卡最要紧的判断。硬在 `page.tsx` 里写 `if (loading)` 是一段
**永远进不去的死分支**——而 A6 自己的注释就写着「硬凑的死分支比没有更坏」。

## 4. 接的过程中撞出一个真缺陷：`DemoFlow` 一次失败卡死整屏

```ts
async function loadPlaza() {
  setBusy(true);
  setClusters(await fetchPlazaHot(day, opts));   // ← 抛了就到不了下一行
  setBusy(false);
}
```

**四个 handler 全是这个形状，一处 `catch` 都没有。** 请求失败时
`setBusy(false)` 永远执行不到——屏幕**永久停在忙碌态，而且一个字都不说**。
`busy` 原本也只画了一个 `hidden` 的占位符，用户什么都看不到。

这不是「少了个错误提示」，是**一次失败把整屏卡死**。
已补 `run()` 包壳（`try/catch/finally`），后端原话原样留下。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_common_states.py tests/v041/test_design_constraints.py -q → 42 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3777 passed（TYPE-04 收卡时 3764，本卡 +13）
            cd web && npm test -- --run → 74 files / 750 passed
            cd web && npx tsc --noEmit  → 只剩 2 条既有错，本卡零新增
            node tools/check_design_constraints.mjs web → **11 条规则 0 处违规**
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 建三件 | `test_the_three_components_exist`、`test_each_state_has_its_own_state_name`（判等值）、`test_the_empty_state_says_it_is_only_for_checked_and_really_empty`、`test_neither_state_invents_a_message`、`test_the_error_state_is_announced_and_the_loading_one_is_polite` |
| ② 四页接入 | `test_all_four_pages_reach_a_common_state_component`、`test_the_server_component_uses_the_route_convention`、`test_the_demo_flow_no_longer_dies_silently_on_a_failed_request` |
| ③ 三态互不混用 | `test_each_state_has_its_own_state_name` + A6 规则自身（空态被当错误态就判红） |
| ④ 删 `KNOWN_GAPS` 四行 | `test_the_known_gaps_registry_is_empty_now`（删空了；**留一行都不行**——那是「登记了一个不存在的缺口」） |
| ⑤ A6 归零 | `test_the_scanner_reports_zero_violations` + `test_no_rule_went_blind_while_we_made_it_green`（**阴性对照**：归零不许靠让规则落不到文件换来） |
| （自加） | `test_the_existing_assertion_surfaces_were_not_touched` |

**② 改既有文件六处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `web/app/jobs/[id]/page.tsx` | 三态接入；失败处**断言面与通用件并存** | 卡上 outputs |
| `web/app/deliverables/[id]/export/page.tsx` | 自造的 pending 行 → `LoadingSkeleton`（`data-export-pending` 原样保留） | 卡上 outputs |
| `web/components/DemoFlow.tsx` | 补 `run()` 包壳 + 三态渲染 | **取数在这里，不在 page**。卡面 outputs 只写了 `web/components/shell/`，但四页接入这件事绕不开它——已在此登记 |
| `tools/check_design_constraints.mjs` | `scanTree` 连同目录 `loading.tsx`/`error.tsx`/`not-found.tsx` 一起看 | 不认这个约定，A6 会**逼 async 服务器组件写死分支**，与它自己的注释矛盾。**不在卡面 outputs，已登记** |
| `tests/v041/test_design_constraints.py` | `KNOWN_GAPS` 四行 → 空集（四条各自怎么解的写进了注释） | 卡上 outputs |
| `web/messages/{zh,en}.json` | +6 词条 | 裸中文会被 i18n 判据拦下 |

**③ 变异考 6 咬住 + 假变异对照绿，其中两条是我自己写弱的**

| 变异 | 判据 |
|---|---|
| ① 空态与错误态共用一个状态名 | 红 |
| ② 错误态编「未知错误」兜底 | 红 |
| ③ `role="alert"` → `data-role="alert"` | 红——**第一版没红**，见下 |
| ④ `DemoFlow` 的 `catch` 被摘掉 | 红 |
| ⑤ 有一个 handler 漏掉包壳 | 红 |
| ⑥ `loading.tsx` 去掉默认导出 | 红——**第一版没红**，见下 |
| ⑦ 假变异对照：只改一句注释 | 全绿 |

- **③ 第一版**判的是子串 `role="alert"`，而 `data-role="alert"` **里面也含它**——
  那个属性对读屏软件毫无作用，判据却放行。改成带边界的正则。
- **⑥ 第一版**只判 `loading.tsx` 存在。**Next 只认默认导出**：
  文件在、组件在，但不是 `export default` 的话框架根本不会用它，
  等于没有加载态——而「文件存在」那条判据照样绿。

**另一处被既有判据当场拦下**：我把失败渲染整块换成 `ErrorState`，
`screens.test.tsx` 立刻红——它要 `data-job-failed` + `job-failed` 类 + 原因原文。
**改样式 NEVER 顺手改断言面**，这是我自己写过的纪律。
最终两块并存：断言面归断言面，通用件提供 `role="alert"`。

**④** 装载约 14k tokens；**⑤** 禁用词六词 0 命中。

## 6. 登记未做

1. **`ScreenFetchState` 还没退役**。`WIRE-03` 建它时就登记了「S1 通用件建好后应被替掉」。
   本卡建了三件，但**没有替换**——那要动 `WIRE-03` 接的四张屏，
   属另一次改动面。建议 `UIX-02` 或单开一张卡一并做。
2. **S1 五件还差两件**：`NotFound404` · `SseDisconnectNotice`（卡面只要前三件）。
   后者与 `docs/blocked/SSE-DISCONNECT-IS-SILENT.md` 是同一件事——
   **只建组件而不加那个状态，组件永远收不到 `true`**。
3. **A6 认约定文件这一改超出卡面 outputs**（`tools/`）。不改则本卡的
   acceptance⑤ 无法诚实达成——只能靠把服务器组件改写成客户端组件，
   那是让尺子指挥架构。已在此写明，若 steward 认为该单开一张卡，本节即卡面草稿。
