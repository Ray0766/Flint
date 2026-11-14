# GRAPH-11 trace — 力导向一次性布局（手写收敛即停，零新依赖）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#GRAPH-11`；
- context_refs：`WORKORDER-v04.md#2-J2`（技术方案增量口径）、`WORKORDER-v04.md#5-F`（F12 行）；
- 前置产物：`web/components/graph-node/GraphNode.tsx`（节点形状）、
  `web/package.json`（依赖面）、`web/test-utils/source.ts`。
- 实测装载 ≈ 6k tokens，未超 40k。

## 2 关键设计判断

**一次性而不是持续模拟**：持续 rAF 的力导向图会一直微微地动——用户想点的节点
会在指尖底下漂走，而且每一帧都在烧电。摆位置是**一次**动作，摆完就停。
故本模块是**纯函数**：不排帧、不设定时器、不持有状态；要重排就再调一次。
源码断言把 `requestAnimationFrame` / `setInterval` / `setTimeout` 四个词直接禁掉。

**确定性初值**：按下标排在圆环上，NEVER 用随机数——随机初值会让同一张图每次打开
都换个样子，用户会以为数据变了。测试断言两次跑出逐字相同的位置 + 源码无 `Math.random`。

**锁定节点不动**：用户手动摆过的位置（GRAPH-04 落盘的那些）传进 `pinned`，
自动布局不挪它们——挪走等于把用户的摆放当成噪声。

**零依赖**：模块只允许相对路径 import（源码断言 `not.toMatch(/from\s+"[^./]/)`），
并另断 `package.json` 里没有 d3 / d3-force / elkjs / dagre / cytoscape / vis-network。

## 3 一次实测推翻的设计（初版真的不收敛）

初版只按「最大位移 < 阈值」停 —— **12 个节点跑满 300 轮也没停**，`converged=false` 报红。
原因不是参数没调好：斥力与引力会把节点推成一个来回摆的极限环，每轮位移都不小。
改法是加**冷却**（单步位移上限逐轮线性降到 0，200 轮走完），终止从此有保证。

冷却在 200 轮走完、上限 300 轮，**两者留出差额是有意的**：这样「跑满 300 轮」
仍然是一个真的异常信号（`converged=false`），而不是每次都必然发生的常态——
若把冷却横跨到 300，`converged` 就永远为真，那个字段也就不再报告任何事。

## 4 一处工具缺陷实测（已并入 I18N-09 的 acceptance）

本卡用 Python 改写源码时，Windows 把文件换行翻成了 CRLF，随后
`node tools/i18n_scan.mjs web/lib/graph-layout --fail-on-cjk` 报红，命中的是
**第 1 行的 `//` 中文注释**——而工具自述「注释行不算」。

根因：工具按 `\n` 切行，CRLF 文件每行尾留下 `\r`；它的剥注释正则 `/\/\/.*$/`
在 JS 里 `.` 不匹配 `\r`、`$`（无 `m` 标志）只匹配串尾，于是整行注释一个字符都没被剥掉。
**任何 CRLF 文件里的中文行注释都会被误报**，这是继 JSDoc 块注释之后的第二类假阳性。

处置两步：① 把本轮被换行翻译过的四个文件（`forceLayout.ts`、`GenerateGate.test.tsx`、
`messages/{zh,en}.json`）改回 LF，与仓库其余同类文件一致；
② 给 owner 已核准的卡 `I18N-09` 追一条 acceptance：「同一份内容以 CRLF 与 LF 两种换行
各扫一次，结果必须相同」。DAG 复跑 acyclic / nodes 104 / errors []。
**没有去改扫描器**——那是 I18N-09 的产出，本卡改它就成了两张卡改同一个文件。

## 5 acceptance ↔ 测试映射

| 测试名 | 覆盖点 |
|---|---|
| `跑完就停：返回迭代次数，且不超过上限` | `converged=true` 且轮数在上限内 |
| `没有持续动画：源码里既不排帧也不设定时器` | 四个词逐个断言不存在 |
| `零新依赖：本模块不 import 任何第三方包` | 只允许相对路径 import |
| `package.json 无新增布局依赖` | 六个常见布局库逐个断言不在依赖面 |
| `50 个节点也跑得完，且每个节点都拿到了位置` | F12 的 ≤50 规模 + 坐标有限 |
| `确定性：同样的输入两次跑出逐字相同的位置` | 两次结果相等 + 无 `Math.random` |
| `相连的节点比不相连的近` | 布局**真的在做事**（否则「跑完就停」可能只是原地不动） |
| `节点不重叠：两两之间留得下一个身位` | 斥力生效 |
| `锁定的节点原地不动` | pinned 语义 |
| `空图与单节点不炸` / `悬空边被忽略而不是让布局崩掉` | 两条边界 |

## 6 verify

```
$ cd web && npm test -- --run lib/graph-layout   → 11 passed
$ npm test -- --run                               → 247 passed / 35 files
$ npm run typecheck                               → 干净
$ node tools/i18n_scan.mjs web/lib/graph-layout --fail-on-cjk → exit 0（改回 LF 后）
$ node tools/i18n_scan.mjs web/components --fail-on-cjk       → exit 0
```

禁用词扫描：本卡两份产出 0 命中。

## 7 产出

- `web/lib/graph-layout/forceLayout.ts`、`forceLayout.test.ts`（11 条）
- `tasks-v04.json#I18N-09`：acceptance +1 条（CRLF 假阳性）
