# 收藏的**内嵌证据快照**今天没有提供方

**状态** closed · 2026-08-11 · `DEC-055` / 卡 `FAV-SNAPSHOT`（开单人 `FAV-WRITES`）

## 现象

`POST /favorites` 的 `evidence_snapshot` 是**必填**（`FavoriteCreate`，`extra="forbid"`）。
而广场那个收藏动作送的是 **`{}`**（`web/components/plaza/cardActions.ts#favoriteCluster`）。

于是**从广场收的每一条收藏，屏上都会说「内容不在了」**
（`FavoritesLibrary` 按 `hasSnapshot: false` 渲染 `favorites.content_gone`）。

**那句话是实话**——快照确实是空的。但它读起来像一个缺陷，而真相是：
**没有人往里面放东西**。

## 为什么 `FAV-WRITES` 没有顺手补一个

冻结件 `Favorite` 的原话：收藏存的是**内嵌**证据快照，
理由是「只存 `snapshot_id` 的话，被引 snapshot 被周删清掉之后，
收藏就变成一个指向空处的壳」。

而本卡 acceptance④ 逐字：**前端 NEVER 自己拼一份快照**。
广场那一屏手上只有热点卡面（`cluster_id` / 名称 / 热度），
拿它们拼一个「证据快照」就是**编一份证据**——那正是这条禁令要拦的。

## 需要 owner / steward 的一句话（三选一）

1. **「收藏时由后端去取那一刻的证据卡，前端只发 target」** →
   `POST /favorites` 的 `evidence_snapshot` 从必填改成可选，
   后端按 `target_kind/target_id` 自己组一份。**worker 倾向这条**：
   快照是「收藏那一刻的证据」，而只有后端手上有证据。
2. **「广场先不提供收藏入口，改从证据卡那一屏收」** →
   那一屏手上有真的证据卡，拼得出真快照。
3. **「空快照就是本版的口径」** → 那么屏上那句「内容不在了」
   要换一句准确的话（它现在读起来像丢了东西，而其实从来没放进去过）。

## 绕行现状

三条写操作（取消 / 更新到最新 / 看陈旧）**已接通**，与本单无关。
广场那条收藏照旧送 `{}`——**没有改成编一份**，判据钉着它里面不许出现前端编的字段。


## 关闭

`DEC-055`（owner 2026-08-10）裁决 + `FAV-SNAPSHOT`（2026-08-11）实现。

**答的是这张单问的那件事**：`evidence_snapshot` 从必填改成可选，
前端只发 `target_kind` / `target_id`，**后端在收藏那一刻自取**当刻的证据卡组。

落点：

- `flint/fav/snapshot_source.py#build_snapshot_source`——按 `cluster_id` 取证据卡，
  `jsonb` 解成值（不解的话快照里存的是一段 JSON 文本）；
- `flint/api/favorites.py#_snapshot_for`——三条路三种答复，
  **NEVER 存空快照冒充成功**；
- `flint/api/app.py`——注的是**真件**，不是 `_unconfigured`；
- `web/components/plaza/cardActions.ts`——不再送 `{}`，
  而「前端 NEVER 自己拼快照」那条禁令原样钉着。

真栈实测（2026-08-11，demo 库）：收 `c-20260810-000` 一条，
不送快照 → 200，存下的快照里是**真的证据卡与真的微博链接**。

### 单据里有一处说法要更正

这张单写的是「从广场收的每一条，屏上都说『内容不在了』」。
实查 `flint/fav/store.py#add_favorite`：它**早就拒空快照**
（422「evidence_snapshot NEVER 为空：空快照的收藏就是一个指向空处的壳」，
`SCHEMA-09` 的既有基线）。

所以广场那一侧的实况比单据写的还硬——**送 `{}` 的那条请求根本存不下去**，
不是「存下了一份空的」。结论没变，病因更准了。
