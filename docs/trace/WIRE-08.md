# WIRE-08 · compose 族两条路由接通

**卡** `docs/steward/tasks-v041-b4.json#WIRE-08` · **cycles 1（oneshot）** ·
**self_review = true** → §5 · **owner_review = false** · **依赖** `AUTH-03`

## 1. 装载清单

卡面 WIRE-08 · `flint/api/compose.py` 全文 · `flint/api/app.py` 的装配段 ·
`flint/api/interventions.py` 的 `_denied` / `may_intervene` ·
`harness/e2e_stack.py` 与 `harness/e2e_smoke.py` 的 compose 构造点 ·
`tests/m3/test_m3_057.py`。约 12k tokens，预算 40k 以内。

## 2. 挂之前先撞见一件事：**这两条端点一次权限都不判**

`WIRE-01` 拒绝挂这一族时给的理由是「缺 `role_resolver`」。**实况比那更进一步**：

```python
class ComposeApiDeps:      # 改前
    dsn: str
    runner: PgJobRunner
    owner_scope_for_project: Callable[[str], Principal]
```

**根本没有 resolver 这个字段**——两条提交端点从头到尾没有任何权限判断，
`owner_scope_for_project` 只用来填 `owner_scope`。
也就是说：**任何 `x_user_id` 都能给任意项目提交一份要花钱的组稿作业**。

所以本卡不是「把 deps 填上就挂」。先给 compose 补那道门：口径与
`interventions` **逐字同一道**（`_INTERVENE_ROLES = {owner, admin}`——
提交组稿是**写**），再挂。

`role_resolver` 在 `ComposeApiDeps` 里是**必填**，**NEVER 给 `None` 默认值**：
「默认不检查」就是「默认开洞」，而这一族此前挂不上的理由正是「挂上等于人人可写」。
判据 `test_the_resolver_is_a_required_field_not_an_optional_one` 判的就是这件事
（用 `dataclasses.fields` 看它有没有默认值）。

## 3. 两族共用一个 runner

`analysis`（`WIRE-07`）与 `compose` 用**同一个** `PgJobRunner`。
各造一个就是两条入队路径，而「作业进了哪条队列」会因此说不清。
判据走 `ast` 数 `app.py` 里 `PgJobRunner(` 出现几次——正好一次。

## 4. `harness/e2e_stack.py` 就此收敛成一句 `create_app`

`WIRE-07` 拿走 analysis、`WIRE-08` 拿走 compose 之后，那个夹具栈
**一族都不再补**。函数体收敛成 `return create_app(...)`，
`extra_families()` 返回空元组。

没删掉它，是因为端到端判据要的是「打的是**装配后的那个**应用」，
而这条口子留着，下一次再有「可部署应用挂不上、夹具先有」的族时，加回来的地方是确定的。
**它此刻的价值就是那句空元组：NEVER 让夹具悄悄比线上多一族。**

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_wire_compose.py -q → 9 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 301 source files
            pytest -q               → 3980 passed（WIRE-07 收卡时 3971，本卡 +9）
对账器:     backend_not_assembled 7 → **5**
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 两条挂进 `create_app` | `test_the_two_paths_are_mounted` |
| ② runner 用真件注入、NEVER 另造 | `test_both_families_share_one_runner`（判 `ast`：`app.py` 里 `PgJobRunner(` 正好一次）、`test_the_resolver_is_a_required_field_not_an_optional_one` |
| ③ 逐条探活 + 无权 403 + 登记里删掉 | `test_neither_path_is_404`、`test_an_outsider_is_refused_on_both_paths`、`test_a_member_is_refused_because_composing_is_a_write`（**member 也被拒**——把口径钉死：读得到的人不等于能提交一份要花钱的作业）、`test_the_owner_gets_past_the_gate`（**正例**：过门之后停在 503（队列没配），**那也不是 403**）、`test_an_unknown_project_is_404_not_403`、`test_compose_is_gone_from_the_unwired_register` |

**② 改既有文件七处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `flint/api/app.py` | 挂 compose；两族共用一个 runner；`UNWIRED_FAMILIES` 删掉 compose | **卡上 outputs** |
| `flint/api/compose.py` | `ComposeApiDeps` 加**必填** `role_resolver`；加 `_denied()`；两条端点各接一次 | **在卡上 outputs 之外**，但不加就等于挂上一个「谁都能提交」的写端点——那正是本批要关的洞（§2）。卡面 acceptance③ 明写「无权用户 403」，而改前的代码里根本没有 403 这条路 |
| `harness/e2e_stack.py` | 删掉自己那份 compose 装配；`build_e2e_app` 收敛成 `create_app`；`extra_families()` → `()` | 不删就是 `RouteConflictError`（§4） |
| `harness/e2e_smoke.py` · `tests/m3/test_m3_057.py` | 补 `role_resolver`（必填字段） | 必填字段加上去之后，旧构造点不补就构造不出来 |
| `tests/v041/test_app_assembly.py` · `test_fe_be_parity.py` · `test_wire_analysis.py` · `test_e2e_full_stack.py` | 等值判据里的数字/集合跟着实况改（10 → 7 → **5**；闲置样本换成 `interventions`；夹具栈多出来的族 → 空集） | 它们钉的是「compose 还没挂」。**每接通一族就要改一次——改它就是在记账** |

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；未新增依赖。

**③ 变异考 5 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 不挂 compose | 红 |
| ② 权限门拆掉（回到谁都能提交） | 红（2 条） |
| ③ 门放宽（`if False`，member 也能提交） | 红（2 条） |
| ④ 登记没跟着删 | 红 |
| ⑤ 两族各造一个 runner | 红 |
| ⑥ 假变异对照：末尾加一行注释 | 全绿 |

**④** 装载约 12k tokens；**⑤** 禁用词六词 0 命中。

## 6. 登记未做

1. **`AUTH-03` 的身份入口仍未接进这两条端点**（同 `WIRE-07` §6-1）。
   缺头仍是 FastAPI 默认 422，不是 401。四族统一换放在 `WIRE-11` 更合适。
2. **`_denied` 在 compose 与 interventions 里各写了一遍**（形状相同、文案不同）。
   提成一个共用件要动两族的公共面，本卡没动——登记在此。
3. **`test_m3_057` 那处给的是恒答 `None` 的解析器**：它的归属是**个人**
   （`kind == "user"`），那条路比的是 id 本身、不问角色。
   所以那个解析器**不放行任何人**，也不影响该用例的语义。
