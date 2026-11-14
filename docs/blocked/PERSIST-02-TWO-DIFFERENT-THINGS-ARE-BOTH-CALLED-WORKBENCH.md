# `PERSIST-02`：仓里有**两个**东西都叫「工作台」，而 `workbenches` 这张表只能是其中一个

**状态** closed · 2026-08-09 · `PERSIST-02`

**开单人**：worker，第 9 批 `PERSIST-02-a` 执行中（2026-08-09）。
**状态**：blocked——**需要 owner 定一句口径**。
**卡**：`PERSIST-02`（本卡按 §4.5 已拆成 `-a` 存储 / `-b` 读端点与屏，两半都卡在这一条上）。

## 现象

`DEC-048` 要建的八张表里有一张叫 `workbenches`。开工写迁移时发现：
**「工作台」在本仓是两个不同的东西，它们的字段对不上，而 `workbenches` 只能是一张表。**

### 甲：`POST /workbenches`（`ENTRY-03` 建的，前端在用）

```
flint/api/workbenches.py     POST /workbenches            body {seed_cluster_id}
                             POST /workbenches/{id}/nodes
web/components/plaza/cardActions.ts#addToWorkbench        广场三动作里的「入台」
```

它知道的东西只有三样：**谁**（`x-user-id`）、**哪个热点**（`seed_cluster_id`）、
**什么时候**。`graph_id` 由 `(user_id, cluster_id)` 哈希决定（`flint/api/app.py`）。

**它没有项目，也没有标题。**

### 乙：`WorkbenchGraph` + `WorkbenchStore`（`GRAPH-14` / `SCHEMA-08` 建的数据层）

```python
# contracts_v04/models_v04.py —— 冻结加件，NEVER 修改
class WorkbenchGraph:
    graph_id: str
    project_id: str        # ← 必填
    owner: Principal
    title: str             # ← 必填
    created_at: datetime
    updated_at: datetime
    archived: bool = False
```

```python
# flint/graph/multi.py:37
class WorkbenchStore:
    """内存实现；SQL 实现随 E2 的 `workbench_graphs` 表接入。"""
```

注意它自述要的表名是 **`workbench_graphs`**，不是 `workbenches`。
`create_workbench(...)` 的形参里 `project_id` 与 `title` **都是必填**。

**甲从来不碰乙**：`flint/api/workbenches.py` 里没有一处 import `flint/graph/multi.py`。
两者今天各活各的。

## 为什么这不是「随便挑一个」

`workbenches` 这张表要给甲用（卡面 acceptance ②③④ 全是甲那条路：
建工作台 → 回 `graph_id` → 幂等 → `/workbenches/[id]` 打得开）。
可是甲**填不出 `WorkbenchGraph` 的两个必填字段**：

- **`title`** 还能诚实地取（热点的 `canonical_name`），这一条不难；
- **`project_id` 填不出来**。入台这条路上**根本没有项目**——
  用户是在广场上点一张热点卡片的「入台」，那时候他还没有建任何项目。

而 `WorkbenchGraph.project_id: str` 是**必填**。于是只剩三条路，**三条都不能由 worker 自己选**：

| 路 | 后果 |
|---|---|
| 填一个空串或者拿 `graph_id` 顶上 | **凭空造出一段关系**。之后任何「这张图属于哪个项目」的查询都会取到一个不存在的项目，而**造出来的行与真的长得一模一样**；`S2` 三条铁律里「数字必有出处」的同一条精神在这里就是「关系必有出处」 |
| 改 `contracts_v04`，让 `project_id` 可空 | `S2-1` / `worker.md` §1.1 写死：冻结件是唯一真相，**类型不够用要停下报 owner**，NEVER 自行改 |
| `workbenches` 表按甲的形状建（`graph_id` · `owner_id` · `seed_cluster_id` · `created_at`），与 `WorkbenchGraph` 无关 | 可行，**但那等于宣布仓里从此有两个「工作台」概念**，而这是一个产品决定，不是实现细节 |

## 我倾向哪一条（**但 NEVER 替 owner 决定**）

**倾向第三条**，理由是它不需要编造任何东西，而且它承认的是**已经存在的事实**：

- 甲是「**一个热点起一张思考图**」——从广场入台，无项目；
- 乙是「**一个项目下的若干张台**」——`GRAPH-14` 明写「多工作台数据层 + archived，
  UI 单台，交互待 `K6`」，且入口 flag 默认 **off**。

两者本来就是**不同阶段的两个东西**，只是名字撞了。落地形态会是：

