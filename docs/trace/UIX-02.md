# UIX-02 · 通用件②：`NotFound404` 与 `SseDisconnectNotice`

**卡** `docs/steward/tasks-v041-b3.json#UIX-02` · **cycles 1（oneshot）** ·
**self_review = true** → §5 · **owner_review = false** · **依赖** `UIX-01`（verified）

## 1. 装载清单

卡面 UIX-02 · `docs/blocked/SSE-DISCONNECT-IS-SILENT.md`（`WIRE-06` 开的那张，
里面有三小步修法）· `web/lib/jobClient.ts` 的 `JobStreamState` 与 `openJobStream` ·
`web/app/jobs/[id]/page.tsx` · `web/components/shell/NotProvided.tsx`。
约 9k tokens，预算 40k 以内。

## 2. `NotFound404`：与「接口未提供」NEVER 用同一个表示

| | 说的是 | 用户该做什么 | 我们该做什么 |
|---|---|---|---|
| `NotFound404` | 这个能力**在**，查了，**这一条**不存在 | 换 id / 回上层 | 什么都不用做 |
| `NotProvided` | 这个能力**还没接** | 等 | 去挂路由或配后端 |

混成一句「找不到」，用户会拿一个**正确的 id** 反复试；
反过来混，用户会以为自己的数据被删了。

它对应的是**带 `code` 的 404**（`BE-09` 的「404 不 403」口径），
而框架的路由未命中回 `{"detail": "Not Found"}`——没有 `code`。
`web/lib/screenClient.ts` 就是按这一点分的，本组件是前者的落点。

**无权与不存在共用这一个表示是有意的**：分开说等于告诉未授权的人
「这个 id 是存在的」，那本身就是一次信息泄露。这条理由写进了组件注释
并配了判据——不写的话，下一个人会「好心」把它们分开。

## 3. `SseDisconnectNotice`：把 `WIRE-06` 那个洞补上

单子给的三小步逐条落地：

1. `JobStreamState` 加 `connection: "connecting" | "open" | "disconnected"`；
2. `openJobStream` 补 `es.onerror`——**只标连接断了**：
   - **不动 `failedReason`**：那是后端明确发来的「作业失败」，
     与「我们收不到消息了」是两件事，两者该做的事完全相反
     （一个去看失败原因，一个刷新页面）；
   - **不 `close()`**：原生 `EventSource` 正在自动重连，关掉就真断了，
     而屏上说的是「正在重连」；
   - 收到消息时置回 `open`——**重连成功要能自己回来**
     （`WIRE-06` trace 交接的那条：「`UIX-02` 做的时候 MUST 带一条」）；
3. `jobs/[id]` 渲染它，带 `data-job-connection` 断言面，**不藏下面的内容**——
   旧内容仍然是真的，只是可能过时了。

组件用 `role="status"` 而非 `alert`：断线是状态变化不是故障，
`alert` 会打断用户正在做的事，而这里的正确反应是「知道一下，继续等」。

## 4. `WIRE-06` 那条判据当场翻面——那是它设计好的

`WIRE-06` 把缺口钉成**等值判据**（处理器集 == `{onmessage}` 且无连接态字段），
并在失败信息里逐字写着「若是补上了 onerror，去关单并把本条改成断言断线态存在」。

本卡补上之后它立刻变红，**照那句话改成了正面断言**。

**这比留一个 TODO 强的地方就在这里：TODO 不会红，也不会告诉你怎么改。**

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_notfound_and_sse_notice.py -q → 14 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3791 passed（UIX-01 收卡时 3777，本卡 +14）
            cd web && npm test -- --run → 74 files / 750 passed（**见 §6：其中一次红过**）
            cd web && npx tsc --noEmit  → 只剩 2 条既有错，本卡零新增
            node tools/check_design_constraints.mjs web → 11 条规则 0 处违规
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 建两件 | `test_both_components_exist_and_export_their_name`、`test_the_five_s1_components_are_all_there_now`（S1 五件到本卡齐了） |
| ② 404 与「接口未提供」不混 | `test_not_found_and_not_provided_have_different_state_names`（判等值）、`test_the_component_says_why_the_two_must_not_merge`、`test_neither_component_invents_a_message` |
| ③ 接进 jobs 屏、断线时可见 | `test_the_stream_state_now_has_a_connection_field`、`test_the_error_handler_is_actually_assigned`、`test_a_disconnect_never_touches_the_failure_reason`、`test_a_reconnect_returns_to_open`、`test_the_jobs_screen_shows_the_notice_when_disconnected`、`test_the_existing_assertion_surfaces_survived`、`test_the_notice_is_announced_politely_not_as_an_alert` |

