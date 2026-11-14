# SLOT-01 · 卡面首见日期槽（零迁移）

> v0.4.1 第 6 批第二张。`depends_on: []`。

## 装载清单

`docs/steward/tasks-v041-b6.json#SLOT-01` · 工单 §3 逐槽代价表 ·
`flint/api/views.py`（plaza 那一段）· `contracts/models.py#Cluster` ·
`web/lib/viewsClient.ts#PlazaCluster` · `web/components/plaza/clusterToCard.ts` ·
`web/components/hotspot-card/HotspotCard.tsx` · `tests/fe_views/test_read_endpoints.py`
（种子形状）· `tests/v041/test_plaza_cards.py`（playwright 探针形状）。
约 9k tokens，**未超 40k**。

## 一、开工前先核实「零迁移」这句话

工单说这一槽零迁移。**我没照抄，先自己看了三处**——因为「零迁移」与「要迁移」
两种情况的做法完全不同，抄错一次要么白改要么破 `S2-1`：

| 看哪 | 实况 |
|---|---|
| 冻结件 `Cluster` | `first_seen: date` **在** |
| `clusters` 表 | 建表迁移里 `first_seen` **在** |
| `views.py` 的 SQL | `SELECT … c.first_seen …` **一直在查** |

第三条是最关键的一条：**它查了，取出来喂给 `ClusterSeries` 算新颖度，算完就丢。**
所以卡面那一槽空着，不是「数据没有」，是**一步之遥**。

三条都成立，本卡才允许「只改端点」。三条判据（`test_the_frozen_contract_already_has_first_seen`
/ `test_the_table_already_has_the_column` / `test_the_sql_already_selected_it`）
把这个前提钉住：哪天冻结件真的没有了，这张卡会当场红，而不是有人默默去加一列。

## 二、改了三处，逐处记账

### 1) `flint/api/views.py`（+6 行）

**改前**：`clusters` 列表推导里回八个字段，`first_seen[cid]` 只活在
`ClusterSeries(...)` 的入参里。

**改后**：多回一个 `"first_seen": first_seen[cid].isoformat()`。

**为什么非改不可**：卡面槽在前端已经建好（`DS-02`），前端拿不到值。
这是本批工单点名的「卡槽建好了端点不返回」——**修的只能是端点**。

**为什么恒 `isoformat()`**：卡面 `<time datetime>` 与判据都按 ISO 日逐字比。
换成时间戳或本地化格式，前端要再解析一次，而**解析失败时它静静地不显示**——
那就绕回本卡要修的那个样子，而且更难查。

### 2) `web/lib/viewsClient.ts`（`PlazaCluster` +1 字段）

**改前**：六个字段，没有 `first_seen`。
**改后**：加 `first_seen?: string`。

**为什么非改不可**：类型里没有的话，`clusterToCard` 写 `cluster.first_seen`
会被 `tsc` 拦下来——这一槽**永远接不上**，而屏上只是少一行。

**为什么是可选而不是必填**：`weak_signals` 那一轨与既有录制回放里没有这个字段。
声明成必填的话，少一个字段就是一处 `tsc` 红，而真相只是「那一条数据早于这次改动」。

### 3) `web/components/plaza/clusterToCard.ts`（+1 行映射 + 头注释）

**改前**：`return { clusterId, categoryId, nameNative, heat }`；
头注释写着「首见日期、地区、陈旧、Gate 判定**这四槽它一个都没有**」。
**改后**：多一行 `firstSeen: cluster.first_seen ?? null`；头注释改成**三槽**，
并逐条点名剩下三槽各归哪张卡（`REGION-08` / `SLOT-02` / `DEC-012`）。

**为什么连注释一起改**：那句「四槽都没有」现在是**假的**。
留着它，下一个人读到的是一份与代码相反的说明——
**指错的说明与指对的长得一模一样**，而它比没有说明更坏。

**`?? null` 而不是留 `undefined`**：卡面对两者的处理相同（都隐藏），
但 `null` 是「明确地没有」，`undefined` 是「没人提过这件事」。
下游要区分「端点回了空」与「取数层漏接了」时，这一处的区别就是唯一线索。

## 三、判据为什么打三处而不是一处

这一槽经过**库 → 端点 → 取数层 → 卡面**四道。任一道掉了它，屏上都只是「少一行」，
而少一行与「这个簇确实没有首见日期」**长得一模一样**。

所以判据把三处的值摆到一起逐字比：

