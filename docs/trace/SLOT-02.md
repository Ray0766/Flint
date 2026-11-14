# SLOT-02 · 卡面陈旧标记 —— blocked

> v0.4.1 第 6 批第三张。`depends_on: ["SLOT-01"]`（已 verified）。
> **状态 blocked**，单据 `docs/blocked/SLOT-02-A-CLUSTER-HAS-NOTHING-THE-REVALIDATOR-CAN-JUDGE.md`。

## 装载清单

`tasks-v041-b6.json#SLOT-02` · 工单 §3 · `docs/trace/HOTSPOT-06.md`（context_refs）·
`flint/analysis/stale_adapter.py` · `flint/fav/stale.py` · `flint/fav/store.py` ·
`flint/api/{staleness,favorites}.py` · `contracts_v04/models_v04.py#Favorite` ·
`docs/前端功能说明-v2.md#2.14/#2.15` · 本机 55432 的 `information_schema` 实查。
约 12k tokens，**未超 40k**。

## 一、为什么停

卡面 acceptance①：「复用 Revalidator 统一 stale，NEVER 新写一套比对——
`HOTSPOT-06` 建的适配器就是为此」。

**适配器在。卡在「拿它去判谁」。** 它的签名要三样：

```
project_id · analysed_at_version/current_version · cited_fact_ids
```

`clusters` 表（实查十列）一样都没有。**一个热点簇不是一份分析**——
它不引用事实，它是事实的来源之一。给这三样各编一个值，就是 acceptance①
禁止的那件事换个地方做。

四条路我都走到底了，逐条记在单子里：

| 路 | 结论 |
|---|---|
| 拿适配器判簇 | 三样输入一样都没有 |
| 库里现成的 stale | 只有 `deliverables.stale_reasons` 与 `pricebook.stale_after_months` |
| `Favorite.snapshot_stale` | 语义是「你的存档旧了」≠「这个热点旧了」；且内存件、无表、demo 没挂、广场匿名 |
| `clusters.last_active` 比日期 | **三处明令禁止**（规格 #2.15 / 冻结件 `Favorite` / `flint/fav/stale.py`） |

## 二、顺带查出来的一件事

**规格 `#2.14`（广场）里根本没有陈旧一条**——四条状态规则是骨架卡 / 空结果 /
单区源全灭 / 译名缺失。陈旧是 `#2.15`（收藏图书馆）的规则，那一屏已经在显示它。

卡面那一槽来自素材 `CardStack.dc.html` 的版式。**这是本批第二次撞见同一形状**：
`DEC-036` 是规格给 `Topic` 写了名称三元组而冻结件里它没有名称；
这一次是素材给了槽而产品没有那个数据。**素材与规格都不是数据面的真相。**

## 三、blocked ≠ 什么都没做

`tests/v041/test_plaza_stale.py`（9 passed）交付四类判据：

1. **前提本身可复核**：判的是 `analysis_stale` 的**签名**而不是它的 docstring
   ——有人改一句说明不会让本单失效，改一个参数才会，而后者才是这张卡能不能做
   真正取决于的东西；
2. **不假装有**：广场端点 NEVER 回 `stale` 键（回一个恒 `false` 是最像「做完了」
   的做法：屏上永远不挂标记，看起来一切正常，而它说的是「已经查过，是新鲜的」）；
   搬运层不赋值（`undefined` = 没判过，连 `null` 都不传，那是「明确地没有值」）；
3. **两条捷径钉死**：全链零 `last_active`、零 `/staleness|refresh-snapshot`；
4. **判据自己的阴性对照**：把 `last_active` 那条捷径注入链里，第 3 条必须红——
   没有这一条，`last_active` 哪天改名或搬家，那条断言会静静变成永真而仍然是绿的。

外加真栈一条：今天广场上**零张卡**挂这个标记（数据面不存在而屏上出现了标记，
只可能是有人编了一个值）。

## 四、给 owner 的四选一（推荐甲）

甲 本槽在广场上恒不显示 + 判据钉死（0 代价，已交付）· 乙 给簇定义「沉寂」口径
（要迁移，**别叫陈旧**）· 丙 favorites 落库后在收藏屏显示（语义对，但不是广场）·
丁 广场接身份显示「你的存档旧了」（**不建议**，会被读成「这个热点旧了」）。

**另请 owner 裁一句**：acceptance② 与 ③ 字面打架——② 说「判过且新鲜（不挂标记）·
未判定过（槽隐藏）」，这两者在屏上就是同一个样子；③ 又要「三种状态屏上互不相同」。
除非给「新鲜」也发一个记号，否则不能同时满足。本单按 ② 的括号为准并按 `DEC-038`
不发新记号；选甲的话这件事不会发生。

## 五、verify

```
pytest tests/v041/test_plaza_stale.py -q  → 9 passed
ruff check . --no-cache                   → All checks passed
python tools/check_line_endings.py        → 219 个文件全是 LF
```

一次返工：`ruff I001`（`import inspect` 排在 `from flint...` 之后）。

## 六、self_review

① 判据不空转：四类判据各有真实失败面，且第 4 类是判据自己的阴性对照；
② 零冻结件改动（本卡一个 `flint/` 文件都没改）；③ 无禁用词；
④ 改动面：只新增两份文档/判据，**未动任何实现文件**——因为该动的地方超出卡上 outputs；
⑤ 装载 ≈12k tokens。
