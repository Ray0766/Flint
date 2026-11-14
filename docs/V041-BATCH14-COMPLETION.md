# 第 14 批完成态报告 · 计划书主工作台（W14）

**日期** 2026-08-12 ｜ **卡** 10 张（DEC-059-LANDING / WB-01~07 / EYE-05 / SHIP-14）
**蓝本** `前端设计/ai工作台/Flint 设计台 v3.dc.html`（owner 2026-08-12 指定）

---

## 一、与蓝本的逐条对照（首节 · owner 只看这一节也够）

| 蓝本有什么 | 做成了什么 | 哪张截图为证 |
|---|---|---|
| 三栏：左卡片 250 / 中对话 / 右预览，两根 7px 拖条 | 三栏并排，实测 250 / 343 / 1103，同高 818.81，拖得动且中栏留得住 | `eye05/workbench-1920x1080-light.png` |
| 左栏热点卡与证据卡 | 复用广场那张 `HotspotCard` + 搬运层，50 张卡；证据跟着已选热点走 | `eye05/flow-2-picked.png` |
| 中栏对话区 + 底部输入框 + 虚线托盘 | 消息区 579.66 自己滚 + 托盘 + 输入区 239.16 钉住（和为栏高，差 0） | `eye05/flow-3-submitted.png` |
| 「生成」按钮 | 真提交 `POST /projects/combo`，服务端原话原样上屏 | `wb/workbench-generate-1920x1080-light.png` |
| 右栏计划书预览 | 复用既有 `BlockTree`/`BlockView`，八种块逐一渲染，三通道逐格标出处 | `wb/workbench-preview-1920x1080-light.png` |
| sticky 章节导航 138px | `position: sticky`、宽 **138**、点章跳到该章（scrollTop 0 → 259） | `wb/workbench-sections-1920x1080-light.png` |
| 逐章检查问句 | 五套模板逐字落地，每章带占比 / 字数区间 / 检查问句 | 同上 |
| 五模板切换 | 下拉五套，切换后导航与预览同步换 | `wb/workbench-annotate-1920x1080-light.png` |
| 单块批注「只重写这个块」 | 走既有干预层，实跑产出 v2 且**只有那一块变了** | `eye05/flow-5-annotate.png` |
| 缺口提示（资料不足不注水） | `gap_notice` 照渲染；**真产物里那 5 块的提示是空的**，开单 | `wb/workbench-preview-1920x1080-light.png` |

### 哪几处**刻意没照蓝本做**，以及为什么

1. **生成 NEVER 走 HTML 正则**（本批最硬的一条，`DEC-059` 第三节）。
   蓝本让模型直吐 `<part id><block type>` 再正则抠回来——它是个没有后端的独立 demo。
   本仓的链吃的是**结构化 JSON**（`_parse_blocks` 读 `payload["blocks"]`）。
   判据三条：喂 JSON 出真 `Block`（正向）· 把蓝本那套 HTML 喂进去得 **0 块**（结构上吃不下）·
   全仓扫「正则构造件与 `<block`/`<part` 同一条语句」（工单点名那条）。
2. **模型下拉不做**（蓝本有 `Claude Haiku / Sonnet / Qwen 本地` 三选）。
   本批规则第一条：一律免费本地档、NEVER 读 key；摆一个能选中付费档的下拉，
   等于把 `S2-10` 那道人审节点交给用户点。
3. **外链字体不引**（CI 恒不联网，且那是第三方请求）。字体走 `_ds` 既有 `--font-*`。
4. **窄屏纵向排开**（蓝本是桌面 demo，没有响应式）。390 下三栏 x 相同、y 递增。
5. **批注按钮不放在每块旁边**，改成「点选一块 + 一个面板」：块由 `BlockTree`/`BlockView`
   渲染，那是 v0.4 已 verified 的封版件（`DEC-021`），往里塞控件要停下报 owner。
6. **章节导航的标题行放进滚动区并 sticky**（蓝本放在滚动区外）：效果一样，
   而 `WorkbenchShell` 一个字都不用动。

---

## 二、五条全局门（逐字贴出）

```
ruff    All checks passed!
mypy    Success: no issues found in 323 source files
pytest  5594 passed, 2 skipped, 12 warnings in 523.09s
tsc     （无输出 = 干净）
vitest  Test Files 85 passed (85) · Tests 858 passed (858)
```

**pytest 的红逐条点名归属**（本批过程中出现过的 12 条，收尾时全部归零）：

