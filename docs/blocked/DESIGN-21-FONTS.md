# DESIGN-21 · 品牌字体需 owner 提供 woff2 二进制（非阻塞·已按回落栈交付）（**已关闭** @2026-08-03）

**状态** closed · 2026-08-03 · `DEC-018`

**裁决（owner 2026-08-03 · DEC-018）：接受系统回落字体，本单关闭。**

品牌字形（得意黑首屏大字与页面级标题、IBM Plex Mono 数值）在 v0.4 交付形态里退成回落栈，**只影响视觉观感，不影响数据、判定与导出正确性**。woff2 自托管移入 v0.4.1，与端到端联调同批处理（`docs/v0.4.1-候选清单.md#⑦`）。DEC-017 的「产物 NEVER 向外部要字体」继续有效，`tools/no_external_fonts.mjs` 保持出口门；`fonts.css` 里自托管的 `@font-face` 接法与放置目录已写死，补二进制时只加文件、不改结构。

---

> 状态：**非阻塞**。卡片 acceptance（`web` 全目录外部字体 URL 零命中）已达成并 verified；
> 本单登记「品牌字形暂时不可用」这一后果，等 owner 决定是否提供字体二进制。

## 现象

挂进仓库的 `_ds` 副本里，`fonts/fonts.css` 原有两条外部引用：

```
@import url("https://cdn.jsdelivr.net/npm/cn-fontsource-smiley-sans-oblique-regular/font.css");
@import url("https://fonts.googleapis.com/css2?family=Inter:wght@...&family=Noto+Sans+SC:...&family=IBM+Plex+Mono:...");
```

`_ds` 自己的 readme 也写着：**「Replace with self-hosted woff2 if the user provides binaries.」**

## 为什么必须去掉

交付出去的文件带着它们，就会在**客户机器上**向第三方要东西：内网打不开、离线打不开、
对方能看见谁在什么时候读了这份文件；而哪天那两个 CDN 改版，早已交付的文件会自己变样。
这与 DESIGN-20 的依赖白名单是同一条纪律。

## 为什么不能自己补上自托管

自托管要 woff2 **二进制**，而取得它们要联网下载——**真实网络属 worker.md §7 的
事前必审项**（S2-7 同款），NEVER 自行触发。

## 当前交付形态（本卡已落地）

- 两条 `@import` 已移除；`fonts.css` 现在只剩一段说明 + 自托管的接法。
- 文字走 `tokens/typography.css` 里**已声明的回落栈**
  （Inter → Noto Sans SC → PingFang SC → system-ui），照常渲染，**只是不是品牌字形**：
  得意黑（首屏大字与页面级标题）与 IBM Plex Mono（数值）会退成系统字体。
- 影响面：视觉观感；**不影响任何数据、判定或导出正确性**。

## 需要 owner 提供什么

三种字体的 woff2 二进制（得意黑 SIL OFL / Inter / Noto Sans SC / IBM Plex Mono），
放进 `web/public/_ds/…/fonts/`；随后在 `fonts.css` 里按 `@font-face` + 同源
`src: url("/_ds/…/fonts/xxx.woff2")` 声明即可，扫描器判据不变（同源不算外部）。

或者：明确接受系统回落字体，本单关闭。
