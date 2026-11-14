# DESIGN-19 trace — 多页面文档（L0/章节 + 375px 无横滚）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-19`；
- context_refs：`WORKORDER-v04.md#5-G`（G25 一行）；
- 前置产物：`web/design/renderer/SrcdocRenderer.tsx`（沙箱与零构建口径）、
  `web/test-utils/source.ts`。
- 实测装载 ≈ 5k tokens，未超 40k。

## 2 关键设计判断

**横向滚动在手机上是「看不见的丢失」**：用户不知道右边还有内容，他只会觉得这一段
写得没头没尾。而横滚最常见的来源不是文字，是某个**写死宽度**的容器（表格、代码块、图）。
所以判据落在**样式约束**上（`max-width:100%` + `overflow-x:hidden`），而不是靠人
在真机上滑一遍；且**外壳与每一页都断**——溢出的往往是页，不是外壳。
另加一条源码断言禁掉 `width: <数字>px` / `minWidth: <数字>px`，从源头堵住写死宽度。

**没有 L0 就说没有**：NEVER 把第一章顶上来充当概览。顶上来的话，用户点「概览」
看到的是「市场」，而他以为那就是全文的开头。配一条源码断言禁掉 `pages[0]` 这种
「随便挑第一个」的写法（与 GRAPH-12 的「不挑一个当根」同源）。

**多个 L0 时取第一个并报出重复**：结构错了要说出来，静默挑一个会让作者一直以为
自己那份大纲是对的。

**章节顺序照给定顺序**：重排会让目录与正文对不上。

## 3 acceptance ↔ 测试映射

acceptance「L0 概览+章节结构；375px 容器无横向滚动断言」：

| 测试名 | 覆盖点 |
|---|---|
| `L0 是根，章节挂在它下面` | 结构 |
| `没有 L0 时如实说没有` | 不顶替 + 源码断言 |
| `多个 L0 时取第一个并报出重复` | 结构错要说出来 |
| `章节顺序照给定顺序` | 目录与正文对得上 |
| `概览与章节各自成页，页数与输入一致` | 渲染面 |
| `目录逐条指向对应页` | 目录锚点 |
| `375px 容器：宽度上限与禁横滚都写在样式约束里` | 外壳约束 + 常量 |
| `每一页内容也不许横向溢出` | 每页各断一次 |
| `源码里没有写死的像素宽度` | 从源头堵住横滚来源 |
| `空页集不渲染空壳` / `页面内容逐字进入` / `文案 key 化` | 三条边界 |

## 4 verify

```
$ cd web && npm test -- --run design/multipage  → 12 passed
$ npm test -- --run                               → 440 passed / 53 files
$ npm run typecheck                               → 干净
$ node tools/i18n_scan.mjs web/design --fail-on-cjk → exit 0
$ node tools/no_hardcoded_models.mjs web           → exit 0
```

禁用词 0；产出均为 LF。

## 5 产出

- `web/design/multipage/MultiPageDoc.tsx`、`MultiPageDoc.test.tsx`（12 条）
- `web/messages/{zh,en}.json`：各 +1 key（83 键，键集一致）
