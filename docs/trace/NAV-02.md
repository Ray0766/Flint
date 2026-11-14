# NAV-02 · 点卡片主体 → 这个热点的分析界面

**结论**：`AnalysisView` 终于有屏装它了。可达屏 6 → 7。

装载：卡 `NAV-02` · `web/views/analysis/AnalysisView.tsx` · `docs/blocked/HOTSPOT-03.md`
· `web/components/plaza/PlazaCards.tsx` · `web/components/plaza/HotspotCardStack.tsx`
· `web/components/hotspot-card-actions/HotspotCardActions.tsx` · `DECISIONS-v04.md#DEC-042`

---

## 1 改前：两头都建好了，中间没有线

| 件 | 状态 |
|---|---|
| `AnalysisView`（`HOTSPOT-03`） | 成品：四态齐全、只读、复用 `viewsClient`。**没有任何屏在用** |
| `GraphOpenAnalysis`（唯一引用它的） | 抽屉组件，**它自己也没有屏在用** |
| `PlazaCards.onSelectCluster` | 入参早就在，**广场屏没往里传** |

于是点卡片什么都不会发生，而这套分析界面从没在屏上出现过一次。

> **建好的东西点不到，与没建长得一模一样。**

## 2 改前 / 改后 / 为什么非改不可

### 新增

| 文件 | 是什么 |
|---|---|
| `web/app/clusters/[id]/page.tsx` | 承载屏。只做承载与接线，`NEVER 再写一遍分析视图` |
| `web/__tests__/app/nav02.test.tsx` | 11 条 vitest：网络层 spy / 四态 / 点击排除区 / 键盘 |
| `tests/v041/test_card_to_analysis.py` | 17 条：源码层 + 把 vitest 拉进全局门 + playwright 真点一遍 |

### 改既有

**① `web/app/plaza/page.tsx`**

- 改前：`<PlazaCards clusters=… region=… regions=… />`，`onSelectCluster` 空着。
- 改后：`onSelectCluster={(id) => window.location.assign(\`/clusters/${…}\`)}`。
- 非改不可：这是**唯一**的接线点。`PlazaCards` 早有入参，调用方不传就等于没接。

**② `web/components/plaza/PlazaCards.tsx`** — 网格项加 `role="link"` + `tabIndex` + `onKeyDown`

- 非改不可：这一下点击**现在真的会跳屏**了。改前点下去什么都不发生，
  所以「只有鼠标能用」不算缺陷；接上之后就算了——**键盘用户走到卡上会过不去**。

**③ `web/components/plaza/HotspotCardStack.tsx`** — deck 的 `onKeyDown` 加回车/空格

- 改前：方向键能翻，**没有一个键能「打开」**。同 ② 的理由。

**④ `web/messages/{zh,en}.json`** — 三个 `cluster.analysis.*` 键（两侧都翻）。

**⑤ `assets/screen_graph.json` / `tests/v041/test_reachability.py`** — 新屏与新边入图，
基线 22 屏/6 可达 → 23 屏/7 可达。**这是 `NAV-01` 那把尺子第一次被人回来改**——
改这一行的动作，就是「这条线真接上了」的签字。

### 一字未动

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
· `AnalysisView.tsx` 本体（v0.4 封版面）。无新增依赖，无迁移。

## 3 断点①：帮手函数会让可达性尺子瞎掉

一开始建了 `web/components/plaza/analysisRoute.ts` 收口路由，广场调
`window.location.assign(analysisRoute(id))`。

`NAV-01` 的尺子读的是**源码里的字面路径**，看到的是一个函数调用——
于是它会报「图里有这条边、源码里没有」。**那条红读起来像图写错了，
实际是代码把路藏起来了**，与昨天那个 `href` 正则截断造出的假发现是同一种误导。

**改后**：删掉帮手，路由写字面量。理由不止是迁就尺子——今天**只有一个**跳转点
（`PlazaCards` 的两处点击都走同一个 `onSelectCluster`），帮手只是多一层间接。
判据 `test_the_route_is_a_literal_so_the_reachability_ruler_can_see_it` 钉住这一条，
并把「看不见的后果是什么」写进 docstring。

