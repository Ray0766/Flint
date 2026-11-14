# GRAPH-05 trace — 双击节点开分析抽屉（不离台）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#GRAPH-05`；
- context_refs：`WORKORDER-v04.md#5-F`（F 组表格 F4 行 + 容器脚注）、`contracts_v04/`（本卡未新增类型）；
- 前置产物：`web/views/analysis/AnalysisView.tsx`（HOTSPOT-03，抽屉里装的就是它）、
  `web/components/graph-node/GraphNode.tsx`（GRAPH-03，测试里用的是真节点）、
  `web/lib/i18n/t.ts`、`web/messages/{zh,en}.json`。
- 实测装载 ≈ 8k tokens，未超 40k。

## 2 这是 V4 第一张**装配**卡（承 SELFCHECK-V3#④ 的风险项）

V3 出口报告里点名的风险是：前端到目前为止只有组件级测试，装到一起没人验过。
本卡的测试因此用**真的 GraphNode + 真的 AnalysisView**，不用替身——
「不离台」这件事只有把容器与子组件真拼起来才验得到：单测一个抽屉壳子，
抽屉里装的是不是那个分析视图、画布是不是还活着，两件都测不到。

具体到断言：抽屉打开后断言 `analysis-view` 与 `analysis-verdict` 这些
**AnalysisView 自己的 testid** 出现且 `data-verdict` 为后端给的值——
这一条同时证明了「复用了那个组件」和「它在抽屉里真的跑起来了（读端点被调、状态到位）」。

## 3 关键设计判断

**不离台 = 不跳路由 + 不罩死画布**。跳路由的后果是画布状态（选中、位置、未落盘的摆放）
要靠恢复逻辑重建，而恢复不全的地方用户会当成「我刚才白摆了」。
故三层断言：地址栏前后逐字相同、源码里没有任何跳转手段（`pushState` / `location.href` /
`useRouter` / `router.push` / `<a ` / `href=` / `window.open` 七项）、
抽屉 `aria-modal="false"`（不是模态，画布仍可交互——罩死的话与跳走一页只差视觉）。

**复用不复制**：正向断言 import 自 `../../views/analysis/AnalysisView`，
反向断言源码里不出现 `analysis-verdict` / `analysis-evidence` / `analysis-verdict-unjudged`
这些槽位 testid——有人顺手在抽屉里自绘一个判定槽，这条立刻红。复刻的后果是
同一个热点在画布上和分析页上显示出不同的东西，而用户以为看的是同一份分析。

**单击不开**：画布上点一下是选中。点一下就弹出一屏东西，会让框选、拖动这些
以单击起手的操作处处踩雷；测试里连「单击后零请求」都断了。

**打开抽屉零写请求**：沿用 HOTSPOT-03 的口径并在装配层复验——点开一个热点
NEVER 顺手跑一次分析。配阴性对照 `calls.length >= 2`（读确实发生了，不是空转）。

## 4 acceptance ↔ 测试映射

acceptance 唯一条：**抽屉复用分析视图组件；路由不跳转断言**。

| 测试名 | 覆盖点 |
|---|---|
| `双击节点打开抽屉，抽屉里是那个分析视图` | AnalysisView 的 testid + `data-cluster-id` + `data-verdict` 三处装配证据 |
| `不离台：画布与那个节点仍然在场` | 抽屉打开后 `graph-node` 与 `data-node-id` 仍在 |
| `路由不跳转：地址栏一个字符都没变` | `window.location.href` 前后逐字相同 |
| `源码里没有任何跳转手段` | 七项跳转手段逐个断言不存在 |
| `复用不复制` | 正向 import 断言 + 三个槽位 testid 的反向断言 |
| `单击不开抽屉` | 单击后无抽屉 + 零请求 |
| `关闭抽屉回到画布` | 抽屉与视图都消失、节点仍在（不留残影） |
| `打开抽屉只读` | 全程只有 GET、无 `/analysis`、阴性对照读确实发生 |
| `抽屉是对话框语义` | `role=dialog`、`aria-modal=false`、关闭控件在场 |
| `文案 key 化` | 源码代码行零 CJK |

## 5 verify

```
$ cd web && npm test -- --run components/graph-open-analysis  → 10 passed
$ npm test -- --run                                            → 188 passed / 29 files
$ npm run typecheck                                            → 干净
$ node tools/i18n_scan.mjs web/components --fail-on-cjk        → exit 0
```

## 6 产出

- `web/components/graph-open-analysis/GraphOpenAnalysis.tsx`、`GraphOpenAnalysis.test.tsx`（10 条）
- `web/messages/{zh,en}.json`：各 +2 key（35 键，键集一致）
