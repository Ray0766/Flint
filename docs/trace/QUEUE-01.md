# QUEUE-01 · 经作业队列跑通 gate1（回放，非红线）

**卡** `docs/steward/tasks-v041-b3.json#QUEUE-01` · **cycles 2（oneshot=false）** ·
**self_review = true** → §6 · **owner_review = true** → §7 · **依赖** `WIRE-01`

## 1. 装载清单

卡面 QUEUE-01 · `docs/blocked/NET-03-CARD-PREMISE-STALE.md` ·
`DECISIONS-v04.md#DEC-033` · `flint/jobs/worker_main.py` 全文 ·
`flint/jobs/gate1.py` 的 `Gate1Deps` / `build_live_deps` / `run_gate1` 头 ·
`flint/jobs/runner.py#PgJobRunner.submit` · `flint/testing/replay.py#HttpReplay` ·
`harness/gate1_live.py` 的 `ScriptedGateProvider` 与 `_run` ·
`tests/v041/test_asm_04.py` 的 worker 起法。约 20k tokens，预算 40k 以内。

## 2. 结论：这条链路本来就是通的，缺的确实只是注入

`DEC-033②` 的判断经实测**成立**。注入 `gate1_deps` 之后，整条链路一次跑通：

```
PgJobRunner.submit  → jobs 表写下 queued 那一行
                    → arq 队列（arq:queue01 里出现 arq-job-queue01-gate1）
build_worker(burst) → 消费 1 条，失败 0 条，arq 记下结果
run_gate1           → plan:done → retrieve:done → judge:done → validate:done
落盘                → snapshots 里 docs / verdict 各一份，doc 是真 arxiv 论文
全程                → 零真实出网（respx 零路由罩着，router.calls 为空）
```

**没有改动 `flint/jobs/` 一个字**。卡上把它列进 outputs 是留着以防要修，
实测不需要——**NEVER 为了「用掉 outputs」去改一个没坏的东西**。

## 3. 判据的两半：通了，与不注入时怎么坏

| 半 | 判据 |
|---|---|
| **注入了** | `test_the_work_actually_went_through_the_queue`（队列侧证据）· `test_the_job_row_exists_and_finished` · `test_the_four_steps_all_ran` · `test_the_verdict_landed_and_cites_retrieved_docs` |
| **没注入** | `test_without_the_injection_the_job_fails_and_says_what_is_missing`：作业以 `failed` 收场，错误里点名 `WorkerDeps.gate1_deps`，且**没有判定落盘** |

第二半是第一半的阴性对照：只有第一半的话，「链路通了」可能是
「这条链路对任何 deps 都通」换来的。

另一条界线也钉住了（`test_the_missing_injection_is_not_an_assembly_time_error`）：
缺 `gate1_deps` **不该**让 worker 起不来。`compose_provider` 是装配期硬前提，
`gate1_deps` 不是——demo 面本来就不接真实源，把它也做成硬前提，连报告都跑不了。

## 4. 两处实测撞出来的东西

**① 只调 enqueue hook 不够，那样跳过的是「提交」这一段。**
第一版直接调 `build_enqueue_hook`，结果没注入那半**连一行 `failed` 都写不出来**：
`jobs` 表里根本没有那一行（它是 `PgJobRunner.submit` 写的），
而 `make_mark_failed` 是 `UPDATE`——没有行可更新，于是失败只活在 worker 的日志里。
从 API/前端看过去，那条作业与「从没提交过」**一模一样**。
改成走生产的提交面之后，队列侧与库侧都对得上。

**② 同一个 `job_id` 第二次提交会静默地什么都不做。**
`build_enqueue_hook` 用 `_job_id=f"arq-{job_id}"` 按作业 id 去重
（原话「同一作业重复提交在队列层就被去重，NEVER 跑两遍」）。
这是生产上要的行为，但它让第二次跑变成：队列空、worker 空转退出、
`jobs` 表零行——**那个「什么都没发生」与「链路断了」长得一模一样**。
判据里显式地忘掉队列侧那几个键，**NEVER 靠换一个随机 id 绕过去**
（绕过去就再也测不到去重这件事）。

另有两处小实测：`arq` 0.28 的队列是**有序集合**（`llen` 撞 `WRONGTYPE`，要用 `zcard`）；
队列里的条数会被上一轮的残留搅浑，所以判据判的是**我们这条在不在**（`zscore`），
数目只做下界。

## 5. 回放护栏（acceptance③）

两层：

1. **搜索客户端**由 `HttpReplay(FIXTURE, "replay")` 造——它内部是
   `respx.Router(assert_all_mocked=True)`：**录制里没有的请求当场抛 `ReplayMiss`**；
2. **整趟罩一层零路由的 `respx.mock`**：回放客户端走 `httpx.MockTransport`
   碰不到它，而任何别处新造的、走真实传输的 httpx 客户端都会撞上并抛。
   跑完断言 `router.calls == []`——**一次都没有人试图出网**。

外加 `tools/check_no_live_network.py`（NET-01 守门器）对本文件实跑 exit 0。

