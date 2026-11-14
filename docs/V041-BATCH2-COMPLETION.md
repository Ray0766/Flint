# v0.4.1 第 2 批 · 完成态报告

> 台账真相：`docs/progress-v041.jsonl`（第 1、2 批共用一本；本报告只算第 2 批的 89 张）。
> 机读任务：`docs/steward/tasks-v041-b2.json`。

## 一、收在哪儿

**89 / 89 收齐 = 88 verified + 1 `skipped_by_owner`**。
停机条件命中第 ①「全部 verified/skipped_by_owner」。

> **2026-08-05 更新**：本节原记「88/89 · 1 blocked · 停机条件②」。
> owner 当日裁决 `DEC-033` 把 `NET-03` 结了案，停机条件随之从 ② 变成 ①。

`NET-03`（真实源冒烟）的经过：卡面 acceptance② 要求断言「已登记未执行」，
而盘上事实与之矛盾（`docs/生产Gate1-真实源切换-payoff.md` 与 `fixtures/gate1_live/`
证明真实源检索已经跑过）。写一条判据把一句不成立的话钉成回归，比不写更坏，
故按 S9 停下上报 `docs/blocked/NET-03-CARD-PREMISE-STALE.md`（两种读法 + 三个选择）。

**owner 的答案是「甲 + 乙 各一半」**（`DEC-033`）：

| 卡面的哪一半 | 结果 |
|---|---|
| 跑一次真实 github/arxiv 检索 | 07-31 payoff 已执行并录制 → `NET-03` 记 `skipped_by_owner`，理由逐字进台账 |
| 经作业队列跑通 gate1 | 缺的是 `gate1_deps` 注入而非网络授权 → **单开普通卡走 respx 回放**，不再挂红线；带回退闸（回放下若暴露真实网络请求，立即回退红线并停下上报） |

**本批零真实抓取发生。**

## 二、全局门（最后一次实跑）

```
ruff check . --no-cache      → All checks passed!
mypy --strict flint          → Success: no issues found in 299 source files
pytest -q                    → 3652 passed
cd web && npm test -- --run  → 74 files / 745 passed
cd web && npx tsc --noEmit   → 2 条**既有**错（`WorkbenchSwitch.test.tsx` 的 `?raw`），本批零新增
node tools/check_design_constraints.mjs web → 4 处（既有已登记缺口，见 §四）
python tools/check_fe_be_parity.py          → 62 条发现（见 §三）
```

## 三、本批最要紧的一条发现：**51 条端点写好了没挂上**

`AUDIT-01` 的对账器第一次把三个面（交付包 README 期望 / `flint/api/` 实况 /
`web/` 实况）摆在一起，头条是：

> `flint/api/app.py` 至今只挂了 `/categories` 一条。其余 **51 条路由全部够不到**。

这件事**在任何单卡的验收里都看不见**：每张卡的测试都是拿自己的 `create_*_app`
直接造 `TestClient` 跑的，造得出来 ≠ 挂上了。本批 BE-01~11 十一族端点、
v0.4 就写好的 deref/interventions/views/compose，全在这 51 条里。

**这是下一步最值得做的一件事**：九张 UI 屏（UI-03~11）此刻全部显示
「接口未提供」，而它们要的后端**已经写完并测绿**——只差装配这一步。

装配卡不在本批范围内（改动面覆盖十一个模块的挂载方式，§六.1 要求停下登记）。

## 四、四张登记单（本批新开三张）

| 单 | 说的什么 | 谁来处置 |
|---|---|---|
| ~~`NET-03-CARD-PREMISE-STALE.md`~~ | 卡面前提与盘上事实矛盾（红线话题） | **已关闭** · owner `DEC-033` 裁决「甲+乙 各一半」 |
| `LOCALE-SEAM-RULER-MISSES-REGION-CODES.md` | BL-09 全仓尺不认九区代码，A3 只守住了语言那条轴 | owner / steward 三选一 |
| `S1-COMMON-STATES-MISSING.md` | S1 三个通用件未建，四个页面无加载态 | 并进 UI 卡或单开一张 |
| `LINEAGE-GOLD-REPLAY-MISSING.md`（既有） | 血缘金标 30 天回放 | owner 未答复，保持挂起 |

