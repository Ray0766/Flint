# HYG-01 · 关闭三张根因已消失的陈旧单 + 单据状态机读化

**卡** `docs/steward/tasks-v041-b3.json#HYG-01` · **cycles 1（oneshot）** ·
**self_review = true** → §5 · **owner_review = false** · **依赖** 无

## 1. 装载清单

卡面 HYG-01 · `docs/blocked/` 全部 34 张单的头部 + 三张待关单全文 ·
`docs/progress-v04.jsonl` 的 I18N 段 · `web/package.json` 的依赖段。
约 14k tokens，预算 40k 以内。

## 2. 三张单的根因**逐条实跑**（acceptance④：NEVER 凭印象关单）

**① `I18N-01`** —— 根因原话：「实测 `web/package.json` 里**没有** next-intl」

```
$ grep -n "next-intl" web/package.json
15:    "next-intl": "4.13.4",
```

**② `I18N-FRONTEND-GROUP`** —— 与 `I18N-01` 同源，另加两项：

```
13 张 I18N 卡在 docs/progress-v04.jsonl 里的末态：全部 verified
  I18N-01/02/03/04/04-a/04-b/05/06/06-a/06-b/07/08/09

前端产出逐个在盘上（七项全在）：
  web/messages · web/components/native-name · web/components/quote-slot ·
  web/stores/prefs.ts · web/components/region-switch ·
  tools/orthogonality_check.py · tools/i18n_scan.mjs
```

**③ `V0-PROMPTS-LOCK`** —— 根因是那两个测试红着（原文 `2 failed, 1348 passed`）：

```
$ python -m pytest tests/m2/test_m2_004.py tests/fe_core/test_section_prompt.py -q
.........
9 passed in 0.05s
```

三段输出都抄进了各自单子的关闭段，判据
`test_the_three_stale_sheets_carry_their_evidence` 判的就是它们在不在——
**「根因消失了」这句话本身不是证据**。

## 3. 一行机读状态：因为「没关」与「忘了写」长得一模一样

改前 34 张单里，「这张还开着吗」只能靠读全文猜：

| 写法 | 张数 |
|---|---|
| 写在 H1 标题括号里（`（**已关闭** @2026-08-03）`） | 5 |
| 正文里的引用块横幅，格式各不相同 | 13 |
| **什么都没写** | 14 |
| `**状态**` 行埋在正文第 25 / 33 行 | 2 |

外加一个**真的坑**：`K1-02-SOURCE-CONTRACTS-MISSING` 正文里出现「已关闭」三个字，
说的却是 **reddit 的自助注册已关闭**——单子本身还开着。
**按字符串搜「已关闭」来数单子，会把它数成已解决。**

立的语法（每张单顶部一行，机器读得懂，缺了判红）：

```
**状态** open
**状态** closed · 2026-08-05 · `FIX-02`
**状态** historical · 2026-08-02 · 历史留存
```

落地后：**closed 21 · open 11 · historical 2**，合计 34 张，零缺标。

## 4. 关闭者可以是卡，也可以是 owner 裁决

实测五张（`CLAUDE-S3-LAG` / `DESIGN-21-FONTS` / `HOTSPOT-03` /
`REGION-06-AXIS-WORDING` / `SCHEMA-05-FROZEN-WORDING`）是被 **owner 裁决**关掉的
（`DEC-012` / `DEC-018` / `DEC-019`），不是被某张卡修掉的。

所以关闭者的形状是「卡号 **或** DEC 号」。只认卡号的话，这五张要么填不出来，
要么被人随手编一个卡号填上——**而编出来的那个卡号看起来和真的一样**。
每一条元数据都是从**单子自己的记录**里抄来的，一条都没有推测。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_blocked_sheets_state.py -q → 8 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3880 passed（LOC-01 收卡时 3873，本卡 +7）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 逐张核实并关闭三张 | `test_the_three_stale_sheets_are_closed_by_this_card`、`test_the_three_stale_sheets_carry_their_evidence`（判**实跑输出**在不在，不判「关了」两个字） |
| ② 两张标历史留存 + 醒目横幅 | `test_the_historical_sheets_are_marked_and_banner_ed`（横幅要在**顶部**：写在第 80 行的警告，读的人已经读完了才看到） |
| ③ 状态机读化，缺标记判红 | `test_every_sheet_declares_its_state_in_its_head`、`test_closed_sheets_carry_a_date_and_the_thing_that_closed_them`、`test_both_open_and_closed_actually_occur`（**非空对照**：全标 closed 也能让前两条全绿，而那正是把一堆没解决的问题一次抹掉的做法） |
| ④ NEVER 凭印象关单 | 见 §2 三段输出 + `test_the_reddit_sentence_is_not_mistaken_for_a_closed_sheet`（把那个坑本身钉住） |
| （自加） | `test_no_sheet_says_open_at_the_top_and_closed_right_below`（顶部不许有两个方向相反的真相） |

