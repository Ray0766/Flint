# NAV-04 · 顶栏只有两项

**结论**：孤岛 14 → **9**。顶栏 2 项 → 6 项，账单从账户屏进。

装载：卡 `NAV-04` · `web/components/shell/AppShell.tsx` · `assets/screen_graph.json`
· `web/app/account/page.tsx` · `web/app/billing/page.tsx`

---

## 1 改前：守错了一条纪律

`AppShell` 文件头一直写着「**NEVER 编造一排链接来把顶栏填满**」——那是对的，
点不开的入口把「还没做」伪装成「做完了」。

而实际发生的是**另一种毛病**：`/account` `/favorites` `/design` `/settings/locale`
四屏建好之后，谁也没回来加过入口，它们只能手敲 URL。

> 「入口点不开」与「屏没有入口」是两种毛病，修法相反，
> **而在报告上都显示为「顶栏很干净」**。

所以本卡的判据判**双向**：顶栏里的每一项都要点得开，
且每一个无参屏都要在顶栏里有位置——不进顶栏的必须逐条写明从哪进来。

## 2 改前 / 改后 / 为什么非改不可

**① `AppShell.tsx#NAV_ITEMS`** 2 项 → 6 项
（`/plaza` `/favorites` `/design` `/settings/locale` `/account` `/demo`）。

**② `AppShell.tsx` 账户位** — 删掉那个无条件的 `NotProvided`

改前顶栏挂着一句**写死的**「接口未提供」。`WIRE-01` 把 `GET /account` 挂上之后
**那句话就成了假的**：端点在，账户屏真的在取数（四态各自显示），
而顶栏没有任何办法知道那四态里是哪一态。**写死其中一态就是说谎。**

这不是「删掉一个诚实态」（诚实态一条都不许删，`FB-10` 的分界）——
删的是**说这句话的地方站错了**。账户屏自己四态齐全，那里说才说得准。
判据成对：顶栏不许再说（`test_the_top_bar_no_longer_hardcodes_one_of_the_four_states`），
屏那边必须还在说（`test_the_account_screen_still_tells_the_truth_about_its_four_states`）。

**③ `globals.css`** — `.app-shell__account` 一起退役。留着的 CSS 会让下一个人
以为那一格还在，而屏上早就没有了。

**④ `web/app/account/page.tsx`** — 加「查看额度与计费」入口（见 §3）。

**⑤ `assets/screen_graph.json`** — 入口 2 → 6；四屏的 `reached_by` 补上顶栏；
`/billing` 记上从账户屏进。

**⑥ `tools/check_reachability.py`** — 入口也与代码比对（见 §4）。

**一字未动**：`contracts/` · `flint/domain/` · `requirements.lock`
· `assets/heldout_questions.yaml`。无新增依赖，无迁移，后端一行没改。

## 3 判据当场逼出两个未决：`/billing` 与 `/combo`

双向判据一上来就报「这两个无参屏在顶栏上没有位置」。卡上只点了四项，
而这两屏也确实没有入口——**它们不是遗漏，是两个没人做过的决定**。

### `/billing` → **从账户屏进**（卡上原话「账户屏或顶栏（NAV-04 决定）」）

它是账户的一部分：免费额度、已用量、计费事件都挂在这个身份上。
放进顶栏会让一个二级页面与「热点广场」平级。

入口放在取数状态**外面**：账户端点回什么都不影响用户去看账单。
放在里面的话，账户读失败会把账单入口一起带走——**而那两件事之间没有任何关系**。

这一处**超出了卡上的 outputs**（`web/components/shell/`）。没有停下走单，
理由：卡自己写着「NAV-04 决定」，而只决定不接线会留下一座没有主人的孤岛。
改动是一个 `<a>` 加一条词条。

### `/combo` → **不进顶栏，照实留在孤岛名单里**

它要从广场带着选中的卡进来。没带 cluster id 进去是一屏「你怎么走到这儿的」
（那一屏自己说清了该怎么来，且一张卡都不编——`CHAIN-04` 的判据盯着）。

而「多选卡片建组合」是广场上**还没有的能力**——那是一个功能，不是一条链接。
硬塞一个顶栏入口的话，用户点进去落在一屏说明文字。

> **NEVER 用一个点得到但没用的入口把孤岛名单做小。**

判据把这条决定钉住：`/combo` 说自己没有入口，那么尺子**必须**还把它算成孤岛——
两句话有一句是假的就红。

## 4 断点：入口是遍历的起点，而它一直没人比对

顶栏的链接写成 `href={item.href}`——**变量**，边扫描器看不见。
于是图里的 `entries` 可以写任何东西：多写一个，遍历就会从一个屏上根本没有的地方出发，
一批孤岛被算成可达。**那正是这把尺子要治的那句假话，只是换了个入口。**

**改后**：`nav_items()` 从 `AppShell.tsx` 解析 `NAV_ITEMS`，与图里的 `entries`
**两个方向**比对。多一个报「图里写着是入口，顶栏里没有」，
少一个报「顶栏里有，图里没算成入口」。

## 5 `/demo` 的去留：留下，理由与撤它的条件都写进代码

它是演示串屏、不是产品屏（屏对照表 §四 已登记「蓝本与 v2 屏总表都没有」）。

**留下**，因为它今天是唯一能看到整条链路怎么走的地方——主链路中间几屏
（工作台、主题、项目）还是孤岛，`NAV-05` 之前只有这个串屏能把一次完整的走法演给人看。

**撤它的条件也写下来了**（`AppShell.tsx` 文件头 + 图上 `entries`）：
`NAV-05` 把主链路真正走通、且那条路上每一屏都从产品入口点得到之后，
`/demo` 就该从顶栏撤下（撤入口，屏留着）。到那时它会成为与产品面并列的第二条路，
而两条路会各自漂移。

理由写在**代码里**而不只在 trace：下一个改顶栏的人不会去翻 trace，
于是要么误删要么再判一次。没有条件的「暂时留着」等于永远留着。

## 6 390px：六项折两行，不溢出

`.app-shell__nav` 本来就有 `flex-wrap: wrap`，六项在 390px 下折成两行。
探针实测（`.ui-probe/nav04-shell-390.png`，本卡看过）：
`documentElement.scrollWidth = 390`、顶栏自身不横向滚、每一项右边缘都 ≤ 390.5。

折行是对的，横向滚出去不是：**顶栏滚出去的那几项，用户根本不知道它们在**。
`FIX-05/06` 的既有判据一条没倒。

## 7 门

```
pytest tests/v041/test_shell_nav.py -q     13 passed（含 390px 真浏览器三条）
pytest tests/v041/ -q                      2869 passed
vitest run                                 84 files · 850 passed
tsc --noEmit                               0
ruff check .                               All checks passed
fe_smoke（23 屏 × 明暗）                    只剩 /deliverables/[id] 那 3 条既有红
check_reachability                         EXIT=1 · 可达 12 · 孤岛 9 · 走不通 1 · 豁免 1
```

一条既有判据改过（`shell.test.tsx` 的账户位那条），改因写在它自己的注释里：
**它红的是前提过期，不是事情坏了**。不变的那一半（NEVER 印 `X-User-Id`）原样留着。

落盘产物重生成：对账表（21 条不变）· gauge_map（b2/v04）· fe_smoke.json。
