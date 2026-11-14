# AUTH-05 · demo 栈那只假手退役

**卡** `docs/steward/tasks-v041-b4.json#AUTH-05` · **cycles 1（oneshot）** ·
**self_review = true** → §4 · **owner_review = false** · **依赖** `AUTH-02`

## 1. 装载清单

卡面 AUTH-05 · `harness/demo_server.py` 的 `build_app` 段与 `__main__` ·
`harness/e2e_smoke.py` 的 `_submit` · `harness/e2e_stack.py` 的 `build_runner` ·
`flint/authz`（`AUTH-02` 的产物）· `docs/blocked/WIRE-01-FOUR-FAMILIES-…md`。
约 8k tokens，预算 40k 以内。

## 2. 全仓扫下来是**五处**，不是三处

卡面点名 `demo_server.py` 那三处。判据按 acceptance③ 扫产品树 + harness，
另外揪出两处：

```
harness/e2e_smoke.py:114     ← ASM-05 留的
harness/e2e_stack.py:70 / :92 ← 我自己上一批 E2E-01 写的
```

三个文件五处全部换成 `flint/authz` 的真解析器。

**那两处「反正走不到」不是留它的理由**：两条 e2e 链路上的作业都是**个人归属**
（`kind == "user"`），`may_view` 在那条路上比的是 id 本身、根本不问角色。
但留着它，**哪天有人把那条链改成 org 归属，越权会静默地通过**——
而那时没有任何判据会红。acceptance③ 那句「NEVER 留一个回来的口子」说的就是这个。

## 3. demo 的身份现在是库里一行真的 `users`

`seed_demo_identity()`：一个用户、一个组织、一条 membership，幂等
（`ON CONFLICT DO NOTHING` / `DO UPDATE`）。`__main__` 里**先种再起服务**——
顺序反了的话，第一个请求打进来时库里还没有那个用户，而那时的拒绝会被读成「鉴权坏了」。

demo 库实测（本卡跑过一次）：

```
demo-user @ org-demo → owner
someone-else @ org-demo → None
```

**demo 库此前已在 0020**（本卡开始前就是，三张表在），本卡没有对它跑过迁移。

## 4. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_demo_uses_real_authz.py -q → 9 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 301 source files
            pytest -q               → 3961 passed（AUTH-04 收卡时 3952，本卡 +9）
连坐面:     test_e2e_full_stack.py + test_asm_05_e2e.py → 24 passed（换解析器没碰倒它们）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 那三处删掉、改用真 resolver | `test_the_demo_server_holds_no_constant_role_anymore`、`test_the_demo_server_imports_the_real_resolver` |
| ② demo 用种子身份 | `test_the_seed_puts_a_real_user_and_membership_in_the_database`（**先清干净再种**，见 §5-③）、`test_a_stranger_is_still_refused_on_the_demo_data`（**阴性对照**：假手在的时候，这条会绿着说 stranger 也是 owner） |
| ③ 全仓扫描零常量角色 | `test_no_constant_role_resolution_survives_anywhere_in_the_product_tree`（扫 `flint` + `harness`，判 `ast`）+ `test_the_scanner_would_catch_the_hand_if_it_came_back`（**自证**：把那只手写进临时文件，扫描器认得出——没有它，绿可能是「谁都匹配不上」换来的，F-08 的形态） |
| ④ demo 仍一键起、报告屏仍打得开 | `test_the_demo_stack_still_covers_the_deployable_app`（`WIRE-02` 那条判据不倒）、`test_building_the_demo_app_touches_no_database`、`test_the_entrypoint_seeds_before_serving` |

**② 改既有文件三处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `harness/demo_server.py` | 三处 `lambda _u, _o: "owner"` → `build_role_resolver(DSN)`；加 `DEMO_USER` / `DEMO_ORG` 与 `seed_demo_identity()`；`__main__` 先种再起；文档段里那句「明知故犯的口径」改写成事实 | **卡上 outputs**，本卡主体。那句注释不改的话，文件里会留着一句已经不成立的话 |
| `harness/e2e_smoke.py` | `role_resolver=lambda _u, _o: "owner"` → 真解析器 | acceptance③ 要**全仓**零常量角色。它在卡面 outputs 之外，但不改就收不了卡——理由见 §2 |
| `harness/e2e_stack.py` | 同上两处 + 模块 docstring 里那段「夹具口径」改写 | 同上。这两处是我自己上一批写的，**这次由自己的判据揪出来** |

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；未新增依赖。

**③ 变异考 4 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 那只手回来（一处） | 红 |
| ② 种子不种 membership | **第一轮绿 → 判据改窄后红** |
| ③ 入口先起服务后种身份 | 红 |
| ④ 建应用时顺手种一次库 | **第一轮绿 → 判据改窄后红** |
| ⑤ 假变异对照：末尾加一行注释 | 全绿 |

**两条第一轮绿的都是判据的洞，且是同一类**——**判据在读别人留下的状态**：

- ② 上一轮跑测试时那行 membership 已经种进去了，而判据不清场就断言，
  于是「种子什么都不种」照样绿。改成**先清、先断言清干净了、再种**；
- ④ 原判据只断言「应用建起来了、路由够多」，从没量过「有没有连库」。
  改成把 `asyncpg.connect` 换成一个一调就炸的桩，**真量一次**。

**④** 装载约 8k tokens；**⑤** 禁用词六词 0 命中。

## 5. 登记未做

1. **`owner_scope_for_project` 在 demo 与 e2e 栈里仍是常量**
   （`lambda _pid: Principal(kind="user", id=DEMO_USER)`）。
   它不是**角色**常量，acceptance③ 扫的也不是它；而且它给出的是**个人归属**，
   `may_view` 在那条路上只放行本人。要换成 `flint/authz` 的
   `build_owner_scope_for_project`，得先决定「demo 里那些没有 `projects` 行的
   演示资源怎么办」——那是 demo 数据面的决定，不是本卡的。
2. **`tests/` 不在扫描面**。判据自己要造反例（`AUTH-04` 的 `_fake_hand` 就是一个），
   扫进去等于逼判据删掉自己的对照。代价：测试里可以写一只假手而不被这条挡住——
   靠的是「变异考会把它咬出来」，不是靠扫描。
3. **demo 只种了一个 org 与一条 membership**。多人多组织的 demo 数据没有，
   所以 demo 上没法演示「同一个人在两个组织里角色不同」。
