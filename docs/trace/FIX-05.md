# FIX-05 · 语言与地区表单在 390px 横向溢出 48px

**卡** `docs/steward/tasks-v041-b4.json#FIX-05` · **cycles 1（oneshot）** ·
**self_review = true** → §4 · **owner_review = false** · **依赖** 无

## 1. 装载清单

卡面 FIX-05 · `docs/blocked/LOCALE-FORM-OVERFLOWS-ON-MOBILE.md` ·
`web/app/globals.css` 的 `.app-shell*` 段 ·
`web/components/locale-settings/LocaleSettings.tsx` 的类名 ·
`web/public/_ds/*/tokens/spacing.css` · `scripts/ui_probe.py` 的 `--json` 形状。
约 9k tokens。

## 2. 单子猜的地方不是溢出的地方

单子写着「溢出的是表单那一行——三件套不换行」，并给下一张卡留了
「`.locale` 那一行加 `flex-wrap` 即可（一行样式）」。

**两句都是错的。** `.locale` 根本没有任何样式规则——`locale__*` 那些类名在
`globals.css` 与 `_ds` 里一条都查不到。

逐元素量（390px 视口下把所有 `right > clientWidth` 的元素列出来）：

```
MAIN    .app-shell__body   right=438  width=438   ← 越界的只有它
SECTION .screen            right=414  width=390
HEADER  .screen__header    right=414  width=390
SECTION .locale            right=414  width=390   ← 单子怀疑的这个，宽度正好是视口
```

**根因算得出来**：

```css
.app-shell__body {
  inline-size: 100%;      /* = 390 */
  padding: var(--sp-5);   /* = 24px（tokens/spacing.css），且默认 content-box */
}
```

390 + 24×2 = **438**，与单子实测的 48px 溢出量对得上小数点。

**一个能对上小数点的算式，比一句「大概是没换行」值钱得多。**
后者把下一个人往错的地方指了一次——这件事写进了单子的关闭段。

## 3. 修法与实测

一行：`box-sizing: border-box`。

```
改前  desktop viewport=1440 scroll=1440 overflow=False
      mobile  viewport=390  scroll=438  overflow=True    ← 48px
改后  desktop viewport=1440 scroll=1440 overflow=False
      mobile  viewport=390  scroll=390  overflow=False   err=0
```

**NEVER 改成写死宽度**（比如 `width: 342px`）：数字当场也对，
但每次改内边距都要有人回来重算一遍，而没有任何东西会提醒他。

**这条容器是所有屏共用的**，所以修它等于一次修掉十三屏——
单子末尾问的「其余十几屏有没有同样的事」，答案是**有，同一处**。
全量逐屏取证是 `FIX-06`。

## 4. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_locale_mobile.py -q → 8 passed（真跑探针，约 31s）
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 301 source files
            pytest -q               → 见收卡时那一行
前端:       npm test -- --run → 754 passed；npx tsc --noEmit → 无输出
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 390px 下 scroll_width 不超视口 | `test_the_locale_screen_does_not_overflow_on_a_390px_viewport`（两主题各一次） |
| ② 用 `EYE-02` 的量法取**真实** scroll_width，NEVER 只断言类名在 | `_probe()` 真起 `scripts/ui_probe.py --json`；探针或前端缺席时 **skip 并说清缺什么**，NEVER 当它通过 |
| ③ 明暗两主题各一次、桌面不倒 | `parametrize(["dark", "light"])` × 两条（mobile / desktop） |
| ④ 关闭单子 | `test_the_ticket_is_closed_and_records_the_wrong_guess`——**判据要求单子写下「猜错了」**，只写「已修复」不算 |

另有两条钉住修法本身：`test_the_container_counts_its_padding_inside_its_width`
（border-box）、`test_no_bare_pixel_value_was_introduced`（不许裸像素、内边距仍走 token）、
`test_the_fix_is_on_the_container_not_on_the_form`（**不许给 `.locale` 加样式**——
加了会让下一个人以为溢出是那儿来的）。

**② 改既有文件一处**（`web/app/globals.css`，卡上 outputs）：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `web/app/globals.css` | `.app-shell__body` 加 `box-sizing: border-box` + 一段说明根因与算式的注释 | 卡的正题；注释是为了让下一个人不必重量一遍 |
| `tests/v041/test_ui_restyle.py` | 裸像素扫描先整块剥掉 `/* … */` 再扫 | 上面那段注释里写着算式（`24px`、反例 `width: 342px`），**当场被判成「写死了间距」**——原来的 `ln.split("/*")[0]` 只砍得掉同行注释，砍不掉跨行块。这是本批**第六次**「说明问题的那句话被当成犯下问题」（`AUTH-02`/`AUTH-05`/`WIRE-09`/`WIRE-10`/`WIRE-12`/本处）。剥完注释后另跑一次阴性对照（把 `padding` 真写成 `24px`）→ 红，确认扫描面没被剥坏 |

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；`flint/` 一行未改；未新增依赖（playwright 恒在 `C:\pwenv`）。

**③ 变异考 3 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 去掉 `border-box`（退回缺陷态） | 红 3 条，报「移动视口横向溢出 48px」 |
| ② 换成写死 `width: 342px` | 红 |
| ③ **照单子的猜想改**：不修容器，给 `.locale` 加 `flex-wrap` | 红 4 条，仍是 48px——**这条把「猜错了」量了出来** |
| ④ 假变异对照：文件末尾加一行注释 | 全绿 8 passed |

变异③ 是本卡最值得留的一条：它证明照单子那句建议改**一点用都没有**。

**④** 装载约 9k tokens；**⑤** 禁用词六词 0 命中。

## 5. 登记未做

1. **没有加全局 `*, *::before, *::after { box-sizing: border-box }`**。
   那是这一类问题的通解，但它会改变**每一个**有内边距元素的宽度——
   在十三屏都量过之前动它，等于拿没量过的十二屏赌一把。
   `FIX-06` 正是那次全量清点，**到时候手里有数据再决定**。
2. **`.locale` 至今没有样式**：这一屏靠浏览器默认排版活着。
   它现在不溢出，但那是「恰好」不是「设计」。要不要给它一份正经样式，
   属设计面，不在本卡。
3. **`FIX-05` 收卡前观测到一次前端红、名字没抓到**：
   登记在 `docs/blocked/ONE-UNNAMED-FRONTEND-RED-NOT-CAPTURED.md`。
   与本卡验收面（横向溢出）无关，所以没有停下——但也 NEVER 吞掉。
