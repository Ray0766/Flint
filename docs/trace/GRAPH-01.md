# GRAPH-01 trace — 工作台容器与路由（对 F15 两案中立）@2026-08-02

## 1 verify
`cd web && npm test -- --run views/workbench-shell` → **7 passed**；typecheck 干净；
`i18n_scan --fail-on-cjk` exit 0。

## 2 为什么容器里不能有 mode（acceptance ②）
F15（页签 vs 模式切换）是**隔离带卡 GRAPH-16** 的议题，**owner 可整体划掉**。
容器若现在就引入 `mode` 概念：
- 等于替 owner 先选了一案；
- 且划掉 GRAPH-16 时容器要跟着改——**隔离带就不成其为隔离带了**
  （工单 §11：带外任何卡不依赖带内卡）。

所以容器只做三件事：**认路由、给插槽、不决定布局**。
「默认 / AI」这类词只能是**预设组合的文案**，NEVER 成为状态树里的键。

断言方式：源码扫 `mode`/`Mode`/`tab`/`Tab`（**只看代码行**，注释里解释 F15 的文字不算）；
props 面只有 `children` 与可选 `aside`，且不含 `layout`/`variant`/`preset`。

## 3 一处自纠：一条空转断言
「容器不导出任何页签/模式相关符号」初版是拿**一个空对象**查 keys——
不管容器导出什么它都绿。改成真的 `await import("./WorkbenchShell")` 看导出名，
并断言导出面恰是 `["WORKBENCH_ROUTE", "WorkbenchShell"]` 两项。

## 4 路由归属（acceptance ①）
`WORKBENCH_ROUTE = "/workbench"` 归 **F 组**（J4 定名，MIGRATE-03 已标 `owner_review`）；
容器把它挂在 `data-route` 上，供上层路由与测试双向核对。

## 5 侧栏是可选插槽
不给就**不渲染**，NEVER 留一个空壳 —— 空壳会在图谱旁边留一条没有内容的竖栏，
看起来像「面板加载失败」。

## 6 产出
`web/views/workbench-shell/WorkbenchShell.tsx`、`WorkbenchShell.test.tsx`（7 条）。
