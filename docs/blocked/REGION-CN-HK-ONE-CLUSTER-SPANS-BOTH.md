# REGION-CN-HK · 有一条簇的成员今天真的跨了两个区

**状态** closed · 2026-08-11 · `DEC-058` / 卡 `REGION-SPAN`（开单人 `REGION-CN-HK`）

## 是哪一条

| | |
|---|---|
| `cluster_id` | `c-20260629-108` |
| 词面 | `brain-computer interface`（脑机接口） |
| 成员来自 | `ghtrend`（`region='global'`）+ `gtrends`（回填后 `region='HK'`） |
| 今天的 `clusters.region` | `NULL` |

## 为什么不给它挑一个区

`flint/region/backfill.py#region_of_members` 的既有口径写死了：成员跨区时
**抛错并点名**，不取众数。原话：

> MUST 停下上报，NEVER 取众数——取众数只会把这个信号抹平，
> 并留下一个哪个区都不存在的假热点。

这条簇正是那个口径预防的情形。迁移 0028 因此**只动「只有 gtrends 一个源」的 35 条簇**，
把这一条留在 `NULL`（未归区）——它在筛选面上有自己的去处（`REGION-11`），
不会从屏上消失，也不会冒充成 CN 或 HK 的热点。

## 三个可选处置（owner 定）

| | 做法 | 代价 |
|---|---|---|
| 甲 | 保持 `NULL`（今天就是这样） | 它只在「未归区」里出现，选 HK 或 CN 的人看不到它 |
| 乙 | 把 `global` 视作「不参与定区」，按其余成员定区 → HK | 得给 `region_of_members` 加一条「源常量不参与」的规则，那是改口径 |
| 丙 | 拆簇 | 同一个事件被拆成两条，跨源印证（主榜核心）就没了 |

**倾向乙**：`global` 是 `ghtrend` 写死的常量，`web/lib/regions.ts` 已经写明
「它不是地理事实」。一个不表达地理的值参与定区，本来就说不通。
但那是**改判定口径**，`region_of_members` 的注释明写这一条不由实现者改。

## 影响面

今天全库只有这一条（实查：只有 gtrends 的簇 35 条 · 混源 1 条 · 不含 gtrends 233 条）。
下一版接更多源之后混源簇会变多，那时甲这条路会开始丢东西。


## 关闭

`DEC-058`（owner 2026-08-11）选了**乙**：不表达地理的源值不参与定区。
`REGION-SPAN` 实现并回填。

- 规则落在 `flint/region/backfill.py#region_of_members`（一行，放在既有两支之前）；
- 「哪些值是源常量」搬到 `flint/region/source_constants.py`——**一处定义他处引用**，
  改前它散在三处（筛选面的清单 · ghtrend 写库 · arxiv 默认参数）；
- 回填 `c-20260629-108`：`NULL → HK`，**只动这一条**，
  且脚本第一步先重新数一遍全库混源簇（还是只有它）。

**判定纪律一字未松**：`["global","CN","HK"]` 照旧抛跨区并点名——
排除源常量之后顺手「取剩下的第一个」，那就是取众数换了个名字。
