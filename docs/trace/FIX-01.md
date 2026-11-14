# FIX-01 · `"" in "%％"` 恒为 True——正文末尾的每个数字都被误判

**卡** `docs/steward/tasks-v041-b3.json#FIX-01` · **cycles 1（oneshot）** ·
**self_review = true** → §4 · **owner_review = true** → §5 · **依赖** 无

## 1. 装载清单

卡面 FIX-01 · `docs/blocked/GROUNDING-EMPTY-TAIL.md` 全文 ·
`flint/grounding/__init__.py` 的 `extract_numbers` / `_cjk_numbers` /
`_number_present` / `_check_date` 段 · `tests/v041/test_cjk_numerals.py`
里那条钉缺陷的判据。约 7k tokens，预算 40k 以内。

## 2. 一行代码，两个后果，都是**放松**

```python
tail = text[m.end():m.end() + 1]     # 正文末尾的数字 → tail == ""
is_percent = tail in "%％"           # "" in "%％"        → True
has_unit  = tail in _QTY_UNIT        # "" in "%％倍万亿…"  → True
```

**Python 里空串是任何字符串的子串。** 修前实测：

| 输入 | 修前 | 修后 |
|---|---|---|
| `发布于 2024` | `('quantity', '2024', is_percent=True)` | `('year', '2024', False)` |
| `营收增长 26` | `('quantity', '26', is_percent=True)` | `('quantity', '26', False)` |

- **后果一**：四位年份落进 `quantity`，而 `_check_date` **只收 `kind == "year"`**——
  日期幻觉那一路少了一个检查项；
- **后果二**：`_number_present` 对 `is_percent` 的数字多试一次 `value/100`——
  一个本不是百分数的数字**凭空多了一种「找得到」的方式**。

两条都是**少查**，而少查在报告上与「查过了没问题」长得一模一样。

## 3. 同一个坑，一处修过一处漏了

`_cjk_numbers` 里那处（第 155 行）`BL-01` 已经写了 `tail != "" and ...`，
还留了注释「`"" in ...` 恒 True，见 §BL-01」——**而 20 行之上的
`extract_numbers` 没改**。

所以判据里另加一条**全模块扫描**：不许再有裸的 `tail in`。
同一个坑不许有第三处。

## 4. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_grounding_tail.py -q → 11 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3853 passed（GAUGE-09 收卡时 3842，本卡 +11）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 修空串尾字符判断 | `test_a_year_at_the_end_of_the_text_is_still_a_year`、`test_a_bare_number_at_the_end_is_not_a_percentage`、`test_the_guard_is_written_out_not_left_to_truthiness`（**判源码**：只判行为的话，有人改回去而恰好没有末尾数字的用例时会继续绿） |
| ② 两个后果各有判据 | `test_the_year_reaches_the_date_check_again`（后果一的下游）、`test_a_non_percentage_no_longer_gets_the_divide_by_hundred_pass`（后果二的下游）；另有两条**正例**防矫枉过正：末尾真带 `%` 的仍是百分数、末尾紧跟量词的仍是 quantity |
| ③ 既有期望值若变要逐条写明 | **一条都没改**（见下）。`test_no_existing_expectation_had_to_change` 把这个事实钉住 |
| ④ 关闭问题单 | `test_the_ticket_is_closed` |

**② 改既有文件三处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `flint/grounding/__init__.py` | `extract_numbers` 里两行补 `tail != "" and ...` | **卡上 outputs**，本卡主体 |
| `tests/v041/test_cjk_numerals.py` | `test_a_number_at_the_very_end_is_still_misread_as_a_percent_quantity` → `..._is_read_correctly_now`，断言从 `("2026","quantity",True)` 翻成 `("2026","year",False)` | 那条判据**把缺陷本身钉住**，且 docstring 逐字写着「**这一条在那天被修好时会红，提醒那时的人来删它**」。本卡修好后它当场变红，照那句话翻成正面断言 |
| `tests/v041/test_grounding_tail.py` | `Decimal("2024")` → `Decimal(2024)` | ruff FURB157 |

**既有 grounding 用例一条都没改期望值**（卡面 acceptance③ 的要求）：
`pytest -k grounding` 51 条全绿、零改动——因为**既有用例里没有一条正文是以数字结尾的**。
这也说明这个缺陷此前为什么没被任何测试抓到。

**③ 变异考 5 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 退回缺陷态（两处都去掉 `tail != ""`） | 红 |
| ② **只修一半**（`is_percent` 修了、`has_unit` 没修） | 红 |
| ③ 矫枉过正：末尾一律不是百分数 | 红 |
| ④ 矫枉过正：末尾一律没量词 | 红 |
| ⑤ 把中文数字那处（`BL-01` 修过的）改坏 | 红 |
| ⑥ 假变异对照：只改一句注释 | 全绿 |

**两条判据我自己写错过**，都在本卡内改对：
`募资 2024 万` 我以为是 quantity——**量词必须紧跟数字**（`_QTY_UNIT` 的注释原话），
中间隔空格就不算，那是原设计不是本卡改坏的；
另一条「既有用例没被改」把**本文件自己**也扫了进去。

**④** 装载约 7k tokens；**⑤** 禁用词六词 0 命中。

## 5. owner_review

一处口径想请你确认：**`募资 2024 万` 仍判 `year`**（数字与量词之间有空格）。

这是原设计——`_QTY_UNIT` 的注释写着「紧跟数字的量词单位」。理由是
「2024 万」在中文里既可能是钱数，也可能是「2024 年 · 万某某」，
**尺子不去猜**：猜错的方向无法预知，而不猜只是少判一类。

本卡**没有动这条口径**，只把空串那个 bug 修掉。
若你认为隔空格也该算量词，那是另一张卡（且要先想清楚上面那个歧义怎么办）。

## 6. 登记未做

1. **`_QTY_UNIT` 只有 `%％倍万亿千元＄$`**。`亿`/`千` 在、`百`/`兆` 不在；
   `¥`/`￥`/`€` 不在。这是原清单，本卡未动——
   哪天正文写「募资 2024 ¥」，它又会被判成 year。
2. **`_number_present` 的 `value/100` 那条通路本身没被审过**。
   本卡只保证「不是百分数的数字拿不到它」，
   而「是百分数时那条通路对不对」不在卡面。
