# AUTH-03 · 身份入口的口径——未知用户 NEVER 静默当成 owner

**卡** `docs/steward/tasks-v041-b4.json#AUTH-03` · **cycles 1（oneshot）** ·
**self_review = true** → §5 · **owner_review = false** · **依赖** `AUTH-02`

## 1. 装载清单

卡面 AUTH-03 · `flint/api/schemas.py` 的 `ErrorCode` / `ErrorBody` ·
`flint/api/analysis.py` 与 `flint/api/account.py` 的取头写法 ·
`flint/api/deref.py` 的 `_not_found()`（那条「查不到与不该看到共用 404」的口径）·
`flint/authz`（本批 `AUTH-02` 的产物）· 工单 §8-④。约 8k tokens，预算 40k 以内。

## 2. 三种拒绝，三种响应

| 情况 | 状态 | code | 要人做的事 |
|---|---|---|---|
| 没有 `X-User-Id` | 401 | `IDENTITY_MISSING` | **加上头**（调用方漏了） |
| 头里的 id 不是任何人 | 401 | `IDENTITY_UNKNOWN` | **换一个身份** |
| 是某个人，但对这资源没角色 | 403 | `PERMISSION_DENIED` | **去要权限** |

混成一句「无权访问」的代价：前两种是「你是谁」，第三种是「你能干什么」。
读到一句通用的拒绝时，调用方**分不出该改请求还是该找人开权限**。

**两个 401 也分开**：一个是调用方漏了头（bug），一个是这个身份不存在（数据）。
同一个状态码下，`code` 是唯一能区分它们的位——所以
`flint/api/schemas.py` 的 `ErrorCode` 加了两个值，照 `EMPTY_HYPOTHESIS` 的先例
（**一个修法一个码**）。

## 3. 身份检查是 async，NEVER 借 `AUTH-02` 那座同步桥

`flint/authz` 里那座「同步调异步」的桥，只为**冻结的同步 `RoleResolver` 签名**存在。
身份检查跑在端点里，端点本来就是异步的——顺手借那座桥等于白占一次线程。
所以 `build_user_check` 返回的是 `async def check(...)`。

## 4. 404 与 403 的边界，以及一条**有意的例外**

资源不存在 → 404；存在但无权 → 403，**NEVER 用 404 去盖 403**。
另有一条：**没有身份时连「这东西存不存在」都不回答**（先 401）——
先回 404 的话，未认证的请求就能拿来探测哪些 id 存在。

`deref` 那一族是有意的例外（查不到与不该看到共用 404，因为状态码本身会泄露存在性）。
那条口径写在 `flint/api/deref.py` 的 `_not_found()` 上，**本卡 NEVER 推翻它**，
只在模块 docstring 里点名它是例外。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_identity_entry.py -q → 10 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 301 source files
            pytest -q               → 3932 passed（AUTH-02 收卡时 3922，本卡 +10）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 身份来源写死一处 | `test_no_second_identity_header_exists_anywhere_in_the_api`（扫 `flint/api/` 全域的**字符串常量节点**，不是正文——`AUTH-02` 刚在这上面踩过） |
| ② 三种拒绝互不相同 | `test_the_three_refusals_are_three_different_responses`（判**互不相同**）+ 三条各自钉值 + `test_the_person_with_a_role_gets_through`（**正例**：没有它，那三条可能是「这个端点对谁都拒」换来的） |
| ③ 404 与 403 的边界 | `test_a_missing_resource_is_404_and_a_forbidden_one_is_403`、`test_identity_is_checked_before_existence` |
| ④ 形状与既有 `ErrorBody` 一致 | `test_every_refusal_body_has_the_existing_error_shape`、`test_the_two_new_codes_are_registered_in_the_frozen_literal` |

**② 改既有文件两处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `flint/api/schemas.py` | `ErrorCode` 加 `IDENTITY_MISSING` / `IDENTITY_UNKNOWN` 两个值（带理由注释） | **卡上 outputs（`flint/api/`）**。acceptance② 要三种拒绝分得开，而两个 401 只能靠 `code` 区分；不加就得让 `_body` 带 `# type: ignore`——那是把类型问题藏起来 |
| `tests/v041/test_doc_content_store.py` | `alembic("upgrade", "0019")` → `alembic("upgrade", "head")` | **实测撞出来的**：那一行写死的版本号在 `AUTH-01` 之前恰好是 head，之后 head 是 0020 → 这条用例把库停在 0019，**后面所有用到身份三张表的用例全部 `UndefinedTableError`**。单独跑 `tests/v041/test_identity_entry.py` 全绿，跑整个目录 10 个 error——那种红看起来像身份那几张卡坏了，其实是这一行把库留在了半路上。改动在本卡 outputs 之外，但**不改就没法收卡**，理由与 `LOC-01` 处理 `test_ui07.py` 同类 |

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；未新增依赖。

**③ 变异考 4 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 未知用户静默放行（不查 `users`） | 红（3 条） |
| ② 缺头兜一个默认身份（`return "demo-user"`） | 红（4 条） |
| ③ 两个 401 并成同一个 code | 红（2 条） |
| ④ 403 降级成 404（用「找不到」盖住「无权」） | 红（3 条） |
| ⑤ 假变异对照：只改一句注释 | 全绿 |

**④** 装载约 8k tokens；**⑤** 禁用词六词 0 命中。

## 6. 登记未做

1. **四族路由还没用上这个入口**。`flint/api/identity.py` 是**库**：
   检查、三个异常、三个处理器都在，但把它接进 analysis / compose /
   interventions / combo 是 `WIRE-07~10` 的事（那四族此刻还没挂）。
   本卡的判据用**真的模块**搭了一个最小应用来验行为——
   NEVER 等到四族挂上才有人验这三种拒绝分不分得开。
2. **既有 16 个 api 模块仍各自写 `x_user_id: str = Header()`**。
   它们的行为没变（缺头 → FastAPI 默认 422）。统一换成本模块的入口
   会动十几个文件，**大于本卡该动的面**；`WIRE-07~10` 会先在新挂的四族上用它，
   其余的换法登记在此。
3. **`RoleMissing` 由调用方抛**。本模块只提供异常与处理器，
   不替端点决定「这个资源的 scope 是什么」——那是各族自己的事。
4. **受信头前面那层网关不在本仓**。模块 docstring 写死了这句话：
   「受信」二字被读成「不用校验」的那天，这个入口就是敞开的。
