# SLOT-02 blocked：热点簇身上没有一样东西是 Revalidator 能判新旧的

**状态** closed（owner 2026-08-08 挑**甲**，落为 `DEC-039`，由 `STALE-01` 执行）

## owner 的答复与它变成了什么

**挑甲**：本槽在广场上恒不显示，并把判据固化。owner 采纳的理由比单子里写的更进一步——
**本卡的产品不是那个隐藏动作，是那条禁令**：

> **全仓禁止**用 `last_active` 或 `first_seen` 做算术得出「陈旧」（形如 `now - last_active > N`）。

`STALE-01` 交付的三样：

| 产出 | 是什么 |
|---|---|
| `tools/check_no_timestamp_staleness.py` | 全仓尺子。两个条件同时成立才算违规：①时间戳字段参与算术或比较 ②结果被绑到一个陈旧词上 |
| `tests/v041/test_no_fake_staleness.py` | 13 条判据，含四条阴性对照（Python 变量 / 字典键 / TS / 驼峰）与两条精度对照 |
| `HotspotCard.tsx` 的 `stale` 槽注释 | 槽保留、恒不显示，**恢复条件写在这一处** |

### 那条边界比禁令本身更要紧

尺子 NEVER 禁「时间戳算术」本身——库里有三处正当的：
`flint/signals.py` 的 `novelty`、`flint/lineage/s4.py` 的 `dormant`、`flint/hotness.py` 的 `age_days`。
这正是本单 §六 乙里那句话的机器形态：**「沉寂」是个有用的东西，但它不叫「陈旧」**。
把它们一起禁掉的尺子会当场废掉三个正确实现，
而那种尺子会在第一次误报之后被人整条注释掉——**那时它一条都不再守**。

### §七 里那两条 acceptance 打架的事

`SLOT-02` 的 ②与③ 在字面上不能同时满足（详见本单 §六 末）。
选甲之后这件事不会发生：**本槽在广场上恒不显示，三态只剩一态**，所以本单不再需要 owner 裁这一句。

---

## 以下为立单时的原文（一字未改）

**状态**（原）open

> worker，v0.4.1 第 6 批 `SLOT-02`（卡面陈旧标记）。
> 卡面 acceptance①：「陈旧口径复用 Revalidator 统一 stale（D8 已决），NEVER 新写一套比对
> ——`HOTSPOT-06` 建的适配器就是为此」。
> **适配器在，卡在「拿它去判谁」**：它要的三样输入，热点簇一样都没有。
> 按第 6 批工单纪律 5「改动面大于卡上 outputs → 停下走 `docs/blocked/`」立单。

## 一、适配器要什么

`flint/analysis/stale_adapter.py#analysis_stale` 的签名逐字如下：

```python
def analysis_stale(
    diff_channel: DiffChannel,      # LedgerStore.diff 通道
    *,
    project_id: str,                # ① 哪个项目的账本
    analysed_at_version: int,       # ② 当时的账本版本
    current_version: int,           #    现在的账本版本
    cited_fact_ids: Iterable[str],  # ③ 这份东西引用过哪些事实
) -> StaleVerdict:
```

它判的是**一份分析引用过的事实，在项目账本里变没变**。

`clusters` 表的全部列（本机 55432 实查）：

```
cluster_id · canonical_name · category_id · centroid · status
· first_seen · last_active · parent_cluster_ids · merged_into · aliases
```

**没有 project_id、没有账本版本、没有引用的事实。** 一个热点簇不是一份分析——
它不引用事实，它**是**事实的来源之一。

要拿适配器去判它，就得给这三样各编一个值——那正是 acceptance① 明令禁止的
「新写一套比对」，只是换了个地方写。

## 二、库里带 stale 的地方，一处都不挂在簇上

全库实查（`information_schema.columns where column_name ilike '%stale%'`）：

| 表 | 列 | 判的是什么 |
|---|---|---|
| `deliverables` | `stale_reasons` | 交付物 |
| `pricebook` | `stale_after_months` | 价格行的时效（D13，另一套口径） |

**没有第三处。** 端点侧同理：

```
GET /deliverables/{id}/staleness   → 交付物（flint/api/staleness.py，BE-04）
POST /favorites/{id}/staleness     → 收藏的快照（flint/api/favorites.py，BE-08）
GET  /design/stale-notices         → 设计图谱（另一套口径）
```

三条各判各的对象，**没有一条判热点簇**。

## 三、唯一能挂到簇上的那个 stale，挂上去说的是另一件事

冻结件 `contracts_v04/models_v04.py#Favorite` 确实能指向一个簇：

```python
target_kind: Literal["cluster", "topic", "deliverable", "card"]
target_id: str
snapshot_stale: bool = False     # 只能由 Revalidator 置 True (§6-H1)
```

所以「**你收藏的那份快照旧了**」这句话，是唯一一句数据上说得出口的。
把它印在广场卡上，用户读到的却是「**这个热点旧了**」——**两句话不是一回事**：
前者是我这份存档过时了，后者是这个热点不再活跃。

这与 `DEC-038` 是同一个形状：**借一个已经有主的记号去说另一件事，比不给记号更坏。**

而且就算决定要借，今天也借不到：

