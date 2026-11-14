# 共用取数层没有「这一条不存在」那一态 —— 带 `code` 的 404 被显示成通用错误

**状态** closed @2026-08-08 · `FIX-11`（v0.4.1 第 6 批）

> 发现者：worker，v0.4.1 第 5 批 `CHAIN-03`（主题详情屏取证时看见的）。

## 现象

后端对未知主题回的是**正确的形状**（`BE-09` 的「404 不 403」口径）：

```
$ curl -s -H "X-User-Id: self" http://localhost:8000/topics/tp-none
404 {"code":"NOT_FOUND","message":"unknown topic: tp-none"}
```

而屏上显示的是**通用错误框**：

```
取数出错
后端回了一个错误状态，下面是它原样给的说明。
unknown topic: tp-none
```

根因在共用取数层：`web/lib/screenClient.ts` 的 `Fetched<T>` 判别联合只有五个成员——

```ts
loading | ready | not_provided | not_configured | failed
```

**没有 `not_found`**。带 `code` 的 404 因此落进 `failed`。

## 为什么这是个真问题

`web/components/shell/NotFound404.tsx` 的 docstring 逐字写着两者的分界：

| | 说的是 | 用户该做什么 |
|---|---|---|
| `NotFound404` | 这个能力在，我们查了，**这一条**不存在 | 换一个 id / 回上一层 |
| 通用错误 | 出故障了 | 重试 / 报障 |

混成一句，用户会拿一个**正确的 id 反复重试**，而那一条本来就不存在。
`NotFound404` 这个组件早就建好了——**取数层递不出那一态，它就永远用不上**。

## 为什么 `CHAIN-03` 不自己改

`Fetched` 与 `ScreenFetchState` 是**十三屏以上共用**的取数层。加一个成员会：

- 让每一处 `ScreenFetchState` 的分支覆盖跟着变；
- 动到每一屏的既有判据（`data-screen-state` 的取值集合）。

本卡的触碰面是 `web/app/`（两屏）+ 测试，按第 5 批工单纪律 4
「改动面大于卡上 outputs → 停下走 `docs/blocked/`」立单。

## 需要 owner 的什么

给 `Fetched<T>` 加 `{ kind: "not_found"; detail: string }`，`ScreenFetchState` 里
渲染 `NotFound404`（`what` 由调用方给，各屏说各自的「这份交付物/这个项目/这条主题」）。
改完之后**每一屏都受益**，不只是主题详情。

## 绕行现状

主题详情屏按当前取数层如实显示——**后端自己的说明原样带出来**，没有改写、没有编。
它说的话是真的，只是没有说到「换一个 id 就行」这一层。

---

## 结案（`FIX-11` · v0.4.1 第 6 批）

`Fetched` 多一态 `not_found`（**404 带 `code`**），接 `UIX-02` 早就建好的
`NotFound404`——那个组件此前**因为取数层没有这一态而一直用不上**。

三种「拿不到」现在三个 kind、三个 `data-screen-state`、三句话：

| 后端回什么 | kind | 屏上 | 用户该做什么 |
|---|---|---|---|
| 404 **带** `code` | `not_found` | 这一条不存在（**带出后端那句原话**） | 换一个 id / 回上一层 |
| 404 **不带** `code` | `not_provided` | 接口未提供 | 等我们去挂路由 |
| 5xx / 其它 | `failed` | 出错了 + 状态码 + 后端说明 | 等一会儿再试 |

**后端那句说明原样带出**：`BE-09` 把**无权**与**不存在**收进同一条路
（分开说等于告诉未授权的人这个 id 存在），所以那句话得由后端来说，
NEVER 在屏上改写成一句自己编的「找不到」。

### 判据分两层，各判各能判的

- **源码层**（pytest）：联合里三态并列 · 三支各走各的 kind ·
  `not_found` 那一支里 NEVER 混进 `not_provided`；
- **渲染层**（vitest）：三种分别构造，断言**三句话互不相同**、
  **三个取证标记互不相同**——那只能在渲染上量，
  源码层看不出两个分支渲染出同一句，而那正是改前的实况。
