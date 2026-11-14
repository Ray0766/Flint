# CHAIN-01 · gate1 收尾把 support_claims 落成 claims 行

**卡** `docs/steward/tasks-v041-b4.json#CHAIN-01` · **cycles 2（oneshot=false）** ·
**self_review = true** → §5 · **owner_review = true** → §6 · **依赖** `WIRE-08`

## 1. 装载清单

卡面 CHAIN-01 · `docs/blocked/GATE1-VERDICT-IS-NOT-A-COMPOSE-SOURCE.md` ·
`flint/jobs/gate1.py` 的 `_judge_payload` / `_validate_verdict` / run 循环 ·
`flint/compose/freeze.py#_load_claims` · `flint/ledger/promoter.py#promote_claims` ·
`flint/align/stage1.py`（`LLMCitationAligner` 与 `align_key_evidence`） ·
`migrations/0008#claims` · `contracts/models.py#Claim` ·
`flint/jobs/worker_main.py#_compose_handler` · `CLAUDE.md#S2`。
约 18k tokens，预算 40k 以内。

## 2. `deliverable_id` 的口径：先定后写（acceptance②）

`claims` 表按交付物索引，而 **gate1 的产出不是一份交付物**——它是一次判定。
本卡定的是**分析产物 id**：`analysis-{job_id}`（`ANALYSIS_PRODUCT_PREFIX`）。

| 为什么这么定 | |
|---|---|
| 与交付物命名空间不相交 | 交付物是 `del-{job}`，分析产物是 `analysis-{job}`，永远撞不上；看一眼就知道这行 claim 来自判定而不是某篇报告 |
| 一次判定一个产物 | job id 已经是那次判定的唯一标识，NEVER 另造一套编号 |
| **不建假交付物行** | `claims.deliverable_id` 没有外键（`migrations/0008`），这个 id 不需要 `deliverables` 里有行；建了的话交付物列表会多出一份**没人能打开的「报告」** |

最后一条有判据钉着（`test_no_fake_deliverable_row_is_created`），
变异考里也造过那一手（⑦）——当场红。

`block_id` 填 `{product_id}#judge`：**判定步的名字**，
说明这条 claim 出自哪一步，NEVER 假装它指向一个 block 行。

## 3. 三种「有多支持」各有其位（acceptance③）

| 情形 | alignment | 后果 |
|---|---|---|
| 对齐器判过、说支持 | `supports` | 可被提升为 Fact |
| 判过、说沾边或不支持 | `partial` / `unsupported` | **NEVER 提升**（S2-4） |
| 超出 K 上限、**根本没判** | `pending` | 同上 |

第三种是本卡最要紧的一条。把没判过的写成 `unsupported`，读起来是
「查过了，证据不支持」——一句系统没有依据说出口的话；写成 `supports` 更糟，
`promote_claims` 会把它提成 Fact。

**「有证据」与「引用落库了」也是两件事**：`confidence="cited"` 意思是
这条结论指得出一条引用。gate1 手里有 doc，但 quote_span 的钉入
（`pin_verdict_citations`）**在离线与队列路径下根本没跑**。
所以按库里实际有没有那条 citation 行来定：有 → `cited` 带上它；
没有 → `speculative` 且 `citation_ids` 为空。编一个 id 的话，
下游解引用会失败，而那种失败读起来像「引用坏了」，真相是「引用从没入过库」。

## 4. 每对 (claim, doc) 的对齐结论怎么拿到的

它只在 `_validate_verdict` 里算得出来（rule C 内部调 `align_key_evidence`），
而那个函数的返回值**原样发给前端**（`GET /jobs/{id}/verdict`）——
多一个键就是多一处对外契约。它还有三个本卡 outputs 之外的调用点
（`gate/replay.py` / `revalidate/run.py` / `tests/m3`）。

所以做成**可选出参** `alignment_out`：三个既有调用点一个字不用改，
payload 一个键都不多。取值时复用**同一个 aligner 实例**——
它带 `LLMJudgmentCache`，键是 `(stage, claim, doc_id)`，
rule C 刚判过的那几对全是缓存命中，**零额外模型调用**。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_gate1_writes_claims.py -q → 14 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 301 source files
            pytest -q               → 4040 passed（ROUTE-01 收卡时 4026，本卡 +14）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 由 gate1 落 claims 行 | `test_gate1_now_writes_claim_rows`、`test_every_support_claim_from_the_judge_becomes_a_row`（**判等值**：judge 有几条就落几行，少落=悄悄丢结论，多落=凭空造结论） |
| ② id 口径先定后写 | `test_the_product_id_is_namespaced_and_derived_from_the_job`、`test_no_fake_deliverable_row_is_created`、`test_two_jobs_never_share_a_claim_row` |
| ③ Claim/Fact 边界不动 | `test_a_partial_claim_is_never_written_as_supports`、`test_a_claim_that_was_never_aligned_says_pending`、`test_promotion_only_takes_the_cited_and_supporting_ones`（**喂给真正的 `promote_claims`**）、`cited`/`speculative` 两侧各一条 |
| ④ 落盘幂等 | `test_rerunning_the_same_job_never_duplicates_rows`（编排层）、`test_writing_the_same_rows_twice_leaves_one_row_each`（**写库层自己**）、`test_a_rerun_never_clobbers_a_promotion` |