| 红 | 归属 | 处置 |
|---|---|---|
| `test_i18n_*` ×6（两份词典不对称） | 本批新增 key 只写了 zh | 两份补齐（收尾 604 条对称） |
| `test_width_fullbleed` ×3 | **环境**：`:3000` 少 `FLINT_API_BASE`，报告屏（服务器组件）恒 500 | 按 `start-demo.ps1` 重起前端，11 条全绿；与本批改动无关 |
| `test_type_gaps_untyped` / `test_parity_dynamic_path` | 本批引入：`WorkbenchSections` 用裸 `fetch` 调 quality | 加 `QualityReport` 类型 + `fetchQuality` 客户端 |
| `test_endpoint_triage` / `test_triage_02` ×3 | 同上带出：那条端点从「已装配未调用」里退出，两张分诊表与两处计数过期 | 表与判据**三处一起改**（16 → 15、B 类 12 → 11） |
| `test_fe_be_parity` | 同上：对账表是跑出来的，数字过期 | `--write` 重跑 |
| `test_i18n_keys_defined`（动态前缀） | 本批新增三处动态 key | 前缀登记进那张表（`wb.section.` / `wb.check.` / `wb.template.`） |
| `test_smoke_seven` | 《怎么测》新一节的小标题与七屏计数撞车 | 那一节小标题去掉加粗 |
| `test_nav_anime` / `test_wb_layout` ×3 | **WB-07 有意改的**：顶栏次序与旧屏名字 | 判据改判「那一屏还在 + 七项一条不少」，名字归 `test_wb_nav_rename.py` |

---

## 三、十张卡的实况

| 卡 | 终态 | 一句话 |
|---|---|---|
| `DEC-059-LANDING` | verified | 裁决落地，水位 058 → 059 |
| `WB-01` | verified | 三栏骨架，蓝本实数逐个对上 |
| `WB-02` | verified | 左栏复用广场那张卡 |
| **`WB-03-a`** | **verified** | 中栏 + 真提交 + 真回执/真失败 + `never_html_regex` 判据 |
| **`WB-03-b`** | **blocked** | 端到端出真 Block：三处断点、两张单 |
| `WB-04` | verified | 右栏渲染真 Block，八种类型逐一 |
| `WB-05` | verified | 章节导航 + 逐章检查项，五套模板照蓝本逐字 |
| `WB-06` | verified | 模板切换 + 单块批注（**实跑产出 v2，只有那一块变了**） |
| `WB-07` | verified | 旧屏改名「模板工具」退居次要，端点一条没少 |
| `EYE-05` | verified | 六张整屏 + 五张流程图 + `report.json` |
| `SHIP-14` | verified | 本报告 |

---

## 四、本批开的六张单（每一张都写了三种口径与各自代价，**没有自己择一**）

| 单 | 一句话 | owner 要答什么 |
|---|---|---|
| `ANALYSIS-ID-HAS-NO-PATH-FROM-AN-ANALYSIS.md` | `report` 端点要的 `analysis_id` 今天**没有一条从分析拿回它的路** | 甲（端点自己换算）/ 乙（新建 analyses 表）/ 丙（改收 job_id）四选一 |
| `COMBO-FAMILY-HAS-NO-PROVIDER-ANYWHERE.md` | `POST /projects/combo` 在**任何部署上**都是 503：`combo_provider` 全仓没有调用方 | 一句「照 §五 接上」（三行，本机模型、零网络） |
| `REAL-GAP-NOTICES-HAVE-NO-HINTS-REF.md` | 真产物里 5 个 `gap_notice` 的 `hints_ref` 是**空串**——「缺什么」那块提示自己是空的 | 甲（生成期拒绝）/ 乙（兜底算一个）/ 丙（把提示写进块里，**要动冻结件**） |
| `REGENERATE-JOB-WRITES-NO-EVENTS.md` | 重写作业跑完了而 `jobs.state` 仍 `queued`、`job_events` 0 行 | 甲（收尾推状态+写事件）/ 乙（端点回产物 id）/ 丙（新增 successor 端点） |
| `PROJECT-DOES-NOT-LIST-ITS-OWN-DELIVERABLES.md` | 项目总览的 `deliverable_ids` 是建项时写死的一列：库里四份，它只列一条 | 甲（落库回写）/ 乙（总览改查，**更贴近一处定义他处引用**） |
| `QUALITY-FAMILY-HAS-NO-BACKEND.md` | 逐章判定的唯一出处 503，且**就算配上也没有章一级的格子** | 不需决定，登记待销 |

