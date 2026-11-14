# UI-01 那把样式尺子把「后来每一段」都当成自己的 —— 已就地收敛，请 owner 复核

**状态** closed @2026-08-08 · `FIX-13`（v0.4.1 第 6 批）

> 发现者：worker，v0.4.1 第 5 批 `PLAZA-01`。
> **本条改的是卡面 outputs 之外的文件**（`tests/v041/test_ui_restyle.py`），
> 按第 5 批工单纪律 4 在此登记。

## 现象

`test_ui_restyle.py::_ui01_css()` 取的是

```python
start = css.find(UI01_MARKER)
return css[start:]            # 起点标记 → 文件尾
```

而 `globals.css` 是**追加式**的：`UI-01` 之后，`DS-02` 追加了卡面版式，
`PLAZA-01` 追加了堆叠与网格。于是那三条 UI-01 的判据
（零颜色字面量 / 零裸字号间距 / token 必须存在于 `_ds`）**把后来每一段都当成 UI-01 判**。

实测报出来的五条全部来自 PLAZA-01 那一段：

```
本卡样式里写死了字号/间距：['height: 420px;', 'perspective: 1100px;',
 'grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));',
 'min-height: 180px;', '--plaza-width: min(1160px, calc(100vw - 2 * var(--sp-5)));']
这些 token 在 _ds 里不存在：['--plaza-width']
```

## 两件事要分开

**① 尺子的扫描面写错了**（本次就地修）。它自己的 docstring 说的是「**本卡**样式」，
实现却是「本卡起点之后的一切」。收敛成「起点标记 → 下一条分节横线」：

```python
end = css.find(SECTION_BREAK, start + len(UI01_MARKER))
return css[start:] if end == -1 else css[start:end]
```

**这不是放宽**：UI-01 那一段的每一行仍然逐条判，只是不再替别人的段落背书。
PLAZA-01 那一段改由 `tests/v041/test_plaza_cards.py::
test_the_plaza_styles_use_tokens_except_the_named_geometry` 按**同样的口径**判
（颜色零字面量、字号与间距零裸值），几何例外在那里**逐个列名**。

**② 「几何值算不算写死间距」是个口径问题**（**请 owner 裁**）。

`_ds` 的刻度里没有「420px 的台面高」「1100px 的透视距」「300px 的网格列底」——
它们是**舞台尺寸**，不是字号也不是间距。把它们拼成 `--sp-*` 的组合
（`calc(var(--sp-10) * 2 + …)`）只会多一层间接、不会多一分一致性——
那正是 UI-01 那条判据自己为 1px 描边写下的原话。

本次的处理是：**允许，但必须逐个列名**（名单少一条即红，多一条要来解释）。
若 owner 认为几何值也该出 token，那是给 `_ds` 加一族 token，属设计系统面。

## 绕行现状

两条判据现在各判各的段，全绿。本条列进第 5 批完成态报告的待裁项。

---

## 结案（`FIX-13` · v0.4.1 第 6 批）

第 5 批就地收敛成「起点标记 → 下一条分隔线」，本卡把它**固化**。

### 固化 = 边界只有一处定义

改前有**四份**判据各写一遍同一个切法，且都带着同一个魔数：

```python
end = body.find("/* ─────", 8)      # 那个 8 是「跳过自己这条分隔线」
```

四份抄件的后果不是重复劳动，而是**它们迟早不一致**——
而不一致时红的那一份看起来像「产品坏了」。

现在只有 `tools/css_sections.py`：`SECTION_BREAK` 与 `section_after()` 各一处，
连三条规则本身（`colour_literals` / `bare_sizes` / `tokens_used`）也收了进去
——**语义一字不动**，只是不再有第二份正则可以与它分叉。

四份判据（`test_ui_restyle` / `test_plaza_cards` / `test_topic_screens` /
`test_design_workbench_ui`）全部改为转调它。

### 几何白名单**由调用方给**

`bare_sizes(section, allowed)` 的 `allowed` 逐段自带：
`UI-01` 一条都不放行、`PLAZA-01` 七条（420/1100/300/180/1160/520/320）、
`DESIGN-02` 四条、`CHAIN-03` 两条。

在工具里给一份公共白名单会让所有段共享同一批例外，
那时**「这个 420px 是谁的」就没人说得清了**。

### 两条阴性对照才是这张卡的重心

- 往 `UI-01` 段内插一处颜色字面量 → 那三条**必红**；
- 往**后来的**段插同样一处 → 那三条**必绿**。

第二条就是这张单子的由来：改前它是红的，而**红得毫无道理**——
谁都看不出「UI-01 的样式面」出了什么问题。

另有三条守着尺子自己：起点标记找不到时**抛**而不是悄悄返回全文
（返回全文会让它某天红在一张不相干的卡上）· 小节首尾相接不留没人管的缝 ·
注释里的算式不算（`width: 342px` 是反例，说明问题的那句话 NEVER 当成犯下问题）。
