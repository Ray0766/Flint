# TAIL-01 · 清掉 steward 已答复的四张单

**第 16 批第二张卡。** 1 cycle。四张单的答复都已经在单子里，本卡做的是落地。

## 一、装载清单

`docs/steward/tasks-v041-b16.json#TAIL-01` · 四张单全文 ·
`_ds/tokens/colors.css`（175 行全文）· `web/app/globals.css:1387-1460 / 1810-1860` ·
`tests/v041/test_palette_v4.py:340-450` · `test_dark_palette.py` 全文 ·
`test_plaza_multiselect_combo.py`（只读，指纹）· `test_plaza_combo_bar.py:40-100` ·
`web/components/plaza/PlazaCards.tsx:180-300` · `tools/visual_assert.py` 接口。
约 30k tokens。

## 二、① `--warn` → `--ochre`：值一个字不动

名字取本仓的**材料名**法（paper / ink / rule / indigo / sulfur / rust / moss 全是材料），
`DEC-060` 把 `--warn` 逐字列进「NEVER 引进本仓」的 v4 记法。

四个块各落一份（`:root` / media dark / `[data-theme=dark]` / `[data-theme=light]`）：
明 `#a3701c` / `#e9deca`，暗 `#c99a4a` / `#352b1b`。

**soft 是算出来的**，判据现算一遍再比：
`rgba(180,130,40,.14)` 合到明 `--paper #f2ede4` = `#e9deca`；
`rgba(200,155,75,.16)` 合到暗 `--paper #191612` = `#352b1b`。与单子里记的逐字相同。

**用途边界写死并各配判据**（卡面点名要的）：`#a3701c` 在明 `--surface` 上实测 **4.01**
——够图形（3:1）不够正文（4.5）。所以：
- 正向：全仓没有一处 `color: var(--ochre)`；
- **阴性对照**：把它挂到一段正文上 MUST 被抓住，且报得出 4.01 这个数
  （改在内存里，NEVER 动真文件）；
- 允许的用法（background / border）**不许被误伤**——阴性对照里一并判了。

暗色那一格 6.55 过得了正文线，但边界按明色定（一个 token 只能有一条用法）。

## 三、② 广场上限：卡面错、既有纪律对

单子转 closed，关闭那节逐字写明「卡面 acceptance⑤ 错、既有纪律对」。
`test_plaza_multiselect_combo.py` **一个字没动**——用 sha256 指纹钉住
（`0ec676bd…`；真要改先说明为什么再改指纹）。

### 关掉时核到、但**没有顺手改**的一处

空态那句 `plaza.combo.empty_hint` 今天是「从上方卡片『+ 组合』加入 **2~5** 张热点卡」
——它**确实说了一个上限**。但它是 v4 设计稿原文，由另一条已 verified 的判据
（`test_plaza_combo_bar.py::test_the_wording_comes_from_the_design_file_verbatim`，
断言 `"加入 2~5" in 设计稿`）钉着照抄。

改它要同时改那条判据，那是**文案**问题、不在本卡三张单里，
本批规则 `no_new_fronts` 逐字写着「碰到别的问题一律开单，NEVER 顺手修」。
故：**如实登记在单子的关闭节里**，判据只判三态（还差几张 / 假设必填 / 就绪）不说上限，
并从**用途**这一侧再判一次「广场没用那句『一次最多』」。

## 四、③ 药丸条与吉祥物：26 行搬进 token 层

**26 行 = 25 处定义 + 1 个规则里的裸 `rgba`**（`.anime-nav__mascot-head` 的描边）。
后者收成 `--mascot-shadow`，于是 `web/` 下除 `_ds/tokens/` 之外一个颜色字面量都不剩，
新加的全仓判据因此**没有白名单**（白名单一开，下一个例外就有先例可循）。

分法按**它们今天的实际行为**，不是重新设计：五个恒定（吉祥物三色 + `--nav-ink-on-*`）
只在 `:root` 一次，六个跟主题翻的在四个块里各一份。改前 `globals.css` 就是这么分的。

