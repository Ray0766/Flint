# GRAPH-15 trace — 工作台空态（从广场拖入引导）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#GRAPH-15`；
- context_refs：`WORKORDER-v04.md#5-F`（F19 行）；
- 前置产物：`web/views/workbench-shell/WorkbenchShell.tsx`（GRAPH-01 容器）、
  `web/views/library-empty/LibraryEmpty.tsx`（FAV-06 的空态口径与 `PLAZA_ROUTE` 常量）、
  `web/test-utils/source.ts`。
- 实测装载 ≈ 5k tokens，未超 40k。

## 2 关键设计判断

**空台不是错误态**：一张还没放东西的画布是每个新用户的起点，所以给的是**一条出路**
（去广场挑一个热点拖进来），不是一句「暂无数据」——后者把用户留在原地。
与 FAV-06 同一条纪律。测试另断不出现任何报错语义（无 `role=alert`、无 `data-error`）。

**只说「去广场」不够**：他到了广场还是不知道下一步该做什么。所以引导里带着**动作**
（把卡片拖进工作台）——那正是这张空画布唯一在等的事，独立成槽 `workbench-empty-hint`。

**路由常量单一来源**：复用 FAV-06 的 `PLAZA_ROUTE`，本文件不再写一遍 `/plaza`，
并有一条源码断言盯着（两处各写一个字符串，改路由时必然漏掉一个）。

## 3 acceptance ↔ 测试映射

acceptance 唯一条：**空态文案 key 化；引导指向广场**。

| 测试名 | 覆盖点 |
|---|---|
| `引导指向广场，且用的是同一个路由常量` | `href` 等于 `PLAZA_ROUTE`；源码里不含字面量 `"/plaza"` |
| `给的是一条可点的出路` | CTA 是真的 `<a href>` |
| `两条文案都取到了词条` | 断言文案不等于 key 本身（t() 缺 key 时回落成 key，只断非空会绿） |
| `说清怎么放东西进来` | 动作提示槽在场且非空 |
| `空态不是错误态` | 无报错语义 |
| `文案 key 化：源码代码行零 CJK` | 走共享 `codeOnly` |

## 4 verify

```
$ cd web && npm test -- --run views/workbench-empty  → 6 passed
$ npm test -- --run                                   → 274 passed / 38 files
$ npm run typecheck                                   → 干净
$ node tools/i18n_scan.mjs web/views --fail-on-cjk    → exit 0
```

禁用词 0；两份产出均为 LF。

## 5 产出

- `web/views/workbench-empty/WorkbenchEmpty.tsx`、`WorkbenchEmpty.test.tsx`（6 条）
- `web/messages/{zh,en}.json`：各 +3 key（60 键，键集一致）
