# DARK-02 · EYE-02 的「明暗两主题」从量同一个东西变成真判据

**卡** `docs/steward/tasks-v041-b2.json#DARK-02` · **cycles 1** · **self_review = true** → §6
**依赖** DARK-01（verified）· EYE-02（verified）

## 1. 装载清单

卡面 DARK-02 · `docs/blocked/EYE-02-TWO-THEMES-MEASURES-ONE.md` 全文 ·
`tools/visual_assert.py` 全文（270 行）· `tests/v041/test_visual_assert.py` 全文（EYE-02 的判据面）·
`tests/v041/test_dark_palette.py` 全文 · `docs/trace/DARK-01.md` 全文 ·
`tests/v041/test_disputed_mark_visible.py` 与 `tests/v041/test_workbench_switch.py` 的取证入口段 ·
`tools/gauge_map.py` 头部（确认它清点的是 `tasks-v04.json`，本卡不进它的表）。
约 12k tokens，预算 40k 以内。

## 2. 顺序（§4.2）

测试先落盘先跑红（**18 failed / 4 passed**）→ 实现判据 → 18 passed / 4 failed（剩下的
四条要真取证与关问题单）→ 真浏览器取证 → 重量旧取证 → 关问题单 → **22 passed**。

## 3. 判据长什么样

`tools/visual_assert.py` 加了**第 0 条**（前置）`theme-switches`：

```
theme-switches  ← 本卡加：两主题量到的颜色对必须不同
rendered-size   ← F-09
contrast        ← WCAG AA
（后两条在两个主题下各判一次）
```

**为什么是「前置」**：后三条回答「看得见 / 看得清」，但它们在两次量到同一组数时
逐条都过——问题单记的正是这个。先回答「这两次量的到底是不是两个东西」，
后面三条的两遍才有意义。

三个不肯含糊的地方：

- **归一到 RGB 之后比**。按原始字符串比的话 `#F7F8F3` 与 `rgb(247, 248, 243)`
  会被判成「换了」——那等于把假绿换个写法留下来。
- **尺寸不参与比较**。调色板换的是颜色；把一像素的布局抖动当成「主题生效了」，
  就会放行一个根本没有暗色规则的元素。
- **`theme_sensitive` 默认 True**。忘了传参得到的是红，不是绿。默认关闭的话，
  本卡关上的洞会以「谁都没想起来传那个参数」的形式无声回来。确实不随主题变的元素
  （固定品牌色一类）显式传 `False`，且**报告里记下这一位**——不记的话，
  一份 `ok=True` 读不出它是验过了还是那条判据被关了。

## 4. 改既有文件：三处（§六.1 逐处交代）

### 4.1 `tools/visual_assert.py`

- **改前**：三条判据；`judge_both_themes` 逐主题跑前两条；`check_fragment` 报告里
  没有 `theme_sensitive` 这一位。两主题量到同一组数时 `ok=True`。
- **改后**：新增 `THEME_SWITCH` 常量、`observed_palette()`、`judge_theme_switch()`；
  `judge_both_themes(..., *, theme_sensitive=True)` 把它排在最前；
  `check_fragment(..., theme_sensitive=True)` 透传并把这一位写进报告；
  CLI 加 `--theme-agnostic`。模块 docstring 从「三条判据」改成「四条判据」并写明这条洞的原形。
- **为什么非改不可**：卡上 outputs 第一项就是它，acceptance① 要的就是这条前置断言。
  **既有三条判据一条没动**——新判据是加一条，不是换掉那三条（判据
  `test_the_old_three_criteria_still_run_alongside_it` 钉着这件事）。

### 4.2 `docs/blocked/EYE-02-TWO-THEMES-MEASURES-ONE.md`

- **改前**：一张挂着的问题单，「三条路要 owner 选」还悬着。
- **改后**：顶部加关闭横幅（走第一条路 + 判据补强 + 两层阴性对照 + 顺带查出的旧假绿），
  **原文原样保留在下面**。
- **为什么非改不可**：acceptance④ 点名要关。

