# FE-DEMO-ENV-FLINT-API-BASE · 按 `start-demo.ps1` 一键起栈，报告屏恒 500

**状态** closed · 2026-08-05 · `WIRE-02`

> **已关闭 · 2026-08-05 · `WIRE-02`**
>
> 修法就是本单末尾给出的那一行：`start-demo.ps1` 的 `$frontCmd` 里补
> **`$env:FLINT_API_BASE = 'http://localhost:8000'`**，与既有的
> `$env:NEXT_PUBLIC_FLINT_API` 并列——一份给服务器组件、一份给客户端组件。
>
> **另配了一条判据，防止同类事再发生**：
> `tests/v041/test_demo_stack_wired.py::test_the_frontend_reads_no_env_var_the_start_script_forgets_to_set`
> 判的是**前端读的环境变量 ⊆ 脚本设的**，而不是「那一行在不在」。
> 只断言那行存在的写法拦不住下一次——前端新读一个变量而脚本没跟上时照样绿。
>
> **报告屏此刻仍有 10 条控制台报错**，那是另一件事
> （`docs/blocked/DEMO-REPORT-REFS-NOT-SEEDED.md`，由 `FIX-02` 处置），
> 与本单的 500 无关；判据判**等值**，数字一变就要有人回来确认。
>
> 以下为关闭前的原文，一字未改。

---

**发现者** worker / EYE-03 前端 e2e 冒烟首跑 · **发现时间** 2026-08-04（机器 UTC 2026-08-03T23:0x）
**危害** 中 —— 唯一一屏有真内容的页面（报告屏）在文档给的启动路径下完全打不开
**改动面** `start-demo.ps1` 一行（不在 EYE-03 卡面 outputs 内 → 按工单 §2 走本问题单，NEVER 自行改）

## 现象（命令原样输出）

`C:\pwenv\Scripts\python.exe harness/fe_smoke.py`，前端按 `start-demo.ps1` 的环境起
（只设 `NEXT_PUBLIC_FLINT_API=http://localhost:8000`）：

```
  [dark]  /deliverables/[id]  HTTP 500  控制台 error 2  页高 900px  无溢出  → deliverables-id-dark.png
        error: Failed to load resource: the server responded with a status of 500 (Internal Server Error)
        pageerror: Failed to parse URL from /deliverables/del-demo-fixture-report/blocks
  [dark]  /demo               HTTP 200  控制台 error 0  页高 152px
  [dark]  /jobs/[id]          HTTP 200  控制台 error 1  页高  58px
  [light] （三屏同上，逐行一致）
EXIT=1
```

同一份代码，前端改用 `FLINT_API_BASE=http://localhost:8000 NEXT_PUBLIC_FLINT_API=… npm run dev` 重起：

```
  [dark]  /deliverables/[id]  HTTP 200  控制台 error 0  页高 422px  无溢出
  [dark]  /demo               HTTP 200  控制台 error 0  页高 152px
  [dark]  /jobs/[id]          HTTP 200  控制台 error 0  页高  58px
  [light] （三屏同上）
EXIT=0
```

**唯一变量是那个环境变量。**

## 怀疑根因（三点实证，非推测）

1. `web/app/deliverables/[id]/page.tsx:15` 是**服务器组件**，取基址用的是
   `process.env.FLINT_API_BASE ?? ""` —— 服务端那一份，**不是** `NEXT_PUBLIC_*`。
2. `grep -n FLINT_API_BASE start-demo.ps1` → **零命中**；脚本第 158 行只设了
   `$env:NEXT_PUBLIC_FLINT_API`（客户端那一份，`web/lib/apiBase.ts` 用它）。
3. 基址为空 → `fetch("/deliverables/…/blocks")` 在 Node 侧是相对 URL →
   `Failed to parse URL` → 服务器组件抛错 → 该路由 500。
   **后端本身没问题**：`curl http://localhost:8000/deliverables/del-demo-fixture-report/blocks`
   直接返回 **200**。

## 已试三案

1. 换真样例 id（`del-demo-fixture-report` 是库里真有的，`select deliverable_id from deliverables` 查得）
   —— 无关，500 照旧；
2. 直连后端同一路径 —— **200**，排除后端与数据；
3. 补 `FLINT_API_BASE` 重起前端 —— **500 → 200**，六行全绿。根因坐实。

## 需要 owner / 下一张卡做什么

`start-demo.ps1` 第 155~160 行那段 `$frontCmd` 里补一行：

```powershell
$env:FLINT_API_BASE = 'http://localhost:8000'
```

（与既有的 `$env:NEXT_PUBLIC_FLINT_API` 并列；两者一个给服务器组件、一个给客户端组件，
**缺任一都会有一半页面取不到数**。）

## 绕行现状

- EYE-03 的冒烟**能跑、能报**：这条缺陷正是它第一次跑就挖出来的，报告与截图都在 `.ui-probe/`；
- `tests/v041/test_fe_smoke.py::test_the_demo_start_script_gap_stays_registered_until_it_is_fixed`
  盯着这份问题单：脚本一天没补那行，问题单就一天不许消失；**补上之后本条自动放行**，
  不会留下一份过期文档。
- 落盘的 `.ui-probe/fe_smoke.json` 是**补了变量之后**那次（六行全 200），因为它同时是冒烟
  自身的正向对照（证明这把尺子报得出绿，不是只会报红）。文档路径下的那组数字在本文上方。