## 五、37 张 `owner_review: true` 待看

第 2 批里有 37 张卡标了 `owner_review`，全部已 verified、等 owner 复核。

**其中 UI-01~11 那 11 张的共同问题，owner 2026-08-05 已一次裁完（`DEC-032`）——按既有实现维持**：

> **未装配期间前端一律显示「接口未提供」，NEVER 显示空态／未启用／隐藏入口。**
> 理由（owner 原话）：**没查过 ≠ 空的／坏的**，空态会让用户以为已查证。

同一条裁决把另两处单独的裁决点也一并定死，**都与本批实现一致，零代码改动**：

- **UI-11**：照真件（`BE-01` 已建 `GET /projects/{id}`），
  **NEVER 照蓝本 P14 那句已失效的「无专属端点」**；
- **UI-09**：陈旧横幅在未查证时 **NEVER 挂出**。

**这条裁决随装配落地自动失效**——组件里两条路都留着，切换成本一行。
装配卡（第 3 批首卡）做完后，须回来把这 11 屏切到真数据路径。

余下 26 张 `owner_review` 仍等复核。

## 六、本批干了什么（按族）

| 族 | 卡 | 产出 |
|---|---|---|
| 主题裁决 | DARK-01/02 · COMP-01 | 暗色主题判据接进全局门 · 上线前合规手续独立档 |
| 文档层 | DOC-01~03 | `Doc.content` 三件套 + 迁移 + 事实增厚 |
| 支付 | PAY-01~03 · SHIP-01 | 接入方案 · 计量器（零定价可关） · 静态安全尺 |
| 后端补口 | BE-01~11 | 十一族只读/读写端点，全部带三态与 404 不 403 |
| 对账 | AUDIT-01/02 | 前后端契约对账器 + 表 · 技术约束清单可执行化 |
| 前端 | UI-01~11 | 外壳 + 主链路四屏 + 九张新屏，全部过 EYE-03 两主题取证 |

**本批反复出现、并被判据钉住的一条纪律**（后端与前端各有形态）：

> **「没查过」与「查过了、是空的 / 是坏的」NEVER 挤进同一个表示。**

后端形态是 `status: "not_checked"` 且**连那个键都不给**；
前端形态是 `NotProvided` 与空态各有各的 `data-*-state`。
本批至少 14 处按这条修过或建过。

## 七、给下一批的三条建议

1. **先做装配卡**（§三）。九张 UI 屏与十一族端点之间只差这一步。
   → **owner 2026-08-05 采纳，定为第 3 批首卡（`DEC-031`）**：验收 MUST 含**逐条探活断言**
   （「挂上了」≠「能通」，仅断言 `include_router` 存在判为空转），
   出口判据 = `check_fe_be_parity.py` 的 `backend_not_assembled` 归零。
   **落地时修好了这把尺子的一处硬伤**：它原先按源码字面量扫 AST，
   而 `app.include_router(x.router)` 那一行没有路径字面量——实测量到 **0 条挂载**，
   意味着装配卡即便做全对，计数也永远停在 51，出口判据**不可能达成**。
   现改为**问建起来的应用要路由表**（详见 `DEC-031` 与 `docs/trace/DEC-030-032-LANDING.md`）。
2. **S1 三个通用件**（`LoadingSkeleton` / `EmptyState` / `ErrorState`）——
   `AUDIT-02` 的尺子正盯着那四个页面，修完把 `KNOWN_GAPS` 里对应的行删掉，
   判据会因为「少一条」而红，那正是提醒你去删的机制。
3. **`options` 接线**：BE-07 的 `GET /settings/locale` 已把九区清单当
   `options` 返回；前端目前仍有一份 `REGIONS` 副本（已从两份收敛回一份）。
   接上之后那份副本才能真正退役。
