# FIX-20 · 匿名走真网络仍回 200

**状态**：调查已完成并写下（`worker.md` §4.4 / 工单 §4.4：**第一件事是查清差别并写进 trace，
NEVER 先改再解释**）。实现见本文件后半。

---

## 1 卡面那个假设**不成立**

卡面 acceptance② 写：

> 差别在 `harness/demo_server.py` 走 `create_app` 而不是 `create_deref_app`

**不是这个。** `create_app` 里第 509 行就挂着它：

```python
assembler.add(create_deref_app(DerefApiDeps(dsn=dsn)))
```

走 `create_app` 拿到的 deref 与 `create_deref_app` 是**同一份**。

## 2 真正的差别：`harness/demo_server.py:149` 的一道中间件

```python
class _InjectUserMiddleware:
    """纯 ASGI 中间件：前端不发 X-User-Id → 注 demo-user（scope 级 …）"""
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and not any(
            k == b"x-user-id" for k, _ in scope["headers"]
        ):
            scope = {**scope, "headers": [*scope["headers"], (b"x-user-id", b"demo-user")]}
        await self._app(scope, receive, send)
```

**走网络的「匿名」请求，到端点手上时已经不是匿名的了**——中间件给它补了一个
`demo-user`。所以端点回 200 是**它按规矩办事**，不是它把门开着。

## 3 四组实测（本轮，`:8000` PID=53932 Start=2026-08-09 07:15:14，新鲜）

| 打法 | 身份 | 结果 | 说明 |
|---|---|---|---|
| 走网络 | 不带头 | **200** | 中间件补了 `demo-user` |
| 走网络 | `demo-user` | 200 | 数据的主人 |
| 走网络 | `stranger` | **404** | **身份确实在起作用**——带错身份就拿不到 |
| 进程内（不经中间件） | 不带头 | **422** | 头**确实必填** |
| 进程内 | `demo-user` | 200 | — |

第三行是关键：**如果端点真的把门开着，带 `stranger` 也该是 200**。它是 404。
所以「门开着」这个读法从一开始就与实测对不上——
`FIX-16` 的进程内证据（422）与这里的网络证据（200）**两个都对**，
中间夹着的是那道中间件。

## 4 为什么不能一删了事

`web/lib/screenClient.ts` 逐字写着：

> **前端不发身份头。** …… 身份该由网关/中间件定，NEVER 由前端自己编一个。
> demo 栈的 `_InjectUserMiddleware` 在没有该头时注 `demo-user`。

删掉中间件 = **整个 demo 界面每一屏都变 422**。那不是收口，那是把灯关了。

而卡面 acceptance⑤ 也写死了另一头：**NEVER 把必填头改成可选**来让判据变绿。

**两头都堵死之后剩下的那条路**：把这道「网关替身」从**隐形**变成**明说**——
它默认照旧（界面照常能用），但
① 可以关掉；② 关掉之后走真网络的匿名请求 MUST 是 422；
③ 它每次替人补身份时，在响应上留一个记号，**让「我现在是谁」这件事永远看得见**。

隐形才是这一条真正的缺陷：`steward` 重起两次都没收口，正是因为
屏幕上、日志里、响应里**没有任何地方说过「你这个请求的身份是补出来的」**。

---

# 实现

## 5 改前 / 改后 / 为什么非改不可

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `harness/demo_server.py` | `_InjectUserMiddleware` **无条件**补身份，且**不留任何痕迹** | ① 加 `enabled` 开关（默认 `True`，环境变量 `FLINT_DEMO_INJECT_IDENTITY=0` 关）；② 补过身份的响应带 `X-Flint-Demo-Identity: injected` | **隐形才是这一条真正的缺陷**。默认不变，所以 demo 界面一屏都没受影响；可关，所以判据能打到端点自己的答复；留记号，所以「我现在是谁」永远看得见 |
| `tests/v041/test_anon_deref_over_network.py` | 不存在 | 新增：起**真 uvicorn** 两台（替身开 / 关），`httpx` 打真 socket | 卡面 acceptance③ 逐字要求打真网络；`TestClient` 在进程内跑 ASGI，量不到网络那一层——`FIX-16` 就是在这里栽的 |
| `docs/blocked/DEREF-PROBE-HIT-A-STALE-BACKEND.md` | open（记的现象是「旧进程」） | **closed**，并写清**两个假设都不成立**与真根因 | 照卡面那个假设关单的话，下一个人再遇到同类现象会去查装配，而那里没有问题 |

**`flint/api/deref.py` 一个字没动**——门本来就是关着的。
判据 `test_the_header_is_still_required_on_the_endpoint` 从源码量这一条：
`x_user_id: str = Header()` 仍无默认值，且全文件没有 `Header(default=`。

## 6 判据为什么起两台

- **关掉替身那一台**：这时「匿名」是真的匿名 → 端点自己的答复（422）。
  主人 200、陌生人 404 一并量——只判「匿名被拒」的话，
  一个把整条路关死的实现也能全绿，而那时用户什么都读不到。
- **开着替身那一台**：不带头 200（界面照常）**且响应带记号**；
  带真身份时**不带记号**——没补的时候留记号，这个记号就不再说明任何事。

**各用各的端口，NEVER 去占 `:8000`**：judged run 占它会打断人在用的界面；
更坏的是反过来——判据可能量到那个**别人起的、代码不知道多旧的**进程。
本仓已经为「旧进程冒充判据的对象」栽过两次。

## 7 一处 ruff 判得对的地方

`Popen` 的参数列表里直接写多行字符串是**隐式拼接**（`ISC004`）。
那种写法里少一个空格就会把两个词粘成一个，而**报错在子进程里**，很难看出来。
提成常量 `_BOOT`。

## 8 自审（`self_review=true`）

**① 判据覆盖 acceptance**：②真根因查清并写进 trace（§1~§4，**改动之前就写好了**）；
③打真网络（真 uvicorn + httpx，不是 TestClient）；
④匿名 422 / 主人 200（外加陌生人 404）；⑤必填头没被改成可选（从源码量）；
⑥单据已关且写清真根因（判据连「单里有没有点名 `_InjectUserMiddleware`」都判）。

**acceptance① 那句「重起两次仍 200」本卡给出了解释**：那不是没收口，
是中间件在按规矩办事——三行实测（尤其 `stranger → 404`）证明门一直是关着的。

**先红后绿**：判据先写，改动前 10 条里 4 条红。

**② 无冻结件偏离**：四件一字未动。
**③ 无禁用词**：0 命中。
**④ 复用断言在位**：不新建任何鉴权路径；`flint/api/deref.py` 一行未改。
**⑤ 装载未超预算**：≈26k / 40k。

## 9 门

```
pytest tests/v041/test_anon_deref_over_network.py -q   10 passed（真 uvicorn × 2）
ruff check . --no-cache                                All checks passed!
mypy --strict flint                                    Success: 317 source files
邻近两把尺子（demo_stack_wired / blocked_sheets_state）  27 passed
```

## 10 留给 owner 的一句（**这一条不是实现细节**）

**默认要不要继续替人补身份**，是一条产品/安全姿态的选择：
今天默认开着（demo 界面靠它取数），而它意味着
**任何打到 demo 后端的请求都被当作 `demo-user`**。

本机 demo 无所谓；**上线前这道替身必须换成真网关**——
已写进单据的关闭说明，与 `docs/上线前合规手续清单.md` 是同一批事情。
