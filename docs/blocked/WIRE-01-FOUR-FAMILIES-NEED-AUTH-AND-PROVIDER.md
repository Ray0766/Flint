# WIRE-01-FOUR-FAMILIES-NEED-AUTH-AND-PROVIDER · 四族装不上，缺的是鉴权与模型，不是接线

**状态** closed · 2026-08-06 · `WIRE-11`

**发现者** worker / `WIRE-01` 装配时 · **发现时间** 2026-08-05
**危害** 中 —— 10 条路由挂不上，`backend_not_assembled` 归不了零
**为什么停下**：`WIRE-01` acceptance⑥「模块若缺参数装不上，**停下走 `docs/blocked/`**
并在 trace 写明缺什么」。**能挂上，但只能靠 demo 的假鉴权**——那是安全洞，不是接线活。

## 实况

装配后 **52 / 62 条通了**（46 条独立路径 + `/categories`，另一条被登记的冲突遮蔽，
见 `RENDER-ROUTE-CLAIMED-BY-TWO-MODULES.md`）。剩下 10 条属四族：

| 族 | 路由数 | 缺的东西 | 为什么不能凑 |
|---|---|---|---|
| `analysis` | 3（`/projects/{}/analysis`·`/jobs/{}`·`/jobs/{}/events`） | `role_resolver` · `owner_scope_for_project` | **判 owner/viewer 的那只手**。`harness/demo_server.py:192` 写的是 `lambda _u, _o: "owner"` —— demo 里无所谓，**可部署应用里等于人人是 owner** |
| `compose` | 2（`/projects/{}/proposal`·`/projects/{}/report`） | `runner`（含同上的 `role_resolver`）· `owner_scope_for_project` | 同上 |
| `interventions` | 4（`/interventions/lock`·`/projects/{}/evidence`·`/projects/{}/disputes`·`/deliverables/{}/sections/{}/regenerate`） | 同上 + `aligner`（吃 LLM） | 同上；另见下一行 |
| `combo` | 1（`/projects/combo`） | `provider`（LLM）· `embed_service` | `flint/config.py:Settings` 只有 `env` / `database_url` / `redis_url`，**没有模型地址这一项**。demo 从 `OLLAMA` 常量拿 |

## 两处**不是**障碍的（已核实，免得下一个人重查）

- **`PgJobRunner.enqueue` 是 `EnqueueHook | None`**：不给也建得出来，
  不必为了装配去连 redis（那会违反 acceptance④「建应用不连库」）；
- **各族的 store 缺持久层**不影响装配：`account` / `billing` / `design` / `quality` /
  `pack` 的相应字段本来就是 `X | None`，走模块自己的「没查过」缝即可，
  已在 `flint/api/app.py` 文件头列表说明。**那几族本轮全部挂上了。**

## 根因是同一件事：没有成员关系

迁移里 34 张表**没有 `users`，也没有 `memberships`**。
`role_resolver(user, owner) -> "owner" | "viewer" | ...` 要答的问题
（这个人对这个项目是什么角色）**在库里没有事实可查**。

所以这四族不是「忘了接线」，是**它们依赖的授权事实还不存在**。
`BE-05`（`/account`）本轮挂上了，而它返回的正是 `memberships` 的
`status: "not_checked"` —— 两处说的是同一件事。

## 需要 owner 给一句话

三选一：

1. **先建成员关系**（`users` + `memberships` 表 + 一个真 `role_resolver`）
   → 四族随后一次挂齐。**这是唯一不引入安全洞的路**，代价是一张新卡；
2. **接受「单用户模式」**：显式声明本阶段所有请求都是同一个 owner，
   把 `lambda _u, _o: "owner"` 写进 `flint/api/app.py` **并配一条判据**
   钉住「这是临时口径」。四族立刻通，`backend_not_assembled` 归零。
   **风险要 owner 明确接受**：任何人带任意 `X-User-Id` 都是 owner；
3. **维持现状**：四族继续不挂，前端那几屏继续显示「接口未提供」——
   诚实，且 `WIRE-01` 的出口判据改成「已挂 52 + 已登记 10」。

**worker 本轮取的是第 3 种**（不自行引入鉴权口径），并把这 10 条
登记进 `flint/api/app.py` 的 `UNWIRED_FAMILIES`，判**等值**：
多一条少一条都会红，逼人回到这张单上。