```
库里的      SELECT first_seen FROM clusters WHERE cluster_id='fs-c1'
端点回的    GET /plaza/hot 那一条的 first_seen
屏上量到的  [data-testid="hotspot-first-seen"] 的 datetime 与 textContent
```

三条阴性对照：

1. **`first_seen != day`**——种子里首见日期**故意与查询日错开**（07-03 vs 07-20）。
   两个日期一样的话，端点拿 `day` 顶上去也能过；顶上去的那一版在每一条上都「有值」，
   看起来完全正常，而它说的是「今天第一次见到」，对一个跑了三周的热点那是假的；
2. **既有八字段一个不动**——下游按名取值，少一个就是一处静默的空；
3. **本卡没有新增迁移**——加一列也能让屏亮起来，而那一列会与既有列说同一件事，
   **下一个人无从知道该信哪一列**。

`checked > 0` 那条守的是判据自己：屏上取到的 `cluster-id` 与端点回的对不上时，
循环体一次都不进，**一条断言都没跑而测试是绿的**。

## 四、取证：本机栈重起过一次

demo 后端 `harness/demo_server.py` **没开 `--reload`**，所以它服务的是改动前的代码。
探针一开始报「154 条全都没有 first_seen」——那**报得对**：库和代码都对了，
在跑的那个进程是旧的。

重起 `:8000`（本机开发服务，非红线；前端 `next dev` 自带热更新，没动它）之后：

```
GET /plaza/hot?day=2026-07-04 → 154 条，first_seen 全在
屏上：159 张卡（精选 5 + 全量 154），159 张都量到这一槽且都有面积
```

截图 `.ui-probe/plaza-first-seen.png` **我自己看过**：
当前卡脚注左边是 `2026-07-04`，侧卡是 `2026-07-03`——
两张卡日期不同，说明它是**逐簇的真值**，不是一个常量。

## 五、verify

```
pytest tests/v041/test_plaza_first_seen.py -q          → 13 passed（含 3 条 compose）
pytest tests/fe_views tests/v041/test_plaza_cards.py
       tests/v041/test_plaza_states.py
       tests/v041/test_screens_live_probe.py -q        → 48 passed（端点形状变了，回归无伤）
cd web && npm test -- --run                            → 802 passed（本卡后 +3 条 → 805）
cd web && npx tsc --noEmit                             → exit 0
ruff check . --no-cache                                → All checks passed
mypy --strict flint                                    → 302 files, no issues
python tools/check_line_endings.py                     → 219 个文件全是 LF
node tools/{i18n_scan,no_scaffold_on_screen,check_design_constraints,check_screen_composition}.mjs
                                                       → CJK 0 / A 类 0 / 11 条 0 违规 / 34 项 0 违规
python tools/check_screen_coverage.py                  → 缺屏 0 · 端点对不上 0
```

一次返工：`re.S` 被 `ruff FURB167` 判了（要求写 `re.DOTALL`）。**它判得对**——
`re.S` 与 `re.M`、`re.I` 在一行里混着出现时，读的人要停下来想哪个是哪个。

## 六、self_review（worker.md §4.6）

① **测试覆盖 acceptance**：四条 acceptance 各有判据，且**三条是阴性对照**
（不拿 `day` 顶 / 不新增迁移 / 无日期时逐槽隐藏）。最容易空转的那条
（屏 ↔ 端点逐字比）自带 `checked > 0` 的守卫。
② **无冻结件偏离**：`contracts/` 与 `flint/domain/` 一个字节没动；
本卡反而**新增了一条判据钉住** `Cluster.first_seen` 必须存在。
③ **无 S2-8 禁用词**：grep 零命中。
④ **改动面**：三个文件，全在卡上 `outputs`（`flint/api/views.py` · `web/` ·
`tests/v041/test_plaza_first_seen.py`）；`web/components/plaza/plazaCards.test.tsx`
是 `web/` 下的判据文件，同在 outputs 内。
⑤ **装载未超预算**：≈9k tokens。

## 七、留给下游

- `SLOT-02`（陈旧标记）与 `REGION-08`（地区）走的是**同一条链**：
  端点多回一个字段 → `PlazaCluster` 加一个可选字段 → `clusterToCard` 搬一行。
  两张卡可以照本卡的形状做，**但 `REGION-08` 多一步迁移**，不要照抄「零迁移」那三条判据；
- 卡面第六槽（Gate 判定）**本批不做**（工单 §7-1，owner 面）。
  `clusterToCard` 的头注释里已经点名它归 `DEC-012`，NEVER 顺手拿 `status` 顶上去。
