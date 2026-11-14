# GRAPH-03 trace — 图谱节点渲染（复用不复制）@2026-08-02

## 1 verify
`cd web && npm test -- --run components/graph-node` → **6 passed**；typecheck 干净；
`i18n_scan` exit 0；前端全套 112 passed / 19 files。

## 2 「子组件复用不复制」怎么断言（acceptance ②）
不是「看起来像复用」，而是**两侧都断**：
- **正向**：源码里有 `from "../hotspot-card/HotspotCard"`；
- **反向**：源码里**不出现**任何被复制的槽位 testid
  （`hotspot-region` / `hotspot-first-seen` / `hotspot-stale` / `hotspot-verdict` / `native-primary`）——
  一旦有人「顺手」在节点里自绘一个槽，这条立刻红。

理由：节点是「热点在画布上的投影」。两处各写一套，同一个热点在**广场与画布上会显示出不同的东西**，
而用户会以为那是两个热点。

## 3 两条从上游继承的纪律，本卡验证它没走样
- **主行仍是 `name_native`**（经 `NativeName`，非本组件另写）；
- **字段缺失仍逐槽隐藏**——复用不能把 HotspotCard 的「NEVER 假数据占位」纪律丢掉。

## 4 两个节点自有属性
- `data-source-kind`：节点是**既有实体的投影**（§6-H8），不是新造的东西；
- `data-primary`：**默认 false**（I12-1 图内 primary 恒 ≤1，默认不抢）。

## 5 产出
`web/components/graph-node/GraphNode.tsx`、`GraphNode.test.tsx`（6 条）。