- `workbenches`（本卡建）＝ 甲：`graph_id` PK · `owner_id` · `seed_cluster_id` · `created_at`；
- `workbench_graphs`（**本批没有卡**）＝ 乙：`WorkbenchGraph` 逐字段落表，
  等 `K6` 的交互稿与 flag 打开时再建。

**代价要写清**：这样一来「我的工作台列表」将来会有两个来源，
合并那一步的口径（同一个 `graph_id` 会不会同时出现在两张表里）今天没有答案。

## 需要 owner 的什么

**一句话就够**，三选一：

1. **「`workbenches` 就按入台那条路的形状建，`WorkbenchGraph` 是另一件事」**
   → worker 立刻继续 `PERSIST-02-a`，并在 `DECISIONS-v04.md` 记一条
   把两个概念的分界写死（含上面那条代价）。
2. **「两者是同一件事，入台也该先有项目」** → 那是产品流程改动
   （广场点「入台」要先建/选项目），`ENTRY-03` 与 `NAV-03` 的前端都要改，
   本批放不下，请给一张新卡。
3. **「先按乙的形状建，`project_id` 允许一个明确的『无项目』哨兵值」**
   → 那要改 `contracts_v04`（`project_id: str | None`），**属冻结件修订通道**，
   由 owner 走 `additive` 校验后下达。

## 绕行现状

- `PERSIST-02-a` 的判据文件已写好（`tests/v041/test_workbench_persist.py`，先红），
  **迁移 0024 没有落盘**——号留着，NEVER 让下一张卡占掉。
- **号不留了**（**上面这条纪律写错过一次，2026-08-09 当天改回来**）：
  第一版为本卡保留 `0024`，让 `PERSIST-03` 编成 `0025`。
  那留出来的正是一个**跳号**，而本批 rules 写死「NEVER 跳号也 NEVER 撞号」；
  仓里三把尺子当场判红（`test_persist_fav_share_prefs` /
  `test_project_optimistic_lock` / `test_cluster_region` 各自的号段判据）——**它们是对的**。
  「四张迁移卡各是哪一号」是 trace 上的记账方便，「号段不许有洞」是写死的不变量，
  两者冲突时后者赢。**`PERSIST-03` 已占用 `0024`**，本卡解阻后接盘上当时最高的那一号。
- 入台今天**仍然拿得到 `ok`**（端点早已装配，`ENTRY-03`），只是那张图活不过一次进程重启。
  这一条与「拿不到 ok」是两种不同的坏，已在 `docs/trace/PERSIST-02.md` 写明。
- worker 转去做下一张依赖就绪的卡（`PERSIST-03`）。

## 顺带纠正卡面两处与实况的出入（与本单同一次核查）

1. 卡面 acceptance ① 写「`POST /workbenches` 也没挂……对账器
   `frontend_wants_missing_backend = 1`，那一条就是它」。
   **实跑对账器：`frontend_wants_missing_backend = 0`**——
   `ENTRY-03` 早就把两条端点建好并装配了（`flint/api/app.py`）。
   真正剩下的对账缺口是 **`frontend_untyped_response = 2`**
   （`/workbenches` 与 `/workbenches/{}/nodes` 在 `web/lib` 里没有类型），归 `PERSIST-02-b`。
2. 卡面 acceptance ④ 要求「入台成功后 `/workbenches/[id]` 真能打开并看到刚入台的那个热点」。
   **那条读端点今天不存在**：`web/app/workbenches/[id]/page.tsx` 里写着
   `const graph: WorkbenchGraph | null = null;` 与注释
   「`GET /workbenches`【未建·接口预留】」，而仓里与工作台有关的 `GET` 一条都没有。
   所以 ④ 不是「接线」，是**要新建一条端点 + 前端类型 + 屏接线**——
   这就是本卡拆成 `-a` / `-b` 的直接原因。

---

## 关闭（`DEC-051` / `PERSIST-02`）

owner 2026-08-09 裁决：本批建**甲**（`workbenches`：`graph_id` · `owner_id` · `seed_cluster_id` · `created_at`，不带项目），**乙**（`workbench_graphs`）本批不建、等 K6。冻结件一字未动。

`workbenches` 加 `project_id text NULL`，语义逐字写死在迁移注释里：**NULL =「这张图还没有归属任何项目」**，且 **NEVER 往这一列写一个编出来的项目 id**。

**代价已按 owner 要求写进 `DECISIONS-v04.md`**：「我的工作台列表」今天有两个来源，合并语义未定，**到 K6 交互稿落地时必须回来定一次，NEVER 到那时才发现**。
