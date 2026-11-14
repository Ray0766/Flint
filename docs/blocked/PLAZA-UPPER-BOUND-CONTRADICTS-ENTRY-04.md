# 卡面要广场说出「上限 5」，而 `ENTRY-04` 的既有纪律禁止广场判这条

**状态** closed · 2026-08-12 · `TAIL-01`（开单人 `PLZ-COMBO-01`）

不阻断（本卡其余两样照做）。**按既有纪律执行**，理由见 §三。

## 一、两处逐字对不上

**`tasks-v041-b15.json#PLZ-COMBO-01` acceptance⑤**：

> **上限 5 也要在屏上说得出**：选到第 6 张时 MUST 说明为什么加不进去
> （`flint/topic/create.py:67` 的 `_COMBO_MIN`~`_COMBO_MAX`），NEVER 静默忽略这一次点击。

**既有判据 `tests/v041/test_plaza_multiselect_combo.py::test_the_plaza_does_not_re_judge_the_two_to_five_rule`**
（`ENTRY-04`，已 verified）：

> `2~5` 说的是**证据卡**张数，广场选的是热点——**两者不是同一个计数**。
> 在广场判一次的话，用户选了 6 个热点会被拦下，
> 而那 6 个热点底下可能一共只有 3 张证据卡。
>
> ```python
> assert "COMBO_MAX" not in code and "comboCountValid" not in code, "广场重判了一次 2~5"
> ```

## 二、实测：照卡面做会当场打红两条既有判据

第一版按卡面把 `COMBO_MAX` 引进广场并用它 gating，全跑时红了两条：

```
test_the_build_entrance_appears_only_with_two_or_more   （它钉的是字面量 `selected.length >= 2`）
test_the_plaza_does_not_re_judge_the_two_to_five_rule    （它禁止 `COMBO_MAX` 出现在这一屏）
```

## 三、为什么按既有纪律执行（而不是改那两条判据）

`gauges_follow_the_ruling` 说：碰到红先分辨是「判据钉着旧口径」还是
「真的碰坏了东西」，**NEVER 直接改判据放行**。

这里两者都不是——是**卡面与既有裁决冲突**，而既有那条的理由今天仍然成立：
广场选的是**热点簇**，`2~5` 数的是**证据卡**，一个热点底下可能有好几张。
卡面 acceptance② 自己也写着同一件事（「这一屏选的是热点簇，而端点吃的是证据卡」）——
**acceptance⑤ 与 acceptance② 在同一张卡里互相矛盾**。

所以：上限**不在广场判**，也不在广场提示。真正的 2~5 由 `/combo` 那一屏
（选证据卡的地方）与服务端判，两处都说得出自己在判什么。

## 四、落地的样子

```
canBuild = 已选 >= 2 且 关联假设非空          ← 「两张或更多」是广场自己那条（DEC-049）
四态提示  空 / 还需 N 张 / 关联假设必填 / 就绪   ← v4 那条三态提示，本卡真正补的东西
上限提示  **没有**                              ← 本单
```

## 五、需要 owner 的什么

一句话：**维持既有纪律**（本单转 closed，卡面 acceptance⑤ 作废），
或**要广场也提示上限**（那要先回答：广场按热点数提示一个证据卡的上限，
用户看到「最多 5 张」而实际能选 6 个热点各带一张卡时怎么办）。


## 关闭（`TAIL-01` · 2026-08-12）

owner 2026-08-12 取**维持既有纪律**：**卡面 acceptance⑤ 错、既有纪律对**。

理由与本单 §三逐字一致：`2~5` 数的是**证据卡**，广场选的是**热点**——
一个热点底下可能有好几张卡。所以：

- `tests/v041/test_plaza_multiselect_combo.py` **一个字不动**
  （`TAIL-01` 用文件指纹钉住它：`0ec676bd…`，真要改先说明为什么再改指纹）；
- 广场那三态提示（还差几张 / 关联假设必填 / 就绪）只说下限，NEVER 说上限；
- 上限由 `/combo` 那一屏与服务端判，两处都说得出自己在判什么。

### 关掉时顺手核到的一处（**没有顺手改**）

空态那一句 `plaza.combo.empty_hint` 今天是「从上方卡片『+ 组合』加入 **2~5** 张热点卡」——
它**确实说了一个上限**，且单位是热点卡。但它是 v4 设计稿的原文，由另一条已 verified 的判据
`test_plaza_combo_bar.py::test_the_wording_comes_from_the_design_file_verbatim`
（断言 `"加入 2~5" in 设计稿`）钉着照抄。

改它就要同时改那条判据，而那是**文案**问题、不在本卡的三张单里。
本批规则 `no_new_fronts` 逐字写着「碰到别的问题一律开单，NEVER 顺手修」，
所以这里只如实登记：**owner 回来时若要清掉这最后一处上限口径，
动的是 `web/messages/zh.json` 与那条 verbatim 判据两处**，不是这一屏的逻辑。
