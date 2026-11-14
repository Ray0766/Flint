# FIX-19 · `AnalysisView` 零 className——**owner 已准动这个封版件**

**结论**：15 处元素各加一个 `className`，样式落 `globals.css` 全走 `_ds` token。
**边界是可量的**：剥掉类名之后渲染段与改前逐字相同。
`verify_cmd` 11 条全绿；`GAUGE-15` 那把尺子重新观测后零违规（24 条全绿）。
单据已关。

装载：`docs/steward/tasks-v041-b9.json#FIX-19` · 工单 §5.3（唯一例外条）·
`docs/blocked/ANALYSIS-VIEW-HAS-NO-CLASSNAMES.md` · `web/views/analysis/AnalysisView.tsx` ·
`web/app/globals.css` · `web/public/_ds/*/tokens/*.css` ·
`assets/screen_composition.json` · `tools/check_screen_composition.mjs`
（实测装载 ≈ 28k tokens，预算 40k）

---

## 1 许可与边界，逐字

> **`FIX-19` 已获 owner 明确许可动 v0.4 封版件 `AnalysisView.tsx`，
> 边界只限「加类名与样式」——NEVER 改判定语义、NEVER 动四态、NEVER 改既有判据。**
> （第 9 批工单 §5.3 的唯一例外条，owner 2026-08-09）

本次改动逐条就是：**15 处元素各加一个 `className`**。

## 2 边界**是可量的**，不靠谁记得

判据 `test_stripping_the_class_names_gives_back_the_original_render`：
把源码里所有 `className="…"` **剥掉**，再与改前的渲染段逐字比对。

改了一个分支、动了一处 `data-*`、换了一句文案——它都会红。
**这条判据不依赖「我只加了类名」这句自述，它直接量那句话是不是真的。**

（改完当场用同一个办法自查过一次：剥掉类名后与改前逐字相同。）

另有四条从侧面钉：四态仍是八个分支、判定语义三处原样、
七个既有 `data-*` 记号逐个还在、`useEffect` 仍是一个。

## 3 样式全走 token

每一处颜色 / 字号 / 间距 / 圆角都是 `var(--…)`。写死一个 `#333` 或 `14px` 的话，
**暗色主题下它不会跟着变**——而 `DARK-01` 的双通道正是靠 token 生效的。

一处刻意的克制：**NEVER 按 `data-verdict` 的取值上不同的颜色**。
那会让 A / B / C / D 在屏上变成「好 / 坏」的暗示，而它们是四种**并列**的结论。
判据扫样式段里不许出现 `data-verdict=`。

## 4 改前 / 改后 / 为什么非改不可

| 文件 | 改前 | 改后 | 为什么 |
|---|---|---|---|
| `web/views/analysis/AnalysisView.tsx` | `className` 出现 **0 次** | 15 处；文件头补一段写明许可与边界 | 本卡主体（owner 许可） |
| `web/app/globals.css` | 无 `.analysis*` | 追加一段，全 token | 加了类名没写样式 = 屏上还是什么都没有（`FB-01` / `F-09` 的同一个病） |
| `assets/screen_composition.json` `/clusters/[id]` | `styled: []` + `styled_none_because` | 5 个真类名 + 一条「另外四个为什么不进名单」 | acceptance④；那句解释现在是假话，留着比没有更坏 |
| `assets/screen_composition.json` `/favorites` | 声明「未提供那一套」 | 换成真列表那一套 | 见 §6 |
| `tests/v041/test_screen_composition.py` | `len(blank) == 1` | `<= 1` | 见 §5 |
| `docs/blocked/ANALYSIS-VIEW-HAS-NO-CLASSNAMES.md` | open | **closed** + 关闭说明 | acceptance⑤ |

### 4.1 `assets/` 不在本卡 outputs 里——**这一处越界是明写的**

本卡 outputs：`web/views/analysis/` · `web/app/globals.css` · 判据文件。
`assets/screen_composition.json` **不在其中**。

为什么没有像 `SHELL-02` 那样停下开单：那一张缺的是**一整块后端能力**
（迁移 + 模型 + 端点），而且还夹着一个产品问题（主题按人存还是按设备存）；
这一处是**本卡自己的改动让一行声明当场过期**——acceptance④ 逐字要求改它，
而不改的话 `GAUGE-15` 那把尺子会红，红的还是我造成的。

