# FAV-03 trace — 图书馆卡片墙 + 四维排序 @2026-08-02

## 1 verify
`cd web && npm test -- --run views/library` → **9 passed**；typecheck 干净；
`i18n_scan` exit 0；前端全套 121 passed / 20 files。

## 2 排序基于**收藏时点的快照**，不是当前源
四个排序键都读收藏项自带的字段（FAV-01 的内嵌快照口径）。
特别是 `verdict_at_save` —— 与卡上的 `verdict` **分开**：
后者可能已被后续分析改写，若排序用它，
「我当时收藏的是一个 A 档」这个问题就失去答案了。
测试断言源码里确实用 `verdictAtSave` 而非当前判定。

## 3 两处「不猜」
- `region` 排序：未归区排**最后**（哨兵 `\uffff`），NEVER 猜一个区把它塞进某组；
- `verdict_at_save`：收藏时未判定同样排最后，而不是当成某个默认档。

## 4 排序**稳定**
主键相等时按 `favoriteId` 兜底 —— 否则同分项每次刷新换位置，
用户会以为列表在自己动。

## 5 复用不复制（acceptance ②）
与 GRAPH-03 同一套两侧断言：正向断言 import 了 `HotspotCard`；
反向断言源码里**不出现** `hotspot-region` / `hotspot-verdict` / `native-primary` 等被复制的 testid。

## 6 产出
`web/views/library/Library.tsx`、`Library.test.tsx`（9 条）。