## 对下游卡的影响

- **`WIRE-03`**（九张屏切真数据）：`/projects/{}/analysis` 那条链路上的屏仍要走
  「接口未提供」，其余可切；
- **`WIRE-05`**（装配面接进全局门）：门要判的是 `已挂 52 + 已登记 10`，
  NEVER 直接判 `== 0`，否则第 3 种选择一落地全局门就恒红；
- **`E2E-01`**（真栈主链路）：主链路要经 `/projects/{}/analysis`，**受本单阻**。

## 追记（SHIP-03 · 2026-08-05）：第 3 批的出口判据卡在这张单上

`DEC-031` 给第 3 批定的出口判据是「`tools/check_fe_be_parity.py` 的
**`backend_not_assembled` 计数归零**」。收尾实测：

```
python tools/check_fe_be_parity.py --json
backend_not_assembled: 10        ← 正是本单这四族的 10 条路由
frontend_untyped_response: 0     ← 这一半达标
```

10 条逐条：

```
interventions.py  /interventions/lock · /projects/{}/evidence ·
                  /projects/{}/disputes · /deliverables/{}/sections/{}/regenerate
analysis.py       /projects/{}/analysis · /jobs/{} · /jobs/{}/events
compose.py        /projects/{}/report · /projects/{}/proposal
combo.py          /projects/combo
```

**归零只有两条路**，两条都不在第 3 批任何一张卡的 outputs 内：

1. **补鉴权**：建 `users` / `memberships` 两张表 + 一个真的 `role_resolver`，
   然后这四族进 `create_app`。这是一批卡的量；
2. **用 `lambda _u, _o: "owner"` 挂上去**：计数当场归零，
   而**每一条写操作从此对任何调用者开放**。`WIRE-01` 当时就拒绝了这条路，
   本单就是那次拒绝的记录。**NEVER 为了让出口判据变绿走第 2 条。**

所以 `SHIP-03` 记 `blocked`：**24/25 张 verified，出口判据的一半卡在这里**。
要 owner 定的是走哪条路——或者认第 3 批以「9/10 项出口全绿 + 这一条挂着」收口。

---

## 关闭（`WIRE-11` · 2026-08-06）

**owner 2026-08-06 裁决走第 1 条：建表 + 真 resolver**，
NEVER 用 `lambda _u, _o: "owner"` 换一个绿色的计数。兑现它的是第 4 批这九张卡：

| 卡 | 做了什么 |
|---|---|
| `AUTH-01` | 迁移 0020 落 `users` / `orgs` / `memberships` 三张表 |
| `AUTH-02` | `flint/authz` 真 resolver 与真归属；查不到返回 `None`，NEVER 兜底 |
| `AUTH-03` | 身份入口：缺头 401 / 未知用户 401 / 无角色 403，三种拒绝三个 code |
| `AUTH-04` | 越权矩阵 12 格；把 resolver 换回假手，拒绝格全部翻绿（证明它们在量权限） |
| `AUTH-05` | 全仓假手退役——**实际是五处，不是本单写的三处** |
| `WIRE-07` | analysis 三条 |
| `WIRE-08` | compose 两条（**并补上那一族从来没有的权限门**：改前任何人都能给任意项目提交组稿作业） |
| `WIRE-09` | interventions 四条（含 aligner 的模型缝） |
| `WIRE-10` | combo 一条 + 模型地址进 `Settings` |

**出口判据实跑（`WIRE-11`，2026-08-06）**：

```
python tools/check_fe_be_parity.py --json
scanned:  backend 62 · frontend 16 · expected 16
  backend_not_assembled          0      ← DEC-031 的出口判据，归零
  frontend_untyped_response      0
  app_unbuildable                0
  backend_unused_by_frontend     35     ← 不是判据，GAUGE-11 逐条分诊
  field_drift                    0
```

**归零的意义由一条阴性对照担保**（`test_a_module_that_is_not_mounted_still_turns_the_zero_red`）：
真造一个不挂的模块，未装配那一类必须报出来。
没有它，「0」有两种读法——「量到了、确实全挂上了」与「尺子塌了」，
而两者在报告上长得一模一样。

**第 3 批 `SHIP-03` 卡在这条判据上而记 blocked**，本单关闭后它的前提消失；
第 4 批收尾（`SHIP-04`）会重跑那五条出口命令。

