# v0.4.1 第 5 批 · 完成态报告

> worker · 2026-08-08。机读真相：`docs/progress-v041.jsonl`（本批 18 卡）+
> `docs/steward/tasks-v041-b5.json`。逐卡细节在 `docs/trace/{卡号}.md`。

## 〇、一句话

**17 verified / 1 blocked / 18。** owner 2026-08-07 指认的三件全部做掉；
蓝本缺的六屏补齐；本仓有了**第一把正向尺子**。
**没做成的那一张与十条后端缺口逐条列在第五节，NEVER 用一句「其余无异常」收口。**

## 一、逐卡状态

| 卡 | 状态 | 一句话 |
|---|---|---|
| DS-01 | verified | `_ds_bundle.js` 接进应用（先喂 `window.React` 再插 script，顺序倒了它会静静失败） |
| DS-02 | verified | 热点卡片按素材落成；判据是**运行时计算值与裸 span 的差集**，不是「类名在不在」 |
| DS-03 | verified | 枚举原值换人类标签，七族 37 值从冻结件解析后判等 |
| PLAZA-01 | verified | 广场换卡片（扇形堆叠 + 网格），`PlazaView` 退役 |
| **PLAZA-02** | **blocked** | **地区筛选与 by_source 分列：两条后端面都不存在**（见第五节） |
| PLAZA-03 | verified | 规格 #2.14 四态；骨架卡与真卡同宽（376px，差 <2px）且占住 420px 台面 |
| PLAZA-04 | verified | 卡片三动作接真端点，三种「不成」各说各的话 |
| DESIGN-01 | verified | `design_generate` 接上消费者；顺带补两处会当场抛的缺陷 |
| DESIGN-02 | verified | 工作台三件补齐（输入 / 流式 / `iframe.srcdoc` 预览） |
| DESIGN-03 | verified | 注册表四态落地，**关掉了那张「缺第四态」的单** |
| CHAIN-03 | verified | 主题列表 + 详情（蓝本 P4/P5） |
| CHAIN-04 | verified | 发起分析 + combo 入口（P6/P3） |
| CHAIN-05 | verified | 受众分叉 + 干预页（P11/P10）——**六屏补齐** |
| GAUGE-12 | verified | **第一把正向尺子**：逐屏组件对照，7 屏 / 34 项声明 |
| GAUGE-13 | verified | 蓝本 ↔ 实仓双向对账，**缺屏 0** |
| FIX-07 | verified | Docker 路径不再写死，等待分支不再挂人 |
| FIX-08 | verified | 连跑 30 次抓名字；**30 次未复现，单据保留开着** |
| SHIP-05 | 本报告 | 五条全局门 + 三个出口判据 |

## 二、五条全局门（输出逐字贴入）

```
### 1) ruff check . --no-cache
All checks passed!

### 2) mypy --strict flint
Success: no issues found in 302 source files

### 3) pytest -q（全量）
FAILED tests/v041/test_sse_live.py::test_the_channel_really_connects_and_delivers_at_least_one_event
1 failed, 4316 passed, 12 warnings in 344.51s (0:05:44)

### 4) cd web && npm test -- --run
 Test Files  79 passed (79)
      Tests  802 passed (802)

### 5) cd web && npx tsc --noEmit
(exit 0)
```

**第 3 条不是全绿，如实记账。** 那唯一一条红是
`docs/blocked/DEMO-JOB-NOT-OWNED-BY-THE-PROBE-USER.md`：
第 4 批接上鉴权之后，取证用的样例作业 `m1004-j` **不属于探针那个用户**，
端点正确地回 403、屏上也正确地显示「无权查看」——
**红的是取证样例没跟着鉴权口径对齐，不是产品**。三个修法在单子里等 owner 挑。

本批开工时这一族红有 4 条；另外 3 条已按各把尺子的要求**登记进基线并点名单据**
（`test_mobile_sweep` / `test_screens_live_probe` / `test_ui_restyle`），
剩下这一条是硬失败：SSE 通道确实收不到事件。

另外三条常跑的尺子：

