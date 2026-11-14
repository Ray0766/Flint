# v0.4.1 第 6 批 · 完成态报告

> worker · 2026-08-09。机读真相：`docs/progress-v041.jsonl`（本批 18 卡）+
> `docs/steward/tasks-v041-b6.json`。逐卡细节在 `docs/trace/{卡号}.md`。

## 〇、一句话

**17 verified / 1 blocked / 18。** owner 2026-08-08 的四条裁决全部落地；
广场那张卡的六槽填上两槽（首见日期 · 地区），两条缺的写入口都建好了；
**九张问题单关掉**（工单说七张，实际清了九张）。

**`pytest -q` 零 failed —— 本批那条额外出口判据达成**（4518 passed）。

**没做成的那一张与本批新立的六张单逐条列在第六节，NEVER 用一句「其余无异常」收口。**

## 一、逐卡状态

| 卡 | 状态 | 一句话 |
|---|---|---|
| DEC-035-038-LANDING | verified | 四条裁决进册。判据不判「编号出现了」——那样写一行「见工单」也能过 |
| SLOT-01 | verified | 首见日期上屏。**零迁移**：那一列 SQL 一直在查，喂完新颖度就丢——一步之遥 |
| **SLOT-02** | **blocked** | **热点簇身上没有一样东西是 Revalidator 能判新旧的**（见第六节） |
| SLOT-03 | verified | `translate` 接上消费者。取源/落盘走注入端口——两件都不是本卡能替产品决定的 |
| SPEC-01 | verified | `DEC-036` 落地 + 一条防漂移判据：提名称三元组的行 MUST 点名实体，且该实体真有那两字段 |
| REGION-08 | verified | 迁移 0021 + 回填（192 写入 / 1 跨区留 `NULL`）+ 日更写入。`upgrade`/`downgrade` 都实跑 |
| REGION-09 | verified | 端点真筛。合法值取自冻结件词表，**不是「表里现在有什么」** |
| REGION-10 | verified | 筛选器上屏；`SourceColumns` 据实没接（第六节） |
| ENTRY-01 | verified | `POST /projects/{id}/design_generate`。四种拒绝各说各的 |
| ENTRY-02 | verified | `POST /projects/{id}/chosen-topic`。刷新之后选择仍在 |
| FIX-09 | verified | 给探针种一条属于它的作业。**403 NEVER 进噪声白名单** |
| FIX-10 | verified | 空假设一个码一句话。那句话**从校验器身上取**，NEVER 手抄 |
| FIX-11 | verified | 取数层补 `not_found`。「这一条不存在」不再被说成「系统出错了」 |
| FIX-12 | verified | 后端不再把枚举原值拼进人话；留下一把扫全 `flint/` 的尺子 |
| FIX-13 | verified | `globals.css` 小节边界固化。四份抄件收成一处 |
| FIX-14 | verified | 卡号跨批次唯一 + 歧义即抛。**四张撞车，不是一张** |
| GAUGE-14 | verified | 对账器两个盲区修掉，**12 条误报移出** |
| SHIP-06 | 本报告 | 五条全局门 + 三个出口判据 |

## 二、五条全局门（输出逐字贴入）

```
### 1) ruff check . --no-cache
All checks passed!

### 2) mypy --strict flint
Success: no issues found in 306 source files

### 3) pytest -q（全量）
4518 passed, 12 warnings in 311.86s (0:05:11)

### 4) cd web && npm test -- --run
 Test Files  80 passed (80)
      Tests  812 passed (812)

### 5) cd web && npx tsc --noEmit
(exit 0)
```

**第 3 条本批零 failed。** 第 5 批收在 `4316 passed / 1 failed`，
那条 SSE 红由 `FIX-09` 修掉——**改的是取证样例，不是产品**：
`/jobs/m1004-j` 回 403 是鉴权正确工作的证据，
`403` **没有**被加进噪声白名单（有一条判据专门守着）。

另外常跑的尺子：

```
python tools/check_line_endings.py         → 行尾一致：220 个文件全是 LF
python tools/check_outputs_declared.py     → 三类差异只剩白名单里的历史条目
node tools/i18n_scan.mjs web --fail-on-cjk → CJK 0 / pending 0 / B7 0
node tools/no_scaffold_on_screen.mjs web   → 产品面没有 A 类脚手架
node tools/check_design_constraints.mjs web→ 11 条规则，0 处违规
node tools/check_screen_composition.mjs    → 7 屏 / 36 项声明，0 处违规
python tools/check_screen_coverage.py      → 缺屏 0 · 端点对不上 0
```

## 三、三个出口判据

### A. 切区后广场卡片集合真的变 ✅

真屏实测（`.ui-probe/plaza_region_filter.json`）：

```
全量 154
CN 68 · AU/FR/GB/IT/JP/KR/SG/US 各 0（各自落既有「该区当日无数据」态）
URL 跟上（?region=CN）· 控制台 0 错 · 区名与 options 逐字相同（无「全球」）
```

端点侧：`154 → CN 68 · US 0（200 + 空）· ZZ 400`。

