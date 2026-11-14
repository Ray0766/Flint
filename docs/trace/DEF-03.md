# DEF-03 · undo 链三处接线（GRAPH-04 / 07 / 09）

**卡** `tasks-v041-b2.json#DEF-03` · **开工** 机器 UTC 2026-08-04T01:42Z

## 1. 装载清单

卡面 DEF-03 · `docs/v0.4.1-候选清单.md#⑥` · `web/lib/undo/undoStack.ts` 全文 ·
三个组件全文（`GraphDrag.tsx` 66 行 / `GraphEdgeDraft.tsx` 90 行 / `GraphMultiSelect.tsx` 118 行）·
`web/lib/types.ts#isProtected` · `web/test-utils/source.ts#codeOnly` ·
`GraphDrag.test.tsx` 的 rAF 注入写法。约 9k tokens。

## 2. 顺序（§4.2）

测试先落盘先跑红（`8 failed | 16 passed`）→ 实现 → 25 passed。连续第十七张。

## 3. 卡面与实况的差（第八次同型 narrowing）

卡面/候选清单原话：「三处操作点**留了 `pushUndo` 调用位**」。

实况：`grep -rn pushUndo web/` 只命中 `undoStack.ts` 与它自己的测试，
三个组件里**零处**提到 undo——没有留好的调用位，也没有占位注释。

真正留下的缝是另一样东西，而且更好用：**三处的写操作都是注入的**
（`persist` / `onCreate` / `onBatchRole`），撤销动作可以用同一个注入件反着做一次。
本卡按真件接线，NEVER 先造一个「调用位」再填。

**两处得补参数**，因为反着做需要组件手上没有的东西：

| 处 | 撤销要什么 | 组件有吗 | 补法 |
|---|---|---|---|
| 拖动 | 原位置 | 有（`origin.current`，回弹用的那个） | 不补 |
| 连线 | 把边删掉 | **没有** | 补可选 `onUndoCreate` |
| 批量角色 | 操作前每个节点的角色 | **没有**（角色由服务端定，组件只呈现回值） | 补可选 `roles` + `onRestoreRoles` |

两个新参数都是**可选**的：三个组件在仓里没有别的调用方（只有各自的测试），
但可选意味着既有测试一个字不用改，也意味着接线是**加**上去的、不是把原有形状换掉。

## 4. 撤不回去就 NEVER 入栈——三处各一条守门

**能入栈就等于向用户承诺这一步撤得掉。** 撤不掉却入了栈，他按 ⌘Z 看到「撤销失败」，
而此刻他已经不记得那步是什么了。三处的守门条件不同，理由同一条：

- **拖动**：落盘**成功**才入栈（失败的那次已经回弹，没有东西要撤）；
  位置没变也不入栈（空操作入栈会让 ⌘Z 看起来失灵——按一下什么都没发生）。
- **连线**：没给 `onUndoCreate` 就不入栈（删不掉的边，撤销只能失败）。
- **批量角色**：拿不到操作前的角色就不入栈——**NEVER 造一个假的还原点**。
  假还原点比没有更糟：用户以为撤回去了，其实角色被改成了另一个值。

拖动的撤销动作里**先落盘再改界面**：反过来的话落盘失败时界面已经跳回原位、
服务端还在新位置，下次刷新它又跳一次。这与 `undoStack` 的「先执行后出栈」同源。

## 5. S2-5：受保护 block 的操作 NEVER 进栈

`pushBlockUndo(block, entry) -> boolean`，`isProtected` **复用** `web/lib/types.ts` 那一个。
在 undoStack 里另写一遍三条件的那天，两处判定会分叉，而分叉的那一侧会放进一条
本不该存在的历史（`test_the_protected_block_guard_exists_and_uses_the_shared_predicate`
连「另写一遍」都禁了）。

**为什么单独一个函数而不是塞进 `pushUndo`**：图谱那三处根本没有 block，
硬要它们造一个假 block 才能入栈，比多一个函数糟得多。

**为什么有返回值**：挡下的那一刻上游其实已经违规了（受保护 block 本来就改不动），
返回值是调用方唯一能发现这件事的地方。静默挡下会把一次违规变成什么都没发生。