```
python tools/check_line_endings.py     → 行尾一致：219 个文件全是 LF
node tools/i18n_scan.mjs web --fail-on-cjk → CJK 0 / pending 0 / B7 0
node tools/no_scaffold_on_screen.mjs web   → 产品面没有 A 类脚手架
node tools/check_design_constraints.mjs web → 11 条规则，0 处违规
```

## 三、三个出口判据

### A. `check_screen_composition` 零违规 ✅

```
逐屏组件对照：7 屏 / 34 项声明，0 处违规。
```

### B. `check_screen_coverage` 缺屏为 0 ✅

```
屏对照：蓝本 14 条 / 实仓 22 屏；缺屏 0 · 蓝本未登记 1 · 端点对不上 0
  extra {"route": "/demo"}   ← 演示串屏，不是产品屏；它不进两份表是对的
```

### C. 广场屏与设计工作台各跑一次真栈取证 ✅

截图（`.ui-probe/`）：

```
ship5-plaza-light-desktop.png     ship5-plaza-dark-desktop.png
ship5-design-light-desktop.png    ship5-design-dark-desktop.png
```

另有全量冒烟 `harness/fe_smoke.py`：**22 屏 × 2 主题 × 2 视口**，
`horizontal_overflow = 0`，控制台噪声面
`{'/deliverables/[id]': 3, '/jobs/[id]': 1, '/topics/[id]': 1}`（三条各点各的单据）。

## 四、owner 指认的三件，逐件对答

| # | owner 说的 | 现在是什么样 |
|---|---|---|
| ① | 热点广场没用卡片 | 扇形堆叠（420px 台面 · perspective 1100 · 扇形 48° · 重叠 0.48 · 圆点导航 · 键盘可达）+ 全量网格，卡面按 `.dc.html` 逐槽落成。`PlazaView` 已删 |
| ② | AI 设计工作台是空壳 | 输入区 + 流式区 + `iframe.srcdoc` 预览三件齐；注册表四态接了真查询；`design_generate` 的消费者也接上了 |
| ③ | 素材没用上 | `_ds_bundle.js` 接进应用，`StickerTag`/`StatusMark` 在屏上真渲染并按 `_ds` token 计算取值 |

## 五、**没做成的与后端缺口，逐条列名**

### 5.1 唯一一张 blocked 的卡

**`PLAZA-02`（地区与源筛选上屏）** — 两条 acceptance 各要一份后端没有的数据：

1. `GET /plaza/hot` **没有 `region` query**。规格 #2.14 写着「已建，增 query」，
   实测端点签名只收 `day`，带 `region=CN` 回 200 且与不带**逐字相同**——
   接上去就是一个**静静地什么都不筛的筛选器**，比没有更坏；
2. `by_source` **没有每个源的地区**，`REGION-08` 是纯函数、零端点。

**后果**：`RegionSwitch` 与 `SourceColumns` 至今**全仓零页面引用**。
单据 `docs/blocked/PLAZA-02-REGION-QUERY-AND-SOURCE-REGION-NOT-BUILT.md`（含三选一）。

### 5.2 本批新立的九张单（全部 open，各含「需要 owner 的什么」）

| 单据 | 卡在谁那里 |
|---|---|
| `PLAZA-02-REGION-QUERY-AND-SOURCE-REGION-NOT-BUILT` | 后端：广场的 region query + 源地区出口 |
| `DEMO-JOB-NOT-OWNED-BY-THE-PROBE-USER` | owner：取证样例与鉴权口径对齐（三选一） |
| `BACKEND-PROSE-EMBEDS-RAW-ENUM` | 后端：`rule_d.py:44` 把 `not_saturated` 拼进了给人看的句子 |
| `DESIGN-GENERATE-HAS-NO-SUBMIT-ENDPOINT` | 后端：消费者有了、**入口没有**；挂哪条路径待定 |
| `TOPIC-HAS-NO-NAME-TRIPLE` | **冻结件**：`Topic` 没有 `name_native`，而规格 #2.4 要它 |
| `TOPIC-CHOOSE-HAS-NO-WRITE-ENDPOINT` | 后端：选主题只有读端点 |
| `FETCH-LAYER-HAS-NO-NOT-FOUND-STATE` | 前端共用层：`Fetched` 没有 `not_found`，`NotFound404` 组件因此用不上 |
| `EMPTY-HYPOTHESIS-TWO-CODES` | 后端：同一件事两个码（`VALIDATION_FAILED` vs `EMPTY_HYPOTHESIS`） |
| `CARD-ID-COLLISION-DESIGN-01` | steward：`DESIGN-01` 在 v0.4 与本批各是一张不同的卡 |
| `UI01-RULER-JUDGES-EVERY-LATER-SECTION` | 已就地修，**口径请 owner 复核**（几何值算不算写死间距） |

