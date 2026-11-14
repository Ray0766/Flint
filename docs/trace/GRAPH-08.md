# GRAPH-08 trace — 空假设阻断生成 + AI 栏摘要条（F9/F10）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#GRAPH-08`；
- context_refs：`WORKORDER-v04.md#5-F`（F9/F10 行）、`contracts_v04/`（本卡未新增类型）；
- 前置产物：`web/components/graph-edge/GraphEdgeDraft.tsx`（GRAPH-07 的边形状）、
  `web/lib/i18n/t.ts`、`web/messages/{zh,en}.json`。
- 实测装载 ≈ 7k tokens，未超 40k。

## 2 关键设计判断

**置灰之外必须给计数与定位**：一个灰着的按钮只说明「不能生成」，不说明「缺什么、在哪」。
用户面对一张十几个节点的图会挨个点开每条边去找——那正是系统已经知道答案却不肯说的时候。
故徽章报条数、点它把缺假设的边 id **逐条**交给调用方高亮。

**闸门自己看数据**：GRAPH-07 之后新建的边不可能空假设（前后端各拦一道），
但这道闸挡的是别的来路——早于该规则入库的边、批量导入、将来任何绕过 UI 的写入。
props 面因此不收 `hasEmptyHypothesis` 这类由调用方给的结论：一旦收了，
闸门的正确性就取决于每个调用点都算对了，而那是没法验的。

**空图不谎报完整**：零条边时完整度是 0/0，按钮同样不可点，但**理由不是缺假设**，
所以那种情况下不出缺假设徽章——否则用户会去找一条并不存在的坏边。

**没有 primary 就如实空着**：挑一个节点冒充主，等于替用户回答「这张图在讲哪件事」。

## 3 一次返工，顺手把踩了六次的坑抽成共享工具

`闸门自己看数据` 那条初版按字符串扫源码，把组件注释里那句
「props 面不收 `hasEmptyHypothesis` 这类结论」判成了违规——**解释自己不做 X 的
那句话被当成做了 X**。这是同一个坑的第六次（SCHEMA-09 / REGION-05 / I18N-06-b /
FAV-04 / GRAPH-07 后端 / 本卡），每次修法都一样：先剥注释再扫。

故本卡把口径抽成 `web/test-utils/source.ts#codeOnly`（与 `tools/i18n_scan.mjs` 同口径：
块注释 + 整行 `//` + 行尾 `//`），本卡两条源码断言都改用它。
**后面的卡直接用同一把尺子**，不再各自踩一次；既有卡的迁移不在本卡范围内
（它们各自的断言仍然正确，只是各写了一遍）。

## 4 自审报告（§4.6，本卡 self_review=true）

**① 测试真实覆盖 acceptance**

acceptance①「存在空假设边 → 按钮置灰 + 计数徽章 + 点击高亮定位」：

| 测试名 | 覆盖点 |
|---|---|
| `有空假设边：生成按钮置灰，且点它不触发生成` | `disabled` + 点击零调用（只断 disabled 的话，一个能点的灰按钮也会绿） |
| `计数徽章报出几条缺假设：空串与纯空白都算` | `data-count=2`，两种空白形态都计入 |
| `点徽章逐条定位` | 回调收到 `["e-3","e-4"]` —— NEVER 只说一句「有问题」 |
| `阴性对照：边都写了假设时按钮可用且点得动` | 否则「置灰」可能只是因为按钮永远灰着 |

acceptance②「摘要条列 primary / 边数 / 假设完整度三项」：

| 测试名 | 覆盖点 |
|---|---|
| `摘要条三项都在` | `data-primary-node-id` / `data-edge-count` / `data-hypothesis-complete` + `-total` |
| `没有 primary 时如实说没有` | 属性为空串且文案非空；断言它 NEVER 变成某个真实节点 id |
| `空图不谎报完整` | 0/0 且不出缺假设徽章 |

另两条：`闸门自己看数据`（props 面无外部结论 + 判断在本文件里）、`文案 key 化`。

**② 无冻结件偏离**：本卡零触碰 `contracts/` 与 `contracts_v04/`（纯前端组件）。

**③ 无禁用词**：本卡三份产出扫描 `BANNED_HITS= 0`。

**④ 复用断言在位**：边的形状沿用 GRAPH-07 的 `{edgeId, fromNodeId, toNodeId, hypothesis}`；
文案全部经 `t()`；源码扫描口径改用共享 `codeOnly`，不再各写一份。

**⑤ 装载未超预算**：实测 ≈7k tokens（上限 40k）。

## 5 verify

```
$ cd web && npm test -- --run components/graph-generate-gate  → 9 passed
$ npm test -- --run                                            → 215 passed / 32 files
$ npm run typecheck                                            → 干净
$ node tools/i18n_scan.mjs web/components --fail-on-cjk        → exit 0
$ node tools/i18n_scan.mjs web/test-utils --fail-on-cjk        → exit 0
```

整棵 `web/` 树仍是 7 个文件（与 V2/V3 记录一致，属 DEC-013 / 卡 `I18N-09` 的范围，
V5 出口前收），本卡未引入新的命中。

## 6 产出

- `web/components/graph-generate-gate/GenerateGate.tsx`、`GenerateGate.test.tsx`（9 条）
- `web/test-utils/source.ts`（共享源码扫描口径）
- `web/messages/{zh,en}.json`：各 +6 key（51 键，键集一致）
