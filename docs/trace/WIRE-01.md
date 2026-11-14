# WIRE-01 · 装配①：把 51 条够不到的端点接通

**卡** `docs/steward/tasks-v041-b3.json#WIRE-01` · **cycles 2** ·
**self_review = true** → §6 · **owner_review = true** → §7
**依赖** 无（第 3 批首卡）

## 1. 装载清单

卡面 WIRE-01 · 工单第 3 批 §2 与 §8 · `flint/api/app.py`（改前 22 行）·
`flint/api/` 20 个模块的 `create_*_app` 签名与 deps 字段（AST 抽取，未全文装载）·
`harness/demo_server.py:176-226`（既有装配的**真件**）· `migrations/versions/` 表名清单 ·
`docs/前后端对账表-v041.md` · `tools/check_fe_be_parity.py` 的 `backend_routes`/`parity`。
约 17k tokens，预算 40k 以内。

## 2. 收在哪儿：52 / 62 通了，10 条**登记在案**

| | 数 |
|---|---|
| 实现的唯一路径 | **52** |
| 已挂上 | **42**（method+path 计 50） |
| 登记未挂 | **10**（四族，见 §4） |
| 已登记的路由冲突 | **1**（见 §3） |

`backend_not_assembled`：**51 → 10**。**没有归零**——卡面出口判据未达成，理由见 §4。

## 3. 撞出一处真冲突：`GET /deliverables/{id}/render`

`deliverables.py:97` 与 `pack.py:147` **各注册一次同一条路径**。
各自建 app 时互不干扰，**并进一个应用就必有一个永远收不到请求**——
FastAPI 对重复注册不报错。

`pack.py` 的文件头自己写着两者的分工表，说明它知道这条路径已经有人注册了；
它成立的前提是「两个 app 各跑各的」，而本卡正好取消了这个前提。

**处置**：装配器**对未登记的冲突直接 raise**，登记过的写明谁赢、谁被遮、为什么、
挂哪张单（`KNOWN_COLLISIONS`）。本处 winner = `deliverables.py`（覆盖五种 fmt，
其中 pack 有明说不可用的 503 降级；反过来选会让另外四种格式全部倒退）。
`pack.py` 的独有端点 `/deliverables/{id}/pack` **照常挂上，模块没被连坐**。

单子：`docs/blocked/RENDER-ROUTE-CLAIMED-BY-TWO-MODULES.md`（owner 三选一）。

## 4. 四族装不上，缺的是**授权事实**，不是接线

| 族 | 路由 | 缺什么 |
|---|---|---|
| `analysis` | 3 | `role_resolver` · `owner_scope_for_project` |
| `compose` | 2 | 同上（在 runner 里） |
| `interventions` | 4 | 同上 + `aligner`（吃 LLM） |
| `combo` | 1 | `provider` · `embed_service` |

**能挂上，但只能靠 demo 的假鉴权。** `harness/demo_server.py:192` 写的是
`lambda _u, _o: "owner"`——demo 里无所谓，**可部署应用里等于任何人带任意
`X-User-Id` 都是 owner**。那不是接线活，是安全洞。

根因：迁移 34 张表里**没有 `users`，也没有 `memberships`**。
`role_resolver` 要答的问题（这个人对这个项目是什么角色）**在库里没有事实可查**。

按卡面 acceptance⑥「模块若缺参数装不上，停下走 `docs/blocked/`」停下登记：
`docs/blocked/WIRE-01-FOUR-FAMILIES-NEED-AUTH-AND-PROVIDER.md`（owner 三选一）。

**两处已核实**不是障碍，免得下一个人重查：`PgJobRunner.enqueue` 是
`EnqueueHook | None`（不必为装配去连 redis）；那几族 store 缺持久层**不影响装配**。

## 5. 没有持久层的族：走模块自己的「没查过」缝

`BE-01~11` 的几族 store 是**内存件**（`dict`/`set`，无 dsn），
而迁移里没有 favorites / prefs / share_links / templates / users 任何一张表。

**给它们塞一个空的内存 store，端点会回「你没有收藏」——那是一句系统没有依据
说出口的话**：它查的是一个刚建出来、进程重启就没了的字典。用户会读成「查过了，
确实没有」。这正是本批一路在治的那件事，只是下沉了一层。

所以走模块**自己设计好的那条缝**（这些字段的注解本来就是 `X | None`）：