**回退条款没有触发**：回放下**没有**暴露出任何真实网络请求。
卡面写的是「若暴露出真实网络请求，立即停下走 `docs/blocked/` 并把该链路退回红线卡」——
本卡没有走到那一步，如实记录。`test_nothing_reaches_the_real_network` 是那条条款的
常驻探测器：它一旦红，下一个人要做的不是改判据，是去开单。

## 6. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_gate1_via_queue.py -q → 9 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3897 passed（HYG-02 收卡时 3888，本卡 +9）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 缺的是注入而非网络授权 | `test_without_the_injection_the_job_fails_and_says_what_is_missing`、`test_the_missing_injection_is_not_an_assembly_time_error` |
| ② 链路逐段跑通（提交→jobs 表→worker 消费→gate1→落盘） | `test_the_work_actually_went_through_the_queue`（**队列侧证据**：zscore 里有我们这条、`worker.jobs_complete == 1`、arq 记下结果）、`test_the_job_row_exists_and_finished`、`test_the_four_steps_all_ran`（**只判 `state == done` 不够：什么都没做就置 done 的路径也是 done**）、`test_the_verdict_landed_and_cites_retrieved_docs` |
| ③ respx 护栏不得绕过，零真实出网 | `ran` fixture 里的零路由 respx + `test_nothing_reaches_the_real_network`（真发一个录制里没有的请求）+ `test_the_repo_guard_still_passes_on_this_file` |
| ④ NET-03 台账行 | `test_net03_is_recorded_as_skipped_by_owner`（末态是 `skipped_by_owner`、理由里有 `DEC-033` 与 payoff、且记着「NEVER 按已登记未执行写判据」那句） |

**② 改既有文件 0 处**（`flint/jobs/` 未动，见 §2）；新增 `tests/v041/test_gate1_via_queue.py`。
`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；未新增依赖（`arq` / `respx` 本来就在 lock 里）。

**③ 变异考 5 咬住 + 两个假变异认出来 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 缺件时静默跳过（不抛 `HandlerDepsMissing`） | 红 |
| ②b 提交不推 arq（只写 `jobs` 行） | 红（5 条） |
| ②c **量具不动，改成手工执行**（队列里那条被抽走） | 红 |
| ③ 判定不落盘（judge 步骤被跳过） | 红 |
| ⑤ 回放护栏被换成另一个传输 | 红 |
| ⑥ 假变异对照：只改一句注释 | 全绿 |

**②的第一版与第二版都是假变异，值得记下来**：

- 第一版「直接调 handler」**之后仍然起了 worker** —— 队列那一段照跑，
  被判的性质根本没被改掉；
- 第二版干脆**把队列证据伪造成字面量返回** —— 那是改量具，不是改被测物。
  测试防不住自己的量具说谎（同 `GAUGE-09` ①「改了生成器不重跑」那一类）。

真正有效的形态是 ②c：**量具原样保留，只把「谁执行」换掉**。它红了，
说明「经队列」这件事真的在判据之下。
**这一轮的教训是：变异要改被测物，NEVER 改量具或加冗余。**

**④** 装载约 20k tokens；**⑤** 禁用词六词 0 命中。

## 7. owner_review

两处请你看：

1. **本卡没有改 `flint/jobs/` 一个字**。卡上把它列进 outputs，是预期这条链路要修点什么；
   实测不用——`DEC-033②` 的判断（缺的只是注入）完全成立。
   若你认为「outputs 列了就该有产出」，那要的是另一件事：
   **把注入接进 `harness/run_worker.py`**（那是本机 worker 进程的装配面，
   现在 `build_deps()` 不给 `gate1_deps`，所以本机 demo 面提交 gate1 作业会失败）。
   那个文件**不在本卡 outputs 内**，且它要决定 demo 面到底走不走真实源——
   属 §五.6 的红线邻区，我没有自作主张。见 §8-1。
2. **回退条款没触发**：回放下零真实出网。这一条我按「如实记录没走到那一步」写，
   NEVER 写成「已验证不会出网」——**我验的是这一趟没有，不是它永远不会**。

## 8. 登记未做

1. **本机 worker 进程仍然跑不了 gate1 作业**。`harness/run_worker.py#build_deps()`
   不注入 `gate1_deps`（它只给 `compose_provider`）。判据证明了链路通，
   但那是**测试里的装配**；本机 demo 面提交一条 gate1 作业，仍会以
   `failed: WorkerDeps.gate1_deps 没注入` 收场。
   接它要先定「demo 面走不走真实源」——见 §7-1。
2. **只跑了 scripted 那一路**。`fixtures/gate1_live/` 下还有 `qwen/`
   （真实 qwen 判官 + 真实检索的双录制）。本卡用 scripted 是因为它零 LLM 网、确定；
   qwen 那路的回放没接进队列判据。
3. **判定内容没有逐字比对**。判据判的是「落盘了、引的是真 arxiv 论文、四步都跑了」，
   **没有**把 verdict 的字段与 `assets/gate1_live/scripted.json` 那份基线逐字对齐——
   那会把本卡与判官口径绑死，而判官口径是 `JUDGE-*` 那组卡的面。
4. **`arq` 的重试面没测**。`build_worker` 用 `max_tries=1`（原话「续跑由 job_steps
   断点负责，NEVER 靠 arq 盲重试」）。断点续跑是 `run_gate1` 的 `crash_after` 那条路，
   本卡没有走。
