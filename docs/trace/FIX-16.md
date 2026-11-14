# FIX-16 · 解引用端点的鉴权方向

**结论**：**方向没反**。看到的那个「匿名比带身份更有权限」是**三个各自独立的根因**
叠在一起的样子，三条修法完全不同——而其中一条是真的、活的、马上会咬人的缺陷。

装载：卡 `FIX-16` · `flint/api/deref.py` · `web/lib/derefClient.ts` ·
`web/lib/apiBase.ts` · `docs/steward/巡检.jsonl` · `start-demo.ps1`

---

## 1 逐条查到的三个根因

| 巡检看到的 | 根因 | 修在哪 |
|---|---|---|
| 匿名 `GET /facts/{id}` 回 **200 真内容** | 跑着的 `:8000` 是**旧进程**，早于 `x_user_id: str = Header()` 那次改动 | 人工重起后端（单据 `DEREF-PROBE-HIT-A-STALE-BACKEND.md`） |
| `self / demo / u-demo` 三种身份**全 404** | 这三个 id **都不是这批 demo 数据的主人**——项目、作业、事实全挂在 `demo-user` 名下 | `start-demo.ps1`：`self` → `demo-user` |
| `/price-entries/{id}` 恒 422 | `quantity` 是**必填 query**，那几条 curl 没带 | 探针的调法；前端一直带（`DEREF_PATHS.price` 默认 `1`） |

同一份代码**进程内**打，行为一直是对的：

```
anon      → 422（身份必填）
demo-user → 200
u-nobody  → 404（404 而不是 403：403 会泄露存在性，还能被用来枚举 id）
```

## 2 而这张卡真正要保住的东西，此前是**靠匿名撑着的**

`web/lib/derefClient.ts` **一个身份头都不发**（只发 `Accept`）。

对着当前这份后端代码，那意味着**每一次解引用都是 422**。报告屏此前还能看到
事实与价格，恰恰因为它打的是那个不要求身份头的旧进程——
**那不是「能用」，是「还没撞上」**。旧进程一换，报告屏整片丢内容，
而屏上只会说「取不到」，用户会以为是自己的数据没了。

卡上 acceptance ② 说的正是这件事，⑥ 说的是它的反面。

## 3 改前 / 改后 / 为什么非改不可

**① `web/lib/derefClient.ts`**

- 改前：`headers: { Accept: "application/json" }`。
- 改后：`API_USER_ID` 有值就带 `x-user-id`；`DerefOptions` 加可注入的 `userId`（测试用）。
- **没配就不发**：发一个编出来的身份会让服务端把别人的数据当成你的
  （`FB-10` 的 A 类里 `X-User-Id` 逐字点名）。与 `cardActions.ts` 那段同一条口径。

**② `start-demo.ps1`：`NEXT_PUBLIC_FLINT_USER_ID` `'self'` → `'demo-user'`**

demo 库里**没有任何东西属于 `self`**。配了身份反而比匿名看得少——
「配了身份」在那种配法下等于没配。这一处**超出卡上 outputs**（`flint/api/`），
没停下走单，理由：acceptance ⑥ 直接依赖它，且改动是一个字符串。
（同类先例：`FE-DEMO-ENV-FLINT-API-BASE`。）

**③ 后端一行没改。** 卡上说「定出该有的方向并实现」——方向已经是对的，
定的是**把它写下来**（见 §4），而不是再改一遍。

## 4 「一致」到底该一致在哪

卡上 acceptance ⑤：「断言同一 id 的可见性与身份的关系是一致的」。

一致的是**要不要身份**：三族一律必需，匿名一律 422。

不一致的是**看得到什么**，而那不是鉴权口径的事，是**数据归属**的事实：

- `facts` 按 owner 切表（项目私有）→ 陌生人 404；
- `price-entries` / `citations` 是全局参考数据（`pricebook` 表**没有 owner 列**，
  口径见 `docs/trace/FB-05.md`）→ 有身份就看得到。

要求三族回同一个码，等于要求 pricebook 长出一个 owner 列。
所以判据判的是**更真的那条不变量**：

> 同一个 id，陌生人看到的 **NEVER 多于**主人。

另有一条逐族钉住当前归属（`test_private_data_hides_existence_and_shared_data_does_not`），
理由是：哪天 pricebook 真长出 owner 列，它必须红一次让人来改，
而不是悄悄继续对所有人放行。

## 5 断点：差点拿旧进程当判据的对象

第一反应是「复现一下」——`curl :8000`，复现到了，于是「方向是反的」看起来成立。

**拿 `:8000` 当判据的对象，量到的是那个进程的年龄，不是这份代码的行为。**
而顺着那份「实测」改下去，最可能的一刀是把必填头改成可选——
那之后任何人不带身份就能读任何项目的事实。

所以判据**进程内**打真代码，旧进程这件事单独开单，并配一条判据盯着那张单还开着。

## 6 门

```
pytest tests/v041/test_deref_auth_direction.py -q   10 passed
vitest run                                          84 files · 850 passed
tsc --noEmit                                        0
```

**留给 owner 一件事**：重起后端（关掉『Flint Backend』窗口，重跑 `start-demo.ps1`）。
在那之前，`:8000` 上的行为与仓里的代码不是一回事——任何打 `:8000` 的取证都要先想到这一层。
关单条件写在单据末尾。