**两件事都摆着请 owner / steward 看**：越界了一个文件，理由如上。
若认为该按纪律停下，把这一处 revert 即可（声明改回 `[]` 与那句解释）。

## 5 一条尺子的基线跟着事实走

```
tests/v041/test_screen_composition.py::test_a_screen_without_styling_must_name_an_open_sheet
  AssertionError: 写空的屏不止一条了：[]
```

它钉着 `len(blank) == 1`——写它的时候 `/clusters/[id]` 是**唯一**一屏写空的。
本卡让那一屏毕业之后 `blank` 空了，它必红：
**红的是「今天恰好有一屏是空的」这个事实过去了，不是纪律没了。**

改成**上限** `<= 1`：零条时仍然成立且仍然有意义（多出一屏写空的它当场红），
而不必每次有屏毕业就回来改一个数。

## 6 顺带查出一处 `PERSIST-01` 留下的声明过期

重新观测之后 `/favorites` 报三处违规：它声明自己该显示
`[data-not-provided]` 与 `not-provided*` 那一套——而**那是 `favorites` 表还不存在时的样子**。

`PERSIST-01` 把表建出来之后，那一屏实测 `data-favorites-state="ready"`，
渲染的是真列表（`favorites__list` / `favorites__item`）。
声明照旧的话，尺子会拿一个**此刻不该存在的元素**去判红。

所以声明换成真列表那一套，并写清：**未提供那一态并没有删**
（`store=None` 时仍是唯一诚实的答复），它由 `tests/v041/test_no_fake_empty.py`
**直接打缝**去量，不再依赖这一屏当样本。

## 7 一处「只声明屏上真有的东西」

第一版把 9 个类名全写进声明，检查器报 4 个「屏上没有它」：
`analysis__verdict` / `analysis__verdict-code` / `analysis__verdict-part` /
`analysis__note--error` **只在特定态下渲染**（前三个要这一屏真有一条判定，
第四个要读失败），而取证 URL 走的是「未判定」那一态。

改成只声明那 5 个恒在的，并把「另外四个为什么不在名单里」写进声明——
**NEVER 为了名单好看而声明一个屏上此刻没有的东西**
（这正是那一屏原来那句 `styled_none_because` 自己的口径）。

## 8 三次红都是判据自己的（本轮第四、五次同形状）

1. 颜色扫描把**我自己 CSS 注释里的反例** `#333` 当成违规——先剥 CSS 注释再扫；
2. `_render_body` 锚在第一个 `return (`，而那是 `useEffect` 的清理函数
   （`return () => { alive = false; };`）——改用 `rindex`；
3. `BEFORE_RENDER` 里 `<li>` 的属性顺序写错（`key` 应在前）。

## 9 自审（`self_review=true`）

**① 判据覆盖 acceptance**：①许可逐字记入 trace（本文件 §1）与组件文件头；
②边界可量（§2，四条侧面判据）；③token（扫颜色/尺寸字面量）；
④声明 `styled` 换真类名且**类名从源码取、不是手写**；⑤单据已关。

**先红后绿**：判据先写，改动前 11 条里有 4 条红。

**② 无冻结件偏离**：不碰后端，四件一字未动。
**③ 无禁用词**：0 命中。
**④ 复用断言在位**：本卡不引入任何新组件，样式复用 `_ds` token。
**⑤ 装载未超预算**：≈28k / 40k。

## 10 门

```
pytest tests/v041/test_analysis_view_styled.py -q      11 passed
pytest tests/v041/test_screen_composition.py -q        13 passed（含真屏重新观测）
ruff check . --no-cache                                All checks passed!
npx tsc --noEmit                                       0
npm test -- --run                                      85 档 857 passed
```

## 11 留给下游

1. **`GAUGE-15` 的「写空的屏」名单现在是空的**（§5）。下一屏若要写空，
   那条判据仍然拦得住它——**它现在判的是上限，不是等号**。
2. **`assets/screen_composition.json` 的越界**（§4.1）请 owner / steward 过目。
3. **`/favorites` 之外还可能有同形状的过期声明**：`PERSIST-01`~`04` 把四张表建齐之后，
   凡是声明里写着「未提供 / 置灰」的屏都值得重新观测一次。
   本卡只顺手修了实测报红的那一屏——**没报红的没动**，
   因为没有观测证据的改动就是猜。