| 模块 | 缝 | 效果 |
|---|---|---|
| `account` | `load_user=None` → `profile_checked=False` | 回 `status: "not_checked"`，连键都不给 |
| `billing` | 三个 loader = None | 同上 |
| `design` | `TemplateRegistry(available=False)` | 「注册表不可用」，不是「没有模板」 |
| `quality` / `pack` | `ref_resolver` / `pack_owner` / `pack_ready` = None | 同上 |

没有 `| None` 缝的（`settings` / `favorites` / `share` / `graph_edges`）挂了**空内存件**，
其余不可为空的依赖填 `_unconfigured`（一被调用就 `NotImplementedError`）。
**这是本卡最需要 owner 看一眼的地方，见 §7。**

## 6. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_app_assembly.py -q → 17 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3676 passed（开工时 3661，本卡 +15；
                                      另修 AUDIT-01 两条随装配过期的判据）
            python tools/check_fe_be_parity.py → 54 条发现（开工 62）·未装配 51→10·建不起来 0
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 全部模块挂进同一应用 | `test_every_implemented_route_is_either_mounted_or_registered_as_unwired`（判等值）、`test_the_app_is_no_longer_the_one_route_starter` |
| ② 逐条探活、NEVER 只断言语句存在 | `test_every_mounted_route_answers_something_other_than_404`、`test_the_liveness_probe_would_notice_a_route_that_went_missing`（阴性对照）、`test_a_probe_that_only_checked_statements_would_have_missed_this`（判本文件自己） |
| ③ 前缀零冲突、冲突指名道姓 | `test_a_path_claimed_by_two_modules_is_reported_with_both_names`（判等值）、`test_each_known_collision_names_a_winner_and_says_why`、`test_an_unregistered_collision_raises_instead_of_shadowing_silently`（阴性对照）、`test_no_path_is_registered_twice_in_the_assembled_app` |
| ④ 建应用不连库 | `test_the_app_builds_with_an_unreachable_database`、`test_building_the_app_twice_gives_two_independent_apps` |
| ⑤ `backend_not_assembled` 归零 | **未达成**。改判等值：`test_the_parity_checker_sees_exactly_the_registered_gap` + `test_the_gap_shrank_from_fifty_one_to_ten`。理由见 §4 |
| ⑥ 不改模块内部、装不上就停下 | `flint/api/*.py` 二十个模块**一字未改**（见②）；两张单已落盘 |

**② 改既有文件三处**（模块内部零改动）：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `flint/api/app.py` | 22 行、一条路由 → 装配器（`_Assembler` 记账 + 撞车 raise + `KNOWN_COLLISIONS` + `UNWIRED_FAMILIES` + `mounted_route_table`） | **本卡的 outputs 就是它** |
| `tools/check_fe_be_parity.py` | `_build_app` 在 `exec_module` 前把模块登记进 `sys.modules` | Python 3.13 的 `@dataclass` 解析注解要 `sys.modules[cls.__module__]`；没登记就拿到 `None`，报成 `'NoneType' object has no attribute '__dict__'`——**读起来像「应用坏了」，其实是装载方式不对**。app.py 一引入 dataclass 就撞上，不修则整个装配面量不到 |
| `tests/v041/test_fe_be_parity.py` | `test_an_unmounted_route_is_reported_as_idle_capacity` 的样本 `/account` → `/projects/{}/analysis` | `/account` 本卡已挂上，旧样本恒红。新样本仍未挂且**有单号**；四族接上后本条会红，那正是提醒改判据的机制 |

另**重生成** `docs/前后端对账表-v041.md`（`--write`，62 → 54 条）——它是跑出来的，不是手写的。

**③ 变异考 6 咬住 + 1 假变异对照绿 + 1 处登记盲区**

| 变异 | 结果 |
|---|---|
| ① 少挂一族（favorites） | 红 |
| ② 撞车不 raise、改成静默遮蔽 | 红——**但第一轮是幸存的**，见下 |
| ③ 把没配后端的族填成假空 loader | **全绿 → 登记为盲区**，见 §7 |
| ④ 建应用时就连库 | 红 |
| ⑤ 探活口径放松（应用自己的 404 也算没挂） | 红 |
| ⑥ 登记面注水（把已挂上的写进 UNWIRED） | 红 |
| ⑦ 假变异对照：只改一句注释 | 全绿 |

