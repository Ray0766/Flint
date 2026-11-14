# REGION-SPAN · trace

**卡**：`DEC-058`——跨区簇走乙：不表达地理的源值不参与定区。
**结果**：verified · 1 cycle · 判据 14 条全绿 · 那一条簇 `NULL → HK`。

## 装载清单

`flint/region/backfill.py#region_of_members` · `flint/api/views.py#SOURCE_CONSTANT_REGIONS`
· `flint/sources/ghtrend.py` / `arxiv.py`（写库那一侧）· `web/lib/regions.ts`
· `docs/blocked/REGION-CN-HK-ONE-CLUSTER-SPANS-BOTH.md`

## 一处定义他处引用：改前是**三处**

`DEC-058` 逐字要求「哪些值是源常量」只有一处。实查 `"global"` 这个字面量散在三处：

| 落点 | 它在那里干什么 |
|---|---|
| `flint/api/views.py#SOURCE_CONSTANT_REGIONS` | 筛选面把它与 `NULL` 一起归入未归区 |
| `flint/sources/ghtrend.py:148` | **写**这个值进库 |
| `flint/sources/arxiv.py:35` | 同上（默认参数） |

新建 `flint/region/source_constants.py` 作为那一处；三处改成引用它。
`views.py` **保留同名再导出**——既有读者与判据都按 `SOURCE_CONSTANT_REGIONS` 这个名字找它，
改名会让一堆无关的东西跟着红，而那与本卡要治的事没有关系。

> 写库那一侧也引用同一份，是这次多做的一步：
> 写的人自带一个字面量的话，改清单时库里已有的行不会跟着变，
> 而「清单里没有这个值」与「库里存着这个值」会同时为真。

前端那一份**不是同一件事**：`web/lib/regions.ts#UNASSIGNED_REGION = "unassigned"`
是**筛选面的选项名**，不是源常量清单。两者刻意不同名也不同物，判据钉住这一点。

## 规则：放宽输入，不放宽纪律

```python
geographic = [r for r in regions if r and not is_source_constant(r)]
```

一行，放在既有那两支之前。**那句 raise 一个字都没动。**

实测四种输入：

| 输入 | 改前 | 改后 |
|---|---|---|
| `["global", "HK"]` | 抛跨区 | **`HK`** |
| `["global"]` | `global` | **`None`**（未归区，NEVER 硬挑） |
| `[]` | `None` | `None`（这一支没动） |
| `["CN", "HK"]` | 抛跨区 | **照旧抛跨区** |
| `["global", "CN", "HK"]` | 抛跨区 | **照旧抛跨区** |

最后一行是本卡最要紧的判据：**混进一个源常量不会让跨真区变得可以判**。
排除源常量之后顺手「取剩下的第一个」，那就是取众数换了个名字。

「放宽的是判定输入，不是判定纪律」这句写进了函数 docstring——
只写在 DEC 里的话，下一个改这个函数的人看不到它。

## 回填：只动那一条，且**先复核前提**

回填脚本第一步不是写库，是**重新数一遍全库的混源簇**：

```
全库混源簇: [('c-20260629-108', None, ['ghtrend', 'gtrends'])]
```

**还是只有那一条**（与开单时实查一致）。不是的话脚本直接停下并说
「前提变了：不止那一条——`DEC-058` 只授权回填今天这一条」。

```
成员 region: ['HK', 'global']
按 DEC-058 判出: HK
回填: None → 'HK'
全库 region IS NULL 的簇还剩: 0
```

**NEVER 顺手重算全库**（`DEC-058` 边界逐字）：顺手重算会把一次规则修订
变成一次静默的批量改数，而那正是 `DEC-056` 的迁移注释在防的事
（「回填是把标签改回与出处一致，不是改写事实」）。

判据那一侧判的是**混源簇的数目 ≤1**，而不是「那一条的 region 等于 HK」——
后者在测试库上永远拿不到（那条簇是 demo 库的数据），
而一次顺手重算会让混源簇的数目变化，那正是要拦的事。

## 单据

`docs/blocked/REGION-CN-HK-ONE-CLUSTER-SPANS-BOTH.md` 关闭：
`DEC-058` 选了乙，本卡实现并回填。


## 受影响面三条红，逐条点名

| 红的 | 归谁 | 处置 |
|---|---|---|
| `test_cluster_region::test_the_majority_is_never_taken` | **第三例的前提被 `DEC-058` 推翻**（`["global"]*5 + ["CN"]` 改前该抛） | 翻那一例、**留另外两例**，并补一条更硬的 |
| `test_cluster_region::…two_source_region_semantics…` | 它判的是**字面量** `region="global"` | 改判**语义** |
| `test_decisions_landed::…continue_the_existing_watermark` | 水位 056 → 058 | 跟着事实改数（第十次） |

### 第一条：翻面之后反而更硬

改前那一例是「5 个 global + 1 个 CN → 该抛」。`DEC-058` 之后它回 `CN`。

**而这一例翻面之后反而更硬**：`global` 在这里是**多数**，结果却是 `CN`——
也就是说，连「按多数」这条错法都被这一例挡住了。
另外补了一条 `["global"]*5 + ["CN"]*3 + ["US"]`：**混进源常量也救不了跨真区**。

### 第二条：判据说「去关那张单」，而那张单不该关

`test_the_two_source_region_semantics_are_still_different` 断言
`'region="global"' in ghtrend`，报错信息是「ghtrend 不再写死 global 了——去关那张单」。

**它的触发条件对，触发原因错**：`ghtrend` 并没有不再写源常量，
它只是从**自带字面量**改成了**引用那一处真相**。语义一个字没变。

改判语义（`"SOURCE_CONSTANT_REGIONS" in ghtrend`）而不是字面量。
`REGION-08-GLOBAL-IS-A-SOURCE-CONSTANT-NOT-A-REGION.md` **保持 open**——
那张单说的是「global 不是一个地区」，而这件事今天仍然成立。

> 一条判据的报错信息叫我去关一张单时，**先核它触发的原因是不是它说的那个**。
> 照着关掉的话，一张仍然成立的单就从盘上消失了。
