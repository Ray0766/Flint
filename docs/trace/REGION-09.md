# REGION-09 · `GET /plaza/hot?region=` 真的筛

> v0.4.1 第 6 批第七张。`depends_on: ["REGION-08"]`（已 verified）。

## 装载清单

`tasks-v041-b6.json#REGION-09` · `DECISIONS-v04.md#DEC-035` ·
`flint/api/views.py`（plaza 段）· `docs/前端功能说明-v2.md#2.14` ·
`tests/v04/region/test_by_source_regions.py`（既有分列判据）·
`docs/trace/REGION-08.md`。约 9k tokens，**未超 40k**。

## 一、改前是什么样

签名 `async def plaza(day: str)`。**FastAPI 对未声明的 query 静默忽略**——
带 `region=CN` 回 200 且与不带**逐字相同**。改后实测（本机 demo 栈）：

```
day=2026-07-04              → 154 条
day=…&region=CN             →  68 条
day=…&region=global         →  85 条
两者互不相交、都是全量真子集
day=…&region=ZZ             → 400 unknown region 'ZZ'; known: CN, global
```

## 二、阴性对照为什么用 `CN` 与 `global`，不是卡面写的 `US`

卡面举的例子是 `region=US`。**库里没有 US**——`REGION-08` 回填之后
实际存在的两个值是 `CN` 与 `global`。

拿一个不存在的区做对照，「两个集合不同」会因为**一边是空集**而恒成立，
判据就退化成「查不存在的区返回空」——**它测不出筛选器有没有在工作**。
所以对照取两个都非空的真值。

`global` 这个值本身语义有问题（`ghtrend` 写死的常量，不是一个区），
已由 `REGION-08` 立单。**那不影响本卡**：端点按列筛这件事是对的，
有问题的是那一列的语义，而那是 `REGION-10` 的文案要等的东西。

## 三、四条判据各挡一种假筛

| 判据 | 挡的是 |
|---|---|
| 两个区集合不同 | 改前那种「回 200 而不筛」——只断言参数被接受的话它照样绿 |
| 都是全量的**真子集** | 把 region 当排序键或后置装饰：结果集不变而顺序变了，上一条会绿 |
| `NULL` 区的簇哪个区都不属于 | 把判不出区的簇塞进某一个——`REGION-08` 留 `NULL` 就是为了这一刻 |
| 不传时逐字相同 | 增量破坏基线（规格 #2.14 的增量口径） |

## 四、无效值：400 且**清单从库里取**

静默回全量是最坏的：用户拼错一个区名，拿到的是全世界的热点，
而屏上写着他选的那个区。

清单 `SELECT DISTINCT region FROM clusters` 现取，**NEVER 在代码里抄一份九区表**
——抄一份的后果是新增的区真的有数据，而端点说它不存在。
判据除了看消息内容，还断言 `views.py` 里**没有写死的区名**。

## 五、`by_source` 的地区维度：另开一键

`by_source` 是 `{源: 分值}`，`HOTSPOT-07` 的分列判据按这个形状读。
往里塞一个对象，那些判据会在**读到分值的地方拿到一个 dict**——
它们不会报错，只会算出一个错的列高。

所以新增 `by_source_region: {源: 区}` 并行一键。判据两头都钉：
`by_source["weibo"]` 仍是数、`by_source_region["weibo"]` 是区；
另断言既有判据文件**还在且本卡一个字没改它**（点名文件，
而不是「某处有 by_source」——后者在判据被整份删掉时，
只要别的文件还写着这四个字就照样绿）。

## 六、取证时又踩了一次同一个坑

第一次打真栈，四条对照**全部为假**（CN 154 / global 154）。
那不是代码没改对——是 `:8000` 还在跑旧进程（`demo_server` 没开 `--reload`）。

**这已经是本批第二次**（`SLOT-01` 时一样）。它值得记下来：
改后端之后打真栈拿到「和改前一模一样」的结果时，
**先确认那个进程是不是新的**，再去怀疑代码。两者的现象完全相同。

## 七、verify

```
pytest tests/v041/test_plaza_region_query.py -q            → 9 passed（含 8 条 compose）
pytest tests/v04/region tests/fe_views
       tests/v041/test_plaza_first_seen.py -q              → 122 passed
ruff check . --no-cache                                    → All checks passed
mypy --strict flint                                        → 304 files, no issues
真栈（:8000，重起后）                                       → 第一节那五行
```

## 八、self_review

① 判据覆盖 acceptance 五条，四条是阴性对照（第三节那张表）；
② 零冻结件改动；③ 无禁用词；④ 改动面只有 `flint/api/views.py` + 判据，都在 outputs；
⑤ 装载 ≈9k tokens。

## 九、留给下游

`REGION-10`（前端筛选器）现在**接得上真东西**了。但屏上那两个选项的**文案**
要等 `REGION-08` 那张单——「全球」两个字今天说的不是实话。
建议 `REGION-10` 直接用端点回的区名原样显示，等 owner 裁完再做人读映射。