### 4.3 `.ui-probe/disputed_mark.json`（**取证产物，非源文件**）

- **改前**：`styled` 两个主题量到 `rgb(27, 42, 46) on rgb(247, 248, 243)`，
  **一位不差**，而 `ok=True`。文件时间戳 08-04 09:20，早于 DARK-01（21:12–21:45）。
- **改后**：用 `C:\pwenv` 的解释器重跑 `tests/v041/test_disputed_mark_visible.py` 的
  取证入口（dev server 在跑，`_ds` 经 :3000 取），得到
  `dark rgb(237,238,230) on rgb(21,34,37)` / `light rgb(27,42,46) on rgb(247,248,243)`。
- **为什么非改不可**：这是**新判据在门里抓到的第一个真东西**。
  尺子补好而旧证据不重量，等于承认「以前那些绿不作数，但我们不查」——
  那正是 F-11 的形状（尺子在、但那一格没人看）。FB-02 的判据一条没改，
  改的是它依据的那份**量测数据**：同一个片段、同一个入口、新的调色板。
  重跑前的原件留在本轮 scratchpad，重跑后 FB-02 的 13 条判据全绿。

**未改**：`web/public/_ds/*/tokens/colors.css`（本卡不碰板，只碰尺子）、
`web/app/globals.css`、`.ui-probe/workbench_switch.json`（DARK-01 已重量过，
两主题本就不同）。`contracts/` · `flint/domain/` · `requirements.lock` ·
`assets/heldout_questions.yaml` 一字未动。

## 5. 阴性对照做了两层，因为它们坏的方式不一样

| 层 | 怎么摘掉暗色规则 | 在哪跑 | 结果 |
|---|---|---|---|
| 判据面 | 读真 `colors.css`，**在内存里**把 `@media (prefers-color-scheme: dark)` 与 `[data-theme="dark"]` 两块从字符串里删掉，按剩下的 `:root` 解析两主题 | `pytest -q`，零 playwright | 摘掉即红，且**唯一红的判据是 `theme-switches`** |
| 量测面 | 把那份摘过的 CSS **内联进片段**，真浏览器量 | `C:\pwenv` 解释器，产物 `.ui-probe/theme_switch.json` | `with_dark.ok=True` / `without_dark.ok=False`，红的同样只有 `theme-switches` |

真量到的两组数：

```
with_dark    dark : rgb(237, 238, 230) on rgb(21, 34, 37)
             light: rgb(27, 42, 46)   on rgb(247, 248, 243)
without_dark dark : rgb(27, 42, 46)   on rgb(247, 248, 243)   ← 落回 :root
             light: rgb(27, 42, 46)   on rgb(247, 248, 243)
```

**产品文件一个字节没动**：两层摘的都是内存里的副本，判据
`test_the_negative_control_changes_nothing_on_disk` 钉着这件事。改产品文件造出来的红
只证明那次改动生效了，证明不了尺子有区分力。

**取证片段里按钮的底色与字色显式取 token**（`background:var(--surface);color:var(--ink)`）：
不取的话浏览器给按钮一层不透明的 UA 默认灰 `rgb(240, 240, 240)`，两个主题当然一样，
那时这份对照会红在「按钮没被上色」而不是「暗色规则被摘了」——一条看起来有效的假对照。