**②第一轮幸存**是本卡最有价值的一次变异：把撞车守卫整个换成「先占的赢，静默遮蔽」，
**十五条判据一条都不红**——已登记那处的结果本来就一样，守卫只对**未登记**的冲突说话，
而盘上此刻没有未登记的冲突。补了阴性对照
`test_an_unregistered_collision_raises_instead_of_shadowing_silently`（造一处假撞车）后才咬住。
顺带发现 `_module_of` 对非 `flint.api.` 模块回「未知模块」——撞车信息里没有模块名
等于把定位活退回给人，已改成永远报真模块名。

**④** 装载约 17k tokens；**⑤** 禁用词六词 0 命中。

## 7. owner_review

三处要你看：

1. **四族不挂**（§4）。三选一在单子里。**第 2 种（单用户模式）能立刻让出口判据归零**，
   代价是任何人带任意 `X-User-Id` 都是 owner——**要你明确接受才做**。
2. **`render` 冲突谁赢**（§3）。worker 选了 `deliverables.py`，代价是 `pack.py` 的
   render 成了死代码。
3. **§5 那几族挂了空内存件**。`settings` / `favorites` / `share` / `graph_edges`
   没有 `| None` 缝，只能挂空 store。**后果**：屏上会显示「还没有收藏」，
   而真相是「这个功能还没有库」——正是 `DEC-032` 要避免的那种假空态。
   变异考③证明**当前判据够不着这一处**（把 `account` 填成假空 loader，17 条全绿）。
   建议下一张卡给这四族也开 `| None` 缝，或在 `WIRE-03` 切屏时按族区分。
   **本卡没做**：那要改模块内部，acceptance⑥ 禁止。

## 7.5 返工一处（2026-08-05 15:5x，`WIRE-03` 开工探端点时发现）

**我在本卡埋的洞**：`_unconfigured` 占位写的是「永不被调用」，抛裸
`NotImplementedError`。但 `quality` / `staleness` / `pricebook` / `profile`
的必填依赖**没有 `X | None` 缝**，处理函数拿到占位就直接调——
实测**每次请求都是 500 Internal Server Error**：

```
500 /pricebook            Internal Server Error
500 /profile/{id}         Internal Server Error
500 /deliverables/{id}/quality    Internal Server Error
500 /deliverables/{id}/staleness  Internal Server Error
```

**500 说的是「坏了」，真相是「没配后端」。** 两者该让人做的事完全相反：
前者去翻栈查日志，后者去配一个后端。这正是本批一路在治的病，
被我在装配时又犯了一次——而本卡原有的 17 条判据**一条都没红**，
因为 acceptance② 只判「不是 404/405」，500 被算作「挂上了」。

**改法**：占位改抛 `FamilyNotConfigured(family)`，经 `create_app` 里的异常处理器
变成 **503 + `{"code": "FAMILY_NOT_CONFIGURED", "family": …}`**，
与 `deliverables.py` 对 `fmt=pack` 的处置同款（E6 姿态：明说不可用）。

**新增两条判据**：

- `test_a_family_without_a_backend_answers_503_not_500`（逐条判 503 且说清哪一族）；
- `test_no_mounted_route_answers_500_out_of_the_box`——**真库下**全表扫一遍，
  一条无脑 500 都不许有。这条第一版用模块级 fixture 的不可达 dsn，
  会**永远走 skip 分支**；永远跳过的判据等于不存在，已改成走
  `FLINT_TEST_DSN`（DSN-ISO 口径，默认 `flint_test`）。实测 0 跳过、19 绿。

改既有文件：`flint/api/app.py`（本卡 outputs）、`tests/v041/test_app_assembly.py`
（本卡 outputs）。全局门重跑：ruff 全绿 · mypy 299 files · **pytest 3690 passed**。

## 8. 登记未做

1. **`WIRE-05` 的门要判「已挂 + 已登记 = 全部」**，NEVER 直接判 `== 0`——
   否则四族一天不接上，全局门一天恒红；
2. **`E2E-01` 受阻**：主链路要经 `/projects/{}/analysis`，属未挂的四族之一；
3. **`WIRE-03`** 切九张屏时，`analysis` 链路上的屏仍要走「接口未提供」；
4. **§7.3 那条盲区**没有判据守着（变异考③实测）。