**这六张单合起来说的是同一件事**：从「我提交了一次生成」到「产物是哪一份」，
今天这条链上**三处路都断着**——作业不写状态与事件 · 端点不回产物 id · 项目总览列不出新产出。
屏上因此只说到「已提交」为止，**NEVER 转圈、NEVER 拿夹具冒充**。

---

## 五、取证路径（owner 不用翻目录）

**六张整屏**（三视口 × 两主题）：

```
.ui-probe/eye05/workbench-1920x1080-light.png    .ui-probe/eye05/workbench-1920x1080-dark.png
.ui-probe/eye05/workbench-1440x900-light.png     .ui-probe/eye05/workbench-1440x900-dark.png
.ui-probe/eye05/workbench-390x844-light.png      .ui-probe/eye05/workbench-390x844-dark.png
```

**流程图五张**（人真的会走的顺序）：

```
.ui-probe/eye05/flow-1-empty.png        空手进来：左栏 50 张卡、右栏空态
.ui-probe/eye05/flow-2-picked.png       选两张：托盘里就是那两条
.ui-probe/eye05/flow-3-submitted.png    提交：服务端 503 原话上屏
.ui-probe/eye05/flow-4-blocks.png       出块：22 块 + 七章导航
.ui-probe/eye05/flow-5-annotate.png     点一块提批注
```

**各卡自己的取证**（含 `report.json`，截图与数一起落盘）：

```
.ui-probe/wb/layout.json    generate.json    preview.json    sections.json    annotate.json
.ui-probe/wb/workbench-generate-1920x1080-{light,dark}.png
.ui-probe/wb/workbench-preview-1920x1080-{light,dark}.png
.ui-probe/wb/workbench-sections-1920x1080-{light,dark}.png
.ui-probe/wb/workbench-annotate-1920x1080-{light,dark}.png · workbench-annotate-protected-light.png
.ui-probe/eye05/report.json
```

**从哪进**：顶栏第二项「计划书工作台」。打开一份已有产物：
`http://localhost:3000/workbench?deliverable=del-job-4d22d6be-c3dc-47cf-b334-70a573efb7f4&project=proj-demo-fixture`
（《怎么测-v041.md#工作台》有「看不到时是谁的问题」三条，各带单号。）

---

## 六、本批的「判据自己是缺陷」共 6 次（照惯例逐条留档）

| # | 判据以为自己在量什么 | 实际量到什么 |
|---|---|---|
| 1 | 中栏三块的几何 | 两个时刻各量一半（中间选了卡，托盘长高把输入区顶上去）→ 量出「输入区在消息区上方」 |
| 2 | 「在等」那一态出现过没有 | 掐时间去问，503 几乎立刻回 → 恒 `False`，一次都没量到 |
| 3 | 四态各有记号 | 去源码里找一个**只在运行时存在**的属性值 → 恒红 |
| 4 | 屏上那个数 == 后端那个数 | 拿整格文字去找 → 被文案里的「12 实例月」喂饱 → 恒绿 |
| 5 | 五套模板的章名 | 整块 `TPLS` 扫成扁平字典 → `timeline` 两个名字被压成一个 → grant 判红而屏上是对的 |
| 6 | 右栏现在是什么态 | 外壳与预览容器**同名记号**，`querySelector` 拿到外面那个 → 恒 `null` |

第 5 条与第 6 条尤其值得记：**屏上是对的，红的是判据自己**；
而第 2、4、6 条属于「永远量不到东西」的那一类——它们与「一切正常」在退出码上长得一模一样。

---

## 七、不许碰的线，一条没碰

- `contracts/` 与 `flint/`：本批**一个文件都没改**（六张单里三条修法指向 `flint/`，全部停下开单）；
- `BlockTree` / `BlockView` / `HotspotCard` / `clusterToCard` / `QuoteSlot` / `InstructionRegenerateBox`：
  一个字没改，全部作为调用方复用（各有判据钉着）；
- `/design` 那一屏与它的 7 条端点：一条没少（判据从 `flint/api/` 源码里数）；
- 顶栏 7 个入口一条不少，`/share/[token]` 仍是唯一豁免屏；
- 本批**零真实网络**：`DEC-057` 那个窗口一次都没动用；模型一律本机 Ollama。
