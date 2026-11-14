# WIRE-09 · interventions 族四条路由接通（含 aligner）

**卡** `docs/steward/tasks-v041-b4.json#WIRE-09` · **cycles 2（oneshot=false）** ·
**self_review = true** → §5 · **owner_review = false** · **依赖** `AUTH-03`

## 1. 装载清单

卡面 WIRE-09 · `flint/api/interventions.py` 全文（deps、四个端点、`_denied`）·
`flint/api/app.py` 的装配段 · `flint/align/stage1.py#LLMCitationAligner` ·
`contracts/protocols.py#LLMProvider` · `flint/scoring/scorer.py` ·
`flint/compose/blocks.py` 的保护谓词 · `harness/demo_server.py` 的装配段。
约 15k tokens，预算 40k 以内。

## 2. 这一族比前两族多一样要注的东西：**模型**

证据注入要跑两段式对齐，对齐吃 LLM。`create_app` 因此多一条缝 `aligner_provider`。
不给就注 `_UnconfiguredProvider`——**一被调用就 `FamilyNotConfigured`**，
与既有 `_unconfigured()` 同一姿态：路由挂着，用到模型的那条回 503 + 点名。

**NEVER 注一个「返回空补全」的假 provider。** 那样对齐会「成功」地把每条 claim
判成没有引用，而**「没配模型」与「模型说这条没有出处」是两件相反的事**：
前者要人去配模型，后者是一条真的判定结果。
变异考②正是把占位改成 `return {}`——**红了三条**。

## 3. 受保护 block 的不变量（S2-5）

`locked ∨ author == "user" ∨ user_modified` 的 block NEVER 被 regenerate 改写。
本卡加了端到端的两条：

- `test_a_protected_block_is_untouched_by_a_regenerate_submission`：
  真发一次 regenerate（owner，过得了门），改前改后**逐字节比对**；
- `test_the_seeded_block_really_is_protected`：**前提自检**——
  夹具那条 block 在 `PROTECTED_SQL_PREDICATE` 下确实算受保护。
  没有它，上一条可能是在一条**根本不受保护**的 block 上验的，
  那时它证明不了任何事（F-08 的形态）。

保护谓词是单点的，本卡**问它**，NEVER 复制一份三条件。

## 4. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_wire_interventions.py -q → 11 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 301 source files
            pytest -q               → 3991 passed（WIRE-08 收卡时 3980，本卡 +11）
对账器:     backend_not_assembled 5 → **1**（只剩 combo）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 四条挂进 `create_app` | `test_the_four_paths_are_mounted` |
| ② aligner 走 provider 适配器、测试恒回放 | `test_the_evidence_path_says_the_model_is_unconfigured`、`test_the_unconfigured_provider_never_pretends_to_answer`、`test_a_real_provider_replaces_the_placeholder`（**缝的两侧都要有实例**，用 `MockTransport` 回放 provider，零真实出网） |
| ③ 受保护 block 不被改写 | §3 那两条 |
| ④ 逐条探活 + 403 + 登记里删掉 | `test_none_of_the_four_is_404`、`test_an_outsider_is_refused_on_all_four`、`test_a_member_is_refused_too`、`test_the_owner_gets_past_the_gate`（正例）、`test_interventions_is_gone_from_the_unwired_register` |

**② 改既有文件六处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `flint/api/app.py` | 挂 interventions；加 `aligner_provider` 缝与 `_UnconfiguredProvider`；`UNWIRED_FAMILIES` 删掉 interventions | **卡上 outputs** |
| `harness/demo_server.py` | 删掉自己那份 interventions 装配；删掉不再需要的 runner（三族都归 `create_app` 了） | 不删就是 `RouteConflictError` |
| `tests/v041/test_app_assembly.py` · `test_demo_stack_wired.py` · `test_fe_be_parity.py` · `test_wire_analysis.py` · `test_wire_compose.py` · `test_demo_uses_real_authz.py` | 等值判据跟着实况改（登记面 5 → **1**；demo 差集只剩 `/projects/combo`；闲置样本换成 combo；两条「只剩哪几族」的集合） | 它们钉的是「interventions 还没挂」。**第三轮记账** |

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；未新增依赖。

**③ 变异考 4 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 不挂 interventions | 红 |
| ② 占位 provider 改成「返回空补全」 | 红（3 条） |
| ③ 用假手（人人 owner） | 红（2 条） |
| ④ 登记没跟着删 | 红 |
| ⑤ 假变异对照：末尾加一行注释 | 全绿 |

**④ 一处判据我自己写错，当场改**：给 demo 那条加了
`assert "lambda _u, _o:" not in text`，当场把 `demo_server.py` docstring 里
「这里原本是 `lambda _u, _o: "owner"`」判成违规——
**说明问题的那句话又一次被当成犯下问题**。这是本批**第三次**踩同一个坑
（`AUTH-02`、`AUTH-05`、本卡），三次都靠改判 `ast` 解决。
本卡顺手加了一个 `_code_of()`：用 `ast.unparse` 剥掉 docstring 再判。

**⑤** 装载约 15k tokens；**⑥** 禁用词六词 0 命中。

## 5. 登记未做

1. **对齐那条路只验到「没配模型时 503」**。真跑一次两段式对齐要
   `aligner_provider` + 一份录制，属 `WIRE-10`/`E2E` 的面，本卡没跑。
2. **regenerate 只验到「提交不动 block」**。真正的改写在 worker 里
   （`flint/jobs/regenerate_worker`），那一段的保护由既有判据守着，本卡没重跑。
3. **`_denied` 仍在三处各写一遍**（interventions / compose / 本卡未动的那份）。
   提成共用件登记在 `WIRE-08` trace §6-2。
4. **demo 的 `_enqueue`（`asyncio.create_task` 那条）现在只服务它自己起的 gate1 路径**；
   提交端点走的是 `create_app` 里那条真 arq 缝。两条派发路径并存这件事，
   等 `WIRE-11` 收口时值得再看一眼。
