# blocked · 同一 v0.4 DAG 上有第二个执行 agent 在并行写

**状态** historical · 2026-08-02 · 历史留存

> ## ⚠ 历史留存 —— 这不是当前状态
>
> 本单记的是**当时**的状况，已不再更新。
> **NEVER 把它当作当前状态引用**：当前状态看 `docs/progress-v041.jsonl` 的尾部
> 与各单顶部那行 `**状态**`。
> 照着一份过期的地图走，而地图上没有一个字说它过期了——那是这条横幅要挡的事。

**发现时间** 2026-08-02（我准备写 REGION-03 时）
**性质** 不是卡内技术问题，是**运行前提被破坏**：`worker.md` §1 写明「你是本仓库 v0.4 增量的
**唯一执行 agent**」，而事实上有第二个 agent 在同时执行同一批卡。

## 证据一：台账里有不是我写的行，且时间戳倒序

```
2026-08-02T10:13:59Z  REGION-01    verified   ← 我
2026-08-02T10:30:00Z  REGION-02    started    ← 不是我（我的 started 在更早）
2026-08-02T10:35:00Z  REGION-02    verified   ← 不是我
2026-08-02T10:40:00Z  REGION-03    started    ← 不是我
2026-08-02T10:58:21Z  REGION-02    verified   ← 我（同一张卡第二条 verified）
2026-08-02T10:45:00Z  REGION-03    verified   ← 不是我（时间戳早于上一行）
2026-08-02T10:48:00Z  REGION-04    started    ← 不是我
```

- **REGION-02 有两条 verified**（10:35 与 10:58），分别来自两个 agent；
- 时间戳**非单调**（10:58 之后出现 10:45），说明两侧各自按自己的时钟追加；
- append-only 台账因此已经不是一条可信的时间线。

## 证据二：对方把我刚写的文件当成了「前会话产出」

对方 REGION-02 的 note 原文：

> 「输出文件已存在（前会话或 REGION-01 越界产出），未在 progress 登记。本会话从 verify_cmd 开始……
> 产出文件均由前会话创建（progress 无记录），本会话验证通过并补录。」

那些文件是我在 10:52~10:58 之间写的（`flint/region/ingest_fields.py`、
`flint/grounding/original_only.py`、两个测试）。对方读到它们时我还没写完台账，
于是把它们判成「前会话遗留」并**替我补录了一条 verified**。

## 证据三：文件层已经在互相插队

- `flint/region/tier_gate.py` 与 `tests/v04/region/test_unknown_tier_gate.py`（REGION-03）
  由对方创建 —— 我在准备写同名文件时才发现，**没有覆盖**。
- 此刻 `pytest tests/v04/region -q` **collection error**：
  对方已写 `tests/v04/region/test_cluster_bucketing.py`（REGION-04 的红态），
  但 `flint/region/bucketing.py` 尚未落地。这是对方的中间态，不是缺陷。

## 风险（为什么必须现在停下问，而不是继续跑）

1. **静默覆盖**：两个 agent 领同一张卡时，后写的一方会无声地盖掉先写的一方。
   我的 REGION-02 产出这次幸存，纯属侥幸——对方选择了「验证既有文件」而不是重写。
2. **台账失真**：同一张卡两条 verified、时间戳倒序，`worker.md` §2.1
   「读末 20 行定位在跑/被阻卡」这条会话启动规则**从此不可靠**。
3. **自审失真**：对方为我的产出写了自审结论（「自审五项…」），
   而那些代码的判断依据只在我的 trace 里。谁为质量负责变得不清楚。
4. **DEC 编号与 blocked 单会撞号**（我已用到 DEC-005）。

## 我没有做的事

- **没有覆盖**对方的 `tier_gate.py` / `test_unknown_tier_gate.py`（已读过，11 passed，
  实现与 acceptance 相符——它把门做成布尔前置门、不携带评分，判断是对的）；
- **没有回改**台账里任何一行（§8：append-only，NEVER 回改历史）；
- **没有继续领 REGION-04**（对方 10:48 已 started）。

## 需要 owner 决定（三选一）

| 方案 | 动作 | 代价 |
|---|---|---|
| **A（推荐）** | 只保留一个执行 agent：停掉另一侧，由留下的那个从台账实际状态续跑 | 最简单；台账仍需一次人工对齐（去重 REGION-02、确认 REGION-03 归属） |
| B | 两侧继续，但**按卡号分区**（例如我只领 I18N-*，对方只领 REGION-*），并各自用独立台账文件 | 要改 worker.md §1「唯一 agent」的前提，且合并台账时仍要人工对齐 |
| C | 我这侧停手待命 | 我手上没有未收口的产出（REGION-02 已 verified 且全量门绿），随时可停 |

在你回话之前，我**不再写任何 v0.4 卡的产出文件**，以免与对方互相覆盖。
