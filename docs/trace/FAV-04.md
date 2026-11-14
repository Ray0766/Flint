# FAV-04 trace — 图书馆筛选与搜索 @2026-08-03

## 1 verify
`cd web && npm test -- --run views/library-filters` → **9 passed**；typecheck 干净。

## 2 「未设 = 不过滤」，NEVER 拿「全部」当枚举值
三个过滤器是**合取**：都设就都要满足；任一未设即该维不过滤。
把「全部」做成一个可选值混进枚举，会让**「没筛」和「筛了全部」在状态里长得一样**，
回读时无从区分（也就无从知道用户是否真的筛过）。

## 3 两处「不猜」延续到筛选层
- `region: null`（未归区）的项 **NEVER 被当成某个区**：按 JP 筛时不出现，不筛时出现；
- 判定按**收藏当时**的 `verdictAtSave` 筛，不是当前判定（与 FAV-03 同一口径）。

## 4 空结果态有引导（acceptance ②）
一个空列表什么都不说，用户不知道是**没有数据**还是**筛过头了**。
空态给引导文案且 key 化。

## 5 一处自纠：测试自己的剥注释逻辑不够
`空态文案 key 化` 首轮红——我只滤了 `//` 行，而 JSDoc 块注释
（`/** 未设 = 不按地区过滤 */`）里的中文被当成了代码。
补上块注释剥离后转绿。**同一类坑第四次**（SCHEMA-09 / REGION-05 / I18N-06-b 各一次），
这次是块注释形态。

## 6 产出
`web/views/library-filters/LibraryFilters.tsx`、`LibraryFilters.test.tsx`（9 条）。
