# SCHEMA-12 trace — I12 三条不变量 @2026-08-02

## 1 装载
SCHEMA-12 卡 + `WORKORDER#4-I12`（三个规定函数名的原文）+ `models_v04.py` 的图谱区。
~1,200 字符 ≈ 1.2k tokens（3%）。

## 2 test-first（真红 3 条）
先写测试 → **3 failed**（`set_primary` / `GraphChange` / `derive_stale` 都不存在）→
实现后 **4 passed**，additive exit 0，全套 80 passed。

三个函数名**逐字照 §4-I12**：`test_primary_unique` / `test_hypothesis_nonempty` /
`test_graph_change_derives_stale`（规定名，NEVER 自己另起）。

## 3 三条各自守什么（判断写进实现的 docstring）
**① primary 唯一**：primary 是「这张图在讲哪件事」。两个 primary = 两个主语，
下游拿它做标题/摘要时无从选择。**自动降级而不是报错**——用户点第二个节点设主，
意思很明确；让他先去取消上一个，是把系统的洁癖变成用户的负担。
另测三条边界：重复设同一个是幂等、全无 primary 的图合法（还没定主语）、设不存在的节点报错。

**② 假设非空**：与 SCHEMA-08 的边校验同一入口（NEVER 两份实现），三种空白形态参数化。

**③ 图变派生 stale**：结构性变更（node/edge 增删）派生；**`node_moved` 不派生**——
画布上挪个位置没有改变任何论断，把布局变动也算 stale 会让「陈旧」这个信号迅速失去意义。
另断言没有关联产物的图不派生任何 stale。

## 4 「纯函数层」是被断言守着的
卡上写「stale 派生为纯函数层验证，运行时接线留 DESIGN-25」。
`test_stale_derivation_is_a_pure_function` 断言 `derive_stale` **不就地修改入参**
（比对调用前后的深拷贝快照）——它只定派生规则，NEVER 自己去改任何对象的 stale 标记；
运行时接线走 §6-H1 的 `Revalidator` 统一口径。

## 5 产出
`tests/v04/schema/test_i12_invariants.py`（4 条，含三个规定名）+ `GraphNode.primary`
+ `GraphChange`/`GraphChangeKind` + `set_primary()` + `derive_stale()`。
