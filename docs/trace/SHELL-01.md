# SHELL-01 · 地区与语言下拉挪到右上角（`DEC-046`）

**结论**：顶栏右上角挂上两个独立下拉；写回走 `PUT /settings/locale`（`PERSIST-01`
的 `prefs` 表），**刷新之后还在**。`verify_cmd` 17 条全绿（含 6 条真浏览器判据），
`ruff` / `tsc 0` / `vitest 85 档 857` 全绿。

装载：`docs/steward/tasks-v041-b9.json#SHELL-01` · `DECISIONS-v04.md#DEC-046` ·
`web/components/shell/AppShell.tsx` · `web/components/region-switch/RegionSwitch.tsx` ·
`web/components/locale-settings/LocaleSettings.tsx` · `web/app/settings/locale/page.tsx` ·
`web/app/plaza/page.tsx` · `web/lib/{useScreenData,screenClient,apiBase}.ts` ·
`web/app/globals.css`（外壳那一段）· `tests/v041/test_shell_nav.py`（真浏览器体例）
（实测装载 ≈ 30k tokens，预算 40k）

---

## 1 卡面那句话不确，`DEC-045-LANDING` 已经记过一次

卡面 acceptance①：「当前两者只在 `/settings/locale` 那一屏里」。

实查：`LocaleSettings` 确实只在那一屏，而 **`RegionSwitch` 在广场页上另有一个实例**
（`web/app/plaza/page.tsx`，按 `?region=` 驱动热点集合）。
真相是**外壳右上角两者都没有**——那才是 owner 说的那件事。

所以本卡是**新增第三处**，不是搬家。照卡面那句去做会顺手把广场那个删掉，
而它驱动的是热点集合的筛选——删了之后广场就没法切区了。
判据 `test_the_plaza_instance_was_not_removed` 钉住这一条。

## 2 改前 / 改后 / 为什么非改不可

### 2.1 新增（都在 outputs `web/components/shell/` 之内）

| 文件 | 是什么 |
|---|---|
| `web/components/shell/LocaleControls.tsx` | 右上角控件本体：地区复用 `RegionSwitch`，语言用 `LocaleSettings` 导出的 `LANGS` |
| `web/components/shell/localeClient.ts` | `PUT /settings/locale`，**一次只发一根轴** |
| `tests/v041/test_shell_locale_dropdowns.py` | 17 条判据（11 源码层 + 6 真浏览器） |

### 2.2 既有文件

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `web/components/shell/AppShell.tsx` | 右上角是 `<span className="app-shell__spacer" />` 一个空占位 | 占位**留着**，其后加 `<LocaleControls />` | 这就是 acceptance①。占位为什么留着见 §3 |

**只碰了这一个既有文件**，且改动只有两行（一条 import、一处 JSX）。

### 2.3 `localeClient.ts` 为什么住在 `components/shell/` 而不是 `web/lib/`

它的自然归宿是 `web/lib/`（`jobClient` / `topicClient` / `derefClient` 都在那儿）。
**本卡 outputs 只有 `web/components/shell/` 与判据文件**，
而本批 rules 写死「改动面大于卡上 outputs → 停下走 `docs/blocked/`」。

为一个文件停下一张卡不成比例；把它悄悄放进 `web/lib/` 也不行——那是**不声明地扩面**。
所以放在 outputs 之内，并在**那个文件的文件头**写明它该搬去哪儿。
**留给后续任一张 outputs 含 `web/lib/` 的卡顺手搬家。**

## 3 真浏览器判据抓到的一处——**源码层怎么判都判不出**

第一版我把 `.app-shell__spacer` **删掉了**，并写了一条判据断言「那个空占位必须没了」，
理由是「留着会把两个下拉挤开」。

**那个理由是猜的，而且猜反了。** 实查 `web/app/globals.css:178`：

```css
.app-shell__spacer { flex: 1; }
```

