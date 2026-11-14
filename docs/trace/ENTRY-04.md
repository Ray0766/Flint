# ENTRY-04 · 广场多选卡片建组合（`DEC-049`）——**项目族的活入口**

**结论**：广场加多选态与「用选中的卡建组合」入口；`/combo` 认多簇。
真浏览器整条走通：勾 → 计数 → **不跳屏** → 切区**选中态还在** → 进 `/combo`。
`verify_cmd` 20 条全绿；`ruff` / `tsc 0` / `vitest 857` / 邻近三把广场尺子 44 条全绿。

装载：`docs/steward/tasks-v041-b9.json#ENTRY-04` · `DECISIONS-v04.md#DEC-043 #DEC-049` ·
`docs/blocked/MAIN-CHAIN-HAS-NO-LIVE-ENTRANCE.md` · `web/components/plaza/PlazaCards.tsx` ·
`web/app/plaza/page.tsx` · `web/app/combo/page.tsx` ·
`web/components/views/ComboEntryView.tsx` · `web/components/chain/chainClient.ts`
（实测装载 ≈ 29k tokens，预算 40k）

---

## 1 先说清一句：**广场选的是热点卡，组合要的是证据卡**

`POST /projects/combo` 的 `card_ids` 是 **`evidence_cards`** 里的 id，
而广场上一张卡是一个**热点簇**——一个热点底下可能有好几张证据卡。

所以从广场带过去的参数叫 **`?clusters=`**，不叫 `card_ids`（卡面 acceptance① 的措辞）。
叫成 `card_ids` 的话，下一个人会直接把它转发给端点，
而那些 id 在 `evidence_cards` 里**一条都查不到**——请求会失败，
而失败信息说的是「这些卡不存在」，读的人无从知道真正的原因是
**「这里传的根本不是那种 id」**。判据 `test_the_parameter_is_named_clusters_because_that_is_what_it_is`
钉住这一条。

同一个理由：**`2~5` 不在广场判**。它说的是证据卡张数，
在广场判一次的话，用户选了 6 个热点会被拦下，
而那 6 个热点底下可能一共只有 3 张证据卡。
真正判它的是 `/combo` 那一屏（`comboCountValid`）与服务端。

## 2 顺带让一句一直做不到的话成立了

`ComboEntryView` 文件头写着「复选证据卡（2~5，**允许跨簇**）」。
而 `/combo` 那一屏一次只拿得到**一个**簇的卡（`?cluster=` 单值）——
**「跨簇」是一句没有落点的话**。

本卡让 `/combo` 接 `?clusters=a,b,c` 并逐簇取卡拼起来之后，那句话第一次成立。
老路 `?cluster=` **原样留着**：它是 `NAV-05` 接的九条边之一，换掉会把那条边弄断。

## 3 多选是**第三层**，`DEC-042` 那两层一个字没动

| 层 | 是什么 | 点它会怎样 |
|---|---|---|
| 卡片主体 | 导航 | 进这个热点的分析界面 |
| 三个动作按钮 | 动作 | 收藏 / 入台 / 分享 |
| **选择控件**（本卡加的） | 选中态 | 只把这张卡放进组合，**屏不跳走** |

**两半都要**：`stopPropagation` 拦 click，而 `<li>` 上那句
`e.target !== e.currentTarget` 拦 keydown——**`stopPropagation` 拦不住 keydown**
（第 8 批 `NAV-02` 栽过一次）。少了任何一半，勾一下就会连带跳去分析界面。

真浏览器实测：勾第一张、第二张，**URL 都没变**。

## 4 真浏览器抓到的那一处——源码层判不出

第一版把计数条放在**「有卡」那一支**里。于是：

> 切到一个没有卡的区（`empty` / `out_of_scope`）时，**整条计数条消失**，
> 而用户的选中态**还在**——屏上说「没有」，手里其实握着两张。

那正是 acceptance⑤ 要防的「**悄悄**」：不是清空了，是**看不见了**，
而看不见与清空了**在用户那里是同一件事**。

修法：把计数条**提到三态分支之上**。判据也跟着加了一条位置断言
（`code.index(combo-bar) < code.index(outOfScope)`）——
这条判据的存在本身就是那次实测的产物。

（这一处是探针先炸出来的：`wait_for_selector` 找得到、下一句 `eval_on_selector`
就找不到了——因为那一刻它正落在「没有卡」的那一支里。）

## 5 选中态跨区不清空

`picked` 住在**屏**上，不在取数结果里，所以重新取数不会带走它；
取数那个 effect 里**没有任何清空动作**（判据逐字扫）。

