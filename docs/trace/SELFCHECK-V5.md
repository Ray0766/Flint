# SELFCHECK-V5 — AI 设计工作台（DESIGN-01~32 + I18N-09，33 张）@2026-08-03

## ① 出口命令输出摘要

工单 §8 的 V5 出口判据 + DEC-013 升格的那条：

```
$ pytest tests/v04/design -q                → 134 passed
$ cd web && npm test -- --run design        → 238 passed / 19 files
$ node tools/i18n_scan.mjs web --fail-on-cjk
  扫描 79 个源文件 · CJK 0 个文件 · 白名单 0 项 · B7 违规 0     → exit 0（DEC-013 出口判据）
```

全局门（`mypy --strict src` 按 DEC-003 → `flint`）：

```
$ ruff check . --no-cache   → All checks passed!
$ mypy --strict flint       → Success: no issues found in 269 source files
$ pytest -q                 → 1840 passed in 138.33s
$ npm test -- --run         → 524 passed / 58 files
$ npm run typecheck         → 干净
```

其余守门工具（本增量新增五把，全部自带阴性对照）：

```
$ node tools/lint_no_confidence_viz.mjs web                        → exit 0
$ node tools/no_external_fonts.mjs web                             → exit 0
$ node tools/no_hardcoded_models.mjs web                           → exit 0
$ node tools/scan_ds_assets.mjs web/public/_ds --tabular-nums --no-warn-emoji → exit 0
$ python tools/orthogonality_check.py --combos all                 → exit 0
```

结构与冻结件：

```
$ python tools/validate_dag_v04.py --file tasks-v04.json  → acyclic true / nodes 104 / errors []
$ python tools/check_frozen_additive.py contracts/models.py contracts_v04/models_v04.py     → 通过
$ python tools/check_frozen_additive.py contracts/protocols.py contracts_v04/protocols_v04.py → 通过
contracts/models.py md5 380d7b5a7dae…   contracts/protocols.py md5 eb19b73e176e…
```

冻结件 md5 与 V2/V3/V4 三次出口**逐位一致**——本增量自始至终零改动。

**卡数**：tasks-v04.json 全量 **104 张，全部 verified**（零 blocked、零 skipped_by_owner）。
台账 `cycles_used` 合计 **121**，与 DAG 估算的 123 相差 2（DESIGN-08/10 等几张估 2 实际 1，
另有 I18N-09 等新增卡）。

## ② 本阶段 DECISIONS 汇总

| 编号 | 内容 | 触发卡 |
|---|---|---|
| DEC-016 | 补齐 DEC-007 漏掉的两处裸 `web/src` → `web`（DESIGN-17/23 的 verify_cmd 与工单两行） | DESIGN-17 |
| DEC-017 | `_ds` 移除两条外部字体 `@import`，走已声明的回落栈；品牌字形待 owner 提供 woff2 二进制 | DESIGN-21 |

（V5 期间未新增其它 DEC；§9-P2 的判据注册表**仍未采纳**，DESIGN-32 按隔离带约束
选择「加一层」而非抽取重构，理由见其 trace。）

## ③ 未清 blocked 清单

| 单子 | 状态 |
|---|---|
| `DESIGN-21-FONTS.md` | **非阻塞·待 owner 一句话**：给 woff2 二进制自托管，或明确接受系统回落字体 |
| `SCHEMA-05-FROZEN-WORDING.md` / `REGION-06-AXIS-WORDING.md` / `CLAUDE-S3-LAG.md` | 非阻塞措辞/滞后登记，待 owner 一句话 |
| `HOTSPOT-03.md` | 已关闭（DEC-012 甲案） |
| `I18N-01.md` / `I18N-FRONTEND-GROUP.md` / `CONCURRENT-WORKER-COLLISION.md` / `V0-PROMPTS-LOCK.md` | 根因已消除，可标记关闭 |

**登记未做项（owner 已知情、本增量 NEVER 动手）**：
① 乙案 cluster→判定持久化 → v0.4.1 候选（DEC-012）；
② §9-P1（收藏快照 pin）、§9-P2（判据注册表）、§9-P3（delta ephemeral）三提案均未采纳，
基线路径已交付且风险各自登记在对应 trace；
③ undo 链在 GRAPH-04/07/09 三处的**接线**（缝 `pushUndo` 已留，见 GRAPH-10 trace）。

## ④ 下阶段风险一句话

v0.4 增量四个阶段的护栏已成体系（三条铁律 → 五把扫描器 → 两道导出闸门 → 两阶段承重墙），
但**它们目前只在 CI 与本地跑过，没有一次真实用户流量**：真正的风险在接线层——
本增量交付的多是模块与判据，`flint/api/` 只新增了两条路由（`graph_edges`、`views` 未动），
前端也没有页面级装配的端到端跑通。下一步若进 v0.4.1，**第一件事应是端到端接线与
一次真实 demo 跑通**，而不是继续加判据：判据再多，没接上就一条都不生效。
