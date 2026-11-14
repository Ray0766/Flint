# PAL-03 · trace

**卡**：真栈重拍取证（换板之后）
**日期**：2026-08-12 ｜ **状态**：verified

## 一、先数清楚（清单是跑出来的，落在 `.ui-probe/palette/inventory.json`）

| 项 | 数 |
|---|---|
| png | 197 |
| json | 44 |
| **有判据在读的 json** | **41** |
| 读它们的测试文件 | 54 |

卡面写的是「134 张 png / 30 份 json / 47 个判据文件」——那是出卡当天的数。
第 14 批又落了六张整屏 + 五张流程图 + 五份 `report.json`，所以今天更多。
**清单不是抄卡面的，是跑出来的**：抄一份的话，下一次重拍会漏掉中间新增的那些。

## 二、重拍了哪些（换板后真栈实拍）

```
ds_tokens.json            scripts/ui_probe.py --tokens --json --url http://localhost:3000/…
ds_components.json        删掉后由 tests/v041/test_ds_bundle_wired.py 自动重拍
hotspot_card_format.json  删掉后由 tests/v041/test_hotspot_card_format.py 自动重拍
eye04/report.json + 六张  tools/ui_probe_palette.py（三视口 × 两主题，视口矩阵照 EYE-04 的键）
palette/onscreen.json     同上（屏上量到的颜色 vs token 声明）
```

其余没重拍的旧图**留了一页说明**：`.ui-probe/换板前的旧图说明.md`
（哪些是新板、哪些是旧板、为什么不一次全重拍）。**NEVER 让旧图默默当现状**。

## 三、屏上量到的就是 token 里的值

```
1920/1440/390 × light  body 底 rgb(242, 237, 228) == --paper 声明 rgb(242, 237, 228)
1920/1440/390 × dark   body 底 rgb(25, 22, 18)    == --paper 声明 rgb(25, 22, 18)
明 != 暗（两个主题量到的确实是两个东西）
换板前后同一屏同一主题的截图**字节不同**
```

## 四、重拍**暴露出三处**，逐条分辨过（`gauges_follow_the_ruling`）

### ① 换板前那份 `ds_tokens.json` 是**假绿**（最要紧的一处）

它的 dark 页记着 `--surface #F7F8F3 / --ink #1B2A2E`——**与 light 页一位不差**。
也就是说那次取证里暗色主题根本没生效（`EYE-02` 那个洞的同一种形状）。
而当时的判据用一条正则扫全 `colors.css`，后面的块覆盖前面的，
最终留下的是最后那个 `[data-theme="light"]` 块——**拿明色声明去比明色数值**，当然过。

改法（意图一个字不动，仍是「浏览器里取到的计算值 == `_ds` 里声明的值」）：
**明暗各比各的**（`:root` 一套，`[data-theme="dark"]` 覆盖上去一套），
并用保下来的那份旧产物做**阴性对照**——
`test_the_re_aimed_judge_would_have_caught_the_old_fake_green` 断言它现在会被判红。

### ② `EYE-04` 的「一行药丸条」在 390 上钉着**更早那一版屏**

重拍量到 390 的 `offsetTop [8, 54]`（两行）、`border-radius 24px`（不是 9999）。
那不是换板碰坏的，是 **`WB-01` 修 `NAV-BAR-OVERFLOWS-AT-390` 时选的折行**——
改前 7 项里后三项整个在屏外（`/workbench` 右缘 529 > 390）。

改法：**分档判**。宽屏两档照旧钉「一行 + 全圆角」；
390 那一档改判「折成几行都行，但**每一项都在屏内**、且条仍是圆角的（≥8px）」。
NEVER 把窄屏整档放过——那样折行退回溢出时又没有人看着了。

### ③ 「最右元素右缘 ≤ 视口宽」这条尺子要**减去裁剪**

390 上量到 838：`div.plaza-stack__slot`（卡堆，`absolute` 排开的一叠）。
它整段落在一个 `overflow:hidden` 的容器里，**屏上根本没露出来**。
不减裁剪就把它算成溢出，等于逼着下一个人去「修」一个本来就该被裁掉的东西。

改法：逐层往上找带 `overflow != visible` 的祖先，把右缘夹到祖先的右缘。
改后三视口逐一 `rightmost == vw`（1920/1440/390），而药丸条那条溢出仍然咬得住
（它是 `fixed`，没有任何祖先裁它）。

## 五、探针自己错两处（当场改）

1. **按记忆写选择器**：第一版量 `.app-shell__nav` + `nav a`，实际屏上是
   `.app-shell__nav-link` + `nav.anime-nav`（`NAV-ANIME-01` 之后的形状）——
   量到 0 个链接，于是「顶栏是不是一行」拿一个空数组去判，**六屏恒红**。
   红的是探针，不是屏。
2. **量了但没写进产物**：`rightmost` 与 `navRadius` 两格在 `MEASURE` 里算了，
   却没进 `report.json`——判据 `KeyError`。量到与落盘是两件事。

## 六、顺带记一处**过期默认值**（没改，只登记）

`scripts/ui_probe.py` 的默认 URL 写的是 **`http://localhost:3001`**，
而 demo 的前端在 **:3000**。不带 `--url` 直跑就是「前端未运行：连接被拒」——
一条会让人以为栈没起的假红。本卡按 `stale_premise` 核过并显式传了 `--url`；
改那个默认值不在本卡 outputs 里，登记在这里与完成态报告里。

## self_review

① 判据 ↔ acceptance：清单落盘 1 · 旧图说明 1 · 屏上 == token 6 + 判准出处 1 ·
   两主题不同 1 · 换板看得见 1 = **11 条**（另有 `test_eye04` 既有 45 条照旧跑）。
② 无冻结件偏离：`flint/` 未改。
③ 无禁用词：命中 0。
④ 复用断言在位：视口矩阵与 `report.json` 的键照 `EYE-04`；`test_eye04` 的四条老线一条没放宽
   （390 那一档改的是**方向**，理由写在判据的注释里）。
⑤ 装载未超预算：约 12k tokens。

## 产出文件

```
tools/ui_probe_palette.py                重拍脚本（三视口 × 两主题 + 屏上颜色）
tests/v041/test_palette_onscreen.py      11 条判据
tests/v041/test_ds_wired.py              明暗各比各的 + 阴性对照（出 outputs，见完成态报告）
tests/v041/test_eye04.py                 390 那一档分档判（出 outputs，同上）
.ui-probe/eye04/*.png + report.json      重拍
.ui-probe/palette/{inventory,onscreen}.json + before/   清单、屏上取证、换板前的对照
.ui-probe/换板前的旧图说明.md              哪些是新板、哪些是旧板
```
