# 登记：BL-09 的 locale 尺子不认九区代码

**状态** closed · 2026-08-05 · `GAUGE-07`

> **已关闭 · 2026-08-05 · `GAUGE-07`**（走三选一里的**第 1 个**：加宽尺子 + 扩豁免）。
>
> **九区从冻结件取**（`contracts_v04.Region`），NEVER 手抄——
> 手抄的清单不会跟着冻结件变：V2 加一个地区，尺子仍按九个量，
> 而**新加的那个地区从此不在护栏内**，最需要护栏的恰恰是新地区。
> 取不到就 raise，NEVER 退化成空集合（空集合会让这半条护栏静静地不再报任何东西，
> 而报告上写的是「0 处违规」）。
>
> **先量再定豁免**（卡面 acceptance③ 的顺序）：加宽后全仓实测 **2 处**，
> 全在 `tools/orthogonality_check.py`——那是**另一把尺子的自证反例**
> （`_BROKEN` 里故意写坏的 A3 接线）。判它红等于逼那把尺子删掉自己的反例，
> 而那条反例守的正是同一条纪律。豁免**逐条列名到文件**，NEVER 通配。
>
> **两种写法各配一条阴性对照**（`BE-07` 变异考⑳ 当时两种都漏了）：
> 分支假设 `if region == "CN"` · 调用点实参 `select_sources(region="CN")`；
> 另有一条**九个地区逐个验**——只验 CN 的话，「集合里少了 SG」照样绿。
>
> 以下为关闭前的原文，一字未改。

---

**发现于** BE-07（`GET/PUT /settings/locale`）变异考⑳ · 2026-08-05 ·
**当时的处置** 已登记，那一批**不改**（改动面大于卡上 outputs → §六.1）
**不阻塞** BE-07：已在本卡测试里加了一把只管 `flint/api/settings.py` 的窄尺补上。

## 事实

`tools/check_locale_seam.py`（BL-09，V2 护栏尺）的字面量集合是：

```python
LOCALE_LITERALS: Final[frozenset[str]] = frozenset(
    {"zh", "zh-CN", "zh_CN", "zh-Hans", "中文", "weibo", "微博"}
)
```

**九区代码一个都不在里面**（`CN` / `US` / `AU` / `SG` / `JP` / `KR` / `GB` / `IT` / `FR`）。

## 后果

`PRINCIPLES#A3` 是**两条轴**：语言与地区。这把尺子现在只守住了语言那条。
下面这种写法**从它下面走得过去**：

```python
if region == "CN":            # 分支假设，但尺子不红
    ...
select_sources(region="CN")   # 调用点写死，但尺子不红
```

变异考⑳ 就是这么过的：往 `flint/api/settings.py` 里插一行 `patch.region == "CN"`，
`scan_source` 返回空、判据全绿。

这正是 BL-09 自己 docstring 写的那件事：
「一处硬编码今天是一行，V2 全球版时是一处要回头找的暗坑——
**而它不会报错**，只会在别的地区上悄悄给出中文口径的结果。」
地区那一半现在就处在这个状态。

## 为什么本批不改

`tools/check_locale_seam.py` 是**全仓门禁**：`LOCALE_LITERALS` 里加九个值，
会把全仓每一处出现 `"CN"` / `"US"` 字符串的地方一次性变红——
其中相当一部分是数据表的键与类型声明（BL-09 自己判为「不算违规」的两类），
需要连带扩白名单与豁免规则。这个改动面远大于 BE-07 的 outputs
（`flint/api/settings.py` + 一个测试文件），按 §六.1 停下登记。

## 给 owner / steward 的三个选择

1. **加宽尺子 + 扩豁免**（推荐，独立一张卡）：把九区代码并入 `LOCALE_LITERALS`，
   同时把「数据表的键」与「类型声明」两类豁免写实（BL-09 已经声明过这两类不算违规，
   但现在没有针对区代码的白名单条目）。先跑一遍全仓看红多少处，再定豁免清单。
2. **只收窄到分支假设那一类**：区代码只在 `ast.Compare` 与 `in (...)` 里算违规，
   调用点实参那一类不收——代价是 `select_sources(region="CN")` 仍然漏。
3. **维持现状**：认下「地区那条轴没有全仓尺子」，各卡各自加窄尺（BE-07 已经这么做了）。
   代价是新写的代码默认不受保护，只有想起来加尺子的人受保护。

## 现状（本卡已做的部分）

`tests/v041/test_be_settings_locale.py#test_the_module_contains_no_locale_literal_at_all`：
从冻结件取全部 11 个值（2 语言 + 9 地区），断言它们**一个都不作为字符串字面量**
出现在 `flint/api/settings.py` 里（docstring 除外）。只管这一个模块。
