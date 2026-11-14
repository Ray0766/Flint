# PLZ-COMBO-01 · trace

**卡**：广场 Combo 栏——补 v4 多出来的两样（假设输入 + 三态提示）
**日期**：2026-08-12 ｜ **状态**：verified

## 一、改前实况（本卡 NEVER 重写这条栏）

`plaza-combo-bar` **已经存在**（`PlazaCards.tsx`），已有：已选计数（`data-selected-count`）·
建组合按钮 · `need_two` 提示 · 它在三态分支**之上**（切到空区时不消失）。

v4 比现网多的只有两样：**假设输入框进同一条栏**、**三态提示**。
本卡只补这两样，外加上限 5 的说明。既有四个取证钩子一个字没动（判据钉着）。

## 二、四态各说各的（v4 第 524 行那条 `comboMsg`）

```
一张没选     从上方卡片「+ 组合」加入 2~5 张热点卡
不够两张     还需 {n} 张卡          n = COMBO_MIN - 已选（**算出来的**）
够了没写假设 关联假设必填
都齐了       就绪 · 生成 5~8 个候选主题
```

四态**逐个 parametrize**，缺一种即红；四句话互不相同（两句一样等于两态合并了）。
三句的判准**取自设计稿原文**（`zh[key] in v4 源码`），不是拿我抄的一份去比。

**提示恒在**，不是只在不可点时才出现——「就绪」那一态才是用户最需要确认的一态。

## 三、按钮可点性与三态同源

```
canBuild = 已选 >= COMBO_MIN 且 已选 <= COMBO_MAX 且 hypothesis.trim() !== ""
```

`trim()` 是**与后端同口径**：后端 `flint/topic/create.py` 走 `strip()`，
各判各的话，屏上说「就绪」而服务端当场拒（`EMPTY_HYPOTHESIS`）。
判据为此单列一条阴性对照（填一个空格仍不可点），并同时核后端那一侧仍是 `strip()`。

2~5 走既有的 `COMBO_MIN`/`COMBO_MAX`（`lib/topicClient`），**NEVER 在这一屏另写一个 5**。
上限到了也说得出（`plaza-combo-at-max`），NEVER 静默吞掉那一次点击。

## 四、簇 id **NEVER** 当 card_ids 发出去（这条坑已经有人踩过）

这一屏选的是**热点簇**，而 `POST /projects/combo` 吃的是**证据卡** id——
一个热点底下可能有好几张。所以按钮**仍然只是跳到 `/combo?clusters=…`**，
由那一屏选证据卡。判据三条钉着：广场屏仍走 `?clusters=`、
组件里不出现 `card_ids`、组件里不直接打 `projects/combo`。

## 五、一条**只留到一半**的缝，写明它今天到哪为止

输入的假设由 `onBuildCombo(hypothesis)` 交给调用方。
`onBuildCombo` 的签名从 `() => void` 改成 `(hypothesis: string) => void`——
**既有调用点一个都不用改**（TS 允许少收入参）。

**今天广场那一屏还没把它带进 `/combo` 的地址**：那一步要改
`web/app/plaza/page.tsx` 与 `/combo` 那一屏，两者都不在本卡 outputs 里。
所以用户到 `/combo` 仍要把假设再打一遍。
**这件事写在组件注释与判据里**，NEVER 假装它已经接上了——
一条留了缝却不说它是空的实现，与「做完了」在屏上长得一模一样。

## 六、我引入的一处真缺陷（被门抓住）

第一版把 `useState("")` 写在 `clusters === null` 那个**早退之后**，
React 当场报「Rendered more hooks than during the previous render」——
`nav02` 与 `mainchain` 两个测试文件 **9 条一起红**。
加载态那一帧的 hook 数少一个、数据回来之后多一个，React 对不上号。
把它挪到早退**之前**（与既有两个 `useState` 放一起）之后 858 条全绿。

**红的是我引入的真缺陷，不是判据**——这一条与本批「判据自己是缺陷」的那几处要分开数。

## 七、判据自己错两处（当场改）

1. **扫得太宽**：「屏里另写了一个 5」那条扫的是「文件里出现过 ` 5`」，
   于是把既有的 `const FEATURED = 5`（首屏几张卡，与组合上下限毫无关系）也判红。
   改成判**边界那几处**（`length >= 2` / `length <= 5` 一类的字面量）。
2. **扫到解释性注释**：「提示写死在组件里」那条扫的是「代码里出现过『选到第』」，
   而那三个字在我自己的注释里。改成判「文案走词典且上限是传进去的」——
   本仓第十次同类（判据扫到解释代码的话）。

## self_review

① 判据 ↔ acceptance：四态 4 + 四句不同 1 + 逐字来自设计稿 1 + N 算出来 1 ·
   可点性 1 + 空格阴性对照 1 + 上限共享 1 + 上限说得出 1 ·
   簇 id 不当 card_ids 1 + 假设交给调用方 1 · 既有钩子 1 + 位置 1 + 裸色值 1 = **16 条**。
② 无冻结件偏离：`contracts/` 未读未改；上下限的真相仍在后端。
③ 无禁用词：命中 0。
④ 复用断言在位：`COMBO_MIN`/`COMBO_MAX` 引自 `lib/topicClient`；后端 `strip()` 口径同时核。
⑤ 装载未超预算：约 10k tokens。

## 产出文件

```
web/components/plaza/PlazaCards.tsx    假设输入 + 四态提示 + 上限说明（既有四个钩子没动）
web/messages/zh.json · en.json         7 条新 key（两份对称）
tests/v041/test_plaza_combo_bar.py     16 条判据
```
