# PARITY-BLIND-TO-PAGES-AND-UNLISTED-PREFIXES · 对账器把 12 条已接线的端点报成「前端没人用」

**状态** closed @2026-08-09 · `GAUGE-14`（v0.4.1 第 6 批）

**发现者** worker / `GAUGE-11` 逐条分诊时 · **发现时间** 2026-08-06
**危害** 中 —— **报的是反的**：人会照着它去接一条已经接好的线
**改动面** `tools/check_fe_be_parity.py`，在 `GAUGE-11` outputs 之外

## 实测

`backend_unused_by_frontend` 当前 35 条，其中 **12 条前端真在调**。
两个盲区，机制不同：

### 盲区一 · 首段白名单（7 条）

```python
_ENDPOINT_LITERAL = re.compile(
    r"/(?:plaza|clusters|projects|topics|jobs|deliverables|categories|"
    r"favorites|shares|public|design|profile|pricebook|account|billing|settings)"
    r"[^`\"'\s]*")
```

首段清单是**写死的**。不在这串里的路径**永远扫不到**：

| 端点 | 调用点 |
|---|---|
| `/facts/{}` | `web/lib/derefClient.ts:17` |
| `/price-entries/{}` | `web/lib/derefClient.ts:18` |
| `/citations/{}` | `web/lib/derefClient.ts:19` |
| `/charts/{}` | `web/lib/derefClient.ts:20` |
| `/cards/{}` | `web/lib/derefClient.ts:21` |
| `/hints/{}` | `web/lib/derefClient.ts:22` |
| `/interventions/lock` | `web/lib/interventionClient.ts:54` |

**这七条全在 `web/lib/` 里**——尺子扫了这个目录，只是那条正则不认它们的首段。

### 盲区二 · 只扫 `web/lib/`（5 条）

`frontend_calls` 里 `lib_dir = web_dir / "lib"`。而 `useScreenData("/account")`
这类调用写在 `web/app/**/page.tsx`：

| 端点 | 调用点 |
|---|---|
| `/account` | `web/app/account/page.tsx:31` |
| `/billing` | `web/app/billing/page.tsx:13` |
| `/favorites` | `web/app/favorites/page.tsx:32` |
| `/projects/{}` | `web/app/projects/[id]/page.tsx:19` |
| `/settings/locale` | `web/app/settings/locale/page.tsx:21` |

## 为什么这比「漏报」更坏

`backend_unused_by_frontend` 这个名字读起来是「后端有、前端没人用」。
**修法完全相反**：

- 真没人用 → 去接线，或考虑退役；
- 尺子没量到 → 去修尺子。

报错了方向的尺子，会让人去接一条**已经接好的线**——接完之后它照样报「没人用」，
那时人会以为自己接错了。

## 尺子自己写过一句相关的话

`frontend_calls` 的 docstring 解释过为什么只扫 `web/lib/`：
页面里的 `/plaza` 是 `href` 导航不是 API 调用、测试里的是样例数据。
**那个理由当时是对的**——`WIRE-03` 之前页面确实不取数。
`WIRE-03`/`WIRE-12` 把五张屏改成真取数之后，这个前提就不成立了，
而没有任何东西提醒过它。

## 修法（建议）

1. **首段白名单换成「后端路由表的首段集合」**：两侧本来就都在这个工具里，
   白名单可以**算出来**而不是写死。写死的清单每加一族端点就要有人记得来改，
   而忘了改的表现是「那一族恒报没人用」；
2. **扫描面加上 `web/app/**/*.tsx`**，但要把 `href` 导航排除掉——
   区分办法是看它是不是进了取数钩子（`useScreenData(...)` / `fetch(...)`），
   而不是看路径长什么样；
3. 加一条阴性对照：**造一条页面里的真取数**，断言尺子能看见。

## 为什么 `GAUGE-11` 不顺手修

那张卡的 outputs 是 `docs/端点分诊-v041.md` 与 `tests/v041/test_endpoint_triage.py`。
改对账器超出 outputs，按第 4 批纪律 §五.1 停下登记。

**分诊表里这 12 条已经单列成 A 类**，并写明「处置是修尺子，不是接线」——
所以这处盲区现在是**有名字的**，不再是 35 条噪音里的一部分。

---

## 结案（`GAUGE-14` · v0.4.1 第 6 批）

### 两个盲区都补上了

**① 首段白名单退役。** `_ENDPOINT_LITERAL` 里那串
`plaza|clusters|projects|topics|jobs|…` 删了。现在**宽着扫**
（任何 `/小写段` 开头的路径样字面量），再**与后端真实路由取交集**。

新增一族端点时尺子自动认得——**而人维护的那串前缀，永远慢一批**。

**② 扫描面从 `web/lib/` 扩到 `web/lib` + `web/app` + `web/components`。**
`useScreenData("/account")` 在页面里、`designSession.ts` 的提交在组件里，
改前一条都看不见。

### 宽扫带进来的噪声，靠三道排掉

| 排掉什么 | 为什么 |
|---|---|
| **注释** | 注释里的路径会过时；当成调用是假实况，而假实况会让一条**真没人用**的端点被当成用着的 |
| **测试与 mock** | `/jobs/job-9` 是样例数据，不是契约 |
| **`href`** | 导航不是调用。后端恰好也有 `GET /topics/{id}`——不排掉的话，一条只被链接、从没被调用的端点会被算成「前端在调」，**那是往反方向错** |

### 判据里两条最值钱的

- **逐条点名**那 12 条误报不再出现在 `backend_unused_by_frontend` 里
  ——只判「条数变少了」是不够的，少下去的可能是**别的**几条；
- **反向守卫**：它没有变成「什么都不报」。把 `frontend_calls` 写成
  「返回全部路由」也能让上一条绿，而那时这把尺子就彻底不响了。
  本仓确实有真没人用的端点（pricebook / profile 两族维护面），判据钉着它们还在报。

外加四条阴性对照：新前缀的真调用认得出 · 页面里的调用看得见 ·
注释里的假调用不误报（`GAUGE-10` 的剥注释不倒）· `href` 不算调用。
