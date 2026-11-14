# CHAIN-03 · 主链路①：主题列表与主题详情两屏（蓝本 P4/P5）

> v0.4.1 第 5 批第十一张。依赖 `DS-02`（verified）。

## 装载清单

`tasks-v041-b5.json#CHAIN-03` · `docs/前端功能说明-v2.md#2.4` · `contracts/models.py#Topic` ·
`web/lib/topicClient.ts` · `web/components/views/TopicListView.tsx` + 其判据 ·
`web/app/projects/[id]/page.tsx`（路由与取数惯例）· `web/lib/ScreenFetchState.tsx` ·
`harness/fe_smoke.py` 的 `SAMPLE_IDS` · 真栈 openapi 与两条端点。约 15k tokens，**未超 40k**。

## 一、改前实况

- `web/app/` 下**没有 `topics` 那一层**——用户从广场走不到主题；
- `TopicListView` 建好了，但**只有 `DemoFlow` 在用**，且是一个 `ul/li`、**零 className**
  （与退役前的 `PlazaView` 同一形状）；
- 主题详情**连组件都没有**。

## 二、两处规格与实况对不上（各立一单，按实况交付）

### 2.1 冻结件 `Topic` 没有名称三元组

规格 `#2.4` 要主行 `name_native` + 机翻次要行。而 `contracts/models.py:222` 的 `Topic` 是
`topic_id / seed_id / one_liner / target_user_tag / form_factor_tag / why_now /
keyword_mapping / embedding`——**没有那两个字段**。

拿 `one_liner`（一句话描述）顶上就是「借一个已经有主的字段说另一件事」（`DEC-034` 同一条）。
更实际的坏处：`NativeName` 的次要行是机翻派生物且必带机翻标记，主题没有译文，那一槽恒空——
屏上于是是一个「有原文名、永远没有译名」的三元组，**看起来像翻译服务坏了**（A7 降级形态），
而真相是这个实体从来就没有三元组。两者在屏上长得一模一样。

**按实况交付**：两屏照 `Topic` 真有的字段渲染，不画那两槽。
单据 `docs/blocked/TOPIC-HAS-NO-NAME-TRIPLE.md`（属 `CLAUDE.md#S2-1`「冻结件不够用」）。
判据条件写成「冻结件里还没有」——它哪天真加了，那条自动放行。

### 2.2 选主题没有写端点

openapi 里 topic 一族三条**全是 GET**。`chosen_topic_id` 只有读的那一半。
选中态因此**恒由后端的值决定**，列表屏**不传处理器**、**不记本地状态**——
记了的话刷新一次就没了，而用户以为自己已经选过，并会在后面的分析里以为用的是他选的那条。
单据 `docs/blocked/TOPIC-CHOOSE-HAS-NO-WRITE-ENDPOINT.md`。

## 三、取证时又挖出两件（各自处理）

### 3.1 `/plaza` 在 390px 下横向溢出 819px —— **这是我在 PLAZA-01 埋下的**

堆叠的侧卡是绝对定位的，中心 ±270px 各摆一张 520px 宽的卡，约 800px 的内容。
桌面端容器够宽看不出来，390px 下它把整页顶宽。**PLAZA-01 我只看了桌面端**，
是 `FIX-06` 的移动端扫描把它量出来的。

修法：`.plaza-stack__deck { overflow: hidden }`——侧卡在窄屏上被切在边缘，
那正是扇形堆叠在窄屏该有的样子。修后全量取证 `horizontal_overflow` 清零。

### 3.2 共用取数层没有「这一条不存在」那一态

后端对未知主题回的是**正确的形状**（`404 {"code":"NOT_FOUND"}`），
而 `web/lib/screenClient.ts` 的 `Fetched<T>` 判别联合没有 `not_found` 成员，
于是它落进 `failed`，屏上显示通用错误框。`NotFound404` 组件早就建好了——
**取数层递不出那一态，它就永远用不上**。

那是十三屏以上共用的取数层，**超出本卡触碰面** → 立单
`docs/blocked/FETCH-LAYER-HAS-NO-NOT-FOUND-STATE.md`，不自行动手。
本屏按当前取数层如实显示（后端自己的说明原样带出来，没改写、没编）。

