# REGION-10 · 广场地区筛选器上屏（第 5 批 `PLAZA-02` 重做）

> v0.4.1 第 6 批第八张。`depends_on: ["REGION-09"]`（已 verified）。
> 本卡跨两个回合：上一回合做完勘查写了交接段，本回合照它实现。

## 装载清单

`tasks-v041-b6.json#REGION-10` · 上一回合的交接段 · `web/app/plaza/page.tsx` ·
`web/components/{region-switch,source-columns,plaza}/` · `web/lib/viewsClient.ts` ·
`assets/screen_composition.json` · `flint/api/settings.py`（区词表出处）·
两张相关单据。约 15k tokens，**未超 40k**。

## 一、做了什么

| 处 | 改前 | 改后 |
|---|---|---|
| `web/app/plaza/page.tsx` | 一个 effect，取数只依赖挂载 | `region` 状态 + **URL query 是它的真相**；取数 effect 依赖 `[day, region]` |
| 同上 | 无筛选器 | `<RegionSwitch>` 接上，清单恒来自 `/settings/locale` 的 `options.region` |
| `web/lib/viewsClient.ts` | `fetchPlazaHot(day)` | 可选 `region`；**不传时一个字都不加**（#2.14 增量口径） |
| `web/components/plaza/PlazaCards.tsx` | 空态里一句「切换还没接上」 | 删掉——`REGION-09/10` 之后它是**假话** |
| `web/app/globals.css` | 无 `.region-switch` 样式 | 补上（结构与样式**成对交付**，`GAUGE-12` 的另一半） |
| `assets/screen_composition.json` | `/plaza` 6 项 | +2 项（`[data-testid='region-select']` / `region-switch`） |

**为什么区要写进 URL**：只放内存里的话，用户分享一个链接给同事，
同事看到的是另一个区的热点，而两人都以为在看同一屏。

**为什么删掉那句话**：留着假话比没有提示更坏——它会让用户不去用一个已经能用的东西。

## 二、开工后发现并修掉的一个真缺陷（我自己在 `REGION-09` 埋的）

把筛选器接上屏，第一次真跑就露馅：`/settings/locale` 给屏上**九个区**
（`contracts_v04.Region`），而 `REGION-09` 的合法值取的是
`SELECT DISTINCT region FROM clusters`——**库里只有 `CN` 与 `global`**。
于是九个选项里**八个一点就报 400**。

那不是小 bug，是**把两件完全不同的事混成了一件**：

```
「AU 不是一个区」   ← 假的。它在产品词表里，只是今天没数据
「AU 今天没数据」   ← 真的，该回 200 + 空，落规格 #2.14 已建的「该区当日无数据」态
```

报 400 的那一版，屏上会说**这个区不存在**。

**改法**：合法性看冻结件词表（`get_args(contracts_v04.Region)`，与
`/settings/locale` **同源**），有没有数据看当天。`REGION-09` 的判据跟着加了两条
阴性对照：合法但无数据 → 200 + 空；词表外的值 → 400。

**顺带的结果**：库里那个 `global` **不在词表里**，所以它筛不出来。
**那是对的、也是要的**——它让 `REGION-08` 那张单
（`global` 是 `ghtrend` 写死的常量，不是一个区）留在明面上，
而不是被一个能用的筛选器盖过去。

## 三、核心判据的形状也改过一次

第一版要「两个都非空的区，集合不同」。本机数据里**只有 `CN` 有热点**，
那条会因为拿不到第二个非空区而红——**红的是判据的假设，不是筛选器**。

改成三条，合起来比原来更强，且**改前那一版一条都过不了**（改前每个区都回全量）：

1. 至少一个区是**非空真子集**（`CN`：0 < 68 < 154）；
2. 至少一个区是**空的**，且落到既有空态（证明筛选真的排除了东西，
   而不是回落到别的区）；
3. **没有任何一个区回全量**——那正是改前的样子。

## 四、真栈取证（截图我自己看过）

```
/plaza                → 154 张卡 + 地区下拉（AU CN FR GB IT JP KR SG US）
切 CN                 → 68 张，URL ?region=CN
切 US/AU/…（八区）     → 0 张，屏上「该区当日无数据」+ 列出其他区，URL 跟上
控制台报错            → 0
区名显示              → 与 options 逐字相同（**没有「全球」「全国」**）
```

