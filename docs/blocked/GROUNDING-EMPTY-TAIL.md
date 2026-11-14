# GROUNDING-EMPTY-TAIL · `"" in "%％倍…"` 恒为 True，正文末尾的每个数字都被误判

**状态** closed · 2026-08-06 · `FIX-01`

> **已关闭 · 2026-08-06 · `FIX-01`**
>
> `extract_numbers` 里那两行补上 `tail != "" and ...`：
>
> ```python
> is_percent = tail != "" and tail in "%％"
> has_unit  = tail != "" and tail in _QTY_UNIT
> ```
>
> **同一个坑，一处修过一处漏了**：`_cjk_numbers` 里那处 `BL-01` 已经写了
> `tail != "" and ...` 并留了注释「`"" in ...` 恒 True」，
> **而 20 行之上的 `extract_numbers` 没改**。判据里另加一条**全模块扫描**：
> 不许再有裸的 `tail in`——同一个坑不许有第三处。
>
> **本单记的两个后果都实测复现过**（修前 / 修后）：
>
> | 输入 | 修前 | 修后 |
> |---|---|---|
> | `发布于 2024` | `('quantity', '2024', is_percent=True)` | `('year', '2024', False)` |
> | `营收增长 26` | `('quantity', '26', is_percent=True)` | `('quantity', '26', False)` |
>
> **既有用例一条都没改**：`pytest -k grounding` 51 条全绿、零改动——
> 因为既有用例里没有一条正文是以数字结尾的。这个事实由
> `test_no_existing_expectation_had_to_change` 钉住：
> 哪天有人改了既有期望值，得先来说明为什么。
>
> 以下为关闭前的原文，一字未改。

---

**发现者** worker / BL-01 接中文数字时撞上 · **发现时间** 2026-08-04
**危害** 中 —— 误判方向是**放松**（把年份当数量、把整数当百分数），会让接地校验少查东西
**改动面** 改的是 v0.4 既有判定逻辑，会动既有用例的期望值 → 超出 BL-01 的「只加不改」

## 一行代码

`flint/grounding/__init__.py` 的 `extract_numbers`：

```python
tail = text[m.end():m.end() + 1]     # 正文末尾的数字 → tail == ""
is_percent = tail in "%％"           # "" in "%％"        → True
has_unit  = tail in _QTY_UNIT        # "" in "%％倍万亿…"  → True
```

**Python 里空串是任何字符串的子串。** 于是「正文以数字结尾」这一种情况下：

- `has_unit=True` → 4 位年份**不会**被判成 year，落进 quantity；
- `is_percent=True` → 它被当成百分数。

## 两个后果，都是放松

1. **年份被拿去查数字出处**：`_check_numbers` 只查 quantity。年份落进 quantity 后，
   要求它出现在被引卡原文里——多半在，于是 clean；但同时 `_check_date` 那条
   **拿不到这个年份**（它只收 `kind == "year"`），日期幻觉那一路就少了一个检查项。
2. **`is_percent=True` 会额外放宽比对**：`_number_present` 对百分数多试一个
   `value/100`（26 → 0.26）。一个本不是百分数的数字凭空多了一种「找得到」的方式。

两条都是**少查**，而少查在报告上与查过没问题长得一模一样。

## 复现（当前真实输出）

```python
>>> extract_numbers("1998 与 2026", GroundingConfig())
[_Number(kind='year', raw='1998', …), _Number(kind='quantity', raw='2026', is_percent=True)]
>>> extract_numbers("1998 与 2026 年", GroundingConfig())
[_Number(kind='year', …), _Number(kind='year', …)]         # 后面多一个字就正常了
```

## 修法（一行，但会动既有期望值）

```python
is_percent = tail != "" and tail in "%％"
has_unit  = tail != "" and tail in _QTY_UNIT
```

**为什么 BL-01 没顺手改**：那张卡的 acceptance③ 原话是「既有阿拉伯数字路径
**逐字不变**（用既有用例证明），本卡只加不改」。改了它就不是只加不改，
而这一改会翻转「正文以数字结尾」的所有既有判定——影响面要重跑接地校验的全部用例
与金标集才说得清。

**BL-01 新写的中文那条路没有照抄这个写法**（照抄最省事，两处逻辑长得一模一样），
并且用 `test_a_number_at_the_very_end_is_still_misread_as_a_percent_quantity`
把现状钉住：那一条在缺陷被修好的那天会红，提醒那时的人来删它。