**② 改既有文件三处**（除 34 张单本体外）：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `docs/blocked/*.md` × 34 | 顶部插入机读状态行；三张转 closed 并附实跑输出；两张转 historical 并加顶部横幅 | **卡上 outputs**，本卡主体 |
| `docs/blocked/S1-COMMON-STATES-MISSING.md`、`LOCALE-SEAM-RULER-MISSES-REGION-CODES.md` | 正文里那行 `**状态** 已登记，本批不修` → `**当时的处置** …` | 它与顶部的机读行**同形不同义**（一个说单子状态，一个说当时那张卡的处置）。留着，机器会读到两个状态 |
| `tests/v041/test_demo_refs_seeded.py` | `assert "已关闭" in head` → `assert "**状态** closed" in head` | 那张单原本用 `**状态** 已关闭 · 关闭者 FIX-02` 记录，本卡把它换成机读语法后该判据必然红。**改判机读行是更强的判法**：按「已关闭」搜字符串正是会把 `K1-02` 数错的那种写法 |

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；未新增依赖。

**③ 变异考 7 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 一张单的状态行没了 | 红 |
| ② `closed` 却没有日期与关闭者 | 红 |
| ③ 按「已关闭」字符串把 `K1-02` 关掉 | 红 |
| ④ 抹掉证据（`I18N-01` 的实跑输出改成「根因已消失」一句话） | 红 |
| ⑤ 撤掉历史留存横幅 | **第一轮绿 → 改窄判据后红**（见下） |
| ⑥ 把所有开着的单一次性标成 `closed` | 红（2 条） |
| ⑦ 假变异对照：改一句无关正文 | 全绿 |

**⑤ 第一轮没咬住，是判据的洞**：原判据写的是
`"NEVER" in text and "当前状态" in text`——两个词在正文别处**各自**出现过，
于是把两处横幅都改软之后照样绿。这是**同一类洞的第三次**
（`UIX-02` ②/⑦ 也是「子串 vs 形状」）。改成判**同一行里两者同在**后当场红。

**⑤b 是假变异**：我把 `SUMMARY.md` 的横幅挪到文件末尾，判据仍绿——
查下来那张单**有两条横幅**（本卡加的 + 2026-08-03 的追记），挪走一条另一条还在头部。
**判据没错，是变异没改到被判的性质。**

**④** 装载约 14k tokens；**⑤** 禁用词六词 0 命中。

## 6. 登记未做

1. **21 张已关闭的单里，人话横幅与机读行并存**。那不是纯重复（横幅写清了为什么关），
   但两者方向相反的那天，读的人得自己猜哪个算数。
   本卡加了 `test_no_sheet_says_open_at_the_top_and_closed_right_below` 挡住最坏的一种
   （标 open 却写着已关闭），**没有**去统一 21 张单的行文——那是纯文字工。
2. **`open` 的 11 张没有逐张复核根因**。卡面要的是「关闭根因已消失的」，
   没说要复核仍开着的。哪张其实也能关，本卡不知道——
   **它只保证被关的那三张有证据，不保证开着的那 11 张都还该开着**。
3. **状态没有「谁在等」这一位**。`DEMO-REFS-NO-STORAGE-FACE` 等 owner、
   `WIRE-01-…` 等 owner、`UI07-LOCALE-TEST-IS-FLAKY` 等下一张卡——
   三者都是 `open`，但要的人不同。本卡在那张单上写了 `**待办归属**`，
   没有把它做成机读位（那要改 34 张单）。