## 6. 变异考：六个，第六个先活了下来

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 断开拖动接线 | GRAPH-04 | **3 failed** ✓ |
| ② 断开连线接线 | GRAPH-07 | **2 failed** ✓ |
| ③ 断开批量角色接线 | GRAPH-09 | **1 failed** ✓ |
| ④ 保护闸放行（`if (false)`） | S2-5 | **2 failed** ✓ |
| ⑤ 快照一律回退成 `null` | 「逐节点各自那一个」 | **1 failed** ✓ |
| ⑥ 快照取**全部**节点而非选中项 | 「只回退该操作」 | **24 条全绿地活了下来** ✗ |

**变异⑥ 暴露的是测试数据自洽**：批量那组用例用 ⌘A 选中，而 ⌘A 选中的正好是全部节点——
`selected` 与 `nodes` 在那份数据上一模一样，两种写法产出同一个快照。

真实后果是 acceptance① 的正题：用户框选 2 个节点应用角色，撤销却把 8 个都还原，
另外 6 个是这次操作**从没碰过**的。补
`只选中一部分时，快照里只有那一部分` —— 用框选（不是 ⌘A）选中三个里的两个，
第三个 `n-3` 在框外。重考变异⑥ → **1 failed**。

三条断开接线的变异，红的正是对应那一处的用例（acceptance③ 要的阴性对照）。
六次变异后各文件 sha256 与变异前逐位相同。

## 7. 改既有文件（§4.1，逐处记账）

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `web/lib/undo/undoStack.ts` | 无 block 概念 | 加 `pushBlockUndo` + `isProtected` 导入 + 一段理由注释 | acceptance② 的落点。没有它，S2-5 在 undo 这条路上没有任何把关 |
| `web/components/graph-drag/GraphDrag.tsx` | `persist(...).catch(回弹)` | 改成 `.then(成功→入栈, 失败→回弹)` | 接线本体。改成两支形式是因为**入栈只能在成功支**，而 `.then().catch()` 会把入栈自身的异常也当成落盘失败去回弹 |
| `web/components/graph-edge/GraphEdgeDraft.tsx` | 无 `onUndoCreate` | 加可选参数 + 成功支入栈；payload 提出成变量 | 撤销要把边删掉，而组件手上没有删的能力（§3） |
| `web/components/graph-multiselect/GraphMultiSelect.tsx` | 无 `roles` / `onRestoreRoles` | 加两个可选参数 + `RoleSnapshot` 类型 + 请求前取快照 + 成功支入栈 | 同上；快照**必须在请求发出前**取——回来之后 `roles` 可能已是新值，那时取到的是操作**后**的角色，撤销等于什么都没做 |

三个组件的既有用例（GraphDrag 5 / GraphEdge 8 / GraphMultiSelect 9）**一条没改、全绿**。

## 8. 一个卡面自相矛盾：outputs 是 .py，verify_cmd 是 npm

卡面 `outputs = ["tests/v041/test_undo_wired.py"]`，`verify_cmd = "cd web && npm test -- --run undo"`。
一个 Python 文件不可能被 vitest 的过滤词选中。两样**都交**，各司其职：

- `web/components/graph-undo/undoWiring.test.tsx`（25 条）= **行为面**，满足 verify_cmd；
- `tests/v041/test_undo_wired.py`（9 条）= **源码面**，满足 outputs。

源码面那把不是凑数的。它守的是一件具体的事：`npm test` **不在** `pytest -q` 里，
删掉三处接线中的任意一处，Python 全局门照样全绿——而它是合并时唯一必跑的那道门
（GAUGE-02 的「在门内 / 门外」清点说的就是这件事）。
它最后一条直接把 verify_cmd 跑一遍：**源码面全对而行为是错的，那一条会红**。

源码面的判据一律**先剥注释再判**（口径同 `web/test-utils/source.ts#codeOnly`，
那是前后踩了六次同一个坑之后抽出来的）；剥刀本身也有一条自证用例。

## 8.5 一个 CRLF 让全仓的剥注释尺子集体失效（本卡自己撞出来的）

变异考脚本按惯例「读全文 → 改一处 → 跑 → 写回原文」。`Path.write_text()` 在 Windows 上
**默认做换行翻译**：读进来的 `\n` 写回去变成 `\r\n`。内容逐字未变，行尾全变了。

