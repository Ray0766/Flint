# DESIGN-09 trace — Tweaks 参数禁用词表（六词拒绝提取）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`（三条铁律：结论必有引用、数字必有出处）、`worker.md`、
  卡片 `tasks-v04.json#DESIGN-09`；
- context_refs：`WORKORDER-v04.md#5-G`（G13 后半的六词表）；
- 前置产物：`web/design/tweaks/tweaks.ts`（DESIGN-08 的定义/引用口径）、`web/test-utils/source.ts`。
- 实测装载 ≈ 5k tokens，未超 40k。

## 2 这张卡不是命名规范，是内容与外观的边界

Tweaks 面板调的是**外观**。一旦面板上出现「confidence threshold」「hide evidence」
「count」这样的旋钮，用户就能在一个**看起来只管样式**的地方改掉内容本身——
少显示几条证据、把把握度调高一档、把不想看的过滤掉。

而燧石的立身之本是「结论必有引用、数字必有出处」。一个能把证据调没的滑块，
等于给这条铁律开了一个**用户自己都不会意识到的后门**：他以为自己在调排版。

**拒绝发生在提取那一步**：让它进了面板再灰掉，那颗旋钮已经在界面上了——
用户会问「为什么这个不能调」，而正确的回答是「它根本不该出现在这里」。

## 3 词边界：不能见谁都拦

按分隔符切词后整词比对：`--discount` 里的 count 不是 count 这个参数、`--counter` 也不是，
但 `--evidence-count` 是。一把见谁都拦的尺子会让人开始想办法绕过它，
而绕过之后连真正该拦的也拦不住了。测试正反两侧各一组（六词 × 四种形态命中；
七个正常外观参数不误伤）。

## 4 acceptance ↔ 测试映射

acceptance 唯一条：**六词参数名提取报错且不入面板**。

| 测试名 | 覆盖点 |
|---|---|
| `表就是卡上那六个词，一个不多一个不少` | 词表逐字 |
| `六个词逐个命中（含大小写与连字符/下划线包裹）` | 每词 4 种形态 |
| `正常外观参数不误伤` | 七个正常参数（含 `--discount`） |
| `词边界按分隔符判` | `--counter` / `--evidences` 不算，`--evidence-count` 算 |
| `含禁用词的参数在提取那一步就报错` | 抛 `DeniedParameterError` |
| `报错说清是哪个参数、命中哪个词` | 消息含参数名与命中词（「参数非法」查不出所以然） |
| `宽松模式下命中项被剔除而不是混进面板` | 结果里没有它 |
| `被剔的清单交得出来` | 静默剔除会让人以为源码里本来就没有那个参数 |
| `一条都不剩时返回空数组而不是抛错` | 空面板是明确状态 |
| `提取只认定义，不认引用` | 与 DESIGN-08 同一条口径 |
| `源码代码行零 CJK` | 走共享 `codeOnly` |

## 5 verify

```
$ cd web && npm test -- --run design/tweaks-denylist  → 12 passed
$ npm test -- --run                                     → 370 passed / 47 files
$ npm run typecheck                                     → 干净
$ node tools/i18n_scan.mjs web/design --fail-on-cjk     → exit 0
```

禁用词 0；产出均为 LF。

## 6 产出

- `web/design/tweaks-denylist/denylist.ts`、`denylist.test.ts`（12 条）
