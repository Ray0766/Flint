# v0.4.1 第 13 批（视觉批）· 完成态报告

**6 / 6 卡 verified · 0 blocked。** 五条全局门全绿，**pytest 零 failed**。

**你的三条意见全部兑现。**

---

## 一 三条意见的兑现对照

| 你说的 | 做成了什么 | 哪张截图为证 |
|---|---|---|
| ①「这个上面导航栏要用我给出的导航栏的样式」+「做成一个横栏」 | 照蓝本做了**顶部居中的药丸浮动条**：`position: fixed` · `border-radius: 9999px` · `backdrop-filter: blur(16px)` · 1px 描边 + 投影 · 居中（左 348 / 右 348，差 0）。**九项排成一行**——6 个导航 + 品牌字 + 地区/语言 + 主题，`offsetTop` 全部 = 8（改前折成三四行）。当前项底下有**跟着走的发光块**：`left/width` 与该项的 `offsetLeft/offsetWidth` **逐字相等**，切屏后仍相等。吉祥物**照蓝本做全**，坐在当前项正上方 | `.ui-probe/eye04/plaza-1920x1080-dark.png` |
| ②「标题做大」 | `h1.screen__title` **31px → 48px**（1920），品牌字 **20px → 30px**；且**随视口分级**（1440 → 37px，390 → 24px），改前三个视口是同一个数 | `plaza-1920x1080-light.png` 与 `plaza-390x844-light.png` 对比 |
| ③「把这一块铺满整个屏幕，所有内容都放大」 | 主体宽度 **476px → 1760px**（1920 下 = 视口的 **0.92**；1440 下 0.97）。**而报告正文仍是 476px**——那一屏是长文，一行 1760px 读起来会不断丢行 | `plaza-1440x900-dark.png` |

### 六张截图（不用翻目录）

```
.ui-probe/eye04/plaza-1920x1080-light.png
.ui-probe/eye04/plaza-1920x1080-dark.png
.ui-probe/eye04/plaza-1440x900-light.png
.ui-probe/eye04/plaza-1440x900-dark.png
.ui-probe/eye04/plaza-390x844-light.png
.ui-probe/eye04/plaza-390x844-dark.png
.ui-probe/eye04/report.json      ← 每张图当时量到的数
```

六张**逐张**同时满足四条：顶栏一行药丸 · 主体 ≥ 视口 × 0.9（390 除外）·
无横向溢出 · **零控制台报错**。

---

## 二 五条全局门（逐字贴）

```
$ ruff check .
All checks passed!

$ PYTHONIOENCODING=utf-8 python -m mypy --strict flint
Success: no issues found in 323 source files

$ PYTHONIOENCODING=utf-8 python -m pytest -q
5376 passed, 2 skipped, 12 warnings in 621.11s (0:10:21)

$ npx tsc --noEmit
（无输出，退出 0）

$ npm test -- --run
Test Files  85 passed (85)
     Tests  858 passed (858)
```

### pytest 的红：一条都没有

本批一路上红过的每一条，**逐条点名归属**（NEVER 按族小结）：

| 曾经红的 | 归谁 | 现在 |
|---|---|---|
| `test_width_fullbleed::…no_longer_uses_the_typography_token` | 判据按行首 `/*` 剥注释，而 CSS 块注释跨多行 | 改成整段正则剥（**第九次**） |
| `test_cn03_preflight::…newest_day_with_data` | dev server 少了两个 `NEXT_PUBLIC_` 变量 | 按 `start-demo.ps1` 补齐后自愈，**与本批改动无关** |
| `test_nav_anime::…active_tab_is_brighter…` | **我的探针拿当前项和自己比**（`tabs[0]` 恰好是当前页） | 改成取第一个非当前项 |
| `test_nav_anime::…labels_become_icons…` | 判据逐字比 `inline-flex`，而浏览器算成 `flex` | 改成「是某种 flex」 |
| `test_nav_mascot::…sits_above_the_bar` | 逐字比浮点（40 vs 39.999996） | 改成四舍五入 |
| `test_nav_mascot::…reduced_motion_stops_every_animation` | **真缺陷**：hover 那几条特异度更高，压过了减动效块 | 在减动效块里把 hover 那几条再停一遍 |
| `test_ui_restyle` / `test_ui_mainchain`（CJK 未 key 化） | **真缺陷**：我把 `aria-label` 写死成中文 | 走既有词条 |
| `test_analysis_view_styled`（写死颜色） | **真缺陷**：蓝本的色直接写进了规则 | 收成 token |
| `test_analysis_view_styled`（写死尺寸） | 判据**射程无限**（扫到文件尾），圈进了蓝本几何 | 收窄到本卡那一段 |
| `test_shell_locale_dropdowns`（`flex:1` 占位没了） | **真缺陷**：我换组件时删了 `.app-shell__spacer` | 放回来 |
| `shell.test.tsx` ×2（前端） | 判据按 `.app-shell__nav-link` 找，而我换了类名 | **两个类名一起挂**，不是改判据 |

---

