# NAV-03 · 「入台」按成功之后要把人带过去

**结论**：前端接完了。**那条路今天仍然走不通**，而这两句话现在能分开说了。

装载：卡 `NAV-03` · `web/components/plaza/cardActions.ts` ·
`web/components/hotspot-card-actions/HotspotCardActions.tsx` ·
`web/app/workbenches/[id]/page.tsx` · `DECISIONS-v04.md#DEC-042`

---

## 1 改前：三个按钮都在真调后端，按完都停在原地

| 动作 | 端点 | 实测答复 |
|---|---|---|
| 收藏 | `POST /favorites` | `{"status":"not_provided",…}` |
| 分享 | `POST /shares` | `422 {"allowed":[…]}` |
| 入台 | `POST /workbenches` | **框架的 404**（没有 `code`）= 路由未挂 |

用户按完不知道有没有成事。`DEC-042` ②：**「入台」才是进图谱工作台的那条路**。

## 2 改前 / 改后 / 为什么非改不可

**① `web/components/plaza/cardActions.ts`** — 新增 `workbenchTarget(outcome)`

只认 `graph_id` 一个名字（冻结件里的名字，也是既有路由
`POST /workbenches/{graph_id}/edges` 用的那个）。**认第二个别名的话，
服务端哪天改口，前端会安静地跳到另一处，而两边都以为自己对。**
拿不到就回 `null`，调用方据此留在原地。

**② `web/components/plaza/PlazaCards.tsx`** — `run()` 回调里三道闸

```
收藏/分享 → 不导航（它们是动作不是去处）
不是 ok   → 不导航（阴性对照盯着这条）
没有 target → 不导航，且说清楚
```

非改不可：这是唯一拿得到答复的地方。

**③ `web/components/hotspot-card-actions/HotspotCardActions.tsx`** — 加 `note` 槽

「成了、却不知道去哪一个」与「失败」是**两件事**：前者用户的东西已经存下了。
塞进 `outcome` 会让「成了」变成「没成」——那是一句假话。所以结果与补充**同时**出现。

**④ `assets/screen_graph.json`** — 这条边带 `blocked`（见 §3）。

**⑤ `tools/check_reachability.py`** — 加第三格（见 §3）。

**⑥ `tools/check_fe_be_parity.py`** — `_NAV`（见 §4）。

**⑦ `harness/fe_smoke.py` + `tests/v041/test_fe_smoke.py`** — 登记 `/clusters/[id]`
的样例 id（`NAV-02` 的收尾，见 §5）。

**一字未动**：`contracts/` · `flint/domain/` · `requirements.lock`
· `assets/heldout_questions.yaml`。无新增依赖，无迁移，后端一行没改。

## 3 断点①：接完之后，尺子差点替我说一句假话

接上导航之后 `check_reachability` 立刻从「孤岛 15」变成「走得到 8 屏」——
**而 `/workbenches/[id]` 今天谁也点不到**：`POST /workbenches` 没挂，
入台永远拿不到 `ok`。

那句「走得到 8 屏」与 steward 上一条「连上了」是**同一种错**：
量的是「代码里有没有这条路」，说的却是「用户点不点得到」。

**改后**：边上可以写 `blocked`，尺子把这种屏放进**第三格**，遍历不走这条边。

| 状态 | 合并进去会说出的假话 |
|---|---|
| 算成可达 | 「这一屏点得到」——屏上点不到 |
| 算成孤岛 | 掩盖「前端已经接完了」，下一个人会再接一遍 |

三格各自成一态，与 `DEC-032` 的 honest-state 纪律同口径。
**尺子照样红**——走不通就是走不通，第三格不是一张免罪符。
判据另要求每条 `blocked` 写清**为什么**，NEVER 只标一个 blocked 了事。

今天：走得到 7 · 孤岛 14 · 走不通 1 · 豁免 1 = 23。

## 4 断点②：对账表把两次跳转当成了 API 调用

`check_fe_be_parity` 报出两条「前端要而后端没有」：`/clusters/{}` 与 `/workbenches/{}`。
**两条都是假的**——它们是 `NAV-02/03` 的跳转，不是请求。

根因是**判据的前提过期了**，而过期的判据看起来与回归一模一样：
那把尺子的文件头写着「导航不是调用」，可它只排 `href`——
因为在 `NAV-02` 之前，站内跳转确实只有 `href` 一种写法。

**改后**：加 `_NAV`，排掉 `router.push` / `location.assign` / `location.href =` 的参数。
**同一条规则的另外两种写法**，不是把判据放宽：排的是那一处的参数，
别处真有一次 `fetch` 打同一条路，照样数得到。`NAV-01` 的可达性尺子认的也是这三种。

对账表回到 **21 条**（与本卡开工前逐条相同），只有「前端路由 22 → 23」变了。

判据 `test_the_navigation_is_a_literal_the_rulers_can_see` 把这件事钉住：
**两把尺子要的东西正好相反**——一把要把它算成边，另一把 NEVER 把它算成调用。

## 5 顺带收尾：四份落盘产物跟着新屏重生成

`NAV-02` 新增一屏，四处**记录型**判据同时红。都不是回归：

| 产物 | 怎么处理 |
|---|---|
| `docs/前后端对账表-v041.md` | 重跑工具生成（21 条不变） |
| `assets/gauge_map*`（b2 / v04） | 重跑 `tools/gauge_map.py` |
| `.ui-probe/fe_smoke.json` | 重跑真栈冒烟（23 屏 × 明暗两主题） |
| `harness/fe_smoke.py#SAMPLE_IDS` | 登记 `/clusters/[id]` |

样例 id 用的是**库里真有证据卡**的簇（`c-20260629-088`，按卡数排第一）——
占位串会让证据概览恒空，而空与「这个热点没有证据卡」在截图上长得一模一样。
`fe_smoke.py` 文件头警告过的「探针给错地址」正是这一种。

取证看过（`.ui-probe/clusters-id-light-mobile.png`）：390px 无溢出、
控制台 0 error、七条证据卡真的画出来了。

## 6 断点③：中文写在行尾注释里，被判据当成了屏上的文案

`test_plaza_states` 的「零硬编中文」只剥**整行** `//` 注释，行尾的那半句剥不掉。

这与本仓栽过十二次的形状同类，修法也同一套：**给那句话一个位置**——
把说明移成整行注释，而不是把判据放宽。判据没错，是那句话站错了地方。
（真要剥行尾注释，就得先分辨 `"https://…"` 里的 `//`，那是把尺子变复杂去迁就一处措辞。）

## 7 门

```
pytest tests/v041/test_add_to_workbench_nav.py -q   13 passed
vitest run __tests__/app/nav03.test.tsx              8 passed
pytest tests/v041/test_reachability.py -q           15 passed（加了第三格那条）
pytest 上述 + parity/gauge/fe_smoke/live_probe        全绿
ruff check .                                         All checks passed
tsc --noEmit                                         0
check_reachability                                   EXIT=1 · 孤岛 14 · 走不通 1
```

孤岛 15 → **14**：`NAV-03` 拆下第一座。它进的是第三格，不是可达名单——
**前端接完了，而那条路今天走不通，两句话都要说。**
