# FIX-13 · `globals.css` 小节边界固化

> v0.4.1 第 6 批第十四张。全量 `pytest -q` **4500 passed / 0 failed**。

## 装载清单

`tasks-v041-b6.json#FIX-13` · `docs/blocked/UI01-RULER-JUDGES-EVERY-LATER-SECTION.md` ·
`tests/v041/test_{ui_restyle,plaza_cards,topic_screens,design_workbench_ui}.py`
（四份抄件）· `web/app/globals.css`（八条分隔线）。约 11k tokens，**未超 40k**。

## 一、那把尺子错在哪

`UI-01` 的三条样式判据取的是「起点标记 → **文件尾**」，而 `globals.css` 是
**追加式**的：`DS-02` 追加卡面版式、`PLAZA-01` 追加堆叠与网格、
`CHAIN-03` 追加主题两屏、`REGION-10` 追加筛选器。

于是**后来每一段都被当成 `UI-01` 判**。第 5 批就地收敛，本卡固化。

## 二、固化 = 边界只有一处定义

改前**四份**判据各写一遍同一个切法，且都带着同一个魔数：

```python
end = body.find("/* ─────", 8)      # 那个 8 是「跳过自己这条分隔线」
```

四份抄件的后果不是重复劳动，而是**它们迟早不一致**——
而不一致时红的那一份看起来像「产品坏了」。

新建 `tools/css_sections.py`：`SECTION_BREAK` 与 `section_after()` 各一处，
**连三条规则本身也收了进去**（`colour_literals` / `bare_sizes` / `tokens_used`）。
**语义一字不动**（acceptance④），只是不再有第二份正则可以与它分叉。

四份判据全部改为转调它，并各自留了一行改因。

## 三、几何白名单**由调用方给**

`bare_sizes(section, allowed)` 的 `allowed` 逐段自带：
`UI-01` 一条不放行 · `PLAZA-01` 七条 · `DESIGN-02` 四条 · `CHAIN-03` 两条。

在工具里给一份公共白名单会让所有段共享同一批例外，
那时**「这个 420px 是谁的」就没人说得清了**。

## 四、两条阴性对照是本卡的重心

| 注入 | 期望 |
|---|---|
| 往 `UI-01` 段内插一处颜色字面量 | 那三条**必红** |
| 往**后来的**段插同样一处 | 那三条**必绿** |

第二条就是这张单子的由来：改前它是红的，而**红得毫无道理**——
谁都看不出「UI-01 的样式面」出了什么问题。

## 五、另有三条守着尺子自己

1. **起点标记找不到时抛**，NEVER 悄悄返回全文。返回全文的话，判据会把整份 css
   当成这一段判，而它看起来仍然是绿的（多半没有违规），
   直到某天别的段里出现一处违规，**红在一张不相干的卡上**；
2. **小节首尾相接**，合起来是整份文件——中间不留没人管的缝。
   留一条缝的话，写进缝里的样式哪条判据都不管，而它在屏上照样生效；
3. **注释里的算式不算**。`FIX-05` 那段注释里写着 `width: 342px`（那是反例），
   当场被判成「写死了间距」——**说明问题的那句话被当成犯下问题**。
   剥注释这一步也固化进工具了。

外加一条「每段说得出自己是谁」：无名的段没法被自己的判据认领，
**那正是「后来每一段都归 UI-01 判」的土壤**。

## 六、verify

```
pytest tests/v041/test_css_section_scoping.py -q                 → 12 passed
pytest tests/v041/test_{ui_restyle,plaza_cards,topic_screens,
       design_workbench_ui}.py -q                                 → 全绿
pytest -q（全量）                                                  → **4500 passed / 0 failed**
ruff / mypy --strict flint                                        → 全绿 / 306 files
python tools/check_line_endings.py                                → 220 个文件全是 LF
```

一次返工：`ruff RUF007`（`zip(bounds, bounds[1:])` → `itertools.pairwise`）。

## 七、self_review

① 判据覆盖 acceptance 五条，含**两条主阴性对照**（本卡的重心）
与三条守尺子自己的；② 零冻结件改动；③ 无禁用词；
④ 改动面：`tools/css_sections.py`（新）+ `tests/v041/` 五个文件，
**全在卡上 outputs**（`tests/v041/` · `tools/`）；⑤ 装载 ≈11k tokens。

## 八、留给下游

**往 `globals.css` 加新一段时**：起一条 `/* ─────` 分隔线、在它后面写清段名
（带卡号），然后在自己的判据里 `section_after(css, "* 你的卡号 · 段名")`。
几何例外**在你自己的判据里逐个列名**，NEVER 加进工具。
