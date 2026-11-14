# GAUGE-15 · 逐屏组件声明从 7 屏铺到全部 23 屏

**结论**：`23 屏 / 134 项声明，0 处违规`。铺的过程中抓到**一屏真的零样式**——
`/clusters/[id]`（`AnalysisView` 全组件零 `className`），已开单等 owner。

装载：卡 `GAUGE-15` · `assets/screen_composition.json` ·
`tools/check_screen_composition.mjs` · `harness/fe_smoke.py#SAMPLE_IDS`

---

## 1 改前：15 屏只有禁止性判据守着

`GAUGE-12` 建这份正向声明时只铺了 7 屏（那一批动过的）。其余 15 屏——
账户、账单、收藏、语言地区、Gate①、Job、报告、导出、质量卡、vibe_pack、
项目总览、主题详情、工作台、外链、演示串屏——**一屏都没有正向声明**。

禁止性判据（NEVER 空转 / NEVER 空态冒充 / NEVER 硬编码）挡得住做错，
**挡不住没做**。广场屏当初四条判据全绿而它是个零 `className` 的 `ul/li`，
就是这么过去的。

## 2 声明不是猜的：先看屏，再写

给这 16 屏写声明之前，用 playwright 逐屏落了一遍实况：
渲染出来的 `data-*`、`data-testid`、以及**真有样式**的类名
（逐条与裸元素的 19 项计算值比）。

选进声明的是**那一屏之所以是那一屏**的东西，不是全量抄一遍：

- 账户：身份 / 档案 / 组织关系三格 + 账单入口；
- 账单：`billing_enabled: false` 与「没查过」各自成格；
- Job：状态 / 已到达数 / 步骤表；
- 报告：Block 树 + 四个同族屏的入口（`NAV-05` 接的）。

**诚实态也进声明**（收藏 / 质量卡 / vibe_pack / 工作台 / 外链五屏）：
一行没有样式的「接口未提供」与「这一屏忘了做」，在屏上长得一模一样。

## 3 铺的过程抓到的那一屏

`/clusters/[id]`（`NAV-02` 建的热点分析屏）是**唯一一屏** `styled` 量出来是空的：
它装的 `AnalysisView` 全文件 `className` 出现 **0 次**。

那时只有三条路：

| 做法 | 后果 |
|---|---|
| 随手填一个别处的类名 | 报告变绿，**而那一屏没有变好**——正是这把尺子要治的病本身 |
| 不给它写声明 | 它从这把尺子上**消失**，而消失与「查过了没问题」长得一样 |
| **写空 + 指一张开着的单** | 报告上是显式的一行「这一屏没有样式，单在这儿」 |

选第三条。`AnalysisView.tsx` 是 v0.4 已 verified 的件，`DEC-021` 要求停下报 owner
——**没自行动手**，单据 `docs/blocked/ANALYSIS-VIEW-HAS-NO-CLASSNAMES.md`
（含改法：6 行类名 + 一段 CSS，一个既有判据都不用改）。

配套判据 `test_a_screen_without_styling_must_name_an_open_sheet`：
写空的屏**逐条**要指出一张真实存在、且还开着的单，且**只许有一屏**。
没有这一条，`styled_none_because` 就成了一句可以随便写的话——
而那正是 `exempt` 那条纪律防的东西。

## 4 新增两条判据

**① 屏数与磁盘对齐（本卡的核心）**

```python
assert {声明里的 route} == set(app_routes())
```

判**等值**：新增一屏没声明就红，删掉一屏而声明还留着也红。
`NEVER 靠人记`——靠人记的话，下一张新屏又会是没人量的那一张。

**② 「任一屏」的阴性对照**

既有那条只把广场的卡片换成裸元素。铺满 23 屏之后，「任一屏」这三个字才有分量：
**只在一屏上验过的尺子，证明不了它在另外 22 屏上也睁着眼**。
新那条挑的是本批新铺进来的 `/settings/locale`，断言尺子报红**并点名
是哪一屏缺哪一项**（`route` + `subject` 都要对上）。

另加一条 `test_every_declared_url_matches_its_route`：动态段填的是真样例 id
且填在对的位置——填错位置的话探针会去看另一屏，那时报出来的红指向本屏，
而屏本身是好的（`fe_smoke.py` 文件头警告过的「探针给错地址」）。

## 5 断点：声明了一个 0 高的空壳

第一版给 `/jobs/[id]` 声明了 `[data-job-connection]`，尺子当场报
`zero_size … 428×0`。

那是**断线通知的容器**——连着的时候它就是个 0 高的空壳。声明它等于要求
屏上恒有一条断线提示。**尺子是对的**：`F-09` 那个占 0 像素的争议记号是同一形状。
改成声明真正看得见的三格，并把「为什么不声明它」写进那一屏的 `why`。

## 6 门

```
node tools/check_screen_composition.mjs        23 屏 / 134 项声明，0 处违规
pytest tests/v041/test_screen_composition.py   13 passed（含两条阴性对照）
pytest tests/v041/ -q                          2915 passed
ruff check .                                   All checks passed
```
