# 作业屏没有「无权查看」态——403 之后它停在加载骨架上，永远

**状态** closed 2026-08-08（由 `UIX-04` 执行，v0.4.1 第 7 批）

## 修完了什么

照本单 §「修法」那三条逐条做的：

| 修法 | 落地 |
|---|---|
| ① `jobClient` 把 401 与 403 **分开**认出来 | `JobStreamState.access: "unknown" \| "unauthenticated" \| "denied"` + `probeJobAccess()`。两个状态码落在**两个分支**上（判据禁止写进同一个条件） |
| ② 屏上第五态，NEVER 与断线态合并 | `web/components/shell/JobDeniedNotice.tsx`（`data-job-denied` + `role="alert"`），排在骨架分支**之前**——骨架那条的条件是 `status === null`，无权时同样成立，排后面永远命中不到 |
| ③ 判据打真栈 | `/jobs/m1004-j` 与它的 `/events` 都实测 403；`/jobs/probe-owned-ingest` 实测 200 |

### `EventSource` 拿不到状态码，所以补了一次探测

原生 `EventSource` 的 `onerror` **不带 HTTP 状态**——它连 403 与断网都分不出来。
所以流出错时走一次 `fetch GET /jobs/{id}`（那条路读得到状态码，且与 SSE 受同一条鉴权）。

**探一次，不轮询**：轮询会在真断网时对着一个连不上的后端反复打，
而屏上那句话不会因为多打几次变得更准。
探不出来（500 / 真断网）就是 `unknown`，**NEVER 猜成 denied**——
猜错会让用户去要一个他本来就有的权限。

### 「不劝重试」与「明说重试没用」是两件事

断线件说「正在重连」（可恢复）；403 是终局的。所以本件里没有任何一句劝重试的话，
**并且逐字写着「重试不会有用」**——
什么都不说的话，用户自己会去刷新，而刷新永远不会成功。

### 第 6 批留的那条反向判据翻过来了

`tests/v041/test_probe_job_owned.py::test_the_job_screen_still_has_no_denied_state`
当初断言那一屏**还没有**这个态，docstring 里写着「它哪天红了是好事」。
`UIX-04` 照那句话执行——换成了正向的
`test_the_job_screen_now_has_a_denied_state`。

**`m1004-j` 原样留着**（`initiated_by = u-sys`）：它是「不属于我的作业」的活样本，
这个态将来还要靠它来量。**403 也没有进控制台噪声白名单**——
那等于把鉴权正确工作的证据当成噪声吞掉（`DEC-037` 的原话）。

---

## 以下为立单时的原文（一字未改）

**状态**（原）open

> 发现者：worker，v0.4.1 第 6 批 `FIX-09`。
> **第 5 批完成态报告里那句「屏上也正确地显示无权查看」是写错了**，
> 本单把它纠正过来并留出修法。

## 现象

`web/app/jobs/[id]/page.tsx` 只有四态：

```
status === null   → 加载骨架（LoadingSkeleton）
failedReason      → 错误态（作业失败）
一个 block 都没到 → 空态
其余              → 就绪
```

`useJobStream` / `jobClient` 里**没有任何一处认 403**（grep `403|denied|forbidden`
零命中）。于是 SSE 被拒之后 `status` 恒为 `null`，屏上就是一张**永远转下去的骨架**。

**「在连」与「不让你连」在屏上长得一模一样**，而两者要用户做的事完全相反：
一个是等，一个是去要权限。

## 为什么本卡没修

`FIX-09` 的 outputs 是 `harness/` + `tests/v041/test_probe_job_owned.py`。
建一个界面状态是 `web/` 的事——按第 6 批工单纪律 5（改动面大于卡上 outputs →
停下走 `docs/blocked/`）立单。

**卡上那条 acceptance⑤ 因此没做**：它要「另建一条判据专门守『无权时屏上
显示无权查看』」，而那句话的前提是屏上已经有这个态。

## 靠什么量

`m1004-j` **原样留着**（`initiated_by = u-sys`，探针身份是 `demo-user`）。
它是「不属于我的作业」的活样本：修好之后，打开 `/jobs/m1004-j`
就该看到「无权查看」，而不是骨架。

`tests/v041/test_probe_job_owned.py::test_the_job_screen_still_has_no_denied_state`
现在断言那一屏**还没有**这个态。**它哪天红了是好事**——
那意味着有人把态建好了，而那时该回到那里，把它换成 acceptance⑤ 要的正向判据。

## 修法（一张小卡，一个 cycle 够）

1. `jobClient` / `useJobStream` 把 403 与 401 **分开**认出来
   （`AUTH-03` 的口径：401 是「你是谁」，403 是「你能干什么」，两者修法相反）；
2. 屏上第五态：`data-job-denied` + 一句「无权查看」，
   **NEVER 与断线态合并**（`SseDisconnectNotice` 说的是「连不上」，不是「不让你连」）；
3. 判据打真栈：`/jobs/m1004-j` 上量到那句话，`/jobs/probe-owned-ingest` 上量不到。

outputs 应为 `web/` + 判据。
