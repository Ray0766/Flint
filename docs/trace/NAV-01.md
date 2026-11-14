# NAV-01 · 导航图声明 + 可达性尺子

**结论**：22 屏里点得到 6 屏，孤岛 15 座 + 豁免 1 座。尺子退出码 1——**本卡就该红**。

装载：`docs/steward/连跑工单-v041-第8批.md` §2 §3 §9 · `docs/steward/交接-STEWARD-HANDOFF.md`
· `assets/screen_composition.json` · `web/app/**/page.tsx` · `web/components/shell/AppShell.tsx`

---

## 1 owner 是对的，而 steward 上一条答错了

owner 2026-08-09 亲自点过界面之后说「前端和后端还没有连接上」。
steward 答「连上了」——**那个回答量的是「端点回不回」，owner 问的是「点不点得到」**。
两件事之间隔着 16 座屏。

三把既有尺子没有一把量得到这件事：

| 尺子 | 量什么 | **不量什么** |
|---|---|---|
| `GAUGE-13` 屏覆盖 | 屏在不在 | 走不走得到 |
| `GAUGE-12` 组件对照 | 屏上有没有那些组件 | 屏与屏之间有没有路 |
| `check_fe_be_parity` | 端点接没接 | 用户点不点得到 |

每张卡的验收都是**逐屏**写的，**没有一条问过「从 A 屏能不能走到 B 屏」**——
所以孤岛可以一路绿灯建到今天。这不是谁偷懒，是判据的形状里缺了一维。

## 2 尺子判三件事，缺一件它就会说谎

1. **图遍历**（`NEVER 用入度计数`）。`/projects/[id]/topics` 有一条真边指向它，
   而起点 `/combo` 自己走不到。按入度算它可达，按遍历算它不是——
   **二级孤岛只有遍历查得出来**。
2. **图与代码两向比对**。一份与代码对不上的图比没有图更坏，它会让人以为路查过了。
   阴性对照 `test_an_edge_that_is_only_in_the_graph_is_reported`：
   往图里画一条源码里没有的线，尺子必须报出来——否则谁都能靠画线把孤岛变成可达的。
3. **两个方向自洽**。`/favorites` 有出口没入口，**只写出口的图查不出这一座**。

## 3 改前 / 改后 / 为什么非改不可

本卡四件产物**全是新增**，一处既有文件都没动：

| 文件 | 动作 |
|---|---|
| `assets/screen_graph.json` | 新增 |
| `tools/check_reachability.py` | 新增 |
| `docs/导航图-v041.md` | 新增 |
| `tests/v041/test_reachability.py` | 新增 |

冻结件（`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`）
一字未动。无新增依赖。无迁移。

## 4 断点：`href` 正则收边错误，一次造出两条互相矛盾的假发现

**改前**

```python
_HREF = re.compile(r"href=(?:\{`|\")([^\"`}]+)")
```

`[^…}]` 里含右花括号，于是 ``href={`/deliverables/${id}/export`}`` 在 `${id}` 的
**右花括号处就被截断**，只剩 `/deliverables/${id`。

后果是同一条真边被同时报成两件事：

- 「图里有、源码里没有」——图声明的 `/deliverables/[id]/export` 在（截断后的）代码里找不到；
- 「源码里有、图里没声明」——截断出来的那半截 `/deliverables/[id]` 图里没写。

**两条发现互相矛盾，而两条都是假的。** 值得记下来的是它读起来完全像图写错了。

**改后**

```python
_HREF = re.compile(r"href=\{`([^`]+)`\}|href=\"([^\"]+)\"")
```

模板字面量**一路读到反引号**，普通字符串读到引号；两个捕获组在 `findall` 里
展平取非空的那个。

**为什么非改不可**：收边错误不会让尺子沉默，它会让尺子**说假话**——
而假话里那两条恰好互相印证，最容易被当成真发现去改图。

## 5 与工单对不上的一处：链接目标是 **6** 个，不是 5 个

工单 §2 列的 5 个全是 `href`。第 6 个是 **`/combo` → `/projects/[id]/topics`**，
写在提交回调的 `window.location.assign()` 里（`web/app/combo/page.tsx:50`）——
**只扫 `href` 看不见它**。

不是随便哪一个：它正是造出二级孤岛的那一条。因为它真的存在，
`/projects/[id]/topics` 的入度不为零；只有遍历才看得出它照样点不到。
**一把只扫 `href` 的尺子会同时漏掉这条边和这座孤岛**——两个漏洞刚好互相掩护。

其余数字复核一致：22 屏 · 顶栏 2 项 · 走得到 6 屏 · 走不到 16 屏（孤岛 15 + 豁免 1）。
已写进 `screen_graph.json#_measured`、导航图 §1、判据
`test_there_are_six_link_targets_not_five`。

## 6 判据 14 条，其中 3 条是阴性对照

| 判据 | 守什么 |
|---|---|
| `test_removing_one_link_turns_a_screen_into_an_island` | **卡上要求的那一条**：摘掉 `/plaza → /gate/[id]`，尺子报红并点名整条链（判定屏 + 交付物屏 + 导出屏），入口自己不受影响 |
| `test_an_edge_that_is_only_in_the_graph_is_reported` | 在图里画一条线不能把孤岛变成可达的 |
| `test_a_second_level_island_is_not_counted_as_reachable` | 入度不为零、起点走不到 → **仍然是孤岛** |
| `test_the_islands_are_exactly_the_ones_on_record` | 名单**判等值**：`NAV-02~05` 每接一条线这里红一次 |
| `test_no_island_was_quietly_moved_into_exempt` | 待办不许挪进豁免顶掉红 |
| `test_the_ruler_is_red_today_and_that_is_the_point` | 退出码 1 —— **它红着才说明它在量** |

孤岛名单判**等值**不判包含：接线接漏了也要响。少一条要来删（删那一行就是「这条线真接上了」的签字），
多一条要停下登记——与本仓既有基线同一套办法。

## 7 exempt 只有一条

`/share/[token]`：token 由**站外**拿到。站内没有、也不该有一条指向它的边——
站内能点到就说明有人把别人的 token 印在了屏上。

`NEVER 把「还没接线」写进 exempt 顶掉红`：那样报告上会写「每一屏都走得到」，而那句话是假的。

## 8 接进全局门

`tests/v041/test_reachability.py` 落在 `pytest -q` 覆盖面内，
其中一条判据以 subprocess 跑 CLI 本身。`NAV-02~05` 每接一条线都会被它量到。
**NEVER 只跑一次就算。**

## 9 门

```
pytest tests/v041/test_reachability.py -q   14 passed
ruff check .                                 All checks passed
mypy --strict tools/check_reachability.py    Success
python tools/check_reachability.py           EXIT=1（孤岛 15 屏——本卡就该红）
```

`ruff` 修了一处 `SIM102`（`_alias` 里的嵌套 `if` 合并成一条），不是抑制。