### 5.3 关掉的一张

`UI-DESIGN-SCREEN-NEEDS-A-FOURTH-STATE` → **closed · DESIGN-03**。
关单的条件是**事情做完了**（四态落地 + 中英文案 + 真查询），不是「那张卡跑完了」——
判据 `test_the_fourth_state_sheet_is_closed` 先验四态在位、再验状态行。

### 5.4 保留开着的一张（**有意的**）

`ONE-UNNAMED-FRONTEND-RED-NOT-CAPTURED`：连跑 30 次全绿，**NEVER 关单**。
`FIX-04` 那处间歇红是 **40 次里第 29 次**才复现的；且这一轮没有复现当时的环境
（变异考期间 `globals.css` 被反复改写、dev server 在监听）。
**30 次未复现只能证明它不常见。**

### 5.5 请 owner 裁的两条口径

- **`DEC-034`**：Gate 四分类 **NEVER** 一一映射到 `_ds` 的内容状态八态——
  那八个记号在本仓每一个都已经有主（`disputed` 是 S2-4 的事实状态、
  `sealed` 是被锁 block…）。代价：A/B/C 三类在记号上看起来一样。
  若要四档各有各的记号，那是**给 `_ds` 加记号**，不是借现成的；
- **几何值算不算「写死间距」**：`420px` 台面高、`1100px` 透视距、`300px` 网格列底
  在 `_ds` 刻度里没有对应 token。本批的处理是**允许但必须逐个列名**
  （名单少一条即红）。见 `UI01-RULER-JUDGES-EVERY-LATER-SECTION`。

### 5.6 本批**仍然没有**解决的（工单 §8 原样继承）

K7 免费额度 / K8 单价币种 · 血缘金标 30 天回放 · chart/质量卡/gap hints 的存储面 ·
三条候选新源的响应契约 · 上线前合规手续 · 38 张 owner_review 的实际复核 ·
广场数据是合成的 · 生产部署与 RAGAS。**八条全部在 owner 面**，本批一条都没动。

## 六、这一批学到的三件（写给下一批）

1. **禁止性判据挡不住「没做」。** 广场屏四条 `EYE-03` 判据全绿而它是个 `ul/li`——
   一屏什么都没做时，它没有错误可犯。`GAUGE-12` 是对这件事的直接回应；
2. **尺子自己也会写错，而它错的样子与「代码有病」一模一样。** 本批修了四把：
   UI-01 的样式尺子扫到文件尾、A6 把写屏当成取数屏、i18n 的 `t\("` 正则咬到 `.get("job")`、
   outputs 对账器只读 v04 那份任务表。**每一处都先确认它报得对不对，再决定改谁**；
3. **「组件建好了而屏上没接」是本批遇到最多的形状**——
   `TopicListView` / `ComboEntryView` / `BlockInterventionPanel` / `RegionSwitch` /
   `SourceColumns` 五个组件都建好了，屏一个都没有。`GAUGE-12`/`GAUGE-13` 两道绊线
   就是为它设的：**新屏不登记进取证与声明，它就进不来**。

## 七、机器可核对的清单

```
docs/progress-v041.jsonl        本批 18 卡的逐条事件（append-only）
docs/trace/{卡号}.md            17 份，含装载清单 / 改前改后 / self_review
docs/blocked/*.md               48 张，本批新立 9 张、关 1 张、保留 1 张
docs/屏对照表-v041.md            蓝本 ↔ 实仓的人读版（机读真相是那个脚本）
assets/screen_composition.json  逐屏组件声明（7 屏 / 34 项）
.ui-probe/                      本批全部取证产物（截图 + JSON）
```
