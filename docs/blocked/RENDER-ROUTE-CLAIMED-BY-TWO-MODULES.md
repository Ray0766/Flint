# RENDER-ROUTE-CLAIMED-BY-TWO-MODULES · `GET /deliverables/{id}/render` 被两个模块注册

**状态** closed · 2026-08-06 · `ROUTE-01`

**发现者** worker / `WIRE-01` 装配时 · **发现时间** 2026-08-05
**危害** 中 —— 两个模块各注册同一条路径，并进一个应用后**必有一个收不到请求**
**为什么停下**：`WIRE-01` acceptance⑥「NEVER 改动任一 `flint/api/*.py` 模块内部实现」。
解开这处冲突要么改模块、要么挑一个静默遮蔽，两条都不该由 worker 自己定。

## 实测

```
同 method+path 被多模块注册: {('GET', '/deliverables/{}/render'): {'deliverables.py', 'pack.py'}}
```

| 模块 | 注册处 | 它管什么 |
|---|---|---|
| `flint/api/deliverables.py` | `:97` | `?fmt=markdown\|html\|pdf\|docx\|pack` 五种格式；`pack_builder`/`pack_gate` 未注入时 `fmt=pack` 返回 **503 SERVICE_UNAVAILABLE**（E6 姿态：明说不可用） |
| `flint/api/pack.py` | `:147` | 专管 `?fmt=pack` → 门禁（M4-027 三与）→ zip |

`pack.py` 自己的文件头写着两者的分工表：「`/render?fmt=pack`（既有） vs `/pack`（本卡）」——
**它知道这条路径已经有人注册了**，两个 app 各自独立时互不干扰。
并成一个应用，这个前提就不成立了。

## 为什么不能「随便挂一个」

FastAPI 对重复注册**不报错**：先注册的先匹配，后注册的那个永远收不到请求。
于是：

- 先挂 `deliverables` → `pack.py` 的 render **永远走不到**，`fmt=pack` 落到既有那条的 503；
- 先挂 `pack` → 另外四种格式（markdown/html/pdf/docx）**全部**落到只认 pack 的处理函数。

**第二种是明确的功能倒退**，第一种是「pack 那条 zip 路径静默失效」。
两种都不会有任何报错——这正是本批一路在治的那件事。

## worker 本轮怎么处置的（**临时，等 owner 一句话**）

装配器 `flint/api/app.py` 里**登记**这处冲突（`KNOWN_COLLISIONS`），
winner = `deliverables.py`，shadowed = `pack.py` 的 render。理由：

1. 它覆盖五种 `fmt`，其中 `pack` 有**明说不可用**的降级路径，不会假装成功；
2. 反过来选会让四种格式全部倒退，代价大一个量级；
3. `pack.py` 的**独有**端点 `GET /deliverables/{id}/pack` **照常挂上**，整个模块没有被连坐丢掉。

装配器对**未登记**的冲突直接 raise，NEVER 静默遮蔽；
`tests/v041/test_app_assembly.py::test_a_path_claimed_by_two_modules_is_reported_with_both_names`
判**等值**——冲突面多一处或少一处都会红，逼人回来确认。

## 需要 owner 给一句话

三选一：

1. **维持现状**（worker 本轮的临时处置）：`fmt=pack` 走 `deliverables.py` 的 503，
   真正的 pack 出件只经 `/deliverables/{id}/pack`。代价：`pack.py` 的 render 是**死代码**。
2. **把 `pack.py` 的 render 删掉**，出件面收敛到 `/pack` 一条。要改模块（本卡禁止），
   且 `pack.py` 自己的测试会红——单开一张卡。
3. **让 `deliverables.py` 在 `fmt=pack` 时转交** `pack.py` 的处理函数。语义最完整，
   但两个模块之间要建依赖，改动面最大。

**在 owner 答复前，第 1 种一直生效，且它是被判据钉住的、不是悄悄发生的。**

---

## 关闭（`ROUTE-01` · 2026-08-06）

owner 裁决走 steward 的建议：**`deliverables.py` 赢**。
但本卡不是「挑一个、遮蔽另一个」——那还是静默遮蔽，只是换了个地方登记：

| 做了什么 | 结果 |
|---|---|
| `pack.py` **删掉那条 route 声明** | 源码里不再有两个模块抢同一条路径；`KNOWN_COLLISIONS` 空了 |
| 三与门（M4-027）**搬进赢家** | `DeliverableApiDeps.pack_gate_inputs`；`fmt=pack` 过门 → 200 zip，门拒 → 409 带 violations 分类 |
| 门禁没注入时 | **503 明说不可用**，NEVER 当成放行 |
| `pack.py` 的 `/deliverables/{id}/pack` | 照常挂，模块没被连坐 |
| `GateInputs` 类型 | **仍在 `pack.py`**，赢家 import 它——同一份真相，不是抄一份 |

上面「三选一」里选的其实是第 3 种的实质（语义最完整），
而代价没有当初估的那么大：两个模块之间只多了一条 `import GateInputs`，
判定函数本来就在 `flint/spec/export_gate.py`，谁都不拥有它。

**一处功能确实没了**：`pack.py` 的 `?fmt=markdown`（CLAUDE.md 单文件预览，带门禁）。
赢家的 `fmt=markdown` 是 Block 树渲染，两种 markdown 在一条路径上放不下。
内容仍可读（`/pack` 逐章给），但那条路**不过导出门**。
要把带门禁的单文件预览接回来需要一个新的 fmt 值——**那是 owner 的口径决定，
本卡 NEVER 自己发明一个**。已登记在 `docs/trace/ROUTE-01.md` §未做。

**判据**：`tests/v041/test_render_route_owner.py`（11 条，含一条阴性对照——
造一对真的抢同一条路径的模块，检测器必须报出来）。

