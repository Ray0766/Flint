# WIDTH-01 · trace

**卡**：③铺满——长文行长 token 被当成了应用容器宽度。
**结果**：verified · 1 cycle · 判据 11 条全绿（全部正向 + 真浏览器实测）。

## 根因（与 steward 实查一致）

`--measure-longform: 34em`（≈476px）是**排版事实**（长文一行最多多少字才好读），
定义在 `_ds/.../tokens/typography.css:15`。
而 `globals.css:141` 与 `:207` 拿它当 `.app-shell__inner` / `.app-shell__body`
的 `max-inline-size`——那是**布局决定**（应用外壳有多宽）。

owner 三条意见里前两条同根：9 个顶栏控件在 476px 里放不下（挤成三行），
卡片网格在 476px 里排不出第二列（不铺满）。

**`--measure-longform` 一个字没改**——改的是「谁在用它」。

## 改了什么

| 落点 | 改动 |
|---|---|
| `_ds/.../tokens/spacing.css` | 新增 `--width-app: 1760px` 与 `--width-app-inset: min(--width-app, 100vw - 2*sp5)` |
| `globals.css` `.app-shell__inner` / `.app-shell__body` | `--measure-longform` → `--width-app-inset` |
| `globals.css` `.screen:has(.plaza/.design)` | **负外边距 hack 退役**，只留 `display: block` |
| `globals.css` 新增 `.screen--longform` | 长文屏另一档，仍走 `--measure-longform` |
| `Screen.tsx` | 加 `longform` 入参——**屏自己声明**，NEVER 在 CSS 里按屏名列举 |
| `deliverables/[id]/page.tsx` | 报告正文标成长文 |

### 1760 这个数是量出来的

第一版取 1440，实测 1920 视口下只有 **0.75**（阈值 0.9）。
1760 → 1920 下 **1760/1920 = 0.92**；1440 下由 `100vw - 2*sp5` 接管，**1392/1440 = 0.97**。

仍留一个上限而不是纯 `100vw`：超宽屏上一行排 8 张卡读起来是一条横带，
而卡片网格的可读上限就在这一带。

### 那个负外边距 hack 为什么必须退役

`PLAZA-01` 当初用它**从 34em 里挣出来**。外壳放宽之后再叠一层，
会真的撑出横向滚动条。

**没有把整条规则删掉**：`.screen` 默认是 flex 列，而广场与设计台要块级流。
删掉之后那两屏会退回 flex，**症状是「卡片挤成一列」——与它改前几乎一样**，
查起来会绕一大圈。

## 实测（playwright 真浏览器打 `:3000`，两屏 × 三视口）

```
网格屏 1920: 主体 1760px = 0.92 视口 · scrollW 1920（零溢出）
网格屏 1440: 主体 1392px = 0.97 视口 · scrollW 1440
网格屏  390: 主体  342px = 0.88 视口 · scrollW  390

长文屏 1920: 主体 1760px · **长文正文 476px**
长文屏 1440: 主体 1392px · **长文正文 476px**
长文屏  390: 主体  342px · 长文正文 294px（按视口收窄）
```

**两个方向各断言一次**：网格屏铺满、长文正文仍是 34em。
只断言前者的话，「铺满」会把正文也拉成 1760px 一行——**把一个错换成另一个错**。

## 判据全部正向（本批 `positive_criteria`）

每条都是「MUST 长成什么样」+ 实测数值，没有一条是禁止性的。
由来：`UI-01~11` 四条禁止性判据全绿而那一屏是 4072px 的裸 `<ul><li>`——
**禁止性判据挡得住做错，挡不住没做**。

阴性对照（acceptance④）判的是**源码**：外壳那两条规则里 NEVER 再出现
`--measure-longform`。它比实测判据先一步说清「是哪一处改回去了」——
「主体只有 476px」这句话对排障没有用，「外壳又在用长文行长」才有。

## 两处坑

**一、判据又扫到我自己的解释性注释。**
`test_the_shell_no_longer_uses_the_typography_token` 第一版按行首 `/*` 剥注释，
而 CSS 的块注释横跨多行且续行不以 `*` 起头——那段解释里正写着旧 token 的名字。
改成整段正则剥 `/* ... */`。**本仓这一坑第九次**，所以这次把怎么剥写进了判据。

**二、`test_cn03_preflight` 红过一次，与本卡无关。**
dev server 少了 `NEXT_PUBLIC_FLINT_API` 与 `NEXT_PUBLIC_FLINT_USER_ID`
（广场是**客户端取数**，用的是带 `NEXT_PUBLIC_` 前缀的那一份；
而报告屏是服务器组件，读的是不带前缀的那一份——`start-demo.ps1:191~204` 三个都给）。
按起栈脚本补齐后自愈。**我只改了 CSS 与一个组件入参，碰不到取数**。
