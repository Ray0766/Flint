# DESIGN-06 trace — 工具调用时间线（30+ 折叠 ≤40px）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-06`；
- context_refs：`WORKORDER-v04.md#5-G`（G8 一行）、`contracts_v04/models_v04.py#DesignToolCall`；
- 前置产物：`web/design/chat-panel/`（DESIGN-01 的事件语义）、`web/test-utils/source.ts`。
- 实测装载 ≈ 5k tokens，未超 40k。

## 2 关键设计判断

**折叠 NEVER 等于丢弃**：工具调用是过程，不是用户要读的东西——全量铺开会把他想看的
生成文字推到几屏之外。但出了问题时「它到底做了什么」是唯一能查的线索，
所以展开要回看全量（34 条一条不少，首尾 id 都断），
且折叠态本身要说得出**折了多少条、其中几条失败**——一句「已折叠」等于什么都没说。

**少量不折叠**：三条也折起来的话，用户要多点一次才能看见本就该看见的东西。
阈值 30 与卡上 acceptance 的「30+」对齐。

**折叠态里不渲染参数**：把几十条参数塞进 DOM 只为让它们不可见，既占内存，
又让「不可见」变成一件靠 CSS 维持的事——CSS 一改就漏出来。测试直接查页面上
搜不到第 12 条的参数文本。

**失败计数恒可读但不恒显**：`data-failed` 始终带值（机器可读），全成功时是 0；
文案里不挂一个恒亮的「0 次失败」——那种常驻的零会让真正出现的 1 显得不特别。

## 3 acceptance ↔ 测试映射

acceptance 唯一条：**30+ 调用折叠态高度 ≤40px（样式断言）；展开可回看全量**。

| 测试名 | 覆盖点 |
|---|---|
| `30+ 调用默认折叠，且折叠态高度上限 ≤40px` | 常量 ≤40 + `maxHeight` 与 `overflow:hidden` 双断言 |
| `折叠态说得出被折了多少` | `data-count=34` 且文案里出现 34 |
| `展开可回看全量：34 条一条不少` | 行数 + 首尾 `data-call-id` |
| `展开后没有高度上限` | 折叠容器消失、展开容器无 `maxHeight` |
| `少量调用不折叠` | 3 条直接铺开 |
| `失败的调用在折叠态也点得出来` | `data-failed=1`；全成功时为 0 |
| `每行带得出工具名与成败` | `data-tool` / `data-ok` + 行内工具名 |
| `参数不在折叠态里渲染` | 页面上搜不到参数文本 |
| `空列表不渲染空壳` | 组件返回 null |
| `文案 key 化` | 走共享 `codeOnly` |

## 4 verify

```
$ cd web && npm test -- --run design/tool-timeline  → 10 passed
$ npm test -- --run                                   → 334 passed / 44 files
$ npm run typecheck                                   → 干净
$ node tools/i18n_scan.mjs web/design --fail-on-cjk   → exit 0
```

禁用词 0；产出均为 LF。

## 5 产出

- `web/design/tool-timeline/ToolTimeline.tsx`、`ToolTimeline.test.tsx`（10 条）
- `web/messages/{zh,en}.json`：各 +2 key（70 键，键集一致）
