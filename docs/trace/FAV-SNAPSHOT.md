# FAV-SNAPSHOT · trace

**卡**：③收藏——快照由后端自取（`DEC-055`）。
**结果**：verified · 1 cycle · 判据 17 条全绿 · 真栈实测通 · 单据 `FAV-SNAPSHOT-HAS-NO-PROVIDER` 已关。

## 装载清单

`flint/api/favorites.py` · `flint/fav/store.py#add_favorite` · `flint/fav/pgstore.py`
· `flint/api/schemas.py#ErrorCode` · `flint/api/app.py`
· `web/components/plaza/cardActions.ts` · `web/messages/{zh,en}.json`
· `contracts_v04/models_v04.py#Favorite` · `docs/blocked/FAV-SNAPSHOT-HAS-NO-PROVIDER.md`

## 改了什么

| 落点 | 改动 |
|---|---|
| `FavoriteCreate.evidence_snapshot` | `dict` → `dict \| None = None`（`None` = 请后端自取） |
| `FavoritesApiDeps.snapshot_for` | 新增缝：`(target_kind, target_id) → dict`；`None` = 这一族没有取证面 |
| `flint/fav/snapshot_source.py` | 新件：按 `cluster_id` 取证据卡组，`jsonb` 解成值 |
| `flint/api/favorites.py#_snapshot_for` | 三条路三种答复（见下） |
| `ErrorCode` | 加 `EVIDENCE_FETCH_FAILED`（自己一码） |
| `create_app` | 注**真件** `build_snapshot_source(dsn)`，不是 `_unconfigured` |
| `cardActions.ts` | 不再送 `evidence_snapshot` |
| `zh/en.json` | 加「取证失败」那一句，与「内容已被清理」分开 |

冻结件 `Favorite` **一字未动**：仍是内嵌本体，不是 `snapshot_id`（判据钉着）。

## 三种「没存下」，三个码

| 送什么 | 码 | 用户该做什么 |
|---|---|---|
| 显式 `{}` | `VALIDATION_FAILED`（422） | 别送空的 |
| 不送、而没有取证面 | `FAMILY_NOT_CONFIGURED`（503） | 等下一版 |
| 不送、取证面在但取不着 | **`EVIDENCE_FETCH_FAILED`（502）** | 再试一次 |

外加列表屏那句「内容已被清理」——**第四种**，重试一万次也回不来。
四者一条都 NEVER 合并（`DEC-055` 边界逐字），判据逐条断言。

`EVIDENCE_FETCH_FAILED` **NEVER 借 `SERVICE_UNAVAILABLE`**：
那一个说的是「这一族没有后端」，这一个说的是「后端在、这次取不着」。

## 断点：单据里那句话不准，而**更准的版本对我们更有利**

单据写的是「从广场收的每一条，屏上都说『内容不在了』」。
实查 `flint/fav/store.py#add_favorite`：

```python
if not evidence_snapshot:
    raise ValueError("evidence_snapshot NEVER 为空: 空快照的收藏就是一个指向空处的壳, "
                     "而内嵌基线的全部意义就是不让它变成壳")
```

**它早就拒空快照**（`SCHEMA-09` 的既有基线）。所以广场送 `{}` 的那条请求
根本 **422、存不下去**，不是「存下了一份空的」。

这一处是我的判据先写错、再被既有代码纠正的：
第一版断言「显式 `{}` 会带着 200 存下去」，实跑回 422。

> **错的是判据，不是代码。** 既有实现早就守着这一条，我只是没有先读它。

判据改成断言 422 **且列表里一条都没有**（NEVER 被后端那份悄悄顶掉——
顶掉的话，调用方送来的数据被我们替换了而他不会知道），
并把这段更正写进了单据的「关闭」一节。

## 真栈实测（2026-08-11 · demo 库 · API 重起于改动之后）

```
POST /favorites  {"favorite_id":"fav-b11-check","target_kind":"cluster",
                  "target_id":"c-20260810-000"}          ← 不送快照
→ 200，evidence_snapshot =
  {"cards":[{"card_id":"card-20260810-c-20260810-000",
             "flags":["novelty"],
             "top_links":["https://s.weibo.com/weibo?q=%23%E9%A9%AC%E5%98%89%E7%A5%BA…"]}]}
```

**真证据卡、真微博链接**。改前这条请求（带 `{}`）会 422。

> 那条收藏留在 demo 库里没有删——它是一条真实有效的收藏，
> 且「删数据」是 owner 人审节点（`S2-10`），本卡 NEVER 自行触碰。

## 另一处：关单格式的判据只认带数字的卡号

`test_blocked_sheets_state` 的 `_CLOSER` 正则是 `[A-Z][A-Z0-9]*-\d+`，
而本批有几张卡的名字**不带数字**（`FAV-SNAPSHOT` / `REGION-CN-HK`），配不上。

没有去放宽那个正则（放宽会让它开始匹配正文里的随便什么词），
而是把关闭者写成 **`DEC-055` / 卡 `FAV-SNAPSHOT`**——
那本来也是更准的说法：**关掉一张单的是裁决，卡只是执行它的那一步**。
这条限制写进了判据自己的注释，下一个人不用再撞一次。

## 判据与门

`pytest tests/v041/test_fav_snapshot.py -q` → **17 passed**
· `test_blocked_sheets_state` 7 passed
· `npx tsc --noEmit` 退 0 · `npm test -- --run` 858 passed。
全量门留到本批收尾一并跑。
