# `AnalysisView` 全组件零 `className`——热点分析屏拿不到设计系统的任何样式

**状态** closed · 2026-08-09 · `FIX-19`

> 改法在 `web/views/analysis/AnalysisView.tsx`——**v0.4 已 verified**（`HOTSPOT-03`，
> 2026-08-02）。按 `worker.md` §9.2 / `DEC-021`「需要改 v0.4 已 verified 的文件时，
> 停下报 owner」立单，NEVER 自行动手。

## 一、实况

`GAUGE-15` 给全部 23 屏铺声明时，逐屏取渲染后的计算样式。
`/clusters/[id]`（`NAV-02` 建的热点分析屏）是**唯一一屏**：

```
styled: []          ← 屏上没有任何一个带样式的类名
```

组件本体逐字如下（节选），全文件 `className` 出现 **0 次**：

```tsx
<section data-testid="analysis-view" data-cluster-id={clusterId}>
  <h2 data-testid="analysis-verdict-heading">{t("analysis.section.verdict")}</h2>
  <p data-testid="analysis-verdict-unjudged">{t("analysis.verdict.unjudged")}</p>
  <ul data-testid="analysis-evidence">
    <li data-testid="analysis-evidence-card">…</li>
```

## 二、这与广场屏当初是同一个形状

`GAUGE-12` 建这把尺子的理由原话：

> 广场屏那四条 `EYE-03` 判据（HTTP 200 · 零控制台报错 · 无横向溢出 · 两主题截图）
> **全绿**，而那一屏是个 `ul/li`、全文件零 `className`——它就是这么过去的。

热点分析屏此刻正是那个样子。它今天不难看（标题继承了排版层的字号，证据卡是一个
`ul`），但**它没有接上设计系统**：卡片、分区、状态色一样都没有，
而同一份内容在图谱抽屉里（`GraphOpenAnalysis`）也会长成这样。

## 三、为什么不先随手填一个类名顶上

声明里 `styled` 那一栏是「MUST 有样式的类名」。填一个别处的类名（比如 `data-row`）
能让这一屏在报告上变绿，**而它没有变好**——那正是这把尺子要治的病本身。

所以声明里写的是 `styled: []` + `styled_none_because`，并由判据
`test_a_screen_without_styling_must_name_an_open_sheet` 逼着它指向这张单。
**报告上它是显式的一行「这一屏没有样式，单在这儿」，不是一片绿。**

## 四、改法（等 owner 一句话）

给 `AnalysisView` 的六个槽位加类名，样式落在 `globals.css`：

| 槽位 | 建议类名 |
|---|---|
| 根 `<section>` | `analysis` |
| 两个 `<h2>` | `analysis__section-title` |
| 判定那一格 | `analysis__verdict` |
| 三种状态句（loading / unjudged / error） | `analysis__state` |
| 证据 `<ul>` / `<li>` | `analysis__evidence` / `analysis__evidence-card` |

**改的是 6 行 + 一段 CSS，一个判据都不用改**：`HOTSPOT-03` 的 6 条 vitest 判的是
`data-testid` 与四态，与类名无关。`GAUGE-15` 那边把 `styled: []` 换成这几个类名、
删掉 `styled_none_because` 即可。

## 五、关掉这一单的条件

`assets/screen_composition.json` 里 `/clusters/[id]` 的 `styled` 非空，
且 `tools/check_screen_composition.mjs` 对它零违规。

---

## 关闭（`FIX-19` · 2026-08-09）

**owner 2026-08-09 明确许可动这个 v0.4 封版件**，边界逐字是
「**只加类名与样式**——NEVER 改判定语义、NEVER 动四态、NEVER 改任何既有判据」。

本次改动逐条就是：`AnalysisView` 里 **15 处元素各加一个 `className`**，
样式落在 `web/app/globals.css` 的 `.analysis*` 一段，全部走 `_ds` token。

**边界是可量的**，不靠谁记得：判据
`test_stripping_the_class_names_gives_back_the_original_render`
把源码里所有 `className="…"` **剥掉**，再与改前的渲染段逐字比对——
改了一个分支、动了一处 `data-*`、换了一句文案，它都会红。

`assets/screen_composition.json` 里 `/clusters/[id]` 的 `styled` 已从 `[]`
换成那 8 个真类名（**从组件源码取，不是手写**），
那句 `styled_none_because` 一并删掉——它现在是假话。