**「US 是 0」不是没筛出来，是那个区今天真的没有热点**——
`REGION-09` 的合法值取自**冻结件词表**而不是「表里现在有什么」，
所以合法但无数据的区回 200 + 空，而不是 400「这个区不存在」。

判据不是「两个非空区不同」（本机只有 `CN` 有数据），而是更强的三条：
至少一个非空真子集 · 至少一个被筛空且落空态 · **没有任何一个区回全量**。
**改前那一版一条都过不了。**

### B. 卡面六槽里首见日期真显示 ✅ / 陈旧标记 —— **没有** ⚠

真屏实测（`.ui-probe/plaza_first_seen.json`）：**159 张卡，159 张都量到首见日期**，
且屏上的值与端点回的**逐字相同**（库 → 端点 → 屏三处比对）。

**陈旧标记这一槽本批没填**，理由不是没做完，是**做不了**：
热点簇身上没有一样东西是 Revalidator 能判新旧的（见第六节 6.1）。
按 `DEC-032` 的诚实态，那一槽**恒隐藏**，并有判据钉死唯一那条捷径。

### C. 对账器 `backend_unused_by_frontend` 误报为 0 ✅

```
改前  35 条：unused 32（其中 14 条是「尺子看不见」）· wants 0 · 类型两类 0
改后  36 条：unused 20 · wants 1 · field_mismatch 7 · frontend_untyped_response 8
误报残留：[]（12 条逐条点名钉住）
```

**「条数变多了」不是变差**：wants 那 1 条是真的（前端在调
`POST /workbenches/{id}/nodes`，后端只有 `…/edges`），
15 条类型缺口**本来就在，只是量不到**——盲区修掉才第一次看见。

## 四、owner 四条裁决，逐条对答

| 裁决 | 落地 |
|---|---|
| `DEC-035` 地区面走迁移 | 迁移 0021 + 回填 + 日更写入 + 端点真筛 + 屏上筛选器（`REGION-08/09/10`） |
| `DEC-036` 主题三元组改规格不动冻结件 | 规格 #2.4 与屏总表订正、`CHAIN-03` 卡面一并订正、单据关闭（`SPEC-01`） |
| `DEC-037` 那条红改取证样例 | 种了一条属于探针的作业，样例改指它，**403 没进噪声白名单**（`FIX-09`） |
| `DEC-038` 维持 `DEC-034` | `verdictStatus.ts` 一个字没改；代价（A/B/C 三类记号相同）写进册 |

## 五、这一批做成的三件（不在卡面上的收获）

1. **同一个形状撞了五次**：判据把**解释问题的那句话**当成问题本身
   （规格 `#2.4` 的作废原文 · `backfill.py` 的「不复用那个异常」·
   噪声基线里的「NEVER 把 403 加回来」· `check_fe_be_parity` 里那串旧白名单 ·
   `FIX-12` 的枚举扫描器撞上 `raise` 的中文消息）。
   五次的修法都不是放宽判据，而是**给「引述」一个位置**：
   Markdown 引述块 + 裁决号、剥注释、`raise` 的实参不算；
2. **两把尺子报得不对，而报错的样子与真有病一模一样**：
   `UI-01` 那把扫到文件尾（`FIX-13`）· 对账器那两个盲区（`GAUGE-14`）。
   每一次都先确认它报得对不对，再决定改谁——
   本批有三次因此**撤回**了对尺子的改动（网络尺子 · outputs 尺子 · 两次插错位置）；
3. **判据的前提会过期，而过期的判据看起来与真回归一模一样**。
   本批动了**十一份**既有判据，每一份都在判据上方写清「红的是什么」：
   `translate` 离开未接线名单 · `TOPIC-HAS-NO-NAME-TRIPLE` 被裁决关掉 ·
   两码统一 · 404 从 `failed` 变 `not_found` · A 类整类消失 · 三条钉零的……

## 六、**没做成的与新立的单，逐条列名**

### 6.1 唯一一张 blocked 的卡

**`SLOT-02`（卡面陈旧标记）** — 适配器在，卡在「拿它去判谁」。

`analysis_stale` 要三样输入（项目 id · 账本前后版本 · 引用的事实），
`clusters` 表一列都没有——**一个热点簇不是一份分析**，它不引用事实，
它是事实的来源之一。

全库带 `stale` 的只有 `deliverables.stale_reasons` 与 `pricebook.stale_after_months`；
唯一能挂到簇上的 `Favorite.snapshot_stale` 说的是「**你收藏的那份快照**旧了」
而不是「这个热点旧了」（`DEC-038` 同形），且它的 store 是内存件、表不存在、
demo 没挂那一族、广场还是匿名屏。剩下 `last_active` 那条捷径被**三处**明令禁止。

单据 `docs/blocked/SLOT-02-A-CLUSTER-HAS-NOTHING-THE-REVALIDATOR-CAN-JUDGE.md`，
**四选一等 owner**（推荐甲：恒不显示 + 判据钉死时间戳捷径）。
随单交付 9 条判据，本批已绿。

### 6.2 本批新立的六张单（全部 open，各含「需要 owner/下一批的什么」）

