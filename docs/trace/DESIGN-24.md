# DESIGN-24 trace — 无障碍（全键盘 / focus-visible / reduced-motion）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-24`；
- context_refs：`WORKORDER-v04.md#5-G`（G31 一行）；
- 前置产物：`web/public/_ds/…/tokens/colors.css`（`--focus-ring` token）、
  `web/test-utils/source.ts`。
- 实测装载 ≈ 5k tokens，未超 40k。

## 2 关键设计判断

**一个只能用鼠标点到的按钮，对键盘用户就是不存在**——他不会觉得「这里有个功能
我够不着」，他会觉得这个产品没有这个功能。所以判据不是「有没有 focus 样式」，
而是**每个交互点能不能被 Tab 走到**。

**正数 `tabIndex` 也算问题**：它把整页 Tab 顺序打乱，其它元素反而被挤到后面。
用 DOM 顺序表达先后，别用数字插队。

**`disabled` 与 `aria-hidden` 不算问题**：它们本来就不该被 Tab 到。
一把把它们也报出来的尺子，会让人开始整体忽略这份清单。

**reduced-motion 下时长归零，不是「放慢」**：对前庭功能敏感的用户，一次滑入动效
可能引发眩晕；系统设置里那个开关是他明确表达过的需求。
`motionStyle` 在 reduce 下**连 `transition` 属性都不下发**——0ms 仍会触发一次
过渡回调，某些实现会据此做动画收尾。

**`focus-visible` 而不是 `outline: none`**：去掉焦点框会让键盘用户在页面上看不见
自己在哪。有一条源码断言盯着 `outline: none`。

**清单带下标与原因**：只回 true/false 的话，调用方只知道「有问题」，不知道是哪一个、
为什么——而无障碍问题恰恰是最需要「照着改」的那类。

## 3 两次小修（都是既有惯例，不是新决定）

1. TS 侧抛错文案改回**英文**（`tweaks.ts` / `designInterfaces.ts` 同款惯例）：
   中文只出现在注释与 `t()` 词条里，代码行零 CJK 是全仓一致的口径。
2. 一段 JSDoc 改写成行注释，避开 `i18n_scan` 对跨行块注释的**已知假阳性**
   （DEC-013 / 卡 `I18N-09`）——与 GRAPH-16、DESIGN-04 同款处置，未改扫描器、未加白名单。

## 4 acceptance ↔ 测试映射

acceptance「Tab 可达全交互点；reduced-motion 下动效时长为 0」：

| 测试名 | 覆盖点 |
|---|---|
| `reduce 下时长归零，而不是放慢` | 归零 + 常态保留 |
| `reduce 下连 transition 属性都不下发` | 不留 0ms 过渡 |
| `负时长直接拒` | 接线错了要报 |
| `button/a/input/select/textarea/summary 天生可聚焦`（参数化 6 条） | 可达面 |
| `div/span 默认够不着` | 要么换 button 要么给 tabIndex=0 |
| `tabIndex=-1 不在 Tab 序里` | 程序聚焦用 |
| `disabled 与 aria-hidden 不抢焦点` | 两种排除 |
| `一屏交互点全可达时清单为空` | 阴性对照 |
| `够不着的元素报出来，并说清怎么改` / `清单带下标` | 可执行清单 |
| `正数 tabIndex 也算问题` | 顺序被打乱 |
| `焦点样式用 outline + 偏移，颜色走 token` / `源码里没有 outline: none` | focus-visible |

## 5 verify

```
$ cd web && npm test -- --run design/a11y  → 20 passed
$ npm test -- --run                          → 493 passed / 56 files
$ npm run typecheck                          → 干净
$ node tools/i18n_scan.mjs web/design --fail-on-cjk       → exit 0
$ node tools/lint_no_confidence_viz.mjs web               → exit 0
$ node tools/no_external_fonts.mjs web                    → exit 0
$ node tools/no_hardcoded_models.mjs web                  → exit 0
```

禁用词 0；产出均为 LF。

## 6 产出

- `web/design/a11y/a11y.ts`、`a11y.test.ts`（20 条）
