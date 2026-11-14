# WIRE-03-EMPTY-FROM-A-STORE-THAT-HAS-NO-DATABASE · 切到真数据会让四张屏显示**假空态**

**状态** closed · 2026-08-06 · `WIRE-12`

**发现者** worker / `WIRE-03` 开工时（`WIRE-01` trace §7.3 已预登记）· **发现时间** 2026-08-05
**危害** 中 —— 屏上会说一句**系统没有依据说出口的话**
**为什么停下**：与 `DEC-032`（owner 2026-08-05 裁决）直接冲突，且解开它要改
`flint/api/*.py` 模块内部，超出 `WIRE-03` 的 outputs（`web/app/` · `web/lib/` · 一个测试文件）。

## 实测：装配后的应用此刻回什么

```
200 /account          {"profile":{"status":"not_checked"}, ...}
200 /billing          {"billing":{"status":"not_enabled","reason":"计费未配置（…）：本端点 NEVER 拿一个 0 元或一个假额度冒充已启用"}, ...}
200 /settings/locale  {"lang":"zh","region":"CN","options":{...九区...}}
200 /favorites        {"items":[]}
200 /design/templates {"items":[]}
404 /projects/p-1     {"code":"NOT_FOUND","message":"unknown project: p-1"}
```

**前三行是诚实的**，第四、五行不是。

## 为什么 `{"items": []}` 在这里是假话

迁移里 34 张表**没有 favorites，也没有 templates / prefs / share_links**。
`WIRE-01` 只能给这几族挂**内存件**（`dict` / `set`，进程重启就没了）：

| 族 | store | 有 `X \| None` 缝吗 |
|---|---|---|
| `account` | — | **有** → 回 `status: "not_checked"`，诚实 |
| `billing` | — | **有** → 回 `status: "not_enabled"` + 理由，诚实 |
| `favorites` | `FavoriteStore()` 内存件 | **没有** → 只能回 `{"items": []}` |
| `design` | `TemplateRegistry(available=False)` | 有一半（`available` 字段），但 `/design/templates` 仍回 `{"items": []}` |
| `settings` | `PrefsStore()` 内存件 | 没有，但**声明过的默认值本来就是真答案**，见下 |
| `graph_edges` | `GraphStore()` 内存件 | 没有 |
| `share` | `ShareLinkStore()` 内存件 | 没有 |

`{"items": []}` 与「查过了，你确实一条收藏都没有」**逐字相同**。
前端照契约渲染，屏上就会写「还没有收藏」——
而真相是「**这个功能还没有库，我们根本没查**」。

`DEC-032` 的原话正是这件事：**没查过 ≠ 空的／坏的，空态会让用户以为已查证。**
只不过那条裁决说的是「端点没挂」这一层，本单是它下沉一层后的同一个病。

**`settings` 是例外，不算假话**：`GET /settings/locale` 在没有存过偏好时
返回的是**声明过的默认值**（`zh` / `CN` + 九区清单），
这与「查过了，你没改过设置」是同一件事——默认值就是真答案。

## `WIRE-03` acceptance② 因此有一处做不到

卡面写：「断言九张屏在装配后的栈上**零 NotProvided**」。

- **account / billing**：能做到且诚实——`NotProvided`（接口未提供）换成
  组件里已有的 `not_checked` / `not_enabled` 那一态。两者**不是同一个 `data-*-state`**，
  第 2 批就是这么钉的。
- **favorites / design / graph_edges / share**：能做到，**但代价是屏上出现假空态**。

也就是说 acceptance② 与本批的头号纪律在这四张屏上是**对立**的，二选一。

## 需要 owner 给一句话

三选一：

1. **给这四族补 `| None` 缝**（照 `account` / `billing` 的样子）：
   deps 里 store 为 `None` → 端点回 `{"status": "not_checked"}`，
   前端照第 2 批的三态渲染，一切自洽。
   **代价**：要改 `flint/api/*.py` 四个模块内部 + 各自的测试 → **单开一张卡**；
   `WIRE-03` 先切能诚实切的那五张屏。
2. **接受假空态**：四张屏照 `{"items": []}` 渲染成「还没有收藏」。
   `WIRE-03` 一次做完，代价是**用户会以为查过了**。
   若选这条，**请明确它是临时口径**，并让 `WIRE-05` 的门盯着这四族：
   一旦有了库就必须回来复查。
3. **四张屏暂不切**，继续显示「接口未提供」。
   诚实，但与「端点已经挂上了」这个事实不符——用户点进去会看到一句
   已经不成立的话，而且没人会回来改。

**worker 本轮取第 1 种的前半**：先切 **account / billing / settings / project-overview /
share-viewer** 这五张（全部诚实可切），四张留在原态并由判据钉住登记，
NEVER 自行给它们造假空态，也 NEVER 自行改模块内部。

## 对下游卡的影响

- **`WIRE-04`**（十三张屏像素取证）：四张屏的取证会是「接口未提供」态，属预期；
- **`WIRE-05`**（装配面接进全局门）：门要认得这四族是「挂了但没库」，
  与「没挂」是两回事；
- **`UIX-01`**（S1 通用件）：`EmptyState` 的语义要写清它**只用于查过了确实为空**，
  NEVER 兼职「没查过」。

---

## 关闭（`WIRE-12` · 2026-08-06）

两条假空态改成了 `/billing` 已经做对的那个形状：

```
200 /favorites        {"status":"not_provided","reason":"收藏还没有存储面（迁移里没有 favorites 表）：本端点 NEVER 拿一个空列表冒充「你确实没有收藏」"}
200 /design/templates {"status":"not_provided","reason":"模板注册表不可用（迁移里没有 templates 表）：本端点 NEVER 拿一个空列表冒充「你确实没有模板」"}
```

**读回 200、写回 503**：读用 200 是因为「这功能还没上」本身就是一个成功的回答；
写用 503 是因为调用方的那次写**确实没有发生**——回 200 会让它以为存下了。

**两种意思各有表示**：`store=None` → `not_provided`；`store` 真在 → `{"items": []}`
照旧是「查过了、确实没有」。**只改一侧的话，第二种意思就没地方表达了。**

前端那一屏改成真取数（`useScreenData` + `toFavoritesView`），
`not_provided` → `favorites={null}`（屏上「接口未提供」），
`{"items":[…]}` → 那个数组。两条路都在组件里备着（`WIRE-03` 建的）。

**本单登记的另外三族**（`settings` / `graph_edges` / `share`）见单内原表：
`settings` 的「声明过的默认值」本来就是真答案；另两族**本卡未动**，
登记在 `docs/trace/WIRE-12.md` §未做。