## 6. 变异考：十七个，三个先活了下来

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 判据恒绿（两主题同值也放行） | acceptance① | **5 failed** ✓ |
| ② 不归一化，按原始字符串比 | 归一 | **5 failed** ✓ |
| ③ 把尺寸也算进比较 | 只比颜色 | **1 failed** ✓ |
| ④ `check_fragment` 默认关掉这条判据 | 默认开启 | **4 failed** ✓ |
| ⑤ 报告里不记 `theme_sensitive` | 留痕 | **1 failed** ✓ |
| ⑥ 把前置判据挪到最后 | 前置 | **3 failed** ✓ |
| ⑦ 少一个主题时放行 | acceptance① | **22 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑧ 元素找不到时放行 | acceptance① | **1 failed** ✓ |
| ⑨ 认不出的颜色当成「不同」放行 | NEVER 猜 | **1 failed** ✓ |
| ⑩ 报红时不贴量到的值 | 可读性 | **1 failed** ✓ |
| ⑪ 把旧的假绿取证放回磁盘 | acceptance③ | **1 failed** ✓ |
| ⑫ 删掉真浏览器阴性对照产物 | acceptance② | **2 failed** ✓ |
| ⑬ 把阴性对照的 `ok` 篡改成 True | acceptance② | **1 failed** ✓ |
| ⑭ 关闭横幅去掉日期 | acceptance④ | **22 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑮ 关闭横幅去掉卡号 | acceptance④ | **1 failed** ✓ |
| ⑯ 问题单只剩横幅、原文全删 | 原文保留 | **22 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑰ 日期从关闭标记挪到同一行别处 | ⑭ 的补判本身 | **1 failed** ✓ |

**⑦ 为什么能活**：判据里「少于两个主题」那一支被抽掉后，单份观测会**掉进下一支**
——「两个主题量到同一组颜色」——照样红。测试只判了「红了没有」，于是分支已经没了
而它全绿。改成**红的理由要点名缺了哪个主题**（`"缺"` 与 `"light"` 同时在 detail 里）。
这是「测试判了结果没判理由」的形态：结果对了，机制没了。

**⑭ 为什么能活**：判据是「关闭那一行里有 `2026-08-04`」，而那一行正文里
「owner **2026-08-04** 裁决」把它喂饱了——去掉真正的关闭日期毫无反应。
**这是 DARK-01 变异考⑫ 的同一个洞在同一类文件上原样复发**，本仓第二十二次同型。
改成把日期与卡号**直接钉在「已关闭」这个词后面**（`re.search(r"已关闭\s*2026-08-04")`），
并顺手把横幅正文里那句裁决挪到下一行。补判后加考⑰ 专门打「日期挪到同一行别处」，红。

**⑯ 为什么能活**：第一次的变异体自己太弱（只删了「一位都不差」四个字），
判据钉的两个字符串都还在。换成**把横幅以下整段删光**再考，仍然绿——
说明判据确实只钉了两个词。改成判**整段还在**：四个小节标题逐个在 + 行数下限。

十七次变异后 `tools/visual_assert.py` 与问题单的内容与变异前逐字相同（baseline 22 passed）。

## 7. verify 与全局门

```
verify_cmd: pytest tests/v041/test_theme_really_switches.py -q → 22 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: no issues found in 288 source files
            pytest -q               → 2996 passed（全绿，零 skip）
相关面回归: tests/v041/test_visual_assert.py + test_disputed_mark_visible.py
            + test_workbench_switch.py + test_dark_palette.py → 50 passed
真量:       C:\pwenv\Scripts\python.exe tests/v041/test_theme_really_switches.py
            → with_dark.ok=True  without_dark.ok=False
            C:\pwenv\Scripts\python.exe tests/v041/test_disputed_mark_visible.py
            → styled.ok=True  unstyled.ok=False
```

## 8. self_review（§4.6）

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 两次量到相同即判红（前置断言） | `test_two_identical_measurements_are_red`、`test_a_real_switch_is_let_through`、`test_the_same_color_written_two_ways_is_still_the_same_color`、`test_changing_only_the_background_counts_as_a_switch`、`test_a_size_only_difference_is_not_a_theme_switch`、`test_one_theme_alone_cannot_prove_a_switch`、`test_a_missing_element_is_red_with_its_own_message`、`test_an_unparseable_color_is_red_not_guessed`、`test_check_fragment_enforces_the_switch_by_default`、`test_the_switch_verdict_is_reported_first`、`test_turning_it_off_takes_an_explicit_argument_and_is_recorded`、`test_the_old_three_criteria_still_run_alongside_it` |
| ② 阴性对照必红、NEVER 改产品文件造红 | `test_the_real_palette_passes_the_new_criterion`、`test_removing_the_dark_blocks_turns_the_criterion_red`、`test_the_negative_control_changes_nothing_on_disk`、`test_the_browser_level_negative_control_is_recorded`、`test_the_two_recorded_runs_differ_only_by_the_dark_blocks` |
| ③ 接进全局门 | `test_there_is_recorded_evidence_to_judge`、`test_every_recorded_ds_element_really_switches_themes`、`test_this_file_needs_no_browser_to_run`；文件在 `tests/` 下，`pytest -q` 直接收 |
| ④ 关掉问题单 | `test_the_blocked_doc_is_closed_with_a_banner`、`test_the_original_report_is_kept_under_the_banner` |