**② 改既有文件一处**（`flint/jobs/gate1.py`，卡上 outputs）：

| 改前 → 改后 | 为什么非改不可 |
|---|---|
| 加 `ANALYSIS_PRODUCT_PREFIX` / `analysis_product_id` / `ClaimRow` / `claim_rows_from` / `_cited_docs` / `_write_claim_rows` | 卡的正题 |
| `_validate_verdict` 加可选出参 `alignment_out` | 每对的对齐结论只在那里算得出来；做成出参是为了**不改三个 outputs 之外的调用点**，也不给对外 payload 加键（§4） |
| validate 步内写 claims | 与 `job_steps` **同一事务**——分两次提交的话，kill -9 卡在中间会留下「步已记完、claim 没写」，续跑会跳过那步，那批结论就永远丢了 |

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；**未新增依赖**。`_judge_payload` 与 payload 形状一字未改。

**③ 变异考 7 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 根本不写 claims（退回缺陷态） | 红 6 条 |
| ② 没判过 = 不支持（把 `pending` 合并掉） | 红 2 条 |
| ③ 一律写 `supports` | 红 |
| ④ 引用没入库也写 `cited`、编一个 id | 红 2 条（连提升那条一起红——正是它要防的） |
| ⑤ `claim_id` 只由文本决定 | 红（两次判定共用一行） |
| ⑥ 重写抹掉 `promoted_fact_id` | 红 |
| ⑦ 顺手建一行假交付物 | 红 |
| ⑧ 假变异对照 | **第一次假红**，见下 |

**④ 假变异对照第一次是红的，原因不在代码**：变异⑦ 往 `deliverables` 里插的
那两行**留在库里没清**，而 `_wipe` 只清 claims/jobs/snapshots。
于是下一轮跑起来，`test_no_fake_deliverable_row_is_created` 照旧红。
清掉残留后重跑 → 14 passed 全绿。

**这是本批第二次「判据读到别人留下的状态」**（上一次 `AUTH-05`）。
教训一样：**变异器留下的写操作要与判据的清理面对齐**，否则下一条判据
量的是上一次变异的尾巴。

**⑤ 我自己写错的一条判据**：第一版幂等测试删掉 `job_steps` 里 validate 那行
再跑，炸在 `snapshots_pkey`——因为 `_put_snapshot` 是**纯 INSERT**。
那个状态**真实系统产生不出来**（快照与步记录同事务提交，有快照必有步记录）。
造一个不可能的状态来量幂等，量的是幻觉。改成量两件真的事：
编排层「重跑跳过已完成步」+ 写库层「同一批行写两次仍是一行」。
这段经过留在了判据的 docstring 里。

**⑥** 装载约 18k tokens；**⑦** 禁用词六词 0 命中。

## 6. owner_review

**1. 那批 claim 现在几乎都是 `speculative`。**
因为 `pin_verdict_citations`（钉 quote_span → 落 citation 行）
**只在 `gate1.main()` 的生产路径跑**，队列 worker 的 `_gate1_handler` 不跑它。
于是队列跑出来的判定，claims 有结论、没引用，**一条也提升不了 Fact**。

这不是本卡造成的——本卡只是**把这件事第一次显示了出来**。
三条路：① worker 的 gate1 handler 也调 `pin_verdict_citations`（要给它注入
http client，CI 用回放）；② 接受「队列路径不钉引用」，报告里那些结论只作
claim 出现、不进账本；③ 让 gate1 自己在离线也能落一条**无 quote_span 的**
citation——我不建议，那等于把「没钉过」写成「钉过了但没有引文」。

**我倾向①**，且它正好是 `CHAIN-02` 端到端要面对的同一件事。

**2. `deliverables` 那张表里没有 `analysis-{job}` 这一行，是有意的。**
若你认为分析产物应当在交付物列表里可见（比如让用户「打开一次判定」），
那是另一种产品口径，要新增一个 `type`（现在是 report/proposal/vibe_pack），
不是本卡该定的。

## 7. 登记未做

1. **`refute_claims` 没有落盘**：卡面只点了 `support_claims`。
   证伪 claim 的语义是「这条证据反对这个方向」，把它写进 `claims` 表
   （那张表的语义是「本交付物内生成的一句结论」）需要先定口径。
2. **`_put_snapshot` 仍是纯 INSERT**：它靠同事务不变量保护，本卡没动。
   动它会掩盖「同一步跑了两次」这个本该炸出来的信号。
3. **组稿那侧还不知道 `analysis-{job}` 这个 id**：`CHAIN-02` 接。
   `_compose_handler` 把 payload 里的 `analysis_id` 原样当来源 id 用——
   端到端只要传 `analysis_product_id(job)` 就接上了，**worker 一个字不用改**。
