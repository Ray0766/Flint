# REGION-08 · `clusters` 加 region 列 + 回填 + 日更写入（迁移 0021）

> v0.4.1 第 6 批第六张。`depends_on: ["DEC-035-038-LANDING"]`（已 verified）。
> 卡本身 **verified**；回填在真库上撞出的那件事**另立单**（第六节）。

## 装载清单

`tasks-v041-b6.json#REGION-08` · `DECISIONS-v04.md#DEC-035` ·
`flint/region/bucketing.py`（context_refs，口径原话）· `flint/jobs/ingest.py` ·
`flint/norm/{canonical,terms}.py` · `migrations/versions/0020_identity.py`（形状）·
本机 55432 两个库的 `information_schema` 与实数据。约 16k tokens，**未超 40k**。

## 一、三跳：簇与 region 之间隔着什么

`clusters` 没有 region，`trend_items_raw` 有。中间的路是 ingest 自己建的：

```
cluster → evidence_cards.keyword_ids → keywords.canonical
        → canonicalize(trend_items_raw.keyword) 相同的那些原始条目 → 它们的 region
```

第三跳要 `canonicalize` 是因为原始词面是「synthetic data curricula for code agents」
而 `keywords.canonical` 是规范形——这正是 `_load_day_canonicals` 建立的对应关系，
本卡**按同一个方向再走一遍**，NEVER 反过来猜。

## 二、迁移 0021（`upgrade` 与 `downgrade` 都实跑过）

```
DATABASE_URL=…/flint_test alembic upgrade head   → 0020 → 0021，region 列 text
                          alembic downgrade 0020 → region 列消失
                          alembic upgrade head   → 又回来
DATABASE_URL 默认（flint）  已在 0021
```

**列可空且无默认值**，这是有意的：非空就必须给每条填一个值——包括成员里根本没有
region 的簇，于是必然逼出一个兜底值，而兜底值就是**给每个簇猜一个区**。
`NULL` 说的是实话：这一条还没判出来。

带索引是因为广场那条 query 的形状恒是 `WHERE region = $1`，而这张表**日更累积**；
等它慢下来再加索引，那是一次生产库变更（S2-10 要人工确认）。

## 三、回填：只算不写，三堆分开

`plan_cluster_regions` **只算**，`apply_cluster_regions` 才写。分两步是因为
撞车的那些要**先给人看**——一个 `UPDATE … SET region = …` 跑完之后，跨区的证据就没了。

三堆分开（`assigned` / `conflicts` / `unknown`）：合成一堆的话，
「填好了」与「有 37 个没判出来」在日志里长得一模一样。

demo 库实跑：**192 写入 · 1 跨区留 NULL · 0 判不出**。

## 四、NEVER 取众数——判据里有两条

1. `region_of_members("c-42", ["CN","CN","CN","US"])` 抛错，且消息**点名簇与区**
   （不点名的话上报的人无从去查）；
2. **阴性对照**：九票 CN 一票 US 也抛。没有这一条，实现换成
   `Counter(...).most_common(1)` 之后只要还留着那个 `raise` 就仍然绿——
   **真正的错法是先取众数再不抛**。

## 五、一次真返工：我差点让一条簇掐掉整天的日更

第一版在日更里直接让 `region_of_members` 的异常往上冒。`tests/m1` 的 30 天回放
**整批红**（15 个 setup error）——一条簇跨区把当天**其余全部热点**一起丢掉。

**改法不是放宽规则，是分清两处的代价**：

| 处 | 撞见跨区怎么办 | 为什么 |
|---|---|---|
| 回填（一次性） | **停下上报**，那一条不写 | 证据还在库里，随时能重跑；停下来正是要人看 |
| 日更（每天的批） | 那一条留 `NULL` + **大声记一笔**，继续跑完 | 停下来的代价是**那一天没有热点**；缺一个区标记的代价只是那一条不参与区筛选 |

**这不是双重标准**：同一条规则（`region_of_members`，一个函数、一处真相），
两处对**异常的处置**不同，而处置的差别由代价决定。日更那一处
NEVER 取众数、NEVER 静默——`region_conflicts` 单独一本（与 `naming_degraded` 分开：
「名字降级了」与「区判不出来」是两件事），逐条 warning + 收尾一条汇总。

改完 `tests/m1` **364 passed**（含金标回放 `test_m1_039`）。

## 六、回填撞出来的那件事：`global` 不是一个区

那条撞车的簇 `c-20260629-108` 查到底是这样：

```
gtrends  脑机接口  region=CN       ← 真的来自中国区
ghtrend  bci       region=global   ← 源码里写死的常量
词表把两者归到同一个规范词 brain-computer interface（**词表在正常工作**）
```

于是发现四个源给 region 的方式**不是一回事**：`weibo` 写死 `CN`、
`gtrends` 按区取、`ghtrend` **写死 `global`**。也就是说这一列同时装着两种断言：
「**这条来自中国区**」（地理事实）与「**这个源没有区可言**」（不适用标记）。

这不是 `PRINCIPLES#B5` 说的那种破法（不是两国报道被平均），
而是一个**数据模型问题**，且它会直接决定 `REGION-09` 那个筛选器说的是不是实话：
用户选「全球」拿到的会是**只来自 GitHub Trending 的那 103 条**。

已立单：`docs/blocked/REGION-08-GLOBAL-IS-A-SOURCE-CONSTANT-NOT-A-REGION.md`，
四选一 + 只要 owner 一句话（`global` 算不算一个区）。
两条判据守着这个发现不丢：单据必须开着且点名那个簇；
**并判源码**（`ghtrend` 还写死着 `global` 吗）——哪天不写死了，那条会红，
那正是该回去关单的时候。

## 七、verify

```
pytest tests/v041/test_cluster_region.py -q  → 20 passed（含 6 条 compose）
pytest tests/m1 -q                           → 364 passed
pytest tests/fe_views tests/v041/test_plaza_first_seen.py -q → 19 passed
ruff check . --no-cache                      → All checks passed
mypy --strict flint                          → 304 files, no issues
python tools/check_line_endings.py           → 219 个文件全是 LF
alembic upgrade / downgrade / upgrade        → 三次都跑通（第二节）
```

## 八、self_review

① 判据覆盖 acceptance 五条，含三条阴性对照（取众数要红 / 跨区不写库 /
跨区不掐日更）与一条「单据前提可复核」（判 `ghtrend` 源码而不是判单子里的转述）；
② 零冻结件改动——`region` 不在冻结件 `Cluster` 上，本卡只动库与 `flint/`；
③ 无禁用词；④ 改动面：迁移 + `flint/region/backfill.py` + `flint/jobs/ingest.py` +
判据，全在 outputs（`migrations/versions/0021_*` · `flint/` · 测试）；
⑤ 装载 ≈16k tokens。

## 九、留给下游

- `REGION-09`（端点真筛）**现在有列可筛了**，且它的阴性对照会拿到真结果：
  `CN` 89 条 / `global` 103 条 / `NULL` 1 条，**三者互不相同且都是全量的真子集**；
- 但 `REGION-10`（前端筛选器）的**文案**要等第六节那张单——
  「全球」这两个字今天说的不是实话；
- `heat_points` 仍然没有 region。按区统计热度是另一回事，本卡没碰。
