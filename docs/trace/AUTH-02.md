# AUTH-02 · 真 role_resolver 与 owner_scope_for_project——替掉那只假手

**卡** `docs/steward/tasks-v041-b4.json#AUTH-02` · **cycles 2（oneshot=false）** ·
**self_review = true** → §5 · **owner_review = true** → §6 · **依赖** `AUTH-01`

## 1. 装载清单

卡面 AUTH-02 · `flint/jobs/runner.py` 全文（`RoleResolver` 定义、文件头第 9 行、
`cancel` 里那次解析）· `flint/api/analysis.py` 的 `may_view` 与 `_VIEW_ROLES` ·
`flint/api/interventions.py` 的 `may_intervene` 与 `_INTERVENE_ROLES` ·
`contracts/models.py` 的 `Principal` / `Job` / `Role` ·
`migrations/versions/0020_identity.py`（本批 `AUTH-01` 的产物）·
`harness/demo_server.py` 那三处假手。约 11k tokens，预算 40k 以内。

## 2. 兑现的是 `runner.py` 文件头第 9 行

> 角色解析经注入 `RoleResolver`（**memberships 表随身份任务落库后接 SQL 实现**）

`AUTH-01` 落了表，本卡写那个 SQL 实现。替掉的是三处
`lambda _u, _o: "owner"`——**谁问都答 owner**。

## 3. 一件必须讲清楚的事：这里有一座「同步调异步」的桥

`RoleResolver = Callable[[str, str], str | None]` 是**同步**签名，
三个调用点（`may_view` / `may_intervene` / `PgJobRunner.cancel`）都同步调它，
而它们跑在 FastAPI 的事件循环里。库这一侧**只有 `asyncpg`**（异步专用）：

```
psycopg2 不可用 · psycopg 不可用 · pg8000 不可用     ← 实测
requirements.lock 里只有 asyncpg==0.31.0
```

而本批 **NEVER 新增依赖**。所以 `flint/authz` 里有一条 `_blocking()`：
没有正在跑的循环时直接 `asyncio.run`；已经在循环里时，把这次查询交给
**一个懒起的后台循环**（守护线程、进程内单例）并等它回来。

**代价写在模块 docstring 里，NEVER 藏着**：这一等会占住调用方那条线程几毫秒
（一次主键命中的查询）。真正的修法是把 `RoleResolver` 变成 async——
那要改签名与三个调用点，**在本卡 outputs 之外**，见 §7-1。

## 4. 判据两层，因为一层挡不住

**行为层**：查得到就答那一行、查不到就 `None`。
**源码层**：`flint/authz/` 里不许有常量角色。

为什么两层都要：有人加一句「查不到就当 owner」时，如果那句兜底
**只在某个分支上**（比如「org 不存在时」），行为判据未必覆盖得到。

**而源码那一层第一版写错了**：按行扫字符串，当场把模块 docstring 里
「它替掉的是 `lambda _u, _o: "owner"`」判成了违规——
**说明问题的那句话被当成了犯下问题**。这与本批 `GAUGE-10` 要修的是同一个病
（扫描器不剥注释，于是「写清楚一点」反而被判红）。
改成走 `ast`：docstring 是 `Expr`，既不是 `Return` 也不是 `Lambda`，
判的是**真节点**而不是正文。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_role_resolver.py -q → 9 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 300 source files（+1 = flint/authz）
            pytest -q               → 3922 passed（AUTH-01 收卡时 3913，本卡 +9）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① `(user_id, org_id)` 查 memberships，查不到 `None`、NEVER 兜底 | `test_each_seeded_role_comes_back_verbatim`（四种角色各一）、`test_a_user_with_no_membership_row_resolves_to_none`（三种查不到：没有 membership 的人 / 不存在的 org / 两个都不存在） |
| ② `owner_scope_for_project` 查 `projects.owner`，项目不存在时抛 | `test_owner_scope_reads_the_principal_stored_on_the_project`（org 归属与 user 归属各一）、`test_an_unknown_project_raises_instead_of_guessing` |
| ③ NEVER 出现常量解析 | `test_no_constant_role_lives_anywhere_in_the_authz_package`（**判 `ast`**，见 §4）+ `test_the_role_it_returns_really_came_from_the_row`（改库里那一行，解析器跟着变——两条合起来才排除「从别处拿了一个常量」） |
| ④ 三条阴性对照 | `test_a_viewer_is_refused_a_write_operation`（viewer 与 stranger 都被拒，owner/admin 通过）、`test_a_personal_scope_only_lets_that_person_through`、`test_an_org_scope_lets_a_member_view_but_not_a_stranger` |
| ⑤ 兑现 `runner.py` 那句话并在 trace 引用 | §2 |

**② 改既有文件 0 处**；新增 `flint/authz/__init__.py`（卡上 outputs `flint/authz/`）
与 `tests/v041/test_role_resolver.py`。
`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；**未新增依赖**（这正是那座桥存在的原因）。

**③ 变异考 5 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 退回假手（常量 `"owner"`） | 红（6 条） |
| ② 查不到时兜底成 `viewer` | 红 |
| ③ 项目不存在时编一个归属 | 红 |
| ④ 归属读错列（把 `origin_id` 当 `owner`） | 红 |
| ⑤ 解析器忽略 `org_id`（只按人查） | 红 |
| ⑥ 假变异对照：只改一句注释 | 全绿 |

⑤ 是这组里最该有的一条：只按人查在**单组织**的夹具上照样全绿，
是「同一个人在另一个组织里是另一个角色」那条种子把它咬住的。

**④** 装载约 11k tokens；**⑤** 禁用词六词 0 命中。

## 6. owner_review

1. **那座同步桥的代价**（§3）：一次角色解析会占住调用方线程几毫秒。
   本卡按「NEVER 新增依赖」的纪律选了这条路，并把代价写在模块 docstring 里。
   若你认为该走另一条（把 `RoleResolver` 改成 async，或引入一个同步 PG 驱动），
   两条都要动本卡 outputs 之外的面——**我没有替你选**。
2. **`memberships` 现在是空表**。解析器已经是真的，但库里一行都没有，
   所以**此刻任何 org 归属的资源对任何人都是拒绝**。这是对的默认
   （拒绝比放行安全），但意味着 `AUTH-05` 之后 demo 栈要种身份数据才跑得起来——
   那张卡会处理。

## 7. 登记未做

1. **`RoleResolver` 仍是同步签名**。改成 async 是更干净的修法，
   要动 `flint/jobs/runner.py` 的类型、`may_view`、`may_intervene`、`cancel`
   四处调用点，以及所有传假手的测试——**本卡 outputs 只有 `flint/authz/`**。
2. **没有连接池**。每次解析开一条连接（与仓里既有写法一致：
   `asyncpg.connect` 满仓都是）。真上量之前这是全仓一起要解的事，不是本卡的。
3. **没有缓存**。同一个请求里连查两次角色就连打两次库。
   加缓存要先定失效口径（改了 membership 多久生效），那是产品决定。
4. **`users` 表本卡一次都没查**。解析只用 `memberships`；
   「这个 user_id 是不是一个真存在的人」是 `AUTH-03` 的事（401 那一路）。
