# 第 17 批卡单（2026-10-27 · owner 在会话里直接驱动）

**为什么卡单在 `docs/trace/` 而不在 `docs/steward/`**：本批没有 steward 会话出工单，
owner 在一个会话里给了四条裁决（`DEC-061`~`DEC-064`）并让同一会话接着做。
`worker.md` §9.4 写着 worker NEVER 写 `docs/steward/`——卡单放这里，不越那条线。

**起点实况**（2026-10-27 亲验）：台账末事件 `SHIP-16 verified`；`FLINT-V041-B16-DONE` 在盘；
`WORKER.lock` 不在；六个冻结件哈希与 steward 交接件逐位一致；本机栈全停（docker 未起）。

## 卡

| 卡 | 裁决 | 做什么 | verify_cmd |
|---|---|---|---|
| `REPORT-SRC-01` | DEC-061 | `ReportSubmit` 加 `analysis_job_id`，与既有 `analysis_id` **二选一**（夹具那条路仍用后者）；服务端核作业存在 / 属本项目 / kind=`gate1_analysis` / state=`done`，再用 `analysis_product_id()` 换算 | `pytest tests/v041/test_report_src.py -q` |
| `OVERVIEW-01` | DEC-063 | 总览不再读 `projects.deliverable_ids`；交付物只认 `deliverables` 表那一份列表（已带 version/supersedes） | `pytest tests/v041/test_overview_deliverables.py -q` |
| `REGEN-EVT-01` | DEC-063 | 单块重写作业照 `run_compose` 推 `state=done` 并写终态事件；失败同样落事件 | `pytest tests/v041/test_regen_events.py -q` |
| `CONTRACT-REV-01` | DEC-064 | 三个文件同步加三个带默认值的字段；`check_frozen_additive` exit 0；块读写 / 生成 schema / 渲染认 `missing_what`/`why`；组稿收尾两版互写 `sibling_deliverable_id`（新列，迁移 0028） | `pytest tests/v041/test_contract_rev_01.py -q` |
| `CHAIN-UI-01` | DEC-061/063/064 | 屏上补齐 ②→③：分析完成 → 「生成报告」（带 `analysis_job_id`）→ 作业页 → 产物从总览列表里找到；缺口块显示内容；受众版互链 | `cd web && npx vitest run __tests__/app/chain_ui.test.tsx` |
| `GATE1-REAL-02` | DEC-062 | 真栈：广场 → combo → 主题 → 分析（**真实网络 ≤40 请求**）→ 报告 → 计划书；逐屏截图；往返留痕转回放夹具 | 逐屏截图 + `fixtures/_probe/gate1/` 计数 |
| `SHIP-17` | — | 五条门 + 完成态报告 + `FLINT-V041-B17-DONE` | 五条门 |

## 本批核到的过期前提（`stale_premise`）

`PROJECT-DOES-NOT-LIST-ITS-OWN-DELIVERABLES` 写「总览如实把那一列读出来」——**半对**：
`flint/api/project_overview.py:75-81` 早就另查 `deliverables` 表并回 `deliverables[]`
（带 `version` / `supersedes`）。断的是**读的人**：`WorkbenchAnnotate` 与
`tools/ui_probe_wb_annotate.py` 读的都是 `deliverable_ids` 那条旧列。
所以 `OVERVIEW-01` 的重心是「总览只剩一份真相 + 读的人改读它」，不是「新建一条查询」。
