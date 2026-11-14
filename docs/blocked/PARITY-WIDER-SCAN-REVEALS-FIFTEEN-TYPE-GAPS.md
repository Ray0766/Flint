# 尺子看清之后：15 条类型缺口浮出来（本来就在，只是量不到）

**状态** closed 2026-08-08（`TYPE-05` + `TYPE-06`，v0.4.1 第 7 批 · 两类计数均为 0）

## 十五条清完了

对账器实跑：`field_mismatch` **0** · `frontend_untyped_response` **0**
（总发现数 36 → 21，剩下的是 20 条「后端有前端没用」+ 1 条「前端要而后端没有」，
两类都不属本单）。

### `field_mismatch` 那七条，**六条不是「漂移」**

`TYPE-05` 开工第一件事是把实跑输出逐条摆出来，发现卡面那句「真漂移」只对
`/cards/{}` 成立。`_best_interface` 的门槛是「至少两个字段重合」——
它挡住了单字段巧合，**没挡住双字段巧合**：

| 端点 | 被误匹到 | 凭什么 |
|---|---|---|
| `/charts/{}` · `/facts/{}` | `types.ts#DisputeSubmitEcho` | 共有 `status` / `ledger_version` |
| `/favorites` · `/shares` | `interventionClient.ts#DisputeInput` | 共有 `target_id` / `target_kind` |
| `/hints/{}` | `viewsClient.ts#VerdictGap` | 共有 `missing_what` / `cause` / `action` |

所以修法**不是「对齐那些接口」**——那会把 chart 的字段塞进一个争议回执里
（`DEC-034` / `DEC-038` 反复禁的借槽），而是**各建自己的类型**。

### 卡面写八条，`TYPE-06` 实做**五条**

`/settings/locale` 与两条 deref（`/citations/{}` `/price-entries/{}`）
由 `TYPE-05` 顺带建了：前者在补完前六条之后**换了类别**
（从 untyped 变成 mismatch），要让 `field_mismatch` 归零就得连它一起做；
后两条与那四条同住六条解引用通道，分两处建会让读的人只看到一半。

**差额记在这里**——照卡面那个八去找，会有三条怎么也找不到。

### 落点

| 文件 | 装什么 |
|---|---|
| `web/lib/derefTypes.ts` | 六条解引用通道（fact / chart / card / hints / citation / price） |
| `web/lib/types.ts` | favorite · share · design_generate（payload 与响应**两个**）· locale |
| `web/lib/accountTypes.ts` | account · billing · design templates / replay · 干预锁 |

**字段逐个对着后端读**，`unknown` 只留两格（`FactDeref.value` 与
`FavoriteRow.evidence_snapshot`——它们真的是任意 JSON），并配闭集判据：
十五个 `unknown` 铺满能让尺子归零，而 `tsc` 从此对这些端点一个字都不检查。

### 尺子改了一处：**单键响应**

`/interventions/lock` 的响应键只有 `locked` 一个，
而「至少两个字段重合」那道门在它身上**结构性地迈不过去**——
无论前端怎么写都凑不出两个重合字段，于是它恒被报成「没建类型」，建了也不算。

改法要求**接口字段集与响应字段集完全相等**：那不是巧合，是精确匹配。
多键响应那道门**一字未改**，三条判据（精确命中 / 更大的接口不算 / 一个字段的巧合不算）
一起守着。

---

## 以下为立单时的原文（一字未改）

**状态**（原）open

> 发现者：worker，v0.4.1 第 6 批 `GAUGE-14`（修对账器的两个盲区）。
> **这 15 条不是新引入的**——它们一直在那儿，是尺子看不见调用点，
> 所以连带看不见那些调用的响应类型对不对。

## 怎么冒出来的

`GAUGE-14` 之前，`frontend_calls` 只扫 `web/lib/` 且首段要在一串写死的白名单里。
扫不到的调用，其响应类型自然也无从比对。

盲区修掉之后，那些调用第一次进了比对面，于是：

| kind | 条数 | 是什么 |
|---|---|---|
| `field_mismatch` | 7 | 建了类型，但字段与后端回的对不上 |
| `frontend_untyped_response` | 8 | 这条端点的响应**前端根本没建类型** |

```
field_mismatch            /cards/{} · /charts/{} · /facts/{} · /favorites ·
                          /hints/{} · /projects/{}/design_generate · /shares
frontend_untyped_response /account · /billing · /citations/{} ·
                          /design/sessions/{}/replay · /design/templates ·
                          /interventions/lock · /price-entries/{} · /settings/locale
```

## 为什么本卡不修

`GAUGE-14` 的 outputs 是 `tools/check_fe_be_parity.py` + `docs/端点分诊-v041.md` + 判据。
补类型是 `web/lib/` 的活——按第 6 批工单纪律 5 停下立单。

**而且它们不该混在一张卡里**：修尺子与补类型是两件事，
混着做的话，下一次尺子出问题时没人分得清「是尺子又瞎了还是类型又缺了」。

## 三条 pinned 判据跟着改了（改的是数，不是意图）

`test_parity_dynamic_path::test_both_kinds_are_genuinely_zero_now`、
`test_types_complete::test_the_untyped_count_is_pinned_until_the_ruler_is_fixed`、
`test_fe_be_parity::test_a_drift_and_an_untyped_response_are_two_different_findings`
此前钉的是**零**。

那个零在**盲的尺子**下是真的；在看得见的尺子下不再是。
三条都改成钉当前的实测集合并引本单——**判据跟着事实走**，
钉死一个过期的零，只会让下一次真正的修复被判成错。

## 修法（一张卡，`web/lib/` + 判据）

1. 八条 `frontend_untyped_response`：给响应建类型（形状照后端实跑）；
2. 七条 `field_mismatch`：把字段对齐（**以后端为准**——前端类型是消费方）；
3. 修完之后回到那三条判据，把集合改回**空**，并关掉本单。

## 顺带：`/workbenches/{}/nodes`

同一次宽扫还露出一条 `frontend_wants_missing_backend`：
前端在调 `POST /workbenches/{id}/nodes`，而后端只有 `…/edges`。
**那是真的**（`GRAPH-02` 的节点入台端点没建），一并记在这里等排期。