它不挤开任何东西——**它就是把后面的东西推到右边的那个机制**。删掉之后实测：

```
locale.right = 146      bar.right = 390        ← 「右上角」只做到了「在顶栏里」
```

把占位放回去（**放在控件前面**）之后 `locale.right = 366`，贴住内容列右内边缘。

**判据也跟着改了方向**，并把「为什么第一版是错的」写进它自己的 docstring——
下一个人读到 `test_the_shell_mounts_the_locale_controls_after_the_spacer`
时能直接看到那条 `flex: 1` 是干什么的，不必再猜一次。

### 3.1 顺带把一个「猜出来的容差」换成量出来的

第一版拿**顶栏**右边缘比、容差写 `< 24`。实测差正好是 24——
那是 `.app-shell__inner` 的 `var(--sp-5)` 内边距。**容差是照着内边距的数值猜的**，
猜对了也说不清它为什么是 24。

改成量**内容列的右内边缘**（`.app-shell__inner` 的 `right - paddingRight`），
容差 4px 留给亚像素。参照物换对了之后，这条判据说的话与它想说的话一致了。

## 4 另外两处「红的是尺子自己」

两处都在本卡自己的判据里，都是第一次跑就撞上的：

1. **硬编中文那条**把一段 JSX 注释里的中文报成了「硬编中文」——
   `{/* … */}` 是第三种注释，而正则又允许字符串跨行，
   于是一行末尾的引号与下一行开头的引号配成了一对。
   修法：先剥 JSX 注释，字符串正则改成不跨行（`[^"\n]`）。
2. **「右上角有两个下拉」那条**按 `data-locale-axis` 认下拉，
   而地区那一格是**复用的** `RegionSwitch`，它身上没有这个属性。
   **为了让判据变绿去给被复用的组件加一个属性，正是「复用既有件」这条 acceptance 要防的事**——
   所以改判 `data-testid`，一个字都没动 `RegionSwitch`。

## 5 两条轴各自独立，两层都量

`PRINCIPLES#A3`：**切地区 NEVER 改语言，切语言 NEVER 改热点集合。**

- **源码层**：`putLocaleAxis` 的请求体是 `JSON.stringify({ [axis]: value })`——
  一次只发改动的那一根；后端 `set_prefs` 也只改传进来的那一项。
  两根一起发的话，用户切地区时会把语言原样写一次，
  而那次写入会把**另一个设备上刚改的语言**覆盖掉，且屏上什么异常都看不出来。
- **真浏览器**：切完地区之后断言语言**一个字都没动**。
  中间隔着一次回读，而回读把两根都写回屏上时最容易把另一根也换掉——
  源码层那条判不出这一层。

## 6 「存得住」是 `PERSIST-01` 的产品面回声

`prefs` 表建出来之前，刷新一次就回默认值了。本卡的
`test_the_choice_survives_a_reload` 在真浏览器上走的正是这条：
切区 → 刷新 → 仍是刚才选的那个。

写完**回读服务端**（`refetch()`）而不是本地乐观改：服务端把值规范化过之后
两边就不一样了，而用户不会知道自己看到的不是存进去的那个。

## 7 开工时踩的两个环境坑（记下来省下一次调查）

1. **前端起法**：`npm run dev` **必须带**
   `FLINT_API_BASE=http://localhost:8000 NEXT_PUBLIC_FLINT_API=http://localhost:8000`
   （`docs/blocked/FE-DEMO-ENV-FLINT-API-BASE.md` 记着这件事）。
   不带的话 `API_BASE` 是空串，请求打到 Next 自己的 origin → 404，
   于是控件停在非 ready 态、`region-select` 根本不渲染——
   **症状看起来像「控件坏了」，其实是取数打错了地方**。
2. **`:8000` 又是旧进程**：`PID=11480 Start=05:51:59`，而 `PERSIST-03` / `PERSIST-04`
   的后端改动都在那之后。两层一起重起后 `PID=55056 / 45744 @ 06:54`，
   本卡的真浏览器证据全部取自这两个新进程。