| 单据 | 卡在谁那里 |
|---|---|
| `SLOT-02-A-CLUSTER-HAS-NOTHING-THE-REVALIDATOR-CAN-JUDGE` | **owner**：四选一 |
| `REGION-08-GLOBAL-IS-A-SOURCE-CONSTANT-NOT-A-REGION` | **owner**：`global` 算不算一个区（一句话即可） |
| `JOB-SCREEN-HAS-NO-DENIED-STATE` | 前端：作业屏没有「无权查看」态，403 之后停在加载骨架上 |
| `SCREEN-DATA-HOOK-HAS-NO-REFETCH` | 前端：`useScreenData` 没有 refetch 句柄，写完只能整屏重读 |
| `DEMO-TOPIC-SAMPLE-ID-IS-A-PLACEHOLDER` | **owner**：种不种一条 demo 主题（三选一） |
| `PARITY-WIDER-SCAN-REVEALS-FIFTEEN-TYPE-GAPS` | 前端：15 条类型缺口 + 1 条真缺的端点 |

### 6.3 关掉的九张

```
DEMO-JOB-NOT-OWNED-BY-THE-PROBE-USER          FIX-09
TOPIC-HAS-NO-NAME-TRIPLE                      SPEC-01（DEC-036）
DESIGN-GENERATE-HAS-NO-SUBMIT-ENDPOINT        ENTRY-01
TOPIC-CHOOSE-HAS-NO-WRITE-ENDPOINT            ENTRY-02
EMPTY-HYPOTHESIS-TWO-CODES                    FIX-10
FETCH-LAYER-HAS-NO-NOT-FOUND-STATE            FIX-11
BACKEND-PROSE-EMBEDS-RAW-ENUM                 FIX-12
UI01-RULER-JUDGES-EVERY-LATER-SECTION         FIX-13
CARD-ID-COLLISION-DESIGN-01                   FIX-14
PARITY-BLIND-TO-PAGES-AND-UNLISTED-PREFIXES   GAUGE-14
```

（十条——`PLAZA-02` 是**部分**关闭：缺口一「region query」建成了，
缺口二「`SourceColumns` 的原文词面」换了形状仍开着，见 6.4。）

### 6.4 `PLAZA-02` 缺口二：`SourceColumns` 仍然接不上

它要 `SourceStatement{sourceId, region, text}`，`text` 的契约逐字是
「**原文；NEVER 是译文**」。广场每个源手上只有**分值**与**地区**——
把分值塞进那个槽，就是拿一个已经有主的槽去说另一件事。

真正缺的是每个源的**原文词面**（`trend_items_raw.keyword`：
微博说「脑机接口」、GitHub 说 `bci`），那正是 `PRINCIPLES#B4`
「把话还给说话的人」要的东西——**离端点只有一个字段**，
但那是 `flint/api/views.py`，不在 `REGION-10` 的 outputs 里。

### 6.5 两处我**越了卡上 outputs**（请 steward 复核）

1. **`ENTRY-02` 改了 `flint/topic/store.py`**：`PgProjectStore.save` 原是纯 `INSERT`
   （只能建不能更，唯一调用方永远新建所以缺口一直没被执行到），
   本卡第二次 save 当场 500。改成 upsert（`created_at` 不进更新列）。
   判断依据：那是**持久化助手的机械缺陷**，形式唯一、可逆，
   且卡的 acceptance 没有它不成立——与 `SLOT-02` 那种**产品决定**不同。
   若该走单据，回退只需一行；
2. **`FIX-14` 的处置与卡面不同**：卡面写「改新的那张」，而四张新的也全部 verified 了，
   改号会让 append-only 台账里的事件指向空处。**一个号都没改**，
   改的是唯一性判据 + 歧义即抛。理由逐条在 `docs/trace/FIX-14.md`。

### 6.6 本批**仍然没有**解决的（工单 §7 原样继承）

Gate 判定槽（cluster→判定未持久化，`DEC-012` 的乙案未开工，属 owner）·
K7 免费额度 / K8 单价币种 · 血缘金标 30 天回放 · chart/质量卡/gap hints 的存储面 ·
三条候选新源的响应契约 · 上线前合规手续 · owner_review 的实际复核 ·
广场数据是合成的 · 生产部署与 RAGAS。**九条全部在 owner 面，本批一条都没动。**

## 七、机器可核对的清单

```
docs/progress-v041.jsonl        本批 18 卡的逐条事件（append-only）
docs/trace/{卡号}.md            17 份，含装载清单 / 改前改后 / self_review
docs/blocked/*.md               54 张，本批新立 6 张、关 10 张（含 1 张部分关闭）
docs/端点分诊-v041.md            20 条（A 类整类消失，见 GAUGE-14 trace）
docs/前后端对账表-v041.md        36 条发现，--write 重跑写回
assets/screen_composition.json  逐屏组件声明（7 屏 / 36 项）
migrations/versions/0021_*.py   clusters.region（upgrade/downgrade 都实跑过）
.ui-probe/                      本批全部取证产物（截图 + JSON）
```