理由写在代码里：跨区挑热点凑一个假设**是正常用法**（组合本来就允许跨簇）。
一换区就清空的话，用户每次回来都要重挑一遍，而屏上不会有任何解释。

真浏览器实测：选 2 张 → 切区到 `unassigned` → **计数仍是 2**。

## 6 改前 / 改后 / 为什么非改不可

| 文件 | 改前 | 改后 | 为什么 |
|---|---|---|---|
| `web/components/plaza/PlazaCards.tsx` | 无多选 | 加选择控件 + 计数条 + 建组合按钮；**三个属性全可选** | 可选是为了 `DemoFlow` 那个既有调用点一个字都不用改（判据 `test_the_selection_layer_is_optional_so_existing_callers_are_untouched`） |
| `web/app/plaza/page.tsx` | 无选中态 | `picked` 状态 + 入口跳 `/combo?clusters=` | 路由写成**字面量**：走帮手的话可达性尺子（`NAV-01`）看不见这条边 |
| `web/app/combo/page.tsx` | 只认 `?cluster=` 单簇 | 认 `?clusters=` 多簇，逐簇取卡拼起来；**老路留着** | 见 §2。某一簇取失败退成空表，**NEVER 编几张卡出来**（既有口径） |
| `web/messages/{zh,en}.json` | — | 各 +4 条 | 顶栏与广场是每天都看得到的地方，硬编中文等于让英文用户永远看见它 |

**三个动作按钮、卡片主体导航、`ComboEntryView`、`submitCombo` 一个字都没动。**

## 7 三次红都是判据文件自己的

值得记下来，因为形状一样：

1. `comboCountValid` 那条——我在注释里**解释「为什么不在广场判」时点了它的名**，
   而尺子读了注释。修法：先剥三种注释再扫（`SHELL-01` 撞过同一形状，这是第二次）。
2. 反斜杠 n 那个字面量在被改写脚本经手时被当成**真的换行**插了进来，
   判据文件连炸三次语法。最后改用 `chr(10)` 常量并把理由写在旁边。
3. 计数条位置那一条——**不是判据的错**，是真缺陷（§4）。

## 8 真浏览器实拍

```
bar_before          count=0  build_disabled=True   hint=1
after_one           count=1  build_disabled=True   url_changed=False   ← 勾了不跳屏
after_two           count=2  build_disabled=False  url_changed=False
after_region_switch count=2  region=unassigned                          ← 切区没清空
after_build         url=/combo?clusters=c-20260704-000,c-20260704-001
                    屏上：关联假设建项 | 选 2~5 张证据…
console_errors      []
```

图：`.ui-probe/entry04-plaza.png` · `.ui-probe/entry04-combo.png`

## 9 自审（`self_review=true`）

**① 判据覆盖 acceptance**：①多选态与入口（+ 真浏览器）；②多选 NEVER 干扰单击
（**两者各有判据**：主体导航那条 + `stopPropagation` 那条 + 键盘那条 + 三按钮未动那条）；
③空假设归服务端（`outcome.message` 原样带出、前端零拒绝话）；
④进 `/combo`（真浏览器走到）；⑤选中态不清空（源码 + 真浏览器 + 位置断言）。

**先红后绿**：判据先写，实现前 20 条全红。

**② 无冻结件偏离**：本卡不碰后端，四件一字未动。
**③ 无禁用词**：0 命中（另有一条判据扫新件里的硬编中文）。
**④ 复用断言在位**：`ComboEntryView` / `submitCombo` / `HotspotCardActions` /
`comboCountValid` 全部复用，一个字没改。
**⑤ 装载未超预算**：≈29k / 40k。

## 10 门

```
pytest tests/v041/test_plaza_multiselect_combo.py -q   20 passed
ruff check . --no-cache                                All checks passed!
npx tsc --noEmit                                       0
npm test -- --run                                      85 档 857 passed
邻近三把广场尺子（plaza_states / plaza_region_query / cn_only_scope）   44 passed
```

## 11 留给下游

1. **`ENTRY-05`（孤岛清零）**：这条入口通了之后，项目族六屏应当不再是孤岛——
   `docs/blocked/MAIN-CHAIN-HAS-NO-LIVE-ENTRANCE.md` 的**前一半**（广场没有多选建组合）
   本卡解决了；那张单里的**另一半**（`POST /workbenches` 未挂）已由
   `PERSIST-01` 的 trace 核实为**不确**（端点早就装配了），
   真正欠的是被阻的 `PERSIST-02` 那三张表。
2. **上限**：广场不判 `2~5`（§1）。如果 owner 想在广场就拦住「选太多」，
   那是一条新口径——**它要先回答「按热点数还是按证据卡数拦」**。