## 4 断点②：`stopPropagation` 拦的是 click，keydown 照样冒上来

补键盘可达时差点造出一个新的「按一下屏没了」：在「收藏」上按回车 →
按钮的 keydown 冒到卡片 → 既收藏又跳走。`HotspotCardActions` 的点击排除区挂的是
`onClick`，对 keydown 无效。

**改后**：卡片的 `onKeyDown` 里 `if (e.target !== e.currentTarget) return`——
只有卡片本身被聚焦时才算。这是点击排除区的键盘形态，且它不依赖
「将来每个新按钮都记得挂一次」。判据逐字钉住这一句。

## 5 断点③：`[data-cluster-id]` 在广场上匹配到两处

同一张卡出现在**堆叠**（精选）与**网格**（全量）两处，两处都带 `data-cluster-id`。
第一版 vitest 用 `querySelector('[data-cluster-id="c-1"]')` 抓到的是堆叠那张——
它没有动作按钮、没有 `tabIndex`，于是两条用例红得莫名其妙。

**改后**：`gridItem()` / `stackCard()` 两个取法分开，**两处各判一遍**——
它们必须进同一屏。这不只是修测试：两个广场各去各的地方，正是这一批要治的病。

## 6 「进入即渲染、进入不触发」判了三层

| 层 | 判据 | 量的是什么 |
|---|---|---|
| 源码 | `test_the_screen_never_writes` | 屏里没有写请求的形状 |
| vitest | 网络层 spy 数方法 | **实际发出去的**全是 GET，且读请求真的发了 |
| 真浏览器 | playwright 监听 `request` | 打开这一屏，非 GET 请求 = `[]` |

三层缺一不可：源码干净可能是把写请求藏在别处；spy 绿可能是那条路没被走到；
而**只断言「零写请求」的话，一个什么都不 fetch 的空组件同样能绿**——那种绿是空转。
所以 spy 那条同时断言 `calls.length > 0`。

代价写在判据的 docstring 里：跑一次分析 = 用户**付一次钱**，
且同一个热点每次可能显示**不同的判定**，判定本身就不再可被引用。

## 7 判定归属：缺就是缺

- 屏从**自己的** URL 读 `?verdictJob=`——那才是「调用方给出」的形态。
- 没带 = 未判定，**一个 verdict 请求都不发**。
- **NEVER 拿 cluster_id 拼一个 job id 去试**：`Job` 无 cluster 字段、`jobs` 表也无
  `cluster_id`（`docs/blocked/HOTSPOT-03.md`）。猜错时用户看到的是**另一个热点的判定**。
- **广场跳转 NEVER 带上 verdictJob**：广场 URL 上那个 job 是调用方手上的一条判定，
  广场今天 154 张卡，它顶多是其中一张的。带过去等于替系统宣布这条对应关系。
  判据在源码层（截 `onSelectCluster` 那一段）与真浏览器层（落地 URL 不含 `verdictJob`）各判一次。

## 8 四态

`AnalysisView` 自己分，本屏不复刻。屏另加一态：**读 URL 参数之前先说「正在读」**——
直接把 `null` 传下去的话，会先闪一下「未判定」再改口，而那一闪是一句**假话**。
判据断言首帧不含未判定。

真浏览器实测（`.ui-probe/nav02-cluster-analysis.png`，本卡看过）：
标题「热点分析」+ 热点 id 贴纸 + 「这个热点还没有过 Gate① 判定」+ 证据概览一条。
`writes_after_open = []`，`console_errors = []`。

## 9 门

```
pytest tests/v041/test_card_to_analysis.py -q     17 passed（含 playwright 真点一遍）
pytest tests/v041/test_reachability.py -q         14 passed（基线已改成 23/7）
vitest run                                        83 files · 842 passed（新增 11）
tsc --noEmit                                      0
ruff check .                                      All checks passed
mypy --strict flint                               307 files, Success
check_screen_coverage / check_screen_composition  缺屏 0 / 0 处违规
check_reachability                                EXIT=1 · 孤岛 15（NAV-03~05 的清单）
```

孤岛数没变：`/clusters/[id]` 是**新建的可达屏**，不是从孤岛里救回来的一座。
`NAV-03~05` 才开始拆那 15 座。
