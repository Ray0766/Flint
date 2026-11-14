# `:8000` 上跑的是旧进程：巡检看到的「匿名能看、带身份 404」有一半来自它

**状态** closed · 2026-08-09 · `FIX-20`

> **要 owner 做的事只有一件**：重起后端（关掉『Flint Backend』窗口，
> 重跑 `start-demo.ps1`）。**代码不用改**——它已经是对的。

## 现象

```
$ curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/facts/fact-demo-vecdb-cost
200                                    ← 匿名，拿到真内容

$ curl ... -H "x-user-id: demo-user" http://localhost:8000/facts/fact-demo-vecdb-cost
200
```

而**同一份代码进程内**打，匿名是 422：

```
$ python -c "TestClient(create_deref_app(...)).get('/facts/fact-demo-vecdb-cost')"
422 {"detail":[{"type":"missing","loc":["header","x-user-id"],"msg":"Field required"}]}
```

## 差在哪

`flint/api/deref.py` 六条端点的签名都是：

```python
async def fact_detail(fact_id: str, x_user_id: str = Header()) -> Response:
```

`Header()` 无默认值 = **必填**。跑着的那个进程早于这次改动，它那份签名还没有这个头，
所以匿名照样放行。

## 为什么这件事要单独记，而不是绕过去

巡检据此写下「鉴权方向是反的」。**方向没反**——反的是那个进程的年龄。
如果判据也打到 `:8000`（那样"复现得到"），下一个人会照着这份「实测」去
**修一个本来就是对的方向**，把必填头改成可选。那一刀下去，
任何人不带身份就能读任何项目的事实。

所以 `tests/v041/test_deref_auth_direction.py` **进程内**打真代码，
并另有一条判据盯着这张单还开着。

## 与它一起看到的另外两件事（都已在 `FIX-16` 修掉）

1. `start-demo.ps1` 配的身份是 `self`，而 demo 库里没有任何东西属于 `self`
   ——项目、作业、事实全挂在 `demo-user` 名下。**配了身份反而比匿名看得少。**
   已改成 `demo-user`。
2. `web/lib/derefClient.ts` **一个身份头都不发**。对着当前代码，那意味着每一次
   解引用都是 422——报告屏此前还能看到内容，靠的正是这个旧进程。已补上。

**这两条修完之后，重起后端就是让实况与代码对齐的最后一步。**
在那之前，`:8000` 上的行为与仓里的代码不是一回事，任何打 `:8000` 的取证都要先想到这一层。

## 关掉这一单的条件

重起后端，且下面三条都成立：

```
curl :8000/facts/fact-demo-vecdb-cost                        → 422
curl :8000/facts/... -H "x-user-id: demo-user"               → 200
curl :8000/facts/... -H "x-user-id: u-nobody"                → 404
```

然后回来把 `test_the_stale_process_is_written_down_not_silently_worked_around`
改成实况（那时它红的是前提过期，不是事情坏了）。

---

## 关闭（`FIX-20` · 2026-08-09）：**根因不是旧进程，也不是装配**

这张单立的时候把现象记成了「`:8000` 上跑的是旧进程」。
`DEC-043-LANDING` 那一轮已经排除了进程年龄（PID 新鲜、行为不变）。
本卡把剩下那一半也查清了——**两个假设都不成立**：

| 曾经的假设 | 实况 |
|---|---|
| `:8000` 是旧进程 | 不是。`DEC-043-LANDING` 核过 PID 与启动时间 |
| 差别在走 `create_app` 而不是 `create_deref_app`（卡面 acceptance②） | **不是**。`flint/api/app.py:509` 就挂着 `create_deref_app(...)`，两条路是同一份 |

**真根因**：`harness/demo_server.py` 的 **`_InjectUserMiddleware`**。
前端不发身份头（`web/lib/screenClient.ts` 写死的口径：
「身份该由网关/中间件定，NEVER 由前端自己编一个」），
所以 demo 栈里有一道中间件替它补 `demo-user`——
**走网络的「匿名」请求，到端点手上时已经不是匿名的了**。

四组实测（`:8000` PID=53932 Start=2026-08-09 07:15:14，新鲜）：

```
走网络 匿名              -> 200     ← 中间件补了 demo-user
走网络 demo-user         -> 200
走网络 stranger          -> 404     ← 身份确实在起作用
进程内 匿名（不经中间件）  -> 422     ← 头确实必填
```

第三行是关键：**门若真开着，带 `stranger` 也该是 200**。它是 404。

## 收的是**隐形**这一条

删中间件 = demo 界面每一屏都变 422（不是收口，是把灯关了）；
把必填头改成可选 = 卡面 acceptance⑤ 逐字禁掉的动作。两头都堵死。

所以把这道**网关替身**从隐形变成明说：
① 默认照旧（界面照常）；② `FLINT_DEMO_INJECT_IDENTITY=0` 可关；
③ **每次替人补身份，响应上留 `X-Flint-Demo-Identity: injected`**。

判据 `tests/v041/test_anon_deref_over_network.py` 起**真 uvicorn**（各用各的端口，
NEVER 去占 `:8000`——那正是「旧进程冒充判据对象」栽过两次的地方）：
关掉替身时匿名 **422**、主人 **200**、陌生人 **404**；
开着替身时不带头 200 **且响应带记号**，带真身份时**不带记号**。

## 留给 owner 的一句

**默认要不要继续替人补身份**，是一条产品/安全姿态的选择，不是实现细节：
今天默认开着（demo 界面靠它），而它意味着**任何打到 demo 后端的请求都被当作
`demo-user`**。上线前这道替身必须换成真网关——
登记在 `docs/上线前合规手续清单.md` 的同一批事情里。
