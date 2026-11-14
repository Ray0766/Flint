# SSE-DISCONNECT-IS-SILENT · 断线时屏上什么都不说，静静停在旧数据上

**状态** closed · 2026-08-05 · `UIX-02`

> **已关闭 · 2026-08-05 · `UIX-02`**
>
> 本单给的三小步**逐条落地**：
>
> 1. `JobStreamState` 加 `connection: "connecting" | "open" | "disconnected"`——
>    **NEVER 用 `failedReason` 兼职**（判据 `test_a_disconnect_never_touches_the_failure_reason`）；
> 2. `openJobStream` 补 `es.onerror`：只标连接断了，**不动 `failedReason`、也不 `close()`**
>    （原生 EventSource 正在自动重连，关掉就真断了，而屏上说的是「正在重连」）；
>    收到消息时置回 `open`——**重连成功要能自己回来**（判据 `test_a_reconnect_returns_to_open`）；
> 3. `jobs/[id]` 屏渲染 `SseDisconnectNotice`，带 `data-job-connection` 断言面，
>    **不藏下面的内容**（旧内容仍然是真的，只是可能过时了）。
>
> 组件用 `role="status"` 而非 `alert`：断线是状态变化不是故障，
> `alert` 会打断用户正在做的事，而这里的正确反应是「知道一下，继续等」。
>
> `WIRE-06` 那条把缺口钉成等值的判据随之变红并被改成正面断言——
> **那正是它当时设计的机制**（「有人修好了它就会红并指向那张单」）。
>
> 以下为关闭前的原文，一字未改。

---

**发现者** worker / `WIRE-06` 实测 · **发现时间** 2026-08-05
**危害** 中高 —— 用户会把**停住的旧数据**读成「还在跑」，而连接早断了
**为什么停下**：修它要改 `web/lib/jobClient.ts` 与 `web/lib/useJobStream.ts`，
而 `WIRE-06` 的 outputs 只有 `tests/v041/test_sse_live.py`。按工单 §五.1 登记。

## 实测

**通道本身是好的**（`WIRE-06` acceptance① 已验）：

```
curl -sN http://localhost:8000/jobs/m1004-j/events -H "X-User-Id: demo-user"
id: 1
data: {"kind": "status", "state": "queued"}
```

**断线那一半是空的**。`web/lib/jobClient.ts`：

```ts
interface MinimalEventSource {
  onmessage: ((e: { data: string; lastEventId: string }) => void) | null;
  onerror: ((e: unknown) => void) | null;   // ← 声明了
  close(): void;
}

export function openJobStream(...) {
  const es = new ES(...);
  es.onmessage = (e) => { ... };            // ← 只赋了这个
  return () => es.close();                   // ← onerror 从未被赋值
}
```

`JobStreamState` 的六个字段（`status` / `steps` / `arrivedBlockIds` /
`failedReason` / `lastEventId` / `done`）里，**没有一个能表示「连接断了」**。

后果：后端挂掉、网络断掉、反代超时——屏上**一个字都不变**，
`data-job-status` 停在最后一次收到的值。用户看到的是「还在跑」。

**`failedReason` 不是它**：那是**作业失败**（后端明确发了 failed 事件），
与「我们收不到消息了」是两件事。挤进同一个表示，
「作业跑挂了」和「你的网断了」会显示成同一句话。

## 修法（一处，三小步）

1. `JobStreamState` 加一个字段，例如
   `connection: "connecting" | "open" | "disconnected"`——
   **NEVER 用 `failedReason` 兼职**，理由见上；
2. `openJobStream` 里补 `es.onerror = () => { state = {...state, connection: "disconnected"}; onState(state); }`；
   拿到消息时置回 `"open"`；
3. `web/app/jobs/[id]/page.tsx` 按它渲染一个 `data-job-connection` 属性
   （**组件本体归 `UIX-02` 的 `SseDisconnectNotice`**，本条只要求那个**状态**可读）。

原生 `EventSource` 断线会自动重连，所以 `disconnected` 是**可恢复态**，
不是终态——重连成功要能自己回到 `open`，NEVER 卡死在断线态。

## 谁来做

- **`UIX-02`**（S1 通用件里的 `SseDisconnectNotice`）：卡面已经点名了它。
  建议把上面三小步一并做掉——**只建组件而没有那个状态，组件永远收不到 `true`**。
- 若 steward 认为该单开一张卡，本单即卡面草稿。

## `WIRE-06` 本轮怎么处置

不改实现，只**把这个缺口钉住**：
`tests/v041/test_sse_live.py::test_the_disconnect_state_is_registered_as_missing`
判**等值**——`JobStreamState` 的字段集与 `openJobStream` 赋的处理器集一旦变了
（也就是有人把它修好了），判据会红并指向本单，逼人来关单。
