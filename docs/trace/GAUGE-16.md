# GAUGE-16 · 两把尺子走到最后一格

**结论**：孤岛那道闸**从不可达改成先遍历再清零**并补了一条规矩；
单据判法从数行号改成判形状、两份逐字重复的副本**收成一处**；
阴性对照从 3 例扩到 **7 例**，四次变异考全部被抓住。
`verify_cmd` 44 条全绿，`ruff check .` All checks passed!

装载：`docs/steward/tasks-v041-b10.json#GAUGE-16` · `docs/V041-BATCH9-COMPLETION.md` ·
`docs/trace/SHIP-09.md` · `tests/v041/test_main_chain_walk.py` ·
`tests/v041/test_workbench_create.py` · `tools/check_reachability.py`
（实测装载 ≈ 25k tokens，预算 40k）

---

## 1 第一处：那道闸的循环体**永远执行不到**

```python
assert report.islands == [], f"又长出孤岛了：{report.islands}"
for route in report.islands:          # ← 上一行断言它是空的
    assert screen.get("island_reason"), ...
```

而 `island_reason` / `island_sheet` 这条纪律，**全仓只有那四行在守**——
等于今天没有任何东西在守它。docstring 却写着
「它必须留着，下一次长出孤岛时它就是那道闸」：**判据的说明与判据的可达性对不上**。

这是我第 9 批翻面时留下的洞：翻面翻对了（清零是实况），
但把「先遍历」与「再清零」的顺序写反了，**而红绿两态都不会告诉我这件事**——
孤岛为 0 时两种写法都绿。

**改法**：抽出 `assert_every_island_is_accounted_for(graph, islands)`，
排在清零断言**之前**；报错先收集再一次报全，**说得出哪一座缺什么**。

## 2 闸补了一条规矩：**孤岛挂一张已关的单 = 这座岛没有主**

写第二条阴性对照时发现闸漏了这一档：理由写了、单据挂了，**而那张单已经关了**——
在图里看起来样样齐全，实际没有主。

这一条正是第 9 批那句 `**状态** open` 断言**原本想守的东西**。
那时它被写成「单据必须 open」，于是单据被正当关掉时它红、而红的原因是活干完了。
**规矩没错，位置错了**：

> 「这张单该不该开着」取决于**有没有一座岛还指着它**，而不取决于这张单自己。

## 3 第二处：阴性对照够不着两条 assert

`test_a_status_line_that_says_neither_open_nor_closed_goes_red` 的三个坏样本
**全部落在 `status_of` 的 `ValueError` 上**。而
「必须有 `## 关闭` 节」与「关闭那一节要点名同一张卡」是两条 `assert`——
**把它们删掉，阴性对照照样绿**。

补第四、第五例，两例都期望 **`AssertionError` 而不是 `ValueError`**：
两者说的是两件事——前者是「这张单没交代清楚」，后者是「状态行读不出来」。
合成一个的话，读到红的人不知道该去补一节还是去修一行。

第五例（有关闭节、里面点的是另一张卡）是三种关法里**最像真的**那一种：
单据看上去交代得齐全，只是状态行说 A 关的、正文说 B 关的——
不判的话，「谁关的」在盘上有两个互相矛盾的答案，而下一个人只会读到其中一个。

## 4 变异考（四次，全部被抓住）

| 变异 | 结果 |
|---|---|
| 拆掉「孤岛挂的单不该关着」 | **2 failed** |
| 拆掉「必须有 `## 关闭` 节」 | **2 failed** |
| 拆掉「关闭节要点名同卡」 | **2 failed** |
| 把整道闸的最终断言拆掉 | **2 failed** |

**每次都是 2 红**：两个判据文件各接住一条。
（第一次做变异②时我直接删掉两条 `assert`，留下一个空 `if` → 缩进错、报的是
`2 errors` 而不是 `2 failed`——**那是我把变异写坏了，不是尺子的账**。
改成换 `pass` 才是一次干净的变异。第 3 批的教训「变异要改被测物」在这里又用上了一次。）

## 5 两份逐字重复的副本收成一处（卡面 MAY，本卡选择「收」）

第 9 批给两个文件各写了一份 `_STATUS_LINE` / `status_of` /
`assert_sheet_keeps_its_trace`，实测**各 1499 字符、逐字相同**。

**收的理由**：两份各自漂移的那天，两张单会按两套规矩判——而它们守的是同一条纪律；
更坏的是，**修好其中一份的人会以为自己修好了这条纪律**。
本卡本身就是证据：这次要改的四处里有三处在这段公共逻辑上，
不收的话每一处都要改两遍，而漏掉一遍不会有任何东西报红。

落在 `tests/v041/_sheet_trace.py`——下划线开头且不叫 `test_*`，pytest 不收集它。
卡面把这个文件名写进 acceptance，所以它在 outputs 之内。

## 6 改前 / 改后 / 为什么非改不可

| 文件 | 改前 | 改后 | 为什么 |
|---|---|---|---|
| `tests/v041/_sheet_trace.py` | 不存在 | 三个函数的唯一真相 | §5 |
| `test_main_chain_walk.py` | 闸不可达 · 单据判 `splitlines()[2]` + `**状态** open` · 3 例对照 | 先遍历再清零 · 判形状 · 5 例对照（含孤岛面 2 例） | §1 §2 §3 |
| `test_workbench_create.py` | 自带一份逐字重复的 helper · 3 例对照 | import 共用件 · 5 例对照 | §3 §5 |

**不再用 `splitlines()[2]` 找状态行**：那种写法把「状态行在第几行」当成纪律的一部分，
单据头上多一行说明它就红，**而红的原因是排版**。

## 7 自审（`self_review=true`）

**① 判据覆盖 acceptance**（八条）：①闸不可达 → §1 改法 + 变异③；
②说明与可达性对不上 → docstring 已重写并写明它当时是拆的；
③先遍历再清零、报错说得出哪一座缺什么 → `unaccounted` 逐条收集；
④单据改判形状、不再数行号 → §6；⑤孤岛面阴性对照（人造图、**只写临时目录**）→ 2 例；
⑥三个坏样本全落在 ValueError → §3 已量；⑦第四、五例期望 `AssertionError` → 已补；
⑧两份重复收成一处并写明理由 → §5。

**先红后绿**：孤岛面两条对照写完即红（`NameError` + 少一条规矩），修到绿。

**② 无冻结件偏离**：本卡只动判据与判据的共用件，四件冻结件未触碰。
**③ 无禁用词**：0 命中。
**④ 复用断言在位**：闸复用 `tools/check_reachability.check(graph_path)`
（第 9 批建的那条「可以喂人造图」的路），**NEVER 新写一个遍历**。
**⑤ 装载未超预算**：≈25k / 40k。

## 8 门

```
pytest tests/v041/test_main_chain_walk.py tests/v041/test_workbench_create.py -q
44 passed
ruff check . --no-cache        All checks passed!
变异考 ×4                      每次 2 failed（两个文件各接住一条）
```

## 9 留给下游

1. `assert_every_island_is_accounted_for` 现在是**唯一**在守
   `island_reason` / `island_sheet` 的东西。下一次有人往图里加孤岛，
   它会要一条理由 + 一张**开着的**单。
2. 单据留痕那三个函数**只此一份**。要改判法就改 `_sheet_trace.py`，
   NEVER 在判据文件里再抄一份回去。
