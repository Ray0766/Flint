# DESIGN-08 trace — Tweaks 面板（快路径不重建 srcdoc + 字节区间回写）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-08`；
- context_refs：`WORKORDER-v04.md#5-G`（G13 一行）；
- 前置产物：`web/design/renderer/SrcdocRenderer.tsx`（DESIGN-02 的零构建口径）、
  `web/design/interfaces/designInterfaces.ts`（DESIGN-03 的 `PatchSpan` 语义）、
  `web/test-utils/source.ts`。
- 实测装载 ≈ 6k tokens，未超 40k。

## 2 关键设计判断

**快路径不重建**：重建 srcdoc 等于整页重新加载——滚动位置回到顶部、动画从头播、
iframe 里的输入框失焦。用户拖着滑块调间距，每动一格页面就跳一次，那个面板根本没法用。
故拖动期只调 `style.setProperty`，测试连拖三次断言 `rebuildSrcdoc` **spy = 0**，
并另有一条源码断言禁掉 `srcdoc =` / `srcDoc =` / `innerHTML` 三种重建写法。

**只认 CSS 变量**：改 `padding` 这类普通属性要动结构，不属于「改一个值」的快路径。
让它悄悄走快路径的后果是用户以为改成了，而下次重建时那处改动并不存在——
所以直接抛错，不猜。

**空值不下发**：把变量设成空串等于把那条样式抹掉，而用户只是把滑块拖到了最左端。

**回写按字节区间**：整段重写会把用户手改过的地方一起冲掉，也会让 diff 变成
「整文件变了」——之后没人能一眼看出这次动了什么。区间只覆盖**值**本身，
缩进/分号/周围空白一个字节不动（测试逐行比对，并断行数不变）。

**引用不是定义**：`var(--gap)` 的位置回写过去，改的是别人用它的地方而不是它自己。
`findVariableSpan` 只匹配定义形态。

**同名多处只改第一处**：一把全替会把作用域不同的两条规则一起改掉。

**变量不存在时报错，NEVER 悄悄追加**：追加会让源码里多出一条用户从没写过的规则，
而他以为自己只是拖了个滑块。

## 3 自审报告（§4.6，本卡 self_review=true）

**①** acceptance ↔ 测试映射：

| acceptance | 测试名 |
|---|---|
| 拖动只 patch CSS 变量（srcdoc 重建 spy=0） | `拖动调用的是 setProperty，srcdoc 一次都不重建`（三次拖动 + spy=0）、`只认 CSS 变量`、`空值不下发`、`源码里没有重建 srcdoc 的写法` |
| 回写按字节区间、缩进保持（diff 最小） | `找得到变量的值所在区间，且区间只覆盖值本身`、`回写只改那一段，其余字节逐字不变`（行数不变 + 该行逐字）、`缩进保持`、`同名变量出现多次时只改第一处`、`变量不存在时报错而不是悄悄追加`、`引用不算定义`、`值里带 var() 也能整体换掉`、`回写不碰内容文本` |

**②** 无冻结件偏离：纯前端工具模块，零触碰 `contracts/`。
**③** 无禁用词：两份产出 `BANNED_HITS= 0`。
**④** 复用断言在位：区间语义与 DESIGN-03 的 `PatchSpan` 同构（[start, end) 半开区间），
未另造一套坐标；源码扫描走共享 `codeOnly`。
**⑤** 装载 ≈6k tokens，未超 40k。

## 4 verify

```
$ cd web && npm test -- --run design/tweaks  → 13 passed
$ npm test -- --run                            → 358 passed / 46 files
$ npm run typecheck                            → 干净
$ node tools/i18n_scan.mjs web/design --fail-on-cjk → exit 0
```

卡上 cycles=2，实际 1。产出均为 LF；禁用词 0。

## 5 产出

- `web/design/tweaks/tweaks.ts`、`tweaks.test.ts`（13 条）
