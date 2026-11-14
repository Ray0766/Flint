# HOTSPOT-07 trace — 信息源 by_source 列渲染（≥2 列，无合成句）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#HOTSPOT-07`（连带读了其依赖
  REGION-08 的卡文，以确认前后端两半的分工）；
- context_refs：`PRINCIPLES#B4`（工单 §3 那一节）、`contracts_v04/`（本卡未新增类型）；
- 前置产物：`flint/region/by_source_region.py`（REGION-08 全文：分列语义、
  `SYNTHESIS_BLACKLIST` 七条、少数派不合并的理由）、
  `web/lib/i18n/t.ts`、`web/messages/{zh,en}.json`。
- 实测装载 ≈ 9k tokens，未超 40k。

## 2 关键设计判断

**组件里没有汇总槽位**，这不是遗漏。渲染层是最容易把「综合各国观点，总体而言……」
那句话加回来的地方——它读起来最顺，也最有害：读者失去了「谁说的」这个唯一能判断
可信度的东西，而那句话没有任何一个来源支持它。故除了运行时扫描渲染树，
还加了一条源码断言：组件源码里不出现 summary / consensus / synthes 这三个词根。

**黑名单前端也要有一份**：后端 REGION-08 已经拦过一次，但那句话若是在渲染层加的，
根本不经过后端。副本的风险是漂移，故配一条**漂移检测**——测试直接读那份 Python 源、
用正则抽出七条模式、与前端逐项比对，任一侧改了而另一侧没跟上立刻红。

**模式放 `.json` 而不是 `.ts`**：它们是**检测模式**不是界面文案，里面的中文必须逐字保留
（key 化会让它们不再匹配任何东西）。i18n 扫描面是 `.ts/.tsx`，放进 `.json` 既避开误判，
也如实表达「这是数据不是文案」。首轮把模式写在 `.ts` 里时 `i18n_scan` 确实报了红
（`synthesisBlacklist.ts` 第 14 行），是这条红把设计推到了正确的位置——
**没有去加白名单**：白名单是推进机制不是豁免机制（I18N-02 口径）。

**为什么不让两边共读一份文件**：那要改动 REGION-08 已验收的模块去读外部文件，
而 DEC-003 定的触碰边界是既有文件只做注册点增量。副本 + 漂移检测是更小的改动面。

**未归区单独成列且排最后**：塞进某个地区是编造来源地，丢掉等于悄悄少给了一份材料
（与 REGION-02 的 `UnknownSourceRegion`、HOTSPOT-01 的「NEVER 猜一个区」同一条纪律）。

## 3 test-first 顺序

1. 先写 10 条测试 → 跑 → 红（`Failed to resolve import "./SourceColumns"`）；
2. 实现 `SourceColumns.tsx` + `synthesisBlacklist.ts` + 2 条 i18n key → 10 passed；
3. `i18n_scan web/components` 红 → 把模式移进 `synthesis-blacklist.json`，`.ts` 变薄封装
   → 扫描 exit 0（20 源文件、CJK 0、白名单 0、B7 0）。

## 4 acceptance ↔ 测试映射

acceptance 唯一条：**分歧 fixture 渲染 ≥2 列；合成句黑名单零命中（前端复检）**。

| 测试名 | 覆盖点 |
|---|---|
| `分歧 fixture 渲染 ≥2 列` | 两地区说法相反的 fixture → 列数 ≥2 且 `data-region` 逐项为 CN/JP |
| `每条陈述留在自己那一列` | 用 `within` 分列断言来源 id，防「都渲染出来了但混在一起」 |
| `原文逐字渲染` | 文本与输入逐字相等（B9：NEVER 翻译、NEVER 归一化） |
| `合成句黑名单零命中` | 扫整棵渲染树 + **阴性对照**（同一把尺子对「综合各国观点，总体而言……」必须报红） |
| `组件里没有摘要/结论槽` | 运行时无 summary/consensus 测试 id + 源码无这三个词根 |
| `少数派不被合并` | 单条陈述的地区照样单独成列（并进多数派等于用列数暗示可信度） |
| `未归区单独成列且排最后` | 哨兵列在最后、内容没丢、NEVER 归进某个地区 |
| `空输入是明确的空态` | 零列 + 空态元素（不是一列空壳） |
| `黑名单与后端逐条同源` | 读 Python 源抽模式、与前端数组逐项相等（漂移检测） |
| `文案 key 化` | 组件源码代码行零 CJK（剥行注释与块注释后判） |

## 5 verify

```
$ cd web && npm test -- --run components/source-columns   → 10 passed
$ npm test -- --run                                        → 170 passed / 28 files
$ npm run typecheck                                        → 干净
$ node tools/i18n_scan.mjs web/components --fail-on-cjk    → exit 0
$ node tools/i18n_scan.mjs web/views --fail-on-cjk         → exit 0
```

禁用词扫描：本卡三份产出 0 命中。

## 6 产出

- `web/components/source-columns/SourceColumns.tsx`
- `web/components/source-columns/SourceColumns.test.tsx`（10 条）
- `web/components/source-columns/synthesisBlacklist.ts` + `synthesis-blacklist.json`
- `web/messages/{zh,en}.json`：各 +2 key（29 键，键集一致）