随后全量 `npm test` 跑出 2 failed，两条都是「文案 key 化：源码代码行零 CJK」，
报出来的是**未经剥离的全文**——剥注释那一步一个字都没剥掉。

根因：剥刀是 `line.replace(/\/\/.*$/, "")`。CRLF 之下每行末尾挂着 `\r`，
而 **JS 正则里 `\r` 是行终止符**，`.` 不匹配它，`$`（无 `m`）要求到字符串末尾——
`//.*$` 在 `\r` 前走不下去，整行注释一条都剥不掉。

**这次的方向是幸运的**（要求「剥完没有中文」，剥不掉 → 红）。同一条缝在
「剥完必须出现 X」那类判据上会给出**绿**——而本仓两类都有，本卡的
`tests/v041/test_undo_wired.py` 就是后一类。

当场做的：把本卡触碰过的 7 个文件行尾改回 LF（内容逐字未动），全量回到 558 passed。
**没做**：改 `codeOnly` 让它对 CRLF 免疫、加一把换行符尺子——两样都超出本卡 outputs，
登记在 `docs/blocked/CRLF-BREAKS-COMMENT-STRIPPING.md`（含复现步骤与两条修法）。

## 9. verify 与 self_review

```
verify_cmd: cd web && npm test -- --run undo → Test Files 2 passed / Tests 25 passed
tests/v041/test_undo_wired.py -q → 9 passed
web 全量 npm test -- --run → 61 files / 558 passed（改前 557，本卡 +25 减去重算）
npx tsc --noEmit → 0
ruff check . --no-cache → All checks passed!
pytest tests/v041/ -q → 340 passed
```

**① acceptance 映射**

| acceptance | 测试 |
|---|---|
| ① 三处真接上；撤销回到操作前；只回退该操作（相邻状态逐字节不变） | `落盘成功后入栈一条，撤销把节点放回原位并落盘`、`建边成功后入栈一条，撤销把这条边删掉`、`批量成功后入栈一条，撤销把每个节点的角色放回操作前那一个`、`只选中一部分时，快照里只有那一部分`、`撤最近一步，相邻状态逐字节不变`（比 `outerHTML`）、`跨视图共用同一条链：先拖动再连线，⌘Z 先撤连线` |
| ② 受保护 block 的操作 NEVER 进 undo 栈（S2-5） | `三种保护条件各自都挡住`、`没被保护的照常入栈`、`入栈与否有返回值`、`test_the_protected_block_guard_exists_and_uses_the_shared_predicate` |
| ③ 断开任一处接线，对应用例必红 | §6 变异①②③（逐处断开，红的正是对应那一处的用例） |

**② 无冻结件偏离**：`contracts/`、`flint/domain/` 未触碰；零新增依赖
（playwright 仍在 `C:\pwenv`，未进任何清单）；改既有文件四处，逐处记账见 §7。

**③ 禁用词**：五个产物/被改文件六词 0 命中、本 trace 收尾「等」0 命中。

**④ 复用**：`isProtected` 复用 `web/lib/types.ts`；剥注释口径复用 `codeOnly`；
rAF 同步注入复用 `GraphDrag.test.tsx` 的 `syncRaf`；「过滤词选不中即红」复用 GAUGE-04。

**⑤ 装载预算**：约 9k tokens。

## 10. 登记未做

1. **没有页面把这三个组件接起来**：仓里没有第二个调用方（只有各自的测试），
   所以 `onUndoCreate` / `roles` / `onRestoreRoles` 现在**没有真实供给方**。
   哪天有页面接了，供给方要把这三样传进来，否则那两处静默不入栈——
   两条「没给就不入栈」的用例是这条现状的书面记录。
2. **⌘Z 没有绑键**：本卡接的是「入栈 + 撤销动作」，`undo()` 由谁调用（快捷键 / 菜单）
   属界面面，卡面未要求。
3. **撤销失败没有界面提示**：`undo()` 抛错时那一条留在栈上（`undoStack` 的既有语义），
   但用户看不到任何东西。提示归 UI 卡。
4. **`pushBlockUndo` 还没有调用方**：编辑器那侧的操作尚未接进 undo 链，
   本卡只把 S2-5 的闸建好。哪天接了，闸就在路上。
