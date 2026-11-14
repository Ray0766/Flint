# 登记：S1 通用件缺三件，四个页面没有加载态/错误态

**状态** closed · 2026-08-05 · `UIX-01`

> **已关闭 · 2026-08-05 · `UIX-01`**
>
> 三件通用件建在 `web/components/shell/`：`LoadingSkeleton` · `EmptyState` ·
> `ErrorState`，各占一个 `data-screen-state`（`loading` / `empty` / `failed`），
> 与既有的 `NotProvided`（`not_provided`）**四态互不相同**。
>
> 四个页面**按各自真实的机制**接入，不是套模板：
>
> | 页面 | 加载态在哪 |
> |---|---|
> | `deliverables/[id]/export` | 已有 `pending`，换成通用件（既有 `data-export-pending` 断言面原样保留） |
> | `deliverables/[id]` | **async 服务器组件** → 同目录 `loading.tsx`（Next 的机制；组件内部没有「正在加载」那一刻可渲染） |
> | `demo` | 取数在 `DemoFlow`，见下 |
> | `jobs/[id]` | SSE：`status === null` = 还没收到第一个事件 |
>
> **接的过程中撞出一个真缺陷**：`DemoFlow` 里**每一处 `await` 都没有 `catch`**——
> 请求失败时 `setBusy(false)` 永远执行不到，屏幕永久停在忙碌态且一个字不说。
> 这不是「少了个错误提示」，是**一次失败把整屏卡死**。已补 `run()` 包壳
> （`try/catch/finally`，后端原话原样留下）。
>
> `A6` 归零、11 条规则 0 违规、`KNOWN_GAPS` 清空。
> 顺带让 A6 认得 App Router 的同目录约定文件——不认的话，
> 它会逼 async 服务器组件写一段永远进不去的死分支，
> 而 A6 自己的注释写着「硬凑的死分支比没有更坏」。
>
> 以下为关闭前的原文，一字未改。

---

**发现于** AUDIT-02（技术约束清单可执行化）· 2026-08-05 ·
**当时的处置** 已登记，那一批**不修**（修法是 UI 工作，超出那张卡 outputs → §六.1）
**不阻塞** AUDIT-02：尺子已建、已接进全局门，这四条作为**逐条列名的已知缺口**
钉在 `tests/v041/test_design_constraints.py#KNOWN_GAPS` 里——
**多一条或少一条都会红**。

## 事实

交付包 README 的 S1 通用件契约点名五件：

> LoadingSkeleton / EmptyState / ErrorState / NotFound404 / SseDisconnectNotice

`web/components/shell/` 现有三件：`AppShell.tsx` · `Screen.tsx` · `NotProvided.tsx`。
**`LoadingSkeleton` / `EmptyState` / `ErrorState` 一件都没有。**

于是这四个页面在源码里连「加载中」这个意思都找不到（中英文都没有）：

| 页面 | 缺 |
|---|---|
| `app/deliverables/[id]/export/page.tsx` | 加载态 |
| `app/deliverables/[id]/page.tsx` | 加载态 |
| `app/demo/page.tsx` | 加载态、错误态 |
| `app/jobs/[id]/page.tsx` | 加载态、错误态 |

## 后果

清单第 6 条要的是「每屏三态齐全，且空态 ≠ 错误态」。缺加载态的实际表现是：
**请求还在路上时，页面渲染的是「空」**——而空态说的是「查过了，没有内容」。
用户看到的是一句「暂无数据」，然后数据到了又变出来。

`app/jobs/[id]` 这一屏尤其要紧：它是 SSE 长连接屏，
断线重连期间没有任何状态可显示，界面会静静地停在旧数据上。

## 为什么本批不修

修法是**建三个通用件 + 改四个页面**，属 UI 卡的活（UI-03~11 还没跑）。
AUDIT-02 的 outputs 是 `tools/check_design_constraints.mjs` 与它的测试——
把七个前端文件一起改进来，改动面远大于卡面（§六.1）。

## 给 owner / steward 的建议

**并进 UI-03~11 里的任一张**（它们本来就要碰这些页面），或单开一张
「S1 通用件补齐」卡。修完之后把 `KNOWN_GAPS` 里对应的行删掉——
**判据会因为「少一条」而红**，那正是提醒你去删的机制。

## 现状（本卡已做的部分）

- `tools/check_design_constraints.mjs` 的 A6 规则会持续盯着这四个页面；
- 规则**跟着本地 import 走一层**，所以「三态写在 `<Screen>` 里」这种正常写法
  不会被误报（第一版没跟 import，六个页面全被报成缺三态，全是误伤）；
- `A4`（状态标记非颜色载体）当前**无可量对象**：`StatusMark` 组件本仓也还没建。
  它进 `noSubject` 名单单独列出来，**不算通过**——
  免得这条规则的绿被读成「状态标记已经查过了」。
