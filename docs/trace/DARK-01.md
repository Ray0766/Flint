# DARK-01 · `_ds` 出一套暗色调色板

**卡** `tasks-v041-b2.json#DARK-01` · **cycles 2** · **owner_review = true** → 见 §7
**依赖** FB-01（verified）

## 1. 装载清单

卡面 DARK-01（含 owner 2026-08-04「允许暗色」的裁决）·
`docs/blocked/DS-NO-DARK-PALETTE.md` 全文（假绿是怎么被发现的）·
`web/public/_ds/*/tokens/colors.css` 全文（26 个 token 逐个）·
`tools/visual_assert.py`（EYE-02 的对比度尺子）· `web/app/globals.css`。约 7k tokens。

## 2. 顺序（§4.2）

测试先落盘先跑红（9 failed / 8 passed）→ 先**量明色基线**（ink/paper 12.68、
ink/surface 13.88、ink-2/paper 4.83）→ 按基线挑暗色值 → 写板 → 关问题单 →
17 passed。

**基线先量再挑值**：不先量，「暗色下对比度不退化」这条只能靠感觉——
而感觉在暗色上最不可靠（暗底上人眼对亮字的容忍度高，容易挑出实际更低的组合）。

## 3. 改既有文件：三处（其中一处是供应商资产，需要单独交代）

### 3.1 `web/public/_ds/*/tokens/colors.css`（**供应商资产**）

- **改前**：只有 `:root` 一块明色板，26 个 token；全仓零暗色声明。
- **改后**：追加 `@media (prefers-color-scheme: dark)` + `[data-theme="dark"]`
  + `[data-theme="light"]` 三块，**明色那一块一个字节没动**。
- **为什么非改不可**：卡上 outputs 第一项就是它，且 owner 2026-08-04 裁决允许暗色。

**这一处与 K6-01 的口径不同，必须说清**：K6-01 的 trace 写着「`_ds` 目录一个字节没动
（它是供应商资产，终检 C6 的口径）」。那条口径**今天被 owner 的裁决覆盖**——
不是我自己松的。凡后续再有人引用 C6 来禁止改 `_ds`，要连带看到这一条：
**允许改的是暗色板这一件事，不是整份资产从此可改。**

### 3.2 `docs/blocked/DS-NO-DARK-PALETTE.md`

- **改前**：一张挂着的问题单。
- **改后**：顶部加关闭横幅（裁决 + 日期 + 由哪张卡解决 + 实测对比度），
  **原文原样保留在下面**。
- **为什么非改不可**：acceptance⑥ 点名要关。留着一张已解决的单，
  下一个人会重做一遍；直接删掉则会丢掉「假绿是怎么被发现的」这段记录。

### 3.3 `web/app/globals.css`

- **没改**。卡上 outputs 列了它，但实查后确认 `body` 已经只用
  `var(--bg-page)` / `var(--text-body)`——**token 一换，明暗自动跟着走**，
  应用层无需任何改动。有判据钉着这件事（`test_globals_css_still_reads_tokens_not_literals`）。
  **列在 outputs 里不等于必须改**：改一处不需要改的地方，就多一处要维护的东西。

## 4. 逐档取值依据（acceptance④：NEVER 由明色取反）

**取反为什么不行**：算术取反（255-x）会把色相翻到**补色**去——
青灰绿的纸取反成粉紫，「纸与墨」当场变成「霓虹与荧光」。
本卡的做法是**纸与墨互换角色，色相留在同一族**。