截图 `.ui-probe/plaza-region-filter.png`。

## 五、`SourceColumns` 没接上——理由写清楚，NEVER 硬凑

卡面 acceptance① 要两个组件都上屏。**只上了一个**，另一个据实停下：

`SourceColumns` 要 `SourceStatement{sourceId, region, text}`，
`text` 的契约逐字是「**原文；NEVER 是译文**」。广场每个源手上只有
**分值**（`by_source`）与**地区**（`by_source_region`，`REGION-09` 刚加的）。
把分值塞进 `text` 就是拿一个已经有主的槽去说另一件事——
`DEC-034`/`DEC-038` 反复禁的那一条。

**真正缺的是每个源的原文词面**（`trend_items_raw.keyword`：微博说「脑机接口」、
GitHub 说 `bci`），那正是 `PRINCIPLES#B4`「把话还给说话的人」要的东西。
它离端点只有一个字段，但那是 `flint/api/views.py`，**不在本卡 outputs
（`web/app/plaza/`）里**——按纪律 5 停下，不自行扩面。
建议单开一张卡，一个 cycle 够，判据要盯原文逐字 / 少数派不合并 / 未归区排最后。

`PLAZA-02` 因此标 **partially_closed**：缺口一（region query）关了，
缺口二换了形状仍开着，两段都写进了单子。

## 六、动了一条既有判据

`web/components/plaza/plazaStates.test.tsx` 那条「地区切换还没接通这件事在屏上说出来」
——它断言的那句话现在是假话。改成「空态**只列出别的区，NEVER 自己再长一个切换控件**」：
空态的纪律一个字没松（仍然 NEVER 回落到别的区假装有数据），
而切换控件在屏顶，**空态 NEVER 自己再长一个**——同一件事两个入口，
两处状态迟早对不上。改因逐字写在判据上方。

## 七、verify

```
pytest tests/v041/test_plaza_filters.py -q        → 15 passed
pytest tests/v041/test_plaza_region_query.py -q   → 11 passed（含新加的两条阴性对照）
pytest tests/v041/test_plaza_{cards,states}.py
       test_screen_{composition,coverage}.py -q   → 81 passed
cd web && npm test -- --run                        → 805 passed
cd web && npx tsc --noEmit                         → exit 0
ruff / mypy --strict flint                         → 全绿 / 304 files
node tools/check_screen_composition.mjs            → 7 屏 / 36 项声明，0 处违规
node tools/{i18n_scan,no_scaffold_on_screen,check_design_constraints}.mjs
                                                   → CJK 0 / A 类 0 / 11 条 0 违规
python tools/check_screen_coverage.py              → 缺屏 0 · 端点对不上 0
python tools/check_line_endings.py                 → 219 个文件全是 LF
```

一处要注意：`check_screen_composition.mjs` 吃的是 `.ui-probe/screen_composition.json`
这份**观测产物**，不自己开浏览器。改完屏必须先重跑
`tests/v041/test_screen_composition.py` 落新观测——不重跑的话，
它报的是**上一次的屏**，而那与「改动没生效」长得一模一样。

## 八、self_review

① 判据覆盖 acceptance 六条中的五条（`SourceColumns` 那条据实停下并写清缺什么），
含四条阴性对照；② 零冻结件改动——本卡反而**靠**冻结件的 `Region` 当合法值真相；
③ 无禁用词；④ 改动面：`web/app/plaza/` + 判据（卡上 outputs）+
`viewsClient.ts`/`PlazaCards.tsx`/`globals.css`/`screen_composition.json`
（同屏的必要配套，逐处记因）+ `flint/api/views.py`（**修我自己在 `REGION-09` 埋的缺陷**，
那张卡的 outputs 就是它）；⑤ 装载 ≈15k tokens。

## 九、留给下游

- **`SourceColumns` 那张后续卡**（第五节）；
- `REGION-08` 那张单仍开着：`global` 的语义没裁之前，
  广场上那 103 条 `global` 簇**任何一个区都筛不到**，只在不筛时可见。
  这是当前最诚实的呈现，但它不是终态。