**② 无冻结件偏离**：`contracts/` · `flint/domain/` · `requirements.lock` ·
`assets/heldout_questions.yaml` 未触碰；零新增依赖；playwright 仍只在 `C:\pwenv`
（EYE-02 的 `test_playwright_stays_out_of_the_dependency_files` 继续绿）。

**③ 禁用词**：六词 + 列表尾「等」在 `tools/visual_assert.py`、
`tests/v041/test_theme_really_switches.py`、问题单三份文件里 **0 命中**。

**④ 复用**：判据长在 `tools/visual_assert.py` **同一把尺子**里（EYE-02 那把），
NEVER 另起一个模块；颜色解析复用既有 `parse_color`，报告结构复用既有 `Verdict`；
取证入口的形状照抄 FB-02 / K6-01 的 `__main__` 约定（同一份 `.ui-probe/` 产物口径）。

**⑤ 装载预算**：约 12k tokens，未超 40k。

## 9. 登记未做

1. **门里判的是「已录取证」，不是「每次都真量」**。`pytest -q` 不起浏览器，
   它判的是磁盘上那几份 JSON。产物过期时门看不出来——本卡这次是**人工发现**
   `disputed_mark.json` 早于 DARK-01。产物新鲜度（比如判据文件与 `_ds` 的 mtime/sha
   对不上就报红）没有做，登记在此。
2. **只盯 `styled` 那一半**。`_recorded_ds_reports()` 跳过 `unstyled`：阴性对照本来
   就没有 `_ds` 规则在起作用，对它要求「主题切换」会造出一条永远红的假警报
   （K6-01 的 unstyled 量到的是浏览器默认按钮灰，两个主题一样是对的）。
   代价是：将来若有第三种 key，它不会被这条门覆盖。
3. **`tools/gauge_map.py` 不收本卡**。它清点的是 `tasks-v04.json` 的 104 张卡，
   v0.4.1 第 2 批不在它的表里。本卡的「在不在门里」由 §7 的实跑与
   `test_this_file_needs_no_browser_to_run` 直接钉。
4. **11 张 UI 卡的整屏取证还没这把尺子**。`.ui-probe/*.png` 是截图，不是结构化观测，
   本判据碰不到它们。整屏那一层是 `UI-01` 的验收面。
5. **收集数对不上 DARK-01 记的那个数，差 1 条，来源没查**。实测：
   `pytest --collect-only` 全仓 2996；`--ignore` 掉本卡文件后 **2974**；本卡 22 条。
   DARK-01 的 trace 记的全局门是 2973。差的那 1 条**不是本卡产生的**，
   本卡也没去追它（最可能是 DARK-01 跑完全局门之后又补了一条判据，未核实，
   NEVER 当成结论）。同批四份视觉测试收集 50 条、实跑 50 passed，零 skip，
   所以它不是「某条 skip 变成了真跑」。
6. **台账时间戳口径**：本卡 `started` 行第一次写成了 UTC（`12:10Z`），与台账既有的
   「本地时间 + Z 后缀」不一致，会让断点定位看起来在倒流。写下 30 秒内、
   在任何事件之后之前改回本地时间 `22:10Z`，此处留痕。台账其余 137 行一字未动。
   另：Windows 上文本模式 append 会把 `\n` 翻成 `\r\n`，本卡两次追加都撞上，
   写完即按字节把那一处改回 LF（全文件 BOM 保留、CRLF 计数实测 0）——
   台账全文行尾必须一致，混着的话下一个按字节读的工具会在这里分叉。
