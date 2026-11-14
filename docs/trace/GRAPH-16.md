# GRAPH-16 trace — [隔离·F15] 页签 + 常驻可折叠 AI 栏（无 mode 键）@2026-08-03

> **隔离带卡 + owner_review**。按 DEC-000：默认照做、完成后打标继续，
> owner 若在 `DECISIONS-v04.md` 划掉则只需删掉 `web/views/workbench-tabs/` 一个目录
> （零下游，有测试盯着）。本卡开工前复查 `DECISIONS-v04.md` 无划除记录。

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#GRAPH-16`；
- context_refs：`WORKORDER-v04.md#11`（①F15 的工单立场与替代方案全文）、`contracts_v04/`；
- 前置产物：`web/views/workbench-shell/WorkbenchShell.tsx`（GRAPH-01 容器，
  它的 docstring 已写明「容器里不能有 mode」）、`web/test-utils/source.ts`。
- 实测装载 ≈ 8k tokens，未超 40k。

## 2 关键设计判断

**状态树里没有 mode**。真放一个 `mode` 键进来，它与「当前页签」「AI 栏是否折叠」
就成了**两份真相**：用户点开 AI 栏时 mode 该不该变？切到树页签时 mode 又是什么？
每加一个入口就要回答一次，而任何一次答得不一致，界面上就会出现
「模式说是 A、页签显示 B」。所以状态只有两个**正交**的键：`tab` 与 `aiPanelCollapsed`。

**「默认 / AI」留在预设组合层**：预设只是一次性把这两个键设成某个组合的快捷方式，
设完就没它的事——NEVER 作为状态存起来。页面上展示的预设名是**派生**的
（由两个键算出），算不出来时返回 `null` 而不是硬塞一个 `default`：
硬塞会让一个并不匹配任何预设的组合看起来像是默认态。

**AI 栏常驻**：折叠时仍在场（一条可展开的边），不是消失。消失的话用户下次要找它
得先想起「它在哪个模式下才有」——那正是模式切换带来的负担，而本卡的立场就是不要模式。

**§11-① 的替代路径已留好**：若 owner 坚持要 mode，替代是**派生只读** mode
（由 tab × 折叠态 算出、不落盘、不可直写）。`describePreset` 就是那个派生函数，
替代路径只需在 UI 层展示它——改动仍只落本卡，与工单承诺一致。

## 3 acceptance ↔ 测试映射

acceptance①「store 键集无 mode（断言）；「默认/AI」仅存在于预设文案层」：

| 测试名 | 覆盖点 |
|---|---|
| `键集恰是 tab 与 aiPanelCollapsed —— 没有 mode` | 初始态与两个预设的键集逐字断言 + 两份源码里 `\bmode\b` 零出现 |
| `预设是一次性组合，不是被存起来的状态` | `applyPreset` 回的仍是那两个键 |
| `预设名是派生的：由两个键算出来，算不出就是 null` | 三种组合逐个断言（含不匹配 → null） |
| `「AI」预设只是把两个键设成一个组合，页面上以派生名呈现` | 点预设后 `data-preset=ai` 且折叠态随之变 |
| `不匹配任何预设时 data-preset 为空` | NEVER 谎称是默认态 |
| `切页签换的是投影，不改 AI 栏折叠态` / `展开 AI 栏不改页签` | 两个键**正交**，双向各验一次 |
| `AI 栏常驻：折叠时仍在场` | 折叠 ≠ 消失；`aria-expanded` 如实 |
| `两个页签都在，默认停在图谱` | 默认组合 = 图谱 + 折叠 |

acceptance②「被划掉时仅移除本卡，零下游」：

| 测试名 | 覆盖点 |
|---|---|
| `零下游：容器与其它 F 组卡都不引用本卡` | 读 `WorkbenchShell.tsx` 断言不含 `workbench-tabs`——依赖方向只有「本卡 → 容器」 |
| `复用容器 GRAPH-01，不另画一个外壳` | 渲染出 `workbench-shell` + import 断言 |

## 4 自审报告（§4.6，本卡 self_review=true）

**①** 见上表；无 `assert true`、无只测 happy path：正交性双向各一条、派生值算不出的
反例一条、零下游一条。
**②** 无冻结件偏离：纯前端，零触碰 `contracts/` 与 `contracts_v04/`。
**③** 无禁用词：三份产出扫描 `BANNED_HITS= 0`。
**④** 复用断言在位：容器复用 GRAPH-01（渲染 + import 双断言），未另起外壳；
文案全部经 `t()`；源码扫描走共享 `codeOnly`。
**⑤** 装载 ≈8k tokens，未超 40k。

## 5 一处已知工具缺陷的规避（不是掩盖）

`workbenchTabsStore.ts` 里一段 JSDoc 块注释被 `i18n_scan` 判成未 key 化 CJK ——
这正是 DEC-013 / 卡 `I18N-09` 已登记的第一类假阳性（跨行块注释未被剥掉）。
本卡把那段改写成行注释并在注释里写明原因与出处，**没有去改扫描器**
（那是 I18N-09 的产出，两张卡改同一个文件会让谁都说不清改动属于哪张卡），
也没有加白名单（白名单是推进机制不是豁免机制）。

## 6 verify

```
$ cd web && npm test -- --run views/workbench-tabs  → 12 passed
$ npm test -- --run                                   → 286 passed / 39 files
$ npm run typecheck                                   → 干净
$ node tools/i18n_scan.mjs web/views --fail-on-cjk    → exit 0
```

禁用词 0；三份产出均为 LF。

## 7 产出

- `web/views/workbench-tabs/WorkbenchTabs.tsx`、`workbenchTabsStore.ts`、
  `WorkbenchTabs.test.tsx`（12 条）
- `web/messages/{zh,en}.json`：各 +4 key（64 键，键集一致）
