# WIRE-06 · SSE 长连接屏在装配后的栈上实测可用

**卡** `docs/steward/tasks-v041-b3.json#WIRE-06` · **cycles 1（oneshot）** ·
**self_review = true** → §4 · **owner_review = false**
**依赖** `WIRE-01`（verified）· `WIRE-03`（verified）

## 1. 装载清单

卡面 WIRE-06 · `web/lib/jobClient.ts`（`JobStreamState` 与 `openJobStream` 段）·
`web/lib/useJobStream.ts` 全文 · `web/app/jobs/[id]/page.tsx` 的取数段 ·
`flint/api/app.py` 的 `UNWIRED_FAMILIES` · `harness/fe_smoke.py` 的 `SAMPLE_IDS`。
约 7k tokens，预算 40k 以内。

## 2. 「装配后的 app」是哪一个——先把这条说清

`/jobs/{job_id}/events` 属 **`analysis` 族**，而那一族**没挂进 `create_app`**
（缺 `role_resolver`，`WIRE-01` §4）。它**活在 demo 栈上**——
`demo_server.build_app()` 从 `create_app` 起，再加 demo 独有的三族。

所以本卡的口径分两半，各判各的：

| 判什么 | 在哪判 |
|---|---|
| 这条路由在**可部署应用**上没挂，且**登记在案** | `create_app` |
| SSE 通道**真连一次、真收到事件** | demo 栈（真进程 `:8000`） |

**NEVER 拿 demo 栈的「通了」去说可部署应用也通了。**

## 3. acceptance①：真连上了

```
curl -sN http://localhost:8000/jobs/m1004-j/events -H "X-User-Id: demo-user"
id: 1
data: {"kind": "status", "state": "queued"}
```

判据不止判「有 data:」：还判每个 payload 带 `kind`（照 `flint/jobs/events.py` 的契约），
以及**有 `id:` 行**——那是断线续订的游标，缺了 `applyEvent` 的 seq 去重就失效，
重连会重复挂载。job id 从 `SAMPLE_IDS` 取（库里查出来的），**NEVER 编一个**。

## 4. acceptance②：断线态**实测是空的**，已登记

`openJobStream` 只赋了 `es.onmessage`，**`onerror` 从未被赋值**；
`JobStreamState` 六个字段里没有一个能表示「连接断了」。

后端挂掉、网断掉、反代超时——屏上**一个字都不变**，
`data-job-status` 停在最后一次收到的值。**用户把停住的旧数据读成「还在跑」**，
正是卡面 acceptance② 点名禁止的那种静默。

修它要动 `web/lib/jobClient.ts` 与 `useJobStream.ts`，而本卡 outputs 只有
`tests/v041/test_sse_live.py` → 按 §五.1 停下登记：
`docs/blocked/SSE-DISCONNECT-IS-SILENT.md`（含三小步修法，责任人 `UIX-02`）。

**钉法**：`test_the_disconnect_state_is_registered_as_missing` 判**等值**——
`openJobStream` 赋的处理器集 == `{onmessage}` 且 `JobStreamState` 无连接态字段。
有人把它修好了，这条就红并指向那张单。
**这比留一个 TODO 强的地方在于：TODO 不会红。**

另配一条 `test_job_failure_and_connection_loss_are_two_different_fields`：
守的是**修的时候别走捷径**——`failedReason` NEVER 兼职断线态。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_sse_live.py -q → 8 passed（0 skipped，真栈在跑）
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3722 passed（WIRE-05 收卡时 3714，本卡 +8）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 真连一次、收到 ≥1 个事件 | `test_the_channel_really_connects_and_delivers_at_least_one_event`（真 `curl`，NEVER mock）、`test_the_sse_route_is_on_the_demo_stack`、`test_the_sse_route_is_not_on_the_deployable_app_and_says_so`、`test_the_screen_subscribes_through_the_hook_not_its_own_fetch` |
| ② 断线态有判据、NEVER 静默停在旧数据 | **实测不存在** → `test_the_disconnect_state_is_registered_as_missing`（判等值）、`test_the_ticket_spells_out_the_fix_and_who_does_it`、`test_job_failure_and_connection_loss_are_two_different_fields` |
| ③ 只验通道与断线态，组件本体归 `UIX-02` | 本卡未建任何组件；单子里点名 `UIX-02` |

**② 改既有文件：零处。** 本卡只新增 `tests/v041/test_sse_live.py` 与一张问题单。

**③ 变异考 5 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 断线态被「修好了」（补上 `onerror`） | 红 |
| ②a 给 `failedReason` 编兜底理由（`?? "连接断开"`） | 红——**前两版都没红**，见下 |
| ②b `failedReason` 直接来自别处 | 红 |
| ③ 依赖数组改成每渲染重订阅 | 红 |
| ④ 屏自己发请求绕过 hook | 红 |
| ⑤ 假变异对照：只改一句注释 | 全绿 |

**② 连错两轮**，两轮的错不一样，都值得记：

1. **第一轮是我写了假变异**：改的是一行注释，而判据用的 `_code()` 会剥注释——
   等于什么都没改。`assert old != new` 拦不住这种：源码字节确实变了，
   **但判据看到的输入没变**。
2. **第二轮是判据扫错地方**：`failedReason` 的真赋值是
   `next.failedReason = payload.reason`，而我扫的是 `failedReason:\s*(...)`——
   那只看得见**类型声明与初值**。扫描面写窄了，判据就是空的。
   改扫 `\.failedReason\s*=\s*(...)` 后仍不红：`payload.reason ?? "连接断开"`
   以 `payload.` 开头，被放过去了。补上「不许有兜底值」这一条才咬住。

**④** 装载约 7k tokens；**⑤** 禁用词六词 0 命中。

## 6. 登记未做

1. **断线态本体**：`docs/blocked/SSE-DISCONNECT-IS-SILENT.md`，由 `UIX-02` 处置。
   **只建 `SseDisconnectNotice` 组件而不加那个状态，组件永远收不到 `true`**——
   单子里写明了这一点。
2. **可部署应用上这条 SSE 仍不通**：随四族的授权问题一并解（`WIRE-01` 的单）。
3. **重连恢复没有判据**：原生 `EventSource` 断线会自动重连，
   所以断线态是**可恢复态**。本卡没法判它（那个状态还不存在），
   `UIX-02` 做的时候 MUST 带一条「重连成功要回到 open，NEVER 卡死在断线态」。
