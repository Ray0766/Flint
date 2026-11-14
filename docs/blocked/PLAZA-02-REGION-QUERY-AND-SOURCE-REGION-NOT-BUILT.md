# PLAZA-02 blocked：地区筛选与 by_source 分列，两条后端面都不存在

**状态** closed 2026-08-08 · 缺口一由 `REGION-08/09/10` 建成，**缺口二由 `REGION-12` 清掉**（v0.4.1 第 7 批）

## 缺口二结案：端点回原文词面了

`GET /plaza/hot` 每条簇多回一键：

```
"by_source_text": {"weibo": "＃脑机接口＃ 临床试验", "ghtrend": "brain-computer-interface"}
```

词面来自 `trend_items_raw.keyword`，走三跳（与 `flint/region/backfill.py` 同一个方向）：
`lineage_results` 当日成员 → `keywords.canonical` → canonicalize 后相同的原始条目。
join 落在新模块 `flint/region/source_text.py`（纯函数），
**NEVER 把 `flint/jobs/ingest.py` 那段 import 进 API**——它绑着整张作业依赖图，
而且是 v0.4 已 verified 的文件。

| 本单当初担心的 | 现在的落法 |
|---|---|
| 「把分值塞进 `text`」 | 判据 `test_the_caller_never_puts_a_score_into_the_text_slot` 扫源码 |
| 「`SourceColumns` 无真可渲染的数据」 | `ClusterSourceLines` 接上广场网格，每条簇一组 |
| 「原文逐字」 | 判据用带首尾空格与全角井号的种子钉住：**回给屏上时 NEVER 再归一化一次** |
| 「少数派不合并 / 未归区排最后」 | `SourceColumns` **一个字没改**（v0.4 已 verified），两条纪律原样生效 |

**同一个源当天说过两条落进同一个簇时：取第一条并记数，NEVER 拼接**——
拼起来的那句话没有任何一个来源说过，那就是 `B4` 禁的合成句，只是换了个地方合成。

**查不到词面的源**不出现在 `by_source_text` 里（不是空串），
由 `ClusterSourceLines` 另起一行如实说「这几个源的原话没查到」——
`text` 槽契约上是原文，塞 `—` 进去屏上会写着「微博说：—」，而微博没说过这句话。

---

## 以下为立单时的原文（一字未改）

**状态**（原）open · 缺口一（`region` query）已由 `REGION-08/09/10` 建成；**缺口二（`SourceColumns` 的原文词面）仍缺**，见文末结案段

> worker，v0.4.1 第 5 批 `PLAZA-02`（广场②：地区与源筛选上屏）。
> 卡面 `blocked_by: null`，但**两条 acceptance 各自要一份后端还没有的数据**。
> 本卡触碰面是 `web/app/plaza/` + 测试，两条都要改 `flint/`——
> 按第 5 批工单纪律 4「改动面大于卡上 outputs → 停下走 `docs/blocked/`」立单。

## 缺口一：`GET /plaza/hot` 没有 `region` query（acceptance②）

**规格逐字写着它该有**（`docs/前端功能说明-v2.md#2.14` 第 104 行）：

```
- **端点**：`GET /plaza/hot?region=`【已建，增 query】。
```

同文件第 41 行还写明增量口径：「不传 `region` 时行为与基线逐字相同（增量不破坏）」。

**实测：那个 query 没有被建。** `flint/api/views.py:66` 的签名是

```python
@app.get("/plaza/hot")
async def plaza(day: str) -> Response:
```

只有 `day`。FastAPI 对未声明的 query 参数**静默忽略**，所以

```
$ curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/plaza/hot?day=2026-07-04&region=CN"
200
```

回的是 **200 + 全量 154 条**，与不传 `region` 逐字相同。
这正是「看起来通了」的形状：前端把 `RegionSwitch` 接上去、切区、请求发出、页面刷新，
**而热点集合一条都没变**——一个静静地什么都不筛的筛选器，**比没有筛选器更坏**：
用户会把「全国的热点」读成「这个区的热点」，并据此做判断。

### 数据面在不在（已查，给 owner 估工用）

| 表 | 有没有 region | 出处 |
|---|---|---|
| `trend_items_raw` | **有**（`sa.Column("region", sa.Text, nullable=False)`） | `migrations/versions/0004_trend_items_raw.py:25` |
| `heat_points` / `clusters` | **没有**（端点 join 的正是这两张） | `migrations/versions/0001_index_layer.py` |

所以「增一个 query」不是改一行签名：要么把 `trend_items_raw.region` 一路带到
`heat_points`（迁移 + 日更作业），要么在查询里多 join 一层。
另有 `flint/region/bucketing.py`（REGION-04：聚类先按 region 分桶）可能已经持有簇的地区血缘，
**下一步该先去核它**——若簇本来就带区，代价会小很多。

## 缺口二：`by_source` 没有每个源的地区（acceptance④）

acceptance 写「`by_source` 分列 ≥2 列且无合成句（`HOTSPOT-07` 既有判据）」。
核过 `HOTSPOT-07` 的口径（`docs/trace/HOTSPOT-07.md`）：那个组件
**是按 `region` 分列的**，列的语义是「哪个地区的源这么说」，
未归区单独成列且恒排最后（与 REGION-02 的 `UnknownSourceRegion` 同一条纪律）。