`[data-theme="light"]` 那一块也补了那六行——少了的话，系统暗色 + 用户手动切明色时，
media 里那套暗色药丸条没人覆盖得掉，整页是明的而导航条还是黑的。

### 「搬的是位置不是值」怎么证的

搬**前**在真浏览器上量一次、搬**后**再量一次（`tools/ui_probe_nav_tokens.py`），
两主题 × 13 个 token × 6 个元素。

**第一版判据比的是 token 文本，实测当场被它抓到**：11 个 token 搬前搬后文本全不同
（`#ffffffb8` → `rgba(255, 255, 255, 0.72)`）。查下去是**格式差别不是颜色差别**——
`globals.css` 过 Next 的 CSS 管线被压成 8 位 hex，而 `_ds/tokens/colors.css` 是
`web/public/` 下的静态文件，原样送到浏览器。

改法：**元素层判逐字相同**（浏览器算出来的值，两条管线在这一层已经合流，
它才是「屏上有没有变」的直接证据——实测 12 项逐字相同，零差异），
**token 层判颜色相同**（规范化后比），并给规范化本身配一条阴性对照：
透明度变了 / 差一个色阶 / 投影形状变了，三种都要抓得住。

## 五、④ `DEC-060` 措辞：steward 认下

单子转 closed。`DECISIONS-v04.md` **一个字没改**（append-only，回头改既有条目是
`DEC-056` 立过的死手），判据钉着那句出处还在。

## 六、连带碰到的四处（每一处都在这里说明为什么非改不可）

搬家改的是**颜色板的形状**，于是三条既有判据的前提变了。它们的**意图一个字没动**，
改的是量法：

1. `test_dark_palette.py::test_every_light_token_has_a_dark_counterpart`
   ——多了一族**故意不跟主题翻**的固定色。改成**判等值**（`THEME_CONSTANT` 六个），
   NEVER 改成「跳过所有没有对照的」：那样下一个漏掉暗色值的 token 会自己溜进来；
2. 同文件的取反判据 ——`--nav-shadow` 是「长度 + 颜色」的复合值，`parse_color` 当场抛。
   加 `_is_plain_colour` 跳过复合值；
3. 同一条判据把 `--nav-surface` 判成「明色的算术取反」（白 ↔ 黑）。
   **它守的是「取反会把色相翻到补色去」，而纯白纯黑没有色相可翻**；
   两边透明度还不同（0.72 / 0.5）——机器取反不会顺手改透明度。
   改成**中性色不在量程内**（按色相判，NEVER 按名字放行：
   那样下一个真被取反出来的**有色** token 会跟着溜过去）；
4. 同文件两条判位置的判据用 `css.find('[data-theme="dark"]')` 比先后，
   而我在 `colors.css` 的注释里解释「哪条规则管暗色」时写了这个选择器
   → **尺子量到了注释的位置**。改成先剥注释再 find。
   本仓这一类（尺子读了注释）此前栽过六次，**第七次就在这里**。

## 七、自审（`self_review=true`）

1. **测试真实覆盖 acceptance**：①→ 四条（落地 / 禁名 / soft 现算 / 用途边界正反各一）；
   ②→ 三条（指纹 / 三态不说上限 / 代码层不判上限）；③→ 四条（搬到位 / 全仓零字面量 /
   搬前搬后逐个相等 ×2 主题 / 规范化的阴性对照）；④→ 两条（四张单按新规矩关 ×4 参数化 /
   出处那句还在）。
2. **无冻结件偏离**：本卡不碰 `contracts/` 与 `flint/`。
3. **无禁用词**：新写与改动段落扫过 = 0。
4. **复用断言在位**：对比度走既有 `tools/visual_assert.py`（NEVER 另造一把尺子）；
   soft 合成走 `--rust-soft` / `--moss-soft` 的既有规则。
5. **装载未超预算**：约 30k / 40k。

## 八、`verify_cmd`

```
PYTHONIOENCODING=utf-8 pytest tests/v041/test_tail_01.py -q → 21 passed
连带跑：test_dark_palette + test_palette_v4 + test_combo_wire → 121 passed
```
