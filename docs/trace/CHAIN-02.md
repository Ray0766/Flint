# CHAIN-02 · 端到端删掉「人手种一条 claim」那一步

**卡** `docs/steward/tasks-v041-b4.json#CHAIN-02` · **cycles 1（oneshot）** ·
**self_review = true** → §4 · **owner_review = false** · **依赖** `CHAIN-01`

## 1. 装载清单

卡面 CHAIN-02 · `tests/v041/test_e2e_full_stack.py` 全文 ·
`docs/blocked/GATE1-VERDICT-IS-NOT-A-COMPOSE-SOURCE.md` · `docs/trace/E2E-01.md` ·
`flint/jobs/gate1.py#analysis_product_id`（`CHAIN-01` 刚落的） ·
`flint/jobs/worker_main.py#_compose_handler`。约 11k tokens。

## 2. 那一步删掉之后，链路才是一条

改前端到端是这样的：

```
提交分析 → 队列 → gate1 → 判定落 snapshots
                              ↓（断）
                       人手种一条 claim ←── 测试自己编的 source id
                              ↓
提交报告（analysis_id = 那个编出来的 id）→ 队列 → 组稿 → 渲染 → 导出门
```

改后：

```
提交分析 → 队列 → gate1 → 判定落 snapshots + **claims**（analysis-{job}）
                                              ↓
提交报告（analysis_id = analysis_product_id(那次判定的 job)）→ 组稿 → …
```

**组稿那侧一个字没改**：`_compose_handler` 把 payload 里的 `analysis_id`
原样当来源交付物 id 用。`CHAIN-01` 把 id 口径定成 `analysis-{job}` 之后，
端到端只要传那个 id 就接上了。

## 3. 守门断言按它自己写的那句话翻面（acceptance②）

`test_gate1_output_is_still_not_the_claims_source` 的 docstring 写着
「哪天接上了，这条会红——那时来这里把链路改成一条，并关掉那张单」。

| | 改前 | 改后 |
|---|---|---|
| 名字 | `test_gate1_output_is_still_not_the_claims_source` | `test_the_chain_now_runs_from_gate1_all_the_way_to_compose` |
| 断言 | 那个来源 id 下**没有**除夹具外的 claim | ① 来源 id 由判定推导（NEVER 是测试编的）② 那批行真在库里 ③ **没有任何带测试前缀的人手行** |

第三条是防回潮的：只判「有 claim」的话，把种 claim 那步加回来照样绿。

## 4. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_e2e_full_stack.py -q → 9 passed（改前 8）
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 301 source files
            pytest -q               → 4041 passed（CHAIN-01 收卡时 4040，本卡 +1）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 删掉种 claim 那步，真从 gate1 接组稿 | `_seed_claim` 整个函数删掉；`test_the_chain_now_runs_from_gate1_all_the_way_to_compose` |
| ② 守门断言按其自述处理 | §3；改前改后写在这里 |
| ③ 全链路走录制回放、零真实出网 | `test_nothing_left_the_machine`（`went_out == []`，原样保留，本卡没动） |
| ④ 关闭那张单 | 单子顶部 `**状态** closed · 2026-08-06 · CHAIN-01 + CHAIN-02`，正文写明两个待定问题各定成什么 |

**② 改既有文件一处**（`tests/v041/test_e2e_full_stack.py`，卡上唯一 outputs）：

| 改前 → 改后 | 为什么非改不可 |
|---|---|
| 删 `_seed_claim` 与它的调用 | 卡的正题 |
| `source` 从 `f"{PREFIX}src-{tag}"` 改成 `analysis_product_id(analysis_job)` | 编出来的 id 下永远只有人手种的行 |
| 守门断言翻正向 + 新增 `_seeded_claims_for` | acceptance② |
| `_wipe` 加一行清 `analysis-{PREFIX}%` 的 claim | 不清的话，下一次跑读到的是上一次的行——**判据会读到别人留下的状态**（本批已栽过两次） |
| 新增 `_claim_shapes` / `_facts_from` 取证与那条记账判据 | §5 |
| `_claims_for` 去掉「排除测试前缀」的条件 | 种的那步没了，那个排除条件会掩盖回潮 |

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；`flint/` **一行未改**（`CHAIN-01` 已备好全部接口）；未新增依赖。

**③ 变异考 3 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① gate1 又不落 claims（退回缺陷态） | 红，报「这一跳又断了」 |
| ② 来源 id 换回测试自己编的 | 红 |
| ③ 人手种一条 claim 混进去 | 红，报「还有人手种的行混在里面」 |
| ④ 假变异对照：一行注释 | 全绿 9 passed |

**④** 装载约 11k tokens；**⑤** 禁用词六词 0 命中。

## 5. 接通之后露出来的下一处，据实记账

实测那批 claim 是 `speculative` / `supports`，账本里 **0 条 Fact**。

原因不在本卡：钉引用那一步（`pin_verdict_citations`）**只在 `gate1.main()`
的生产路径跑**，队列 worker 的 gate1 handler 不跑它。于是队列跑出来的判定
有结论、没引用，`promote_claims` 一条都提不动（要 cited ∧ supports）。

新增 `test_the_chain_carries_conclusions_but_not_yet_citations` **钉住这个实况**
（等值判据：`[("speculative", "supports")]` 与 `0`），并在 docstring 里写明
**NEVER 把它读成「本来就该是 0」**。钉引用那步哪天进了队列路径，本条会红——
那正是提醒来改判据的机制。

处置三选一在 `docs/trace/CHAIN-01.md` §6（我倾向让 worker 的 gate1 handler
也调 `pin_verdict_citations`，CI 注入回放 client）。

## 6. 登记未做

1. **队列路径不钉引用**：见 §5，等 owner 裁。
2. **端到端只跑了一个关键词**：`support_claims` 因此只有一条。
   多关键词会同时验到 K 上限那条路（`pending`），但那要重录一份回放夹具。
3. **`E2E-01` 的 trace 没改**：本卡的经过写在这里，那份是上一张卡的记录。
