# SELFCHECK-V4 — 图谱工作台（GRAPH-01~16，16 张）@2026-08-03

## ① 出口命令输出摘要

工单 §8 的 V4 出口判据（`src/…` 按 DEC-007 重映射）：

```
$ pytest tests/v04/graph -q
39 passed in 0.54s

$ cd web && npm test -- --run components/graph-node components/graph-edge lib/undo lib/graph-layout views
Test Files  16 passed (16)
Tests  128 passed (128)
```

全局门（`mypy --strict src` 按 DEC-003 重映射为 `flint`）：

```
$ ruff check . --no-cache   → All checks passed!
$ mypy --strict flint       → Success: no issues found in 257 source files
$ pytest -q                 → 1716 passed in 159.61s
$ npm test -- --run         → 286 passed / 39 files
$ npm run typecheck         → 干净
$ node tools/i18n_scan.mjs {web/components, web/views, web/lib/undo, web/lib/graph-layout, web/test-utils} --fail-on-cjk
  → 五个目录全部 exit 0
$ python tools/validate_dag_v04.py --file tasks-v04.json
  → acyclic true / nodes 104 / errors []
```

冻结件零改动：`contracts/models.py` md5 `380d7b5a7dae…`、
`contracts/protocols.py` md5 `eb19b73e176e…`（与 V2/V3 出口逐位一致）。

本阶段本会话新增卡 11 张（GRAPH-05~13、15、16），各 1 cycle（GRAPH-07/10 卡上估 2，实际各 1）；
V4 十六张全部 `verified`，零 blocked、零 skipped_by_owner。

**一处环境处置**：跑全局门时 PostgreSQL 未在线（compose 栈被停），
按仓库既有方式 `docker compose up -d postgres redis` 起栈后复跑，1716 passed。
未改任何测试口径、未跳过 compose 用例。

## ② 本阶段 DECISIONS 汇总

| 编号 | 内容 | 触发卡 |
|---|---|---|
| DEC-014 | 新增 `flint/graph/roles.py` 作为「图内主唯一」的**运行时落点**（契约 `set_primary` 是纯规则函数，没有落点可供并发测试打）；临界区语义 = 内存锁 ≡ SQL 同事务 + 部分唯一索引；同文件带反例探针 | GRAPH-06 |
| DEC-015 | `ErrorCode` 注册表增 `EMPTY_HYPOTHESIS` + 新增 `flint/api/graph_edges.py`（acceptance 要真实 422，函数级测试出不了状态码）；单列一码而非并进 `VALIDATION_FAILED` | GRAPH-07 |

另有两处**卡内记录、未占 DEC 号**的决定：GRAPH-10 把三个图谱操作接入 undo 链的
**接线**留作后续卡（缝已留：`pushUndo`）；GRAPH-11 实测到 `i18n_scan` 的第二类假阳性
（CRLF 行尾使行注释剥不掉），已追加为卡 `I18N-09` 的第三条 acceptance。

## ③ 未清 blocked 清单

- `docs/blocked/SCHEMA-05-FROZEN-WORDING.md`、`REGION-06-AXIS-WORDING.md`、
  `CLAUDE-S3-LAG.md` — 三份措辞/滞后登记单，非阻塞，仍待 owner 一句话；
- `HOTSPOT-03.md` 已于 V3 关闭（DEC-012 甲案）；
- `I18N-01.md`、`I18N-FRONTEND-GROUP.md`、`CONCURRENT-WORKER-COLLISION.md`、
  `V0-PROMPTS-LOCK.md` — 根因已消除，可标记关闭。

**登记未做项**：① cluster→判定持久化（乙案）挂 v0.4.1，NEVER 在 V5 任何卡里假定该端点存在；
② undo 链的三处接线；③ `I18N-09` 的三项（两类扫描器假阳性 + `app/` 与旧词条表）
MUST 在 V5 出口前完成，届时整棵 `web/` 树 `i18n_scan` exit 0 升格为出口判据（DEC-013）。

## ④ 下阶段风险一句话

V5 是 DESIGN-01~32 共 32 张 + `I18N-09`，是本增量最大的一批，且其中
DESIGN-27/28/29/31/32 五张属隔离带（owner 可整体划掉）——按 DEC-000 默认照做；
真正的风险是 G 组两阶段模型的**承重墙**（G3 固化 + G6 生产只认模板，见工单 §11-③）：
若实现时把「生产渲染接受任意 HTML」当成可接受的中间态，两阶段会退化成一阶段，
探索期的示例数字就能直接漏进生产文书——那是品牌级事故而非 UI 瑕疵，
故 DESIGN 组开工时 MUST 先落 G6 门禁再落生成路径，顺序反了等于把闸门修在洪水之后。