1. `flint/fav/store.py:35` 逐字写着「**内存实现**；SQL 实现随 E2 的 `favorites` 表接入」，
   而 `favorites` 表**不存在**（实查：`information_schema.tables` 里零命中）——
   标记会在每次重起后消失，屏上于是「昨天有今天没了」；
2. demo 后端（owner 亲自看的那一份）**根本没挂 favorites 那一族**；
3. 广场是**匿名可看**的屏，`GET /plaza/hot` 没有身份头。收藏是**按人**的，
   要在广场显示它，广场就得先知道你是谁——那是一次鉴权面的扩张。

## 四、剩下那条路是明令禁止的

`clusters.last_active` 就在手边，拿它跟今天一比就能算出「多少天没动了」。
**三处白纸黑字禁止这一条**：

- 规格 `docs/前端功能说明-v2.md#2.15`：「stale 判定来自后端 `Revalidator` 统一口径，
  **前端 NEVER 自行按时间戳推断**」；
- 冻结件 `Favorite` 的 docstring：「前端 NEVER 自行按时间戳推断新鲜度」；
- `flint/fav/stale.py` 的 docstring 把代价说透了：
  「按时间戳推断看起来总是对的：三个月前的收藏『显然』旧了，可事实一个字没变时
  那个标记只让用户白重跑一次；而昨天的收藏也可能因一次事实移除而彻底失效。」

## 五、顺带一条：规格 `#2.14` 里本来就没有这一槽

`docs/前端功能说明-v2.md#2.14`（热点卡片广场）的状态呈现规则共四条：
骨架卡 / 空结果 / 单区源全灭 / 译名缺失。**没有陈旧一条。**
陈旧是 `#2.15`（收藏图书馆）的规则，那一屏已经在显示它
（`web/components/favorites-library/FavoritesLibrary.tsx` 三态齐全）。

卡面那一槽来自素材 `CardStack.dc.html` 的版式，`DS-02` 照素材建了槽——
**素材有的槽，产品不一定有那个数据**。这是本批第二次撞见同一形状
（第一次是 `DEC-036`：规格给 `Topic` 写了名称三元组，而冻结件里它没有名称）。

## 六、给 owner 的四选一

| 选项 | 做什么 | 代价 | 我的看法 |
|---|---|---|---|
| **甲** | **本槽在广场上恒不显示**，并把判据固化：广场 NEVER 按时间戳推断陈旧 | 0（已随本单交付 `tests/v041/test_plaza_stale.py`） | **推荐**。今天没有这个数据，诚实的做法就是不显示。判据挡住下一个人「顺手用 last_active 补上」 |
| 乙 | 给簇定义一套自己的活跃度口径（例如「N 天无热度点 = 沉寂」），迁移 + 日更写入 | 一次产品决定 + 一次迁移 + 一张卡 | 它是个**有用的东西**，但它不叫「陈旧」——叫「沉寂」才不会与 Revalidator 的 stale 混。要做请单开一张卡、单起一个名 |
| 丙 | 先把 `favorites` 落库（E2 的表），再在**收藏屏**的热点卡上显示 stale | 一次迁移 + favorites 的 SQL 实现 | 语义是对的，但它是**收藏屏**的事，不是广场。规格 `#2.15` 本来就这么写 |
| 丁 | 广场接身份 + 挂 favorites + 显示「你的存档旧了」 | 鉴权面扩张 + 上面全部 | **不建议**：广场上那个记号会被读成「这个热点旧了」 |

### 顺带请 owner 裁一句：acceptance②与③在字面上打架

② 说「判过且新鲜（**不挂标记**）· 未判定过（**槽隐藏**）」——这两者在屏上就是同一个样子；
③ 又说「三种状态分别构造，断言**屏上互不相同**」。**两条不能同时满足**，
除非给「判过且新鲜」也发一个记号（一个绿点之类）。

本单按 ② 的括号为准（它是具体的那一条），并按 `DEC-038` 的口径不发新记号。
选甲的话这件事不会发生——本槽在广场上恒不显示，三态只剩一态。

**在 owner 挑之前，本槽维持隐藏**——`HotspotCard` 的逐槽隐藏规则原样不动，
`clusterToCard` **不传** `stale`（`undefined` = 没判过），
`tests/v041/test_plaza_stale.py` 把这个状态钉住并挡住那条时间戳捷径。

## 七、本单交付了什么（blocked ≠ 什么都没做）

`tests/v041/test_plaza_stale.py`：

- **三态在组件层分别构造**（`web/components/hotspot-card/HotspotCard.test.tsx` 已有）：
  `true` → 挂标记 · `false` → 不挂 · `undefined` → 不挂。
  另钉住挂标记的条件**恒是 `=== true`**：写成 `{stale && …}` 时行为一样，
  但下一个人改成 `{stale !== false && …}` 不会有任何判据响，
  而那一版会给**没判过**的簇挂上陈旧标记；
- **禁止时间戳推断**：广场那一条链（`views.py` 的 plaza 段 · `clusterToCard` ·
  `PlazaCards`）里 NEVER 出现 `last_active` 与今天的比较；
- **禁止顺手重核**（acceptance④）：广场取数不打任何 `staleness` / `refresh` 端点；
- **本单自身在位**：单据 open 且这四条判据引着它——单子被关掉而问题没解决时，
  判据当场红。