**② 改既有文件四处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `web/lib/jobClient.ts` | `JobStreamState` 加 `connection`；`openJobStream` 补 `onerror`、收到消息置回 `open` | acceptance③「断线时可见」**要求那个状态存在**，而它此刻没有。**不在卡面 outputs**（只有 `shell/` 与测试文件）——照 `UIX-01` 的先例做并在此登记 |
| `web/app/jobs/[id]/page.tsx` | 渲染 `SseDisconnectNotice` + `data-job-connection` | 同上 |
| `tests/v041/test_sse_live.py` | 那条钉缺口的判据翻成正面断言 | 它自己的失败信息就是这么写的（§4） |
| `web/messages/{zh,en}.json` | +3 词条 | 裸中文会被 i18n 判据拦下 |

**③ 变异考 7 咬住 + 假变异对照绿，其中两条是我自己写弱的**

| 变异 | 判据 |
|---|---|
| ① 断线写进 `failedReason` | 红 |
| ② 断线时 `close()` | 红——**第一版没红** |
| ③ 重连后不回 `open` | 红 |
| ④ `onerror` 又被摘掉 | 红 |
| ⑤ 404 与「接口未提供」共用状态名 | 红 |
| ⑥ 断线用 `alert` | 红 |
| ⑦ 断线时把内容藏起来 | 红——**第一版没红** |
| ⑧ 假变异对照：只改一句注释 | 全绿 |

- **② 第一版**按 `split("};")` 切 `onerror` 的函数体，切在了**第一个** `};` 上——
  而 `es.close()` 写在那之后，判据根本看不见它。改成按缩进找收尾行。
- **⑦ 第一版**只判 `data-job-id={id}` 这个串在不在。把内容包进
  `connection === "disconnected" ? null : …` 之后**串还在**，而内容已经被藏起来了。
  改成判**那一行长什么样**。

**④** 装载约 9k tokens；**⑤** 禁用词六词 0 命中。

## 6. 全局门里有一次**间歇红**，如实记下

第一次跑 `npm test -- --run`：

```
Tests  1 failed | 749 passed (750)
FAIL __tests__/app/ui07.test.tsx > 后端给的不是默认值时，屏上跟着变
```

单独跑 `npx vitest run ui07` → **17 passed**；随后全量连跑 **4 次全绿**。

**单独恒绿、全量偶红**这个形状指向**跨文件污染**（多个测试文件都在
`vi.stubGlobal("fetch", …)`，而 vitest 默认不在用例间还原），
但**那是「最像」，不是实测出来的因果**。

已登记 `docs/blocked/UI07-LOCALE-TEST-IS-FLAKY.md`，里面写了怎么查
（先 `--no-file-parallelism` 连跑 20 次坐实并发嫌疑，改完**再连跑 20 次**——
一次绿不算数）。

**间歇红比稳定红更坏**：它会训练人「重跑一遍就好」，
而那个习惯会让下一次真缺陷也被重跑掉。所以 NEVER 写成「全绿」了事。

## 7. 登记未做

1. **`ScreenFetchState` 仍未退役**（`WIRE-03` 与 `UIX-01` 都登记过）。
   S1 五件到本卡齐了，替换的条件成熟了——但那要动 `WIRE-03` 接的四张屏，
   属另一次改动面。
2. **`NotFound404` 还没有调用点**：`deliverables/[id]` 的
   `data-not-found` 分支是最自然的第一处，但改它超出本卡 outputs。
3. **断线态没有前端交互测试**：本卡判的是源码性质（不碰 `failedReason` /
   不 `close()` / 回到 `open`）。真正的「断开连接 → 屏上出现提示 → 重连 → 提示消失」
   要在 vitest 里造一个假 `EventSource` 走一遍，属 `E2E-01` 或单开。
