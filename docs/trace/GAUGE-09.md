# GAUGE-09 · 第 2 批 89 张卡的 acceptance ↔ 尺子专项清点

**卡** `docs/steward/tasks-v041-b3.json#GAUGE-09` · **cycles 2** ·
**self_review = true** → §5 · **owner_review = true** → §6 · **依赖** 无

## 1. 装载清单

卡面 GAUGE-09 · `tools/gauge_map.py` 全文（约 420 行，含它的口径 docstring）·
`docs/trace/GAUGE-02.md` · `docs/steward/tasks-v041-b2.json` 的 89 张卡 ·
`tests/v041/test_caliber_realign.py` 的判官产物扫描段。约 15k tokens，预算 40k 以内。

## 2. 用**同一把**尺子量两批，不是复制一份工具

卡面说「照 `GAUGE-02` 的同一套办法」。复制一份工具是最省事的做法，
但**复制出来的第二份从复制那一刻起就开始各走各的**——
而这张卡的全部价值在于**两批的数能比**。两把尺子量出来的数没法比。

所以 `tools/gauge_map.py` 加了 `--batch`（`v04` / `b2`），两批共用同一套归属规则：
只认 `verify_cmd` 与 `outputs`、目标必须在磁盘上真解析得到、推不出的一律进第三类。

## 3. 实测

```
89 张卡 / 363 条 acceptance
  在门内            304
  有尺子但不在门内   55   ← **全部是 vitest**
  查不到尺子          4   ← **全部来自 NET-03**
  弱关联             44
```

**门外那 55 条全部是 vitest**：全局门是 `ruff` / `mypy` / `pytest -q` 三条命令
（`worker.md` §5 逐字），前端 `npm test` 要单独跑。
**这不是贬低前端测试**——是陈述一个事实：合并时跑的那三条命令碰不到它们，
忘了单独跑就没人会知道。

## 4. 那 4 条「查不到尺子」不是缺口

**全部来自 `NET-03`**：那张卡按 `DEC-033①` 记了 `skipped_by_owner`
（真实源检索 owner 2026-07-31 payoff 已执行并录制），
**它的测试文件从来没写过**，所以 `verify_cmd` 里的尺子在磁盘上解析不出来。

这是清点器**如实报出的实况**，不是它漏了什么。
卡面 acceptance② 要的正是这个：「或逐条列名并说明为什么守不住——
NEVER 用『已覆盖』一句话带过」。判据判**等值**：
多一条要有人来确认（那可能是真缺口），少一条说明 `NET-03` 被补了测试。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_gauge_map_b2.py -q → 12 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3842 passed（GAUGE-08 收卡时 3830，本卡 +12）
            python tools/gauge_map.py --check --batch b2 → exit 0
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 照同一套办法逐条回答 | `test_the_same_tool_measures_both_batches`（**同一把尺子**，且两批输出各自落盘）、`test_every_card_and_every_acceptance_is_accounted_for`（89 卡 × 每条都有一行，一条都不许漏） |
| ② 查不到的为 0 或逐条列名说明 | `test_the_no_gauge_entries_are_exactly_the_ones_we_can_explain`（判等值）、`test_the_report_names_them_instead_of_saying_covered`（报告里不许出现「已覆盖」） |
| ③ 每条指到具体测试函数名或工具名 | `test_every_entry_points_at_a_named_gauge_or_says_why_not`、`test_a_named_gauge_actually_exists_on_disk`（**F-08 的形态**：过滤器谁都匹配不上却报绿） |
| （自加） | `test_the_out_of_gate_entries_are_all_vitest`、`test_the_counts_add_up`（三类之和 == 总数，不许有第四种落法）、`test_the_weak_link_table_is_separate_from_the_three_way_split`（弱关联是**正交信号**，混进三分类就分不开机械判定与启发式判定）、落盘不许过期三条 |

**② 改既有文件三处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `tools/gauge_map.py` | 加 `BATCHES` 与 `--batch`；`_report` 按 `generated_from` 说清量的是哪一批；写回路径改用 `paths` 里那两个 | **卡上 outputs 要 `assets/gauge_map.json`**，而同一套办法要能对两批跑。写回路径那处是**实测撞出来的**：先前仍写死成模块级常量，`--batch b2` 差点把第 2 批的结果盖到 v04 的文件上——**而两份报告的标题都写着自己是对的** |
| `tests/v041/test_caliber_realign.py` | 判官产物扫描从「文件里出现 `"rate"` 等词」→「那几个词出现在**键位**上（`"rate":`）」 | 本卡新落盘的 `gauge_map_b2.json` 里有 `"rate"`——它只是 `Z-01` 那条 acceptance 原文里被抽出来的一个**标识符**（「任务一次通过率」那句），那份文件一个判官数都没有。**收窄后 15 份真判官产物照样认得出**（实测） |
| `assets/gauge_map.json` · `docs/尺子清点-v041.md` | 重生成（口径未变，只是报告头改了措辞） | 它们自带「落盘过期就红」的判据 |

新增：`assets/gauge_map_b2.json` · `docs/尺子清点-v041-b2.md` ·
`tests/v041/test_gauge_map_b2.py`（卡上 outputs）。

**③ 变异考 4 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 写路径写死回模块常量（**且真跑一次**） | 红 |
| ② 落盘副本被手改（`no_gauge` 抹成 0） | 红 |
| ③ 漏掉一条 acceptance | 红 |
| ④ b2 与 v04 共用同一份输出路径 | 红 |
| ⑤ 假变异对照：只改一句注释 | 全绿 |

**① 第一轮是假变异**：只改工具不重跑，落盘文件没变，判据当然不该红。
补上「改完真跑一次 `--batch b2`」才验到——**改了生成器不重跑，等于什么都没测**。

**④** 装载约 15k tokens；**⑤** 禁用词六词 0 命中。

## 6. owner_review

一处要你看：**门外 55 条全部是 vitest**，占第 2 批 acceptance 的 15%。

它们不是没尺子——是那把尺子不在合并时跑的三条命令里。本批我每次收卡都手动
跑了 `npm test`，但那是**纪律，不是机制**：

- 要么把 `npm test -- --run` 加进全局门（代价：每次合并多跑约 20 秒，
  且需要 node 环境恒在）；
- 要么维持现状，并接受「忘了单独跑就没人会知道」这个风险。

**本卡没有替你决定**——改全局门口径是 `worker.md` §5 的事，超出卡面。

## 7. 登记未做

1. **弱关联 44 条没有逐条看**。它是启发式信号（acceptance 里提到的标识符
   在尺子文件正文里一次都没出现），**不是判决**。清单已落盘，
   要不要逐条看是 owner 的取舍。
2. **`GAUGE-03` 那一类仍看不见**：尺子在、也在门里、但施加的压力够不到被测机制
   （`F-05` 的形态）。本工具是**静态归属清点**，NEVER 声称能查出这一类——
   这句话是 `GAUGE-02` 写的，本卡照抄不改。
3. **第 3 批自己没清点**。同一套办法再加一个 `b3` 条目即可，
   但 b3 还没跑完（本卡收卡时 15/25），现在量出来的数明天就过期。
