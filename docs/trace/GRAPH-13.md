# GRAPH-13 trace — 移动端只读（禁拖禁连，可看可开分析）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#GRAPH-13`；
- context_refs：`WORKORDER-v04.md#2-J2`、`WORKORDER-v04.md#5-F`（F17 行）；
- 前置产物：`web/components/graph-drag/GraphDrag.tsx`（GRAPH-04 的拖动与落盘口径）、
  `web/components/graph-open-analysis/GraphOpenAnalysis.tsx`（双击开分析）、
  `web/test-utils/source.ts`。
- 实测装载 ≈ 6k tokens，未超 40k。

## 2 关键设计判断

**不挂载，而不是「挂了再拦」**。挂上再拦的话，手指按住节点时它仍然会抢走滚动手势——
用户想滑动页面，画布却以为他在拖节点，页面就卡住不动。触摸端最该保住的是
**能滑能看**，而不是把桌面交互硬塞进来再逐个屏蔽。测试因此断两层：
`data-draggable="false"` + 真的发一串 pointer 事件确认零落盘；
另断节点样式里没有 `touch-action: none`（那正是抢走滚动的写法）。

**只读不等于残废**：双击开分析仍然可用——看得见、点得开分析，这两件在手机上
恰恰是最常做的。另有一条「节点内容两端一致」的断言：**只读的是交互，不是信息**。

**触摸判定由外部传入**：组件不嗅探 UA。UA 嗅探在平板、触屏笔记本上会判错，
而判错的代价是「这台机器上拖不动」，用户完全无从理解。判定归调用方
（媒体查询 / 指针类型 / 用户设置皆可），组件只按拿到的布尔值行事；
源码断言禁掉 `navigator.userAgent` / `ontouchstart` / `maxTouchPoints` 三种嗅探写法。

**只读态要说明白**：横幅明说此处不可编辑。让拖动与连线**静静地不生效**，
用户只会以为界面坏了（与 HOTSPOT-01 的「NEVER 用占位符糊弄」同一条纪律）。

**桌面端阴性对照**：同一组件在 `touch=false` 时挂上拖动与连线且落盘照常发生——
否则「触摸端不落盘」可能只是因为这个组件根本就不会落盘。

## 3 acceptance ↔ 测试映射

acceptance 唯一条：**触摸端拖/连 handler 不挂载；双击开分析仍可用**。

| 测试名 | 覆盖点 |
|---|---|
| `触摸端：节点上不挂拖动 handler` | `data-draggable=false` + 无 `touch-action: none` |
| `触摸端：拖动手势不产生任何落盘请求` | 真的发 pointerDown/Move/Up 三连，落盘零调用 |
| `触摸端：连线入口不渲染，长按也建不出边` | 入口不在 DOM + 事件序列后零建边 |
| `触摸端：双击开分析仍然可用` | 回调恰一次且带正确 nodeId |
| `触摸端：只读横幅说清为什么` | 文案取到词条（非 key 回落） |
| `桌面端阴性对照` | 同组件 `touch=false` 时拖动落盘 1 次、连线回调 1 次 |
| `桌面端不出只读横幅` | 横幅只在真的只读时出现 |
| `节点内容两端一致` | 只读的是交互不是信息 |
| `触摸判定由外部传入，组件不自己嗅探 UA` | 三种嗅探写法逐个断言不存在 |
| `文案 key 化` | 走共享 `codeOnly` |

## 4 verify

```
$ cd web && npm test -- --run views/graph-mobile  → 10 passed
$ npm test -- --run                                → 268 passed / 37 files
$ npm run typecheck                                → 干净
$ node tools/i18n_scan.mjs web/views --fail-on-cjk → exit 0
```

禁用词 0；两份产出均为 LF（收卡前断言无 `\r\n`）。

## 5 产出

- `web/views/graph-mobile/GraphMobile.tsx`、`GraphMobile.test.tsx`（10 条）
- `web/messages/{zh,en}.json`：各 +2 key（57 键，键集一致）
