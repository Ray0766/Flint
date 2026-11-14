# PAL-01 · trace

**卡**：换板——v4 的值写进 `_ds/tokens/colors.css`（组件侧零改动）
**日期**：2026-08-12 ｜ **状态**：verified

## 换板对照表（16 个 token，明 / 暗）

| `_ds` token | v4 变量 | 明色 | 暗色 | 来源 |
|---|---|---|---|---|
| `--paper` | `--bg` | `#f2ede4` | `#191612` | 直搬 |
| `--paper-2` | `--panel2` | `#ece5d7` | `#2c261d` | 直搬 |
| `--surface` | `--panel` | `#faf7f1` | `#211d17` | 直搬 |
| `--ink` | `--ink` | `#26221c` | **`#f9f0e2`** | 暗色**提亮**（见下） |
| `--ink-2` | `--sub` | **`#736a59`** | `#9a8e7d` | 明色**压暗**（见下） |
| `--ink-3` | `--unk` | `#8f8574` | `#93887a` | 直搬 |
| `--rule` | `--line` | `#ded4c2` | `#393226` | 直搬 |
| `--sulfur` | `--accent` | `#d1531f` | `#e8763a` | 直搬 |
| `--indigo` | `--accent` | `#d1531f` | `#e8763a` | **与 sulfur 合并**（见下） |
| `--rust` | `--bad` | `#b03a2e` | `#d4695e` | 直搬 |
| `--moss` | `--ok` | `#4f7d43` | `#7fae72` | 直搬 |
| `--sulfur-soft` | `--accent-soft` | `#f6ded0` | `#43301f` | 直搬（v4 这一格本来就是 hex） |
| `--indigo-soft` | `--accent-soft` | `#f6ded0` | `#43301f` | 跟着合并 |
| `--indigo-mist` | （v4 没有） | `#e39877` | `#95532c` | accent 与 soft 的**逐通道中点** |
| `--moss-soft` | `--ok-soft` | `#dddfcf` | `#292e21` | rgba **合成到同主题 `--paper`** 上 |
| `--rust-soft` | `--bad-soft` | `#ead8ce` | `#37231e` | 同上 |

soft 那三格的合成结果与卡面给的数**逐字相同**——它们是算出来的，不是抄的，
判据也算一遍再比（抄一个色号的话，判据钉的是我抄得对不对）。

## 两处**没有照抄 v4 原值**（卡面点名，实测复现）

| 处 | v4 原值 | 实测 | 落地值 | 实测 | 理由 |
|---|---|---|---|---|---|
| 明 `--ink-2` / `--paper` | `#867b67` | **3.57** | `#736a59` | **4.58** | 低于 AA 正文线 4.5 |
| 暗 `--ink` / `--surface` | `#ede5d7` | **13.4** | `#f9f0e2` | **14.84** | 低于明色同一对的 14.79，`DARK-01` acceptance③ 要求暗色**不退化** |

改前值 / 改后值 / 实测比值三样都写进了 `colors.css` 的注释，判据逐条比对它们。
判据还**两个方向各量一次**：v4 原值确实不过线（否则这次偏离是多余的）、改后值过线。

## `--indigo` 与 `--sulfur` 合并（照 v4 原意，不是手滑）

v4 自己写的就是 `a{color:var(--accent)}`——它**没有第二个性格色**。
`colors.css` 的注释里点名这件事，并写明**反悔只需把 `--indigo` 一族三行改回蓝值**
（明 `#2E4A7D`/`#DDE3EE`/`#8FA3C4`，暗 `#8AA9DE`/`#1E2A3E`/`#5C7099`）。
判据同时判「两值相等」与「文件里点名了这是合并」——只判前者的话，
下一个人会把它当成复制粘贴的手滑「顺手修好」。

## 对比度四条全部实测过线

```
--ink/--paper     明 13.56 · 暗 15.96   两边 >=4.5 且 暗 >= 明
--ink/--surface   明 14.79 · 暗 14.84   同上
--ink-2/--paper   明  4.58 · 暗  5.61   同上
--indigo/--sulfur/--rust 在暗 --surface 上 5.65 / 5.65 / 4.77   >=3.0
```

尺子是既有的 `tools/visual_assert.py`（WCAG 2.x），**NEVER 另造一把**。

## 「组件侧零改动」是数得出来的

换板**之前**先落一份实况：`.ui-probe/palette/var-usage-before.json`
（`web/{app,components,lib,views,design}` 下逐 token 的 `var()` 出现次数 = 80 个 token；
`web/` 下每个文件的内容指纹 = 275 个文件，`tokens/colors.css` 自己除外）。
换板后判据逐条比：**80 个 token 的出现次数逐个相等**，275 个文件**指纹逐个相等**、
无新增、无删除。这一条不成立就说明有人在组件里写死了色值。

## 缺一格：`--warn` 一族没落，且它不是被忘了

卡面 acceptance④ 要落 `--warn`/`--warn-soft`，而 `DEC-060` 第一条把 `--warn`
**逐字**列进「NEVER 引进本仓」的 12 个名字里。两处矛盾 →
按 `worker.md §1.4` 停下开单、**NEVER 自行择一**：
`docs/blocked/WARN-TOKEN-NAME-CONTRADICTS-DEC-060.md`。

单里写清两种口径（甲：照卡面用 `--warn`，那条禁令破一个口子；
乙：改叫本仓材料名如 `--ochre`，与卡面字面不符）、值已算好、
以及一件卡面没提而我实测到的事：**明色 `#a3701c` 在 `--surface` 上只有 4.01**，
够图形与大字号（>=3.0），**不够正文线 4.5**——这一格要连同名字一起定。
今天没有任何组件读它（`var(--warn` 出现 0 次，实测），所以缺着不影响任何一屏。

## 判据自己错一处

`_landed()` 切 `colors.css` 四个块的那条正则写的是行首锚点却**没带 `MULTILINE`**——
换板那天文件开头多了一段说明注释，于是它不再落在 `:root` 上，四个块一个都切不出来，
55 条判据整片红成同一句话。红的是判据自己：它把「文件从这里开始」当成了「这一行从这里开始」。

## self_review

① 判据 ↔ acceptance：直搬 20（10 token × 2 主题）· 两条通道同值 1 · 手动明色 1 ·
   两处偏离 2 + 就地写明 1 · soft 合成 4 + sulfur-soft 1 · 合并 2 + 声明 1 + mist 2 ·
   对比度 3 + 3 · 零改动 2 · v4 名字 11 · 缺的那一格 1 = **55 条**。
② 无冻结件偏离：`contracts/` 未读未改。
③ 无禁用词：命中 0。
④ 复用断言在位：尺子走 `tools/visual_assert.py`；期望值从设计稿与 `colors.css` 现场解析。
⑤ 装载未超预算：约 14k tokens。

## 产出文件

```
web/public/_ds/.../tokens/colors.css                   换板（web/ 下唯一被改的文件）
tests/v041/test_palette_v4.py                          55 条判据
.ui-probe/palette/var-usage-before.json                换板前的实况
docs/blocked/WARN-TOKEN-NAME-CONTRADICTS-DEC-060.md    新单
```