| token | 明色 | 暗色 | 依据 |
|---|---|---|---|
| `--paper` | `#EDEEE6` | `#0F1A1C` | 取**墨**那族的深青黑再压暗；`b≥r` 且三通道极差 13，仍看得出是青绿，不是纯黑 |
| `--paper-2` | `#E3E5DA` | `#131F22` | 比暗纸亮一档，保持「次级底比主底亮」的既有关系 |
| `--surface` | `#F7F8F3` | `#152225` | 卡面比纸亮一档（与明色同向）；亮度选到让 ink/surface 达 13.96 ≥ 明色 13.88 |
| `--ink` | `#1B2A2E` | `#EDEEE6` | **直接取明色的纸**——同一张纸，换到底下当字。这是「互换」而不是「取反」的直接体现 |
| `--ink-2` | `#5A6A6E` | `#A9B5B3` | 次级文字：在暗纸上 8.40:1，高于明色下的 4.83:1 |
| `--ink-3` | `#8B9799` | `#7E8C8D` | 元信息：暗底上 4.68:1（明色下 3.2:1），比明色**更好** |
| `--rule` | `#D2D6C9` | `#2E3F44` | 细线：与暗纸 1.61:1——细线本来就该是「看得见但不抢眼」，明色下同样是低对比 |
| `--indigo` | `#2E4A7D` | `#8AA9DE` | 藍染提亮到暗底上 6.84:1；色相保持在 217° 附近，仍是那个藍 |
| `--sulfur` | `#E8B93C` | `#F0C95A` | 硫磺只需微提（明色本就亮）；暗底 10.26:1 |
| `--rust` | `#B4472C` | `#E0785C` | 铁锈提亮到 5.45:1——它是**唯一告警色**，暗色下更要看得清 |
| `--moss` | `#6B7A5A` | `#94A585` | 苔绿提亮到 6.20:1，插画辅助用 |
| `--indigo-soft` | `#DDE3EE` | `#1E2A3E` | 淡底类在暗色下改成**深色底**：它们的角色是「底」，不是「亮」 |
| `--indigo-mist` | `#8FA3C4` | `#5C7099` | 降权藍在暗底上压暗一档，保持「比主色弱」的关系 |
| `--moss-soft` | `#E0E4D6` | `#222A22` | 保护只读底，同上 |
| `--sulfur-soft` | `#F6E5B3` | `#3A3320` | 高亮划线底，同上 |
| `--rust-soft` | `#F0DAD2` | `#38241E` | 阻塞级底纹，同上 |

11 个语义别名（`--bg-page` / `--text-body` …）在两块里都指向同名基础 token，
**没有另起一套映射**：换一套映射就等于暗色下的语义与明色不同。

## 5. 双通道与优先级（acceptance②）

三块的**顺序有意义**：

```
@media (prefers-color-scheme: dark) { :root { …暗色… } }   ← 跟随系统
[data-theme="dark"]  { …暗色… }                            ← 手动切暗
[data-theme="light"] { …明色… }                            ← 手动切明（压过系统暗色）
```

**第三块是关键**：只做 `prefers-color-scheme` 的话，系统是暗色时用户在应用里
**切不回明色**——那不是「支持暗色」，那是「强制暗色」。
它必须写在 media **之后**才压得住，判据逐条钉着位置关系。

## 6. 变异考：十三个，一个先活了下来

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 删掉一个 token 的暗色值 | acceptance① | **1 failed** ✓ |
| ② 两条通道给不同的值 | acceptance② | **1 failed** ✓ |
| ③ 某个 token 的暗色值抄成明色值 | 覆盖 | **5 failed** ✓ |
| ④ 去掉 media 通道 | acceptance② | **2 failed** ✓ |
| ⑤ 去掉 data-theme 通道 | acceptance② | **5 failed** ✓ |
| ⑥ 去掉 `[data-theme="light"]` | acceptance② | **1 failed** ✓ |
| ⑦ 把 light 块挪到 media 之前 | 优先级 | **1 failed** ✓ |
| ⑧ 暗色 ink 调暗到对比度低于明色 | acceptance③ | **2 failed** ✓ |
| ⑨ 暗色 surface 调亮到 ink/surface < 明色 | acceptance③ | **1 failed** ✓ |
| ⑩ 把某个暗色值改成明色的算术取反 | acceptance④ | **1 failed** ✓ |
| ⑪ 暗纸改成纯黑 `#000000` | 色相同族 | **1 failed** ✓ |
| ⑫ 关闭横幅去掉日期 | acceptance⑥ | **17 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑬ 关闭横幅去掉卡号 | acceptance⑥ | **1 failed** ✓（补判顺带） |

**⑫ 为什么能活**：判据是「横幅前 8 行里有 `2026-08-04`」，而横幅正文那句
「owner **2026-08-04** 裁决」把它喂饱了——去掉**关闭行**上的日期毫无反应。
改成判在**关闭那一行**上（含「已关闭」的那行必须同时有日期与卡号）。
本仓第二十一次同型。

**一条判据自己先写错了**：`_dark_media()` 原本从 media 标记切到**文件末尾**，
于是把后面 `[data-theme="light"]` 的声明也算进了 media 块，
「两条通道同值」那条去比了两个不相干的块。改成只取 media 块内那一段。
**判据的取值范围写错，比判据判错更难发现**——它红得理直气壮。

十三次变异后 `colors.css` 的 sha256 与变异前逐位相同。

## 7. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_dark_palette.py -q → 17 passed
全局门: ruff check . --no-cache → All checks passed!
        pytest -q → 2973 passed
        cd web && npm test -- --run → 62 files / 574 passed（既有面不倒）
        node tools/no_external_fonts.mjs web → exit 0（判据内跑）
        tools/gauge_map.py → 查不到尺子 0