## 8 自审（`self_review=true`）

**① 判据真实覆盖 acceptance**

| acceptance | 判据 |
|---|---|
| ① 右上角直接下拉选择 | `test_the_shell_mounts_the_locale_controls_after_the_spacer`、`test_both_dropdowns_are_really_on_the_top_right`（真浏览器量位置与面积） |
| ② 复用既有件；九区清单从端点取 | `test_the_controls_reuse_the_existing_pieces_instead_of_writing_a_second_copy`、`test_the_region_list_still_comes_from_the_endpoint`（连 `"CN"` 这种字面量都判） |
| ③ 两条轴各自独立 | `test_a_write_carries_exactly_one_axis`、`test_switching_region_never_touches_lang_and_the_other_way_round`、`test_the_region_switch_still_carries_lang_through_untouched`、`test_switching_the_region_in_a_real_browser_leaves_the_language_alone` |
| ④ 选择存得住 | `test_the_choice_is_written_to_the_server_not_kept_in_memory`（连 `localStorage` 都判）、`test_the_screen_after_a_write_shows_what_the_server_took`、`test_the_choice_survives_a_reload`（真浏览器刷新） |
| ⑤ `/settings/locale` 保留，两处同值 | `test_the_detail_screen_is_kept_and_reads_the_same_endpoint`、`test_the_detail_screen_shows_the_same_value`（真浏览器逐屏比对） |
| ⑥ 390px 不溢出 | `test_the_bar_does_not_overflow_at_390` |
| （本卡加的）广场那个实例不许被删 | `test_the_plaza_instance_was_not_removed` |

**先红后绿**：第一版跑出 3 次红，**三次都是判据自己的问题或真缺陷**，
逐条记在 §3 §4，NEVER 为了变绿去改被复用的组件。

**② 无冻结件偏离**：本卡不碰后端，四件一字未动。

**③ 无禁用词**：新增文件六个词 0 命中；另有一条判据扫新件里的硬编中文。

**④ 复用断言在位**：`RegionSwitch` 与 `LANGS` **一个字都没改**，
判据 `test_the_controls_reuse_the_existing_pieces_…` 就是那条复用断言。

**⑤ 装载未超预算**：≈30k / 40k。

## 9 门

```
pytest tests/v041/test_shell_locale_dropdowns.py -q   17 passed（含 6 条真浏览器）
ruff check . --no-cache                               All checks passed!
npx tsc --noEmit                                      0
npm test -- --run                                     85 档 857 passed
邻近尺子未回归：test_shell_nav / test_locale_seam_regions /
                test_regions_from_backend / test_plaza_region_query   44 passed
```

图：`.ui-probe/shell01-locale-390.png`（390px 顶栏实拍）

## 10 留给下游

1. **`SHELL-02`（白天/夜间三态）**：控件也放右上角，**排在 `LocaleControls` 之后**，
   同一个 `.app-shell__spacer` 一起推。`prefs` 表已经在了，三态存得住走同一条路——
   但 `Prefs` 今天只有 `lang` / `region` 两列，**主题那一列由 `SHELL-02` 的迁移加**
   （`PERSIST-01` trace §9 记着这件事）。
2. **`localeClient.ts` 该搬去 `web/lib/`**（§2.3），由后续任一张 outputs 含 `web/lib/` 的卡顺手做。
3. **`/settings/locale` 详情屏今天仍然存不了**：它只有草稿态（`status="idle"`、
   没有 `onSave`），**改前改后都是如此，本卡没有动它**（不在 outputs 里）。
   右上角现在能存，详情屏还不能——两处显示同一个值这条成立，
   但「详情屏那个保存按钮按下去没反应」是一件**本卡范围外的既有缺陷**，
   建议给它一张卡（或把 `web/app/settings/locale/` 并进某张卡的 outputs）。
