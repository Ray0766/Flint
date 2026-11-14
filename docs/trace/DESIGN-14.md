# DESIGN-14 trace — 演示模式（全屏/隐 chrome/方向键）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-14`；
- context_refs：`WORKORDER-v04.md#5-G`（G18 一行）；
- 前置产物：`web/design/renderer/SrcdocRenderer.tsx`（沙箱标志与 srcdoc 口径）、
  `web/test-utils/source.ts`。
- 实测装载 ≈ 5k tokens，未超 40k。

## 2 关键设计判断

**「退出恢复原态」是最容易做漏的一半**：演示完回到编辑器，若侧栏没回来、全屏没退，
用户就得自己把工作台重新拼一遍——而他刚才只是想给人看一眼。演示模式是**一次借用**，
借完原样还回去。故退出有两条路都要通：Esc 与卸载。

**Esc 自己先退全屏再通知**：用户按了 Esc，画面该**立刻**回来，而不是取决于调用方
有没有把这个组件卸载掉。同时用一个 ref 守住「退全屏恰一次」——两条路都通、但不能各退一次。

**到头不循环**：第一页再往左、最后一页再往右都停住。循环回第一页会让演示者以为
自己按多了一次，接着讲错顺序——而台下正看着。

**退出后把键还给编辑器**：卸载时移除 keydown 监听。不移除的话，回到编辑器后
按方向键还在翻演示页——而演示已经结束了。测试用一个后挂的监听器验证事件正常抵达（未被吞）。

**空页集不进演示**：没有内容可讲时黑一屏，比什么都不做糟。此时也不进全屏
（断言 `calls == []`）。

**本层不改内容**：只是换一种方式显示同一份产物（四词源码断言），与 DESIGN-02 的零构建、
DESIGN-12 的评论层同一条边界。

## 3 一次实现修（测试逼出来的真行为差异）

`Esc 退出` 初版只调 `onExit()`，把退全屏留给卸载路径——测试断言 `["enter","exit"]` 报红。
这条红是对的：**浏览器是否离开全屏不该取决于调用方是否正确卸载了组件**。
改为 Esc 自己退（带一次性守卫），两条路合起来仍恰好退一次。

## 4 acceptance ↔ 测试映射

acceptance「三行为齐全；退出恢复原态」：

| 行为 | 测试名 |
|---|---|
| 全屏 | `进入即全屏、隐 chrome`（`enter` 恰一次） |
| 隐 chrome | 同上（`data-chrome=hidden` + 编辑器 chrome 不在 DOM） |
| 方向键翻页 | `方向键翻页：右前进、左后退`、`到头不循环`、`当前页渲染的是那一页的内容` |
| 退出恢复原态 | `Esc 退出：退全屏 + 通知调用方恢复原态`、`卸载也退全屏`、`退出后不再吃键盘` |
| （边界） | `空页集不进演示`、`演示层不改内容`、`文案 key 化` |

## 5 verify

```
$ cd web && npm test -- --run design/present-mode  → 10 passed
$ npm test -- --run                                  → 417 passed / 51 files
$ npm run typecheck                                  → 干净
$ node tools/i18n_scan.mjs web/design --fail-on-cjk  → exit 0
```

产出均为 LF；禁用词 0。

## 6 产出

- `web/design/present-mode/PresentMode.tsx`、`PresentMode.test.tsx`（10 条）
- `web/messages/{zh,en}.json`：各 +1 key（81 键，键集一致）