而 `GET /plaza/hot` 回的 `by_source` 是 `{source_id: 热度}`：

```
{"weibo": 100.0}                      ← 154 条里 153 条是单源
{"ghtrend": 0.0, "gtrends": 100.0}    ← 唯一一条多源簇
```

**没有任何一个源带地区**。产出地区的模块是 `flint/region/by_source_region.py`（REGION-08），
它是纯函数，**全仓没有任何端点暴露它**（`grep by_source_region flint/api/` 零命中）。

### 为什么不拿 source_id 去填 region 位

那正是本批 `DEC-034` 刚立下的同一条：**NEVER 借一个已经有主的字段去说另一件事**。
`SourceColumns` 的 `region` 是「来源地区」，把 `weibo`／`gtrends` 填进去之后：

- 屏上会出现一列叫「weibo」的「地区」，与真的地区列（CN／JP）混在同一个维度里；
- `HOTSPOT-07` 那条「未归区单独成列且排最后」的纪律当场失效——没有未归区这个概念了；
- 等缺口一修好、真地区来了，两套语义会在同一个组件里打架。

## 已试三条

1. 打端点带 `region=CN` → 200 且结果与不带逐字相同（上面的 curl）；
2. 读 `flint/api/views.py:65-82` 的实现与 SQL → 只 join `heat_points`／`clusters`，
   两张表都没有 region 列；
3. 全仓找 `by_source_region` 的端点 → 零命中（模块在、出口不在）。

## 需要 owner 的什么

1. **缺口一**：`GET /plaza/hot` 增 `region` query 由谁做？它要动 `flint/api/views.py`
   （可能还要动迁移与日更作业），**属后端面，不在本批 18 卡的触碰面内**。
   建议先核 REGION-04 的簇地区血缘再估工。
2. **缺口二**：`by_source` 要带地区，需要给 REGION-08 开一个出口
   （或在 `/plaza/hot` 的 `by_source` 里带上每个源的 region）。
   **在那之前 `SourceColumns` 在广场上无真可渲染的数据**。
3. **本卡怎么算**：三选一——
   ① 等两条后端补齐再回来做（本卡保持 blocked）；
   ② 拆成 `PLAZA-02a`（后端两条）+ `PLAZA-02b`（前端接线），2a 交给后端批次；
   ③ 只做「九区清单从 `GET /settings/locale` 取并上屏、但**明说该区筛选尚未生效**」的诚实态
   ——**不推荐**：屏上出现一个自称没生效的控件，不如不出现。

## 绕行现状

`PLAZA-02` 记 `blocked`，本轮改取 `PLAZA-03`（依赖 `PLAZA-01`，已 verified）。
`RegionSwitch` 与 `SourceColumns` 仍然全仓零页面引用——**这件事本卡没能修掉，如实记账**。
第 5 批完成态报告会把这两条逐条列名。

---

## 结案（v0.4.1 第 6 批）· 一条关了，一条换了形状

### 缺口一：`GET /plaza/hot?region=` —— **已建，已上屏**

| 卡 | 做了什么 |
|---|---|
| `REGION-08` | 迁移 0021 给 `clusters` 加 region 列 + 回填（192 写入 / 1 跨区留 `NULL`）+ 日更写入 |
| `REGION-09` | 端点真筛。合法值取自冻结件 `contracts_v04.Region`（与 `/settings/locale` 同源） |
| `REGION-10` | `RegionSwitch` 接上广场屏；区写进 URL；空区落既有「该区当日无数据」态 |

真屏实测：全量 154 → `CN` 68，其余八区 0 且各自落空态，**没有任何一个区回全量**。

### 缺口二：`SourceColumns` —— **换了形状，仍然开着**

单据原先写的是「`by_source` 没有每个源的地区」。**那一半补上了**：
`REGION-09` 给每条簇加了 `by_source_region: {源: 区}`。

**但 `SourceColumns` 还是接不上，缺的是另一样东西。** 它要的是

```ts
SourceStatement { sourceId: string; region: string; text: string }
                                                    ^^^^ 契约逐字：「原文；NEVER 是译文」
```

广场每个源手上只有**分值**（`by_source`）与**地区**（`by_source_region`）。
把分值塞进 `text`，就是拿一个已经有主的槽去说另一件事——
`DEC-034` / `DEC-038` 反复禁的那一条。

**真正缺的是每个源的原文词面**：`trend_items_raw.keyword`
（微博说「脑机接口」、GitHub 说 `bci`，同一个热点两种说法）。
那正是 `PRINCIPLES#B4`「把话还给说话的人」要的东西——
两国对同一件事说法不一致时，读者失去「谁说的」就失去了唯一能判断可信度的东西。

**它离端点只有一个字段**（`/plaza/hot` 每条簇多回一个
`by_source_text: {源: 原文词面}`），但那是 `flint/api/views.py`，
**不在 `REGION-10` 的 outputs（`web/app/plaza/`）里**——
按第 6 批工单纪律 5 停下，不自行扩面。

**建议**：单开一张卡（`SLOT-04` 之类），outputs = `flint/api/views.py` +
`web/app/plaza/` + 判据；一个 cycle 够。判据要盯住：
原文**逐字**（NEVER 归一化空白或全半角）· 少数派不合并 · 未归区单独成列且排最后。