## 四、改既有文件（工单纪律 4）

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `web/components/views/TopicListView.tsx` | 零 className 的 ul/li | 加卡面类名（`topic-card` 等），`data-*` 与结构逐字保留 | acceptance④「与广场同源」；四条既有判据不改而全绿 |
| `web/app/globals.css` | 无主题样式 | +主题两屏一段（与热点卡同一组 `_ds` token）；`.plaza-stack__deck` 加 `overflow: hidden` | 见 3.1；同一产品里两种卡片长得两样，用户会以为是两个产品 |
| `harness/fe_smoke.py` | 16 屏 | +两条动态路由与样例 id | **那条尺子当场判红**：新屏不登记就会被跳过取证。**超出 outputs，在此登记** |
| `tests/v041/test_fe_smoke.py` | 钉 16 条路由 | +2 条 | 同上，它是那道绊线 |
| `tests/v041/test_screens_live_probe.py`、`test_mobile_sweep.py` | 噪声基线 1 行 | 各 +2 行并点名单据 | 尺子的原话「多了要停下登记」。两行**都不是产品坏了**：一条是 403（取证样例没跟鉴权对齐），一条是新屏的占位 id 404 |
| `tests/v041/test_ui_restyle.py` | 非 404 报错一条不许 | 放行**那一条、那一屏**的 403 | NEVER 放宽成「所有 403」——放宽成一类的话，哪天别的屏真的鉴权坏了，这条判据不会响 |

## 五、取证

```
harness/fe_smoke.py 全量（18 屏 × 2 主题 × 2 视口）
  horizontal_overflow  0（修 3.1 之前 /plaza 两主题各溢出 819px）
  控制台报错面 {'/deliverables/[id]': 3, '/jobs/[id]': 1, '/topics/[id]': 1}——三条各点各的单
```

截图已看过：

- `/projects/[id]/topics`：全宽，「主题列表」+ 贴纸副标，其下「候选主题」与虚线空态
  「暂无候选主题」（**demo 库当日一条主题都没有，那是查过了、确实没有**）；
- `/topics/[id]`：屏头 + 「取数出错 / 后端回了一个错误状态，下面是它原样给的说明 /
  `unknown topic: tp-none`」——见 3.2，说的话是真的，只是没说到「换一个 id 就行」那一层。

## 六、verify

```
pytest tests/v041/test_topic_screens.py -q  → 16 passed
pytest tests/v041 -q                        → 2397 passed / **1 failed**
                                              （只剩那条 SSE 403，已立单，非本批）
cd web && npm test -- --run                 → 78 files / 794 tests passed（既有 4 条主题判据未改而全绿）
cd web && npx tsc --noEmit                  → 0
ruff check . --no-cache                     → All checks passed
python tools/check_line_endings.py          → 213 个文件全是 LF
```

返工三轮：我自己的两条判据写得糙（`useScreenData` 数的是出现次数而不是调用点；
`speculative` 的正则把 JSX 的 `data-speculative={…}` 也咬了，且留了一行 `or True` 的**死代码**
——那正是审核检查单禁的空转，已删）；移动端溢出（3.1）；四把取证尺子要登记新屏。

## 七、self_review（worker.md §4.6）

① **测试覆盖 acceptance**：16 条。两处做不到的 acceptance **不是跳过而是反向钉住**——
「NEVER 拿 `one_liner` 冒充 `name_native`」与「列表屏 NEVER 自己记选中态」各一条正向断言，
另配「缺口单必须还开着」的守单条。
② **无冻结件偏离**：`contracts/` 一字未动；判据直接读冻结件的 `Topic` 字段面。
③ **无禁用词**：grep 零命中。
④ **复用断言在位**：列表复用 `TopicListView`（NEVER 另写一份主题呈现）；
卡壳与热点卡同源（判据逐个 token 比对）。
⑤ **装载未超预算**：≈15k tokens。

## 八、留给下游

- `CHAIN-04`（发起分析 + combo 入口）与 `CHAIN-05`（受众分叉 + 干预页）继续补那六屏；
- 三张新单加上此前两张，第 5 批的**后端缺口清单**已到五条，`SHIP-05` 会逐条列名；
- demo 库没有主题这件事：造主题属**种子数据**，是 owner 面（`worker.md §7` 事前必审），
  本卡 NEVER 自己造。库里有主题那天，`harness/fe_smoke.py` 里 `/topics/[id]` 的占位串
  MUST 换成查出来的真 id，否则那一屏取证的永远是错误态而不是内容。
