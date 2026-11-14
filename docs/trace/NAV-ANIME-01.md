# NAV-ANIME-01 · trace

**卡**：①顶栏——照蓝本做成顶部居中的药丸浮动条（含跟随发光块，两主题各一套）。
**结果**：verified · 1 cycle · 判据 17 条全绿（全部正向 + 真浏览器实测）。

## 照蓝本抄了什么（逐条对着 `Anime Navbar.dc.html`）

| 蓝本 | 本仓 |
|---|---|
| `gap: 12px` · `padding: 8px` · `border-radius: 9999px` | 逐字 |
| `backdrop-filter: blur(16px)` · 1px 描边 · `0 8px 32px` 投影 | 逐字（暗底） |
| tab `padding: 12px 24px` · `font-size: 14px` · `font-weight: 700` | 逐字 |
| 发光块四层模糊 `blur(6/14/26/40)` + 一层扫光 | 逐字 |
| `navIn` / `glowPulse` / `shine` 三个 keyframes | 逐字 |
| `measure()`：量每个 `a[data-tab]` 的 `offsetLeft`/`offsetWidth` | 逐字 |
| `isMobile`（<768 收成图标） | 逐字 |

## 没照抄的三处，各有理由

**一、字体。** 蓝本引外链 `fonts.googleapis.com`（Manrope）。
**NEVER 引**：CI 不联网，且那是第三方请求。
字号与字重照抄（14px / 700），字形走本仓既有 `--font-body`。
**差异**：Manrope 是几何无衬线、字腔较大；本仓中文屏走 Inter + Noto Sans SC，
同字号下视觉重心略低、中文字宽更大——所以本仓的条比蓝本宽（实测 1224px）。
有一条判据扫全仓禁止任何 `fonts.googleapis.com`。

**二、图标。** 蓝本那四个是 Home/Convert/Pricing/About，与本仓六屏不是一回事。
尺寸与描边照抄（18×18 / `stroke-width: 2.5` / `currentColor`），形状按各屏自己的意思挑。

**三、品牌字与三个控件进了条里。** 蓝本只有四个 tab。
owner 要「做成一个横栏」，而判据量的是 6 导航 + 品牌 + 地区/语言 + 主题
**全部 `offsetTop` 相等**——实测全是 `8`。

## 实测（playwright 真浏览器打 `:3000`）

```
position          fixed
border-radius     9999px
backdrop-filter   blur(16px)
居中              左 348px / 右 348px（差 0）
一行              offsetTop 全部 = 8
发光块            left 127 / width 104  ==  当前项 offsetLeft 127 / offsetWidth 104
切换后            /favorites 上仍然逐字相等，且位置变了
慢字体（1.2s）    仍然逐字相等
亮底              rgba(255,255,255,0.72) · 深色字 · 0 6px 20px rgba(27,42,46,0.12)
暗底              rgba(0,0,0,0.5)        · 白字   · 0 8px 32px rgba(0,0,0,0.4)
390               文字 display:none、图标显示；整页零横向溢出
```

## 四处坑

**一、`backdrop-filter` 被 CSS 管线吃掉了。**
源码里 `backdrop-filter` 与 `-webkit-backdrop-filter` 两条并排写，
而 lightningcss **只保留了 `-webkit-` 那一条**——
`getComputedStyle().backdropFilter` 读的是无前缀的，于是判据量到 `none`，
**而屏上其实是糊的**。改成只写无前缀那一条，前缀交给管线按 browserslist 补。

> 这一处正是「正向判据」的价值：一条「NEVER 没有毛玻璃」的禁止性判据
> 在这里量到 `none` 也不会红。

**二、居中不能用 `transform: translateX(-50%)`。**
它会与 `navIn` 的 `translateY` 打架——动画那一条整条覆盖它，
条在入场时会飞到左边。改用 `inset-inline: 0` + `margin-inline: auto` + `fit-content`。

**三、「一行」要量到孙子那一层。**
条内直接子项全部 `offsetTop = 8` 之后，判据仍红——
控件**内部**那几个（品牌字 25px 显示体）把自己顶到 `offsetTop: -15`。
屏上看着像一行，量出来不是。给 `.anime-nav__controls > *` 统一 40px 高度。

**四、我的探针拿当前项和自己比。**
`tabColor` 取的是 `tabs[0]`，而 `/plaza` 恰好排第一、恰好是当前页——
于是「当前项与其余项不同色」那条**永远绿**。
改成取第一个 `data-active !== 'true'` 的。

> 又一次：**判据自己是缺陷**。这一批已经是第二回（上一批三回）。

## 既有导航语义一条没改

6 个 `href` 逐字照旧（判据量的是 DOM 里真实的 `pathname` 列表），
`aria-current` 照旧，文字标签在窄屏下**只是被 CSS 藏了**（仍在 DOM 里）——
读屏软件读到的仍是中文屏名，可达性一条没退。
