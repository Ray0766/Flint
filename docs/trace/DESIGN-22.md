# DESIGN-22 trace — 快捷键 + ⌘K 命令面板@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-22`；
- context_refs：`WORKORDER-v04.md#5-G`（G28 一行）；
- 前置产物：`web/lib/undo/undoStack.ts`（GRAPH-10 的全局撤销链）、
  `web/views/graph-mobile/GraphMobile.tsx`（GRAPH-13 的「平台判定由外部传入」）、
  `web/views/workbench-tabs/`（GRAPH-16 的页签）、`web/test-utils/source.ts`。
- 实测装载 ≈ 6k tokens，未超 40k。

## 2 关键设计判断

**绑定表是唯一真相**：注册与「设置里查看」读同一份表（测试用 `toBe` 断言**同一个对象**，
不是内容相等）。分两处写的话，用户在设置里看到的与实际按下去发生的会不一样——
而他会照着设置里那份去按，然后以为键盘坏了。

**⌘Z 不在这里实现撤销**：派发给 GRAPH-10 的全局撤销栈。快捷键层自己维护一条撤销链，
就会出现「按钮撤的和快捷键撤的不是同一件事」。有两条源码断言盯着（无 `undoStack`、
无本地 `const stack`）。

**平台修饰键由外部传入**：mac 用 ⌘、其它平台用 Ctrl；组件不嗅探 UA——
在触屏笔记本/远程桌面这类场合会判错（与 GRAPH-13 同一条纪律）。
另断两条方向：mac 上 Ctrl 不当 ⌘ 用、非 mac 上 ⌘（Windows 键）不触发。

**输入框里的取舍**：⌘Z / ⌘1 / ⌘2 / ⌘\ 在输入态**不抢**——用户在文本框里按 ⌘Z
想撤的是刚打的字，不是画布上的操作；打字时按 ⌘1 多半是手滑。
只有 ⌘⏎（发送）与 ⌘K（命令面板）仍生效，它们本来就是给输入用的。

**大写也认**：Shift 按着不该让快捷键失灵。**没有匹配就是 null**，NEVER 猜一个最近的。

## 3 acceptance ↔ 测试映射

acceptance「六绑定生效且可在设置查看」：

| 分句 | 测试名 |
|---|---|
| 六绑定生效 | `⌘enter/z/\/1/2/k → 对应 id`（参数化六条）、`Ctrl+Z 生效`（非 mac） |
| 可在设置查看 | `设置页读的是同一份表`（`toBe` 同一对象）、`每条都带展示文案 key` |
| （不误触发） | `不带修饰键不触发`、`mac 上 Ctrl 不当 ⌘ 用`、`非 mac 上按 ⌘ 不触发`、`没有匹配就是 null` |
| （输入态取舍） | `⌘Z 在输入框里不抢`、`⌘⏎ 与 ⌘K 仍生效`、`页签切换在输入框里也不抢` |
| （纪律） | `撤销不在这里实现`、`平台判定由外部传入`、`大写字母也认`、`源码零 CJK` |

## 4 verify

```
$ cd web && npm test -- --run design/shortcuts  → 21 passed
$ npm test -- --run                               → 473 passed / 55 files
$ npm run typecheck                               → 干净
$ node tools/i18n_scan.mjs web/design --fail-on-cjk → exit 0
$ node tools/no_external_fonts.mjs web             → exit 0
```

禁用词 0；产出均为 LF。

## 5 产出

- `web/design/shortcuts/shortcuts.ts`、`shortcuts.test.ts`（21 条）
- `web/messages/{zh,en}.json`：各 +6 key（89 键，键集一致）