## 三 六张卡各做了什么

| 卡 | 病 | 现在 |
|---|---|---|
| `WIDTH-01` | 长文行长 token 被当成应用容器宽度（34em≈476px 套住全部屏） | 容器档与排版档各自命名；网格屏 0.92，长文屏仍 476px |
| `NAV-ANIME-01` | 顶栏是纸面横条，9 个控件折成三四行 | 照蓝本的药丸浮动条 + 跟随发光块，两主题各一套 |
| `NAV-ANIME-02` | — | 吉祥物照蓝本做全（六个 keyframes、四种交互动画） |
| `TITLE-01` | 标题 31px 且三个视口一样大 | 两档写进 `_ds`，随视口 clamp |
| `EYE-04` | — | 六张截图 × 四条正向，截图与数一起落盘 |
| `SHIP-13` | — | 本报告 |

---

## 四 「判据一律正向」这条纪律，本批兑现了三次

你定这条的由来是 `UI-01~11`：四条禁止性判据全绿，而那一屏是个 4072px 的裸列表。
本批有三处**只有正向判据抓得住**：

1. **`backdrop-filter` 被 CSS 管线吃掉了。**
   源码里无前缀与 `-webkit-` 两条并排写，lightningcss **只保留了 `-webkit-` 那条**，
   而 `getComputedStyle().backdropFilter` 读的是无前缀的——量到 `none`，
   **而屏上其实是糊的**。
   > 一条「NEVER 没有毛玻璃」的禁止性判据在这里量到 `none` 也不会红。

2. **减动效在最需要它的时候失效。**
   静止时确实不动，**鼠标一悬停三个动画全回来**——
   hover 那几条选择器带 `[data-hovered]`，特异度压过了减动效块。
   是「hover 之后再量一次」那半条正向判据逼出来的。

3. **吉祥物只剩一条白尾巴。**
   `NAV-ANIME-01` 给条加的 `overflow-x: auto` 把探出条外的头整个裁掉。
   一个「为了稳妥」加的属性把下一卡的主体裁没了，**而且裁得很干净**：
   屏上不是缺一块，是看起来本来就没有。

---

## 五 判据自己是缺陷，本批四次

延续上一批那条教训（**前提判据要钉契约的事实，NEVER 钉实现的事实**），本批又抓到四次：

1. **探针拿当前项和自己比**——`tabColor` 取 `tabs[0]`，而 `/plaza` 恰好排第一、
   恰好是当前页。那条「当前项与其余项不同色」**本来永远绿**。
2. **逐字比浮点**——断言头 `== 40`，而浏览器算的是 `39.999996185302734`。
3. **逐字比 CSS 关键字**——断言 `inline-flex`，而 flex 容器的子项会被算成 `flex`。
4. **判据射程无限**——`test_analysis_view_styled` 扫到文件尾，
   把下一批追加的蓝本几何圈了进来。
   > 一条射程无限的判据，会在下一个人往文件尾追加任何东西时红——
   > 而红的原因与它自己守的那件事无关。

外加一条**不算判据错、但同一形状**的：判据按行首 `/*` 剥 CSS 注释，
而块注释横跨多行且续行不以 `*` 起头——**本仓第九次**撞上「判据扫到解释性注释」。

---

## 六 不许碰的那条线，一个字没碰

- **6 个入口 `href` 逐字照旧**（判据量的是 DOM 里真实的 pathname 列表）；
- `aria-current` 照旧；
- 窄屏下文字标签**只是被 CSS 藏了**，仍在 DOM 里——读屏读到的仍是中文屏名；
- `.app-shell__nav-link` 这个既有判据认的钩子**留着**——
  换掉它等于把「6 个入口一个都不多」变成空转；
- `ENTRY-05` 的判据一条都没倒。

---

## 七 与蓝本的三处差异（各有理由，都写在 trace 里）

| 差异 | 理由 |
|---|---|
| **不引外链 Google Fonts（Manrope）** | CI 不联网，且那是第三方请求。字号字重照抄（14px/700），字形走本仓既有档；本仓中文字更宽，所以条比蓝本宽 |
| 图标形状自己挑 | 蓝本那四个是 Home/Convert/Pricing/About，与本仓六屏不是一回事。尺寸描边照抄（18×18 / 2.5） |
| 品牌字与三个控件进了条里 | 蓝本只有四个 tab；你要的是「做成一个横栏」 |

**本仓补的两条**（蓝本没有）：`prefers-reduced-motion` 全停（停动不停位置）·
亮底那一套配色与吉祥物描边。

---

## 八 收工纪律的落地检查

- **顺序**：先写六张 trace 与台账 → 再跑五条门 → 最后只改本报告的数字；
  门跑完之后**没有再动任何被判据读的文件**；
- 改配色与占位之后**重拍了六张截图**——图必须与现状一致；
- **每张卡的 `started` 与终态成对**；
- pytest 的红**逐条点名归属**（§二），NEVER 按族小结；
- **本批零真实网络**（`DEC-057` 的额度一发没动，仍剩 12）。
