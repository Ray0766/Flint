# PAL-02 · trace

**卡**：判据跟着裁决重新瞄准（改方向，意图一个字不动）
**日期**：2026-08-12 ｜ **状态**：verified

## 一、先把「会红的到底有几处」核成实测

换板后全跑 `pytest tests/v041 -q`：**8 红**（steward 静态清点预测 2 处）。
逐条点名归属，分三类：

| # | 红的是谁 | 类 | 处置 |
|---|---|---|---|
| 1 | `test_dark_palette::test_the_dark_palette_keeps_the_paper_and_ink_hue_family` | **判据钉着旧板** | 本卡重新瞄准 |
| 2 | `test_theme_toggle::test_the_dark_palette_ruler_still_stands` | **同一处的回声** | 它 `subprocess` 跑上面那个文件——第 1 条绿了它就绿 |
| 3 | `test_ds_wired::test_the_tokens_are_live_in_the_browser_with_the_declared_values` | **取证是旧照片** | `PAL-03` 重拍 |
| 4-5 | `test_ds_bundle_wired` 两条 | 同上 | `PAL-03` |
| 6-8 | `test_hotspot_card_format` 三条 | 同上 | `PAL-03` |

**「换板真碰坏了东西」：0 处。**

第 3~8 条的形状完全一致：判据从 `tokens/colors.css` **现场解析**期望值
（`_hex_to_rgb(tokens["--surface"])` 那个范式，正是卡面点名的那一种），
而它比对的是 `.ui-probe/*.json` 里换板**之前**拍的运行时取值——
报出来的原话是「`[light] --surface 运行时 #F7F8F3，_ds 声明 #faf7f1`」。
**判据没错、板没错，错的是照片的日期**。

## 二、steward 预测的第二处**没有红**，而它没红是对的

预测：`test_theme_really_switches.py:57-58` 的 `FROZEN_FG/FROZEN_BG` 会红。
实测：**没红**。核过原因——那两个常量不是「期望值」，是**合成观测的输入**：
判据拿它们造一组「两个主题量到一位不差的同一组数」喂给尺子，
验的是**尺子会不会把这种情况判红**，而那与今天的板是什么颜色无关。

静态清点把「文件里有两个写死的色号」读成了「判据钉着这两个色号」。
两者的差别正是本卡要说清的：**写死的色号在判据里当输入，还是当期望值。**

## 三、`FROZEN_FG/FROZEN_BG` 仍然改了，理由与预测的不同

它们绿得没错，**却在拿一组过期的数在验**：`PAL-01` 换板之后，
那组数与屏上任何一处都对不上了。按卡面 acceptance③ 的意思处置：

- 那两行**降级成注释里的历史记录**（`EYE-02` 那个洞的原形，2026-08-04 实测）；
- 判据本身改成从 `tokens/colors.css` **现场解析**今天的明色 `--ink`/`--surface`。

守的仍是「两主题量到的颜色对 MUST 不同」这件事本身，
而喂给尺子的是**今天真的会出现在屏上的那一组**。

## 四、色相族判据：改的是方向，意图一个字不动

```
改前：max-min >= 4  且  b >= r   （青绿族：那时的板是「纸与墨」）
改后：max-min >= 4  且  r >= b   （暖族：v4 暗纸 #191612 实测 r=25 >= b=18）
```

`max-min >= 4` 那半条**原样保留**——它才是「还看得出色相」的可量形式
（v4 暗纸实测 max-min=7）。docstring 里点名 `DEC-060`，并写明改前那半条守的是哪块板。
**NEVER 删掉换成「有色相就行」**：那样两个方向都过，
而「暗纸悄悄漂成蓝黑」这件事就再也没有人看着了。

## 五、阴性对照：重新瞄准之后它还咬得住

两处都加了阴性对照，**改在内存里，NEVER 动真文件**：

- `test_the_hue_family_ruler_still_bites_after_being_re_aimed`：把暗 `--paper`
  换成明色同值 → 「暗纸确实更暗」这条当场为假。
  顺带发现：光靠色相那两条**判不出**这个局面——明纸也是暖的、`max-min` 也够。
  所以把「暗纸到底暗没暗」单独立成 `_paper_really_darkens`，与色相那条各管一半：
  一条管「还看不看得出颜色」，一条管「它到底暗没暗」。**这是本卡真正补上的那道缝。**
- `test_the_switch_ruler_bites_a_palette_whose_dark_paper_is_the_light_one`：
  用当前板造一组「两主题同值」的观测 → 尺子当场判红。

## 六、其余判据一条没动

`test_hotspot_card_format` / `test_ds_bundle_wired` 那一族**零改动**——
它们从 token 现场解析期望值，换板后自动跟着走。今天它们红，红在照片旧，
不在判据错；`PAL-03` 重拍之后自愈。**动了它们就说明换板碰坏了别的东西。**

## self_review

① 判据 ↔ acceptance：红的逐条列出（本 trace §一）· 色相方向改 1 + docstring 点名 ·
   FROZEN 降级 1 + 现场解析 · 阴性对照 2 + 正面对照 1 · 其余零改动（靠全跑证）。
② 无冻结件偏离：`flint/` 未改。
③ 无禁用词：命中 0。
④ 复用断言在位：仍用 `va.judge_theme_switch` 与 `parse_color` / `relative_luminance`。
⑤ 装载未超预算：约 8k tokens。

## 产出文件

```
tests/v041/test_dark_palette.py            色相方向重新瞄准 + 阴性/正面对照两条
tests/v041/test_theme_really_switches.py   FROZEN 两值降级成注释、判据改现场解析 + 阴性对照一条
```
