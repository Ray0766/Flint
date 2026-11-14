# EYE-02 · 视觉判据可执行化：「用户看不看得见」变成机器可验

**卡** `tasks-v041-b2.json#EYE-02` · **批次** v0.4.1 第 2 批 · **开工** 2026-08-03T23:20Z

## 1. 装载清单

卡面 EYE-02 · `scripts/ui_probe.py`（EYE-01 刚建的观测面，复用它的量测口径）·
`docs/review/终检-v04.md#F-09` 全节 · WCAG 2.x 相对亮度/对比度定义与 SC 1.4.3 阈值（既有知识，
用规范自带参照值校准，未联网）。约 11k tokens。

## 2. 顺序（§4.2）

**测试先落盘先跑红**：`ERROR ... 1 error during collection`（`tools/visual_assert` 还不存在）→
实现 → 15 passed。连续第二张卡顺序正确。

## 3. 三条判据（acceptance①）与它们各自挡什么

| 判据 | 挡的是 | 由来 |
|---|---|---|
| `rendered-size` | **DOM 里有 ≠ 屏幕上有** | F-09：空 span 占 0 像素，`querySelector(...) !== null` 照样通过 |
| `contrast` | **画出来了 ≠ 看得清** | 灰底灰字与不画没有区别 |
| `both-themes` | 只在深色下看得见的记号，浅色用户看不见 | F-09 的记号本来就是主题相关的 |

**两条不肯含糊的地方**：

1. **背景透明时报红，NEVER 当成白底算**。当成白底会在深色主题下给出一片假绿——
   真背景是深色，而算出来的是「黑字白底 21:1」。取不到有效背景色是**量测的问题**，
   该被报出来，不该被一个默认值盖住。
2. **少一个主题算红**，不算「没量到就跳过」。跳过的那一半正是最可能坏的那一半。

**对比度照 WCAG 不自己发明**：相对亮度（sRGB 线性化 → 0.2126/0.7152/0.0722 加权）与
`(L1+0.05)/(L2+0.05)`，阈值 AA 正文 4.5、大字号 3.0。校准用规范自带参照值：
纯黑/纯白 = 21:1、自己对自己 = 1:1，另用 `#777` 白底 ≈ 4.48（常被当成「够用」的那一档，
实际差一点点）验证判据能把它判红。**通用问题照权威口径，自造一套数没人能复核。**

## 4. 真驱动实跑（acceptance③ 的真半边）

判定是纯函数、量测由驱动做。默认驱动用 `C:\pwenv` 的 playwright 打开**静态 HTML 片段**
（`data:`/`set_content`，**不起前端**）。三次真跑：

**① F-09 形态（空 span，仅 `display:inline-block`）**
```
✗ rendered-size —— [dark]  .mark 在 DOM 里，渲染尺寸 0.0×0.0——用户看不见它
✗ contrast     —— [dark]  .mark 的背景是透明的，取不到有效背景色——对比度无从算起…
✗ rendered-size —— [light] （同上）
✗ contrast     —— [light] （同上）
EXIT=1
```
**这就是终检 F-09 的那个记号**：DOM 里查得到、量出来 0×0。

**② 有尺寸但对比度不够（`#111` 字 / `#b23` 底）**
```
✓ rendered-size —— [dark] .mark 渲染尺寸 10.0×10.0
✗ contrast     —— [dark] .mark 对比度 3.05:1 < 阈值 4.5
EXIT=1
```
这一条是意外收获：我按「看起来挺清楚」挑的两个颜色，实测 **3.05:1**，达不到 AA。
**「看起来够」和「量出来够」不是一回事**——这正是这把尺子存在的理由。

**③ 全绿正例（`#000` 字 / `#fff` 底、12×12）**
```
✓ rendered-size —— [dark] 12.0×12.0     ✓ contrast —— [dark] 21.00:1 ≥ 4.5
✓ rendered-size —— [light] 12.0×12.0    ✓ contrast —— [light] 21.00:1 ≥ 4.5
EXIT=0
```
实测 21.00:1 与 WCAG 参照值逐位对上——**真驱动量出来的数和纯函数算出来的数是同一个**。

## 5. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_visual_assert.py -q → 15 passed
ruff check . --no-cache → All checks passed!
```

**① acceptance 映射**

| acceptance | 测试 |
|---|---|
| ① 三条判据 | `test_a_zero_sized_element_is_red_and_says_why`、`test_one_zero_dimension_is_enough_to_be_invisible`、`test_contrast_matches_the_wcag_reference_values`、`test_the_aa_threshold_sits_where_wcag_puts_it`、`test_both_themes_must_pass_and_the_failing_theme_is_named`、`test_a_missing_theme_is_red_not_skipped` |
| ② 阴性对照（0×0 红 / 正常放行） | `test_a_zero_sized_element_is_red_and_says_why` ↔ `test_an_element_with_a_real_box_is_let_through`；`judge_contrast` 侧 `#777` 红 ↔ 黑白 21:1 绿 |
| ③ 与浏览器解耦、可对静态片段跑 | `test_a_static_fragment_can_be_judged_without_the_front_end`（注入假驱动跑通整条链）、`test_the_same_chain_is_green_for_a_real_looking_element`、`test_playwright_stays_out_of_the_dependency_files` + §4 真驱动三次实跑 |

另有两条守「不含糊」的：`test_a_transparent_background_is_red_not_assumed_white`、
`test_a_missing_element_is_red_with_a_different_message`（「找不到」与「0×0」两句话不同，
前者查渲染、后者查样式）。颜色解析覆盖浏览器真给的四种形态 + 认不出即抛。

**② 无冻结件偏离**：零新增依赖（stdlib `re`/`json`/`argparse`/`dataclasses`），
`requirements.lock` / `pyproject.toml` / `web/package.json` 一字未动且本卡断言其无 playwright。

**③ 禁用词**：两个文件扫描，六词 0 命中、收尾「等」0 命中。

**④ 复用**：量测口径与 `scripts/ui_probe.py`（EYE-01）同源——`boundingBox` 宽高判可见、
`getComputedStyle` 取色；本卡新增的是**有效背景色上溯**（元素自己的背景通常是 transparent，
用户看到的是祖先那层）与对比度。NEVER 另写一套尺寸判定。

**⑤ 装载预算**：约 11k tokens。

## 6. 登记未做

1. **没有对真前端跑过**：本卡验的是判据面 + 静态片段，真页面逐屏取证是 EYE-03 的面。
2. **`.mark--disputed` 本身还没有样式**（F-09 的修复在 FB-01/FB-02）：本卡只交尺子，
   NEVER 顺手去写 CSS——那是另一张卡的 outputs。
3. **大字号阈值 3.0 已定义但判据不自动区分字号**：区分需要量 `font-size`/`font-weight`，
   属 EYE-03 真页面取证时的面，本卡留常量与参数入口（`--min-contrast`）。
4. **不判非文本对比度（SC 1.4.11，图形/UI 组件 3:1）**：记号是图形而非文本，
   严格说该用 3:1；本卡默认 4.5 更严，`--min-contrast 3` 可切。口径选择留给用它的那张卡。
