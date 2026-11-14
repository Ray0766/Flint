# JUDGE-TAB-01 · trace

**卡**：判定台五件之间的屏内互链带
**日期**：2026-08-12 ｜ **状态**：verified

## 一、改前实况

v4 把这五件做成**一屏五个 tab**（主题列表 / Gate① 判定 / 作业进度 / 受众选择 / vibe_pack）。
本仓这五件是**五条独立路由**，而它们**彼此之间一条互链都没有**——
只有项目总览那个枢纽屏各链一次。

`DEC-060` 第二条：29 条路由与 7 个导航入口一条不动，v4 的 5 tab
**只以互链带的形式吸收**。所以本卡加的是一条**屏内导航条**：
NEVER 新建 `/judge` 一类的合并屏、NEVER 碰 `NAV_ITEMS`。判据两条钉着这一点
（顶栏仍是 7 项 · `web/app/judge` 不存在 · 屏图里没有 `/judge`）。

## 二、五条 tab 指的都是既有路由，且**真去取过**

| tab | 路由 | 要哪个 id |
|---|---|---|
| 主题列表 | `/projects/{id}/topics` | project |
| Gate① 判定 | `/gate/{id}` | job |
| 作业进度 | `/jobs/{id}` | job |
| 受众选择 | `/projects/{id}/proposal` | project |
| vibe_pack | `/deliverables/{id}/pack` | deliverable |

判据**逐条真栈取一次**（拿库里真有的样例 id），五条都不是 404。
只判源码里那五个字符串的话，指向一条不存在的路由也会绿——而屏上那一条点下去是 404。

## 三、拿不到 id 的那几条：**列出来 + 说出在等什么**

三种 id 不是同一个。今天主题列表那一屏手上只有 `project`，
所以 Gate①/作业进度/vibe_pack 三条走**未就绪**那条路：

- **仍然列出来**（藏起来 = 用户不知道这一步存在）；
- **印出它在等什么**（灰着不说 = 他不知道要做什么才能走过去）；
- 两句「在等什么」互不相同（等作业 vs 等交付物是两件事）；
- **NEVER 拼一个 id 出来**（`DEC-012` 同一条纪律）——判据扫组件里有没有
  `del-` / `job-` / `proj-` 这类前缀拼接。

## 四、挂在哪

挂在**主题列表**那一屏（`current="topics"`）。
只建组件不挂的话，它与「没做」在屏上长得一模一样（`F-09` 记过的坑），
所以判据里有一条专门判「它真的挂上了」。

**出 outputs 一处**：卡面 outputs 只列了组件、两份词典与判据文件，
而**不挂就到不了屏上**。所以动了 `web/app/projects/[id]/topics/page.tsx`
（两行：import + 一处渲染），以及 `web/app/globals.css`（这条带的样式）。
两处都写进完成态报告。其余四屏还没挂——**下一批把它带到另外四件上**时，
组件不用改，只加 `current=` 那一个入参。

## 五、样式

颜色全部走 `_ds` token（裸色值 0，判据钉着）。当前那一条用
`--accent-highlight` 画一条下边线 + 正文色；未就绪那一条**弱一档而不灰掉**，
下面跟一行「在等什么」。

## self_review

① 判据 ↔ acceptance：五条指向 5 + 真栈逐条取 5 · `aria-current` 1 ·
   未就绪列出+说明 1 + 两句不同 1 + 不拼 id 1 · 不加路由 2 + 不动导航 1 ·
   真的挂上了 1 · 文案两份 1 · 裸色值 1 = **19 条**。
② 无冻结件偏离：`contracts/` 未读未改。
③ 无禁用词：命中 0。
④ 复用断言在位：`test_shell_nav.py` 既有判据零改动且全绿（7 项一个不多不少）。
⑤ 装载未超预算：约 9k tokens。

## 产出文件

```
web/components/judge-tabs/JudgeTabs.tsx        新建（五条 tab + 未就绪那条路）
web/app/projects/[id]/topics/page.tsx          挂上（出 outputs，见报告）
web/app/globals.css                            JUDGE-TAB-01 段（出 outputs，同上）
web/messages/zh.json · en.json                 8 条新 key（两份对称）
tests/v041/test_judge_tabs.py                  19 条判据
```
