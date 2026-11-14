# DESIGN-26 trace — 反向高亮（节点 ↔ 首个引用 Block）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-26`；
- context_refs：`WORKORDER-v04.md#5-G`（G32 一行）；
- 前置产物：`web/components/graph-node/GraphNode.tsx`（节点 id 口径）、
  `web/design/multipage/MultiPageDoc.tsx`（文书顺序）、`web/test-utils/source.ts`。
- 实测装载 ≈ 5k tokens，未超 40k。

## 2 关键设计判断

**取「首个」而不是「全部」**：一个节点常被文书里好几处引用。一次把七处都高亮，
用户还是不知道该看哪；滚到第一处并高亮它，是一个明确的落点，他从那里往下读就行。
其余引用不是丢了——它们仍在，只是这次跳转不替他决定看哪个。

**顺序按 `order` 而不是数组下标**：数组可能是乱序读回来的，按下标取会跳到
一个「碰巧排在前面」的块上。测试用打乱过的数组验这一点。

**找不到就明说**（`reason: "no_reference"`）：一个点了没反应的节点，用户会以为
界面卡了，然后反复点。也 NEVER 退而求其次跳到第一个 Block——那会把他带到一段
与这个节点无关的文字前，而他以为那就是引用处。

**这一层不碰 DOM**：滚动与高亮时长归调用方。在这里 `scrollIntoView` 的话，
容器与偏移量都由这一层猜，而真正知道布局的是上层；两边各滚一次会把页面弹两下。
两条源码断言盯着（无 DOM API、无定时器）。

**未知 Block 返回空数组而不抛**：点到一个还没渲染出来的块不该炸。

**往返闭合**：跳过去的那个 Block 反查得回原节点——这条是「双向」这两个字的实际含义，
只测单向的话，反向映射写错了也发现不了。

## 3 acceptance ↔ 测试映射

acceptance「点节点滚动到首引用 Block；点 Block 高亮来源节点」：

| 测试名 | 覆盖点 |
|---|---|
| `按文书顺序取第一处引用` | 节点 → 首引用 |
| `顺序按 order 而不是数组下标` | 乱序数组仍取对 |
| `没有任何引用时返回 null` | 不退而求其次 |
| `一个 Block 的全部来源节点都交出去` | Block → 节点 |
| `无引用的 Block 返回空数组` / `未知 Block 返回空数组而不是抛` | 两条边界 |
| `找得到时给出滚动目标与高亮目标` | 跳转计划形状 |
| `找不到时明说原因` | `no_reference` |
| `计划是数据：这一层不碰 DOM` | 三个 DOM API 断言 |
| `同一次跳转算两遍结果一样` | 纯函数 |
| `跳过去的那个 Block，反查得回原节点` | 往返闭合 |
| `空文书不炸` / `源码零 CJK` / `不在这一层设定时器` | 三条纪律 |

## 4 verify

```
$ cd web && npm test -- --run design/cross-highlight  → 14 passed
$ npm test -- --run                                     → 507 passed / 57 files
$ npm run typecheck                                     → 干净
$ 四把扫描器（i18n_scan web/design / lint_no_confidence_viz / no_external_fonts /
  no_hardcoded_models）                                  → 全 exit 0
```

禁用词 0；产出均为 LF。

## 5 产出

- `web/design/cross-highlight/crossHighlight.ts`、`crossHighlight.test.ts`（14 条）
