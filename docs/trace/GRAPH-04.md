# GRAPH-04 trace — 节点拖动（rAF 节流 + 松手落盘 + 失败回弹）@2026-08-03

## 1 verify
`cd web && npm test -- --run components/graph-drag` → **6 passed**；typecheck 干净；
前端全套 152 passed / 25 files；`i18n_scan` exit 0。

## 2 三条 acceptance 的理由
**① 拖动期零写请求**：每移动一像素发一次 PATCH，会把一次拖动变成上百次写，
而其中 99 次的位置**用户根本没打算保留**。测试连发 20 次 pointerMove 后断言 `persist` 未被调用。

**② 松手恰一次**：断言 `toHaveBeenCalledTimes(1)` 且带**最终坐标**——
只断言「被调用过」的话，发 3 次也会绿。

**③ 失败回弹原位**：不回弹的话，界面上节点停在新位置、服务端还在老位置，
下次刷新它自己跳回去，**用户会以为是 bug 或数据丢了**。
配**阴性对照** `落盘成功则停在新位` —— 否则「回弹」可能是无条件的。

## 3 rAF 注入让节流可被确定地验证
`raf` 作为 prop 注入：测试里传一个**同步执行**的假 rAF 来驱动位置更新，
另一条测试传一个**只收集不执行**的假 rAF，断言三次 pointerMove **只排了一帧**——
这才是「节流」本身被测到了，而不是「看起来没卡」。

## 4 一条边界
`未按下时移动不生效` —— NEVER 幽灵拖动：鼠标扫过画布不该让节点跟着走。

## 5 产出
`web/components/graph-drag/GraphDrag.tsx`、`GraphDrag.test.tsx`（6 条）。
