# GRAPH-12 trace — 树视图 = primary 根 BFS 投影 + 未连接区@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#GRAPH-12`；
- context_refs：`WORKORDER-v04.md#4-I8`（图谱三实体：边有向、hypothesis 必填）、
  `WORKORDER-v04.md#5-F`（F13/F14 行）；
- 前置产物：`flint/graph/store.py`（节点/边的字段与有向语义）、
  `web/components/graph-generate-gate/GenerateGate.tsx`（primary 缺席时的口径）、
  `web/test-utils/source.ts`。
- 实测装载 ≈ 7k tokens，未超 40k。

## 2 关键设计判断

**投影的硬约束：树里的节点 + 未连接区 = 图里的全部节点**，一个不多一个不少。
切一下视图少了两个节点，用户不会想到「那是投影规则的问题」——他会以为自己把它们删了，
然后回到图谱里去找那两个再也找不到的东西。这条写成了一条直接的集合相等断言。

**未连接区是如实的去处**：从 primary 走不到的节点**不挂到根下面充数**。
挂上去等于凭空发明一条关系，而这张图里每条边都要有假设（GRAPH-07）；
进「未连接」区则让用户一眼看见「这几个还没接进来」——那正是他下一步要做的事。

**没有 primary 就没有树**：不挑一个节点当根（与 GRAPH-06/08 同一条纪律），
全部进未连接区。配一条源码断言禁掉 `nodes[0]` 这种「随便挑一个」的写法。

**有向不倒置**：BFS 只沿 `from → to`。倒过来的话，「A 导致 B」会在树上显示成
「B 之下有 A」——那是把因果读反了。测试用一条只有反向边的图验：`n-2` 从根出不去，
进未连接区。

**环只落一层**：回边不让 BFS 转不出来，每个节点恰好一个深度。

**同层稳定排序**：兄弟按 id 排。不排的话同一张图每次刷新兄弟次序都可能变，
用户会以为结构动了。

## 3 acceptance ↔ 测试映射

acceptance①「同一存储双投影一致（图↔树切换零丢节点）」：

| 测试名 | 覆盖点 |
|---|---|
| `零丢节点：树里的节点 + 未连接区 = 图里的全部节点` | 集合相等（投影的硬约束） |
| `渲染出树与未连接区两块，节点计数与图一致` | 渲染层复验：两块行数之和 = 节点数，且 `data-node-count` 对得上 |
| `primary 是根，层级按 BFS 距离` | 根与三层深度逐个断言 |
| `每一行带得出自己的深度与 id` | 树形是**数据**不是缩进（上层与测试都能读回） |

acceptance②「未连接节点入独立区」：

| 测试名 | 覆盖点 |
|---|---|
| `未连接的进独立区，NEVER 被挂到根下面充数` | `detachedIds=["n-5"]` 且它不在 `depthOf` 里 |
| `没有 primary 时整棵树为空、全部进未连接区` | 不挑根 + 源码断言无 `nodes[0]` |
| `有向：反向边不把父子关系倒过来` | 只有反向边时从根出不去 |
| `未连接区在树为空时也渲染` | 空态是明确状态（沿用 FAV-06 口径） |

另两条：`环不让 BFS 转不出来`、`同深度的兄弟按 id 稳定排序`。

## 4 verify

```
$ cd web && npm test -- --run views/graph-tree  → 11 passed
$ npm test -- --run                              → 258 passed / 36 files
$ npm run typecheck                              → 干净
$ node tools/i18n_scan.mjs web/views --fail-on-cjk → exit 0
```

禁用词 0；两份产出均为 LF（GRAPH-11 实测的 CRLF 假阳性之后，本卡写文件时显式指定
`newline="\n"`，并在收卡前断言无 `\r\n`）。

## 5 产出

- `web/views/graph-tree/GraphTree.tsx`（含 `projectToTree` 纯函数）、`GraphTree.test.tsx`（11 条）
- `web/messages/{zh,en}.json`：各 +1 key（55 键，键集一致）