```

**实测：假绿消失了。** 重跑 K6-01 的像素取证（`C:\pwenv` 解释器）：

```
dark : rgb(237,238,230) on rgb(21,34,37)
light: rgb(27,42,46)   on rgb(247,248,243)
```

此前两个主题量到**同一组数**（`docs/blocked/EYE-02-TWO-THEMES-MEASURES-ONE.md`
记的就是这件事），现在两组数真的不同了。**判据本身的补强是 DARK-02 的事**——
本卡只出板；判据仍会对「两次量到相同」放行，那条洞由下一张卡关。

**① acceptance 映射**

| acceptance | 测试 |
|---|---|
| ① 逐 token 暗色对照、覆盖率 100% | `test_the_light_palette_still_has_its_tokens`、`test_every_light_token_has_a_dark_counterpart`、`test_no_dark_value_is_the_light_value` |
| ② 双通道 + data-theme 压过系统偏好（两方向各一条） | `test_the_media_channel_exists`、`test_the_attribute_channel_exists`、`test_an_explicit_light_choice_beats_the_system_preference`、`test_the_explicit_dark_choice_also_works_without_the_system_preference`、`test_the_two_dark_channels_declare_the_same_tokens` |
| ③ 对比度不退化且过 AA，尺子复用 EYE-02 | `test_dark_contrast_is_not_worse_than_light`（3 例）、`test_the_accents_stay_readable_on_the_dark_surface` |
| ④ NEVER 取反、色相同族 | `test_no_dark_value_is_the_arithmetic_inverse_of_the_light_one`、`test_the_dark_palette_keeps_the_paper_and_ink_hue_family`；逐档依据见 §4 |
| ⑤ 既有前端测试不倒、no_external_fonts exit 0 | `test_no_external_font_sneaks_in_with_the_dark_palette`；574 条前端测试实跑全绿 |
| ⑥ 关闭那张问题单 | `test_the_blocked_doc_is_closed_with_a_banner` |

**② 无冻结件偏离**：`contracts/`、`flint/domain/` 未触碰；
`_ds` 的**明色块一个字节没动**（只追加三块）；零新增依赖；
`requirements.lock` / `package.json` 未动。

**③ 禁用词**：两个产物文件 + 本 trace 六词 0 命中。

**④ 复用**：对比度判据直接调 `tools/visual_assert.py#contrast_ratio` 与
`AA_NORMAL_TEXT`（**NEVER 另造一把尺子**——两把尺子会给出两个数，
那时没人知道该信哪个）；语义别名沿用既有映射，没另起一套。

**⑤ 装载预算**：约 7k tokens。

## 8. owner_review：三件要 owner 拍板的

1. **这套暗色值认不认**。它是我按「纸与墨互换、色相同族」这条原则挑的，
   逐档依据在 §4，**每一档都有实测对比度**。但配色终归是设计判断——
   owner 若不认，改的是 `colors.css` 里那 16 个基础 token 的值，判据不用动
   （判据钉的是关系：覆盖率、双通道、对比度不退化、不取反）。
2. **`_ds` 的可改边界**。本卡改了供应商资产（§3.1），依据是 owner 的裁决。
   建议把这条边界写进 DECISIONS：**允许改的是暗色板，不是整份资产从此可改**。
3. **默认主题是什么**。现在没有 `data-theme` 时跟随系统。若产品要「默认明色、
   用户手动才暗」，那要在应用层写一个默认 `data-theme="light"`——
   那是 UI 卡的面，本卡没做。

## 9. 登记未做

1. **判据本身的假绿没关**：EYE-02 仍会对「两次量到相同」放行。**那是 DARK-02**。
   本卡把板做出来了，所以那条洞现在**量得出来**（§7 的实测就是证据）。
2. **只验了片段级像素**：`.ui-probe/workbench_switch.json` 是片段取证，
   **没有整屏截图**。整屏是 UI 卡的验收面（`UI-01` 要明暗两主题截图存档）。
3. **没有做主题切换的 UI**：切换器（一个按钮把 `data-theme` 写到 `<html>` 上）
   属 UI 卡，本卡只出板。
4. **纹理 token 没有暗色对照**：`tokens/texture.css` 里的 `--tex-*` 是底纹图案
   （`repeating-linear-gradient` 之类），不是颜色 token，本卡的覆盖率判据
   只管 `colors.css`。暗底上底纹是否需要另调，等 UI 卡真正用到时再看。
