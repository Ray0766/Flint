# AUTH-04 · 越权矩阵：四种角色 × 三类操作逐格断言

**卡** `docs/steward/tasks-v041-b4.json#AUTH-04` · **cycles 2（oneshot=false）** ·
**self_review = true** → §4 · **owner_review = true** → §5 · **依赖** `AUTH-03`

## 1. 装载清单

卡面 AUTH-04 · `flint/api/analysis.py` 的 `may_view` 与 `_VIEW_ROLES` ·
`flint/api/interventions.py` 的 `may_intervene` 与 `_INTERVENE_ROLES` ·
`contracts/models.py` 的 `Role` 与 `Job` 的权限 docstring ·
`flint/authz`（`AUTH-02` 的产物）。约 7k tokens，预算 40k 以内。

## 2. 矩阵（实测值，不是设计值）

| | 读 | 写 / 干预 |
|---|---|---|
| `owner` | ✓ | ✓ |
| `admin` | ✓ | ✓ |
| `member` | ✓ | ✗ |
| `viewer` | **✗** | ✗ |
| 非成员（真人，不在这个 org） | ✗ | ✗ |
| 未登录（不是任何人） | ✗ | ✗ |

12 格全部有断言，**没有「其余同理」**——那句话一写，没写的格子就没人量了。
口径不是本卡定的：`_VIEW_ROLES = {owner, admin, member}` 与
`_INTERVENE_ROLES = {owner, admin}` 都是既有的，本卡只把它们钉住。

## 3. 本卡最值钱的一条：阴性对照

`test_the_refusals_all_flip_when_the_resolver_goes_back_to_the_fake_hand`
把解析器换回那只假手（`lambda _u, _o: "owner"`），
**矩阵里每一个拒绝格都变成通过**。

它证明那些格子**真的在量权限**，而不是在量别的——比如「这个人不存在」
或者「这条路本来就不通」。没有它，一个恒假的判定也能让整张矩阵全绿。

配套还有一条**边界**：`test_the_fake_hand_does_not_flip_the_personal_scope`。
假手翻不动个人归属那一行，因为 `kind == "user"` 时比的是 id 本身、根本不问角色。
写下来是为了让「全部翻绿」有个准确的范围——**NEVER 让一句话比它证到的更大**。

## 4. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_authz_matrix.py -q → 20 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 301 source files
            pytest -q               → 3952 passed（AUTH-03 收卡时 3932，本卡 +20）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 逐格断言（4 角色 + 非成员 + 未登录）× 三类操作 | 三条 `parametrize`（读 / 写 / 干预各四格）+ `test_a_non_member_is_refused_on_all_three` + `test_an_unknown_identity_is_refused_on_all_three` + `test_the_matrix_covers_every_cell_it_claims_to`（**元判据**：12 格、通过的正好 5 个——docstring 里写着表格而断言少几条的那天，读的人以为都量过了） |
| ② 越权 NEVER 静默降级 | `test_a_refusal_is_a_refusal_not_a_downgrade`（判 `is False`，且不是空列表/空字典——一个越权的写请求收到 200 + 空列表时，调用方以为自己写成功了） |
| ③ 个人归属与组织归属分开 | `test_a_personal_scope_ignores_memberships_entirely`（org 里的 admin 读不到别人的私人项目）+ `test_the_initiator_can_always_see_their_own_job`（**对照**：没有它，那些 `False` 可能是「这条路对谁都不通」换来的） |
| ④ 阴性对照 | §3 那两条 |

**② 改既有文件 0 处**；新增 `tests/v041/test_authz_matrix.py`（卡上唯一 output）。
`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；未新增依赖。

**③ 变异考 4 咬住 + 假变异对照绿**（变异打在**生产码**上，不是打在判据的常量上）

| 变异 | 判据 |
|---|---|
| ① `_INTERVENE_ROLES` 放进 `viewer` | 红（4 条） |
| ② `_VIEW_ROLES` 放进 `viewer` | 红（2 条） |
| ③ `may_view` 丢掉 org 分支 | 红（4 条） |
| ④ `may_intervene` 恒放行 | 红（8 条） |
| ⑤ 假变异对照：末尾加一行注释 | 全绿 |

**④** 装载约 7k tokens；**⑤** 禁用词六词 0 命中。

## 5. owner_review

**一个叫 `viewer` 的角色，在作业这条路上连读都不行。**

`_VIEW_ROLES = {owner, admin, member}` —— 里面没有 `viewer`。
本卡按既有口径断言（拒绝），并把这件事原样交给你：

- 要么这个名字**名不副实**（一个什么都看不了的 viewer）；
- 要么冻结件 `Job` 那句「SSE 订阅 = 同上 + **member 只读**」本来就没打算让
  viewer 看作业，而 viewer 的用武之地在**文档**那一侧（报告 / 交付物）——
  那一侧此刻还没有任何角色判断。

**NEVER 由本卡替它改口径**：改 `_VIEW_ROLES` 是一行的事，
但那一行决定的是「谁能看见别人的作业」。
