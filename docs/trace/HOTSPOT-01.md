# HOTSPOT-01 trace — 热点卡片组件（六信息槽）@2026-08-02

## 1 verify
`cd web && npm test -- --run components/hotspot-card` → **7 passed**；
typecheck 干净；`i18n_scan --fail-on-cjk` exit 0；前端全套 99 passed / 17 files。

## 2 「主行恒 name_native」用**组件树断言**（acceptance ②）
不是在本组件里再写一遍主次规则，而是**复用 I18N-04-b 的 `NativeName`**——
两份实现就是两种主次规则，迟早有一处把译名提到主行。
测试因此直接断言 `native-primary` 的 textContent 逐字等于原文，
并加一条反向断言：**译名存在时也 NEVER 取代主行**。

## 3 「缺失逐槽隐藏」为什么不能用占位符（acceptance ①）
占位符会让**「这个热点没有判定」**和**「判定还没跑」**看起来一模一样，
而用户据此做的决定完全不同。
`字段缺失逐槽隐藏` 一条同时断言五个槽都不渲染，**并扫卡片全文**确认不含
`—` / `暂无` / `N/A` / `null` / `undefined` —— 最后两个尤其要防：
JS 里一个 `undefined` 漏进 JSX 就会原样显示出来。

## 4 两处三态区分
- **stale**：`true` 才显标记；`false`（判过、不陈旧）与 `undefined`（**没判过**）都不显——
  两者都不是「陈旧」，但它们彼此也不同，所以本卡只保证「不误报陈旧」，
  「没判过」的可见化留给 R4 陈旧横幅那条线；
- **region**：未归区（`null`）时隐藏该槽 —— **NEVER 猜一个区填上**
  （与 REGION-02 的 `UnknownSourceRegion` 同一条纪律）。

## 5 产出
`web/components/hotspot-card/HotspotCard.tsx`、`HotspotCard.test.tsx`（7 条）。
