# CAL-01 · 金标集标注（DeepSeek 代判 θ_rel / δ / 血缘）

**卡** `tasks-v041-b2.json#CAL-01` · **cycles 2** · **owner_review = false**
**依赖** JUDGE-02（verified）· BL-05（verified）

## 1. 装载清单

卡面 CAL-01 · `harness/gold_collect.py` 全文（「只采不判」「可复现」「标注槽留白」三条口径）·
`CLAUDE.md#S4`（θ_rel / δ 是未决项，调参归 owner）·
`docs/blocked/LINEAGE-GOLD-REPLAY-MISSING.md`（血缘金标与 30 天回放的关系）·
`assets/labels.yaml` 结构 · postgres `flint` 库的 clusters / keywords / evidence_cards /
lineage_audit / trend_items_raw 五张表实查 · `flint/llm/deepseek.py`。约 10k tokens。

## 2. 顺序（§4.2）

测试先落盘先跑红（`ImportError: harness.gold_annotate`）→ 模块 → 24 passed / 8 skipped →
抽样 → 标注 → **两次发现抽样退化并重做**（见 §4）→ 38 passed → 变异考补判后 38 passed。

## 3. 产出

`assets/goldsets/`：三份 JSONL（各 60 条）+ `rubrics/`（三份判准）+ `manifest.json`。

| 类 | 标签分布 | 说明 |
|---|---|---|
| `relevance`（θ_rel 面） | 18 relevant / 42 irrelevant | 两类都有，可用于调参 |
| `same_topic`（δ 面） | 14 same / 46 different | 两类都有 |
| `lineage`（血缘面） | **60 correct / 0 wrong**（60 簇 ≥ 50） | **这个 60/60 是真的，但它说明的是语料，不是系统**，见 §5 |

**花费**：$0.0099 + $0.0065 + $0.0063 = **$0.023**（三轮共 360 次调用，其中两轮是重做）。

## 4. 抽样退化了两次，两次都是「标注器在判我的提示词」

**第一次**：`relevance` 的正例本想取「同簇的另一个关键词」——实查发现
**193 个簇每个只有 1 个关键词**（193/193），正例构造出来是「簇名 × 它自己」，
字面完全相同。改成「簇名 × 词面最近邻关键词」，结果 **60 条全判 irrelevant**：
簇名多是中文占位（`热搜话题55`）、关键词表多是英文，两边零词面重叠，
**最近邻等于随便挑一个**。第三版把两侧都取关键词词表（`quantum` × `quantum computing`、
`admet` × `ai admet`），才有了 18 个正例。

**第二次**（更值得记）：`lineage` 第一版每簇取首个事件——而首个事件几乎全是簇出现那天的
`new`，**60 条全判 correct，从没考过 continued**。按事件类型分层后，
15 条 `continued` **全被判 wrong**，理由都是「无前一天的簇却判 continued」。
一看就不对：我从 event 里取 `previous_cluster_id` / `parent_cluster_id`，
而**那两个键根本不存在**（event 只有 `kind` / `cluster_id` / `keyword_ids`）。
于是每条 continued 都被喂进「前一天的簇 =（无）」，标注器照判准如实回答——
**它在判我的提示词，不是在判系统**。

真相是 `continued` 表示**同一个 cluster_id 延续到第二天**，没有「另一个簇」；
可判的是**挂在这个簇下的关键词在两天之间有没有漂移**。按这个重建 item、
同步改判准，才得到 §3 那个结果。

**这 15 条如果不看就收下，会以「血缘 25% 判错」的样子进入 CAL-02。**

## 5. 60/60 correct 说明的是语料，不是系统

重建之后每条 `continued` 的两天关键词**逐字相同**（`热搜话题42` / `热搜话题42`）——
demo 库里**没有任何一次簇漂移**。所以这批标注**判不出血缘的错**：
不是系统没错，是**这批数据里没有可错的地方**。

这与 `docs/blocked/LINEAGE-GOLD-REPLAY-MISSING.md` 是同一件事的两面：
那张单说的是「30 天回放没灌库，血缘准确率评不了」，本卡实测补一句——
**即使只看现有 7 天，语料里也没有漂移样本**。两者都要等 owner 的回放决定
（§4-3：NEVER 自行灌库）。

## 6. 三条本卡自己钉住的纪律

1. **判准先落盘再标注**：`annotate()` 核盘上判准与内置判准的指纹，对不上直接抛错。
   「判准写在提示词里」跑完就没了，**落了盘才是下一个人复核这批标注的唯一依据**；
2. **模块里一个浮点常量都没有**（AST 扫着）：内置阈值，标出来的金标就带着当前阈值的
   偏见，用它去调那个阈值等于**拿答案去验算答案**（`gold_collect.py` 的原话）；
   另有一条判据禁止本模块碰调参通道（`load_tuning` / `TUNING_KEYS` / `THETA_REL`）；
3. **可复现分两半**：序列化确定（同一批两次落盘逐字节一致）+ **两轮差异逐条报出**
   （`diff_rounds`）。LLM 不保证复现，所以真正要保的是
   **「不一样时看得见」**——静默覆盖会让「模型这次判得不一样」看起来像「一直就是这样」。

## 7. 变异考：十一个，两个先活了下来

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 判准没落盘也照标 | acceptance② | **1 failed** ✓ |
| ② 盘上判准被改过也照标 | acceptance② | **1 failed** ✓ |
| ③ 越界标签直接收下 | 闭集 | **3 failed** ✓ |
| ④ 判词坏了顶一个标签 | 闭集 | **3 failed** ✓ |
| ⑤ 标注不带被标的东西 | 自包含 | **38 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑥ 判准指纹写死 | acceptance③ | **1 failed** ✓ |
| ⑦ 序列化不定序 | 可复现 | **1 failed** ✓ |
| ⑧ 只报增删不报改判 | 可复现 | **1 failed** ✓ |
| ⑨ 只在一轮出现的不报 | 可复现 | **1 failed** ✓ |
| ⑩ 用途标签不带类别 | 记账归因 | **1 failed** ✓ |

**⑤ 为什么能活**：盘上那份产物有同名判据（`每行自带被标的是什么`），
但它读的是**已落盘的文件**——改 `annotate()` 不会让它红。
判据落在产物上，改的是代码，两边不相交。补了一条**单元级**断言：
`annotate()` 返回的每条都要带 `payload`。
**「产物对」与「代码对」是两件事**，本卡撞上的这一次尤其明显。

十一次变异后 `harness/gold_annotate.py` 的 sha256 与变异前逐位相同。

## 8. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_gold_annotate.py -q → 38 passed
全局门: ruff check . --no-cache → All checks passed!
        pytest -q → 2934 passed
```

**① acceptance 映射**

| acceptance | 测试 |
|---|---|
| ① 逐条标注三类（θ_rel / δ / 血缘 ≥50 簇） | `test_three_kinds_each_have_a_rubric`、`test_the_goldset_labels_are_all_in_the_closed_set`（3 例）、`test_the_lineage_goldset_has_at_least_fifty_clusters`（实为 60 簇） |
| ② 每轮标注前判准先落盘 | `test_the_rubrics_land_on_disk_before_any_annotation`、`test_annotating_without_the_rubric_on_disk_is_refused`、`test_a_tampered_rubric_is_caught`、`test_the_stored_rubric_matches_the_one_in_force`（3 例：**判准改了而标注没重标 → 红**） |
| ③ 带判官标识与时间戳、可复现 | `test_every_annotation_carries_judge_time_and_rubric`（含 payload）、`test_every_row_carries_its_provenance`、`test_every_row_carries_what_was_annotated`、`test_serialisation_is_byte_identical_twice`、`test_two_rounds_that_differ_are_reported_item_by_item`、`test_identical_rounds_report_no_change`（阴性对照）、`test_an_item_only_in_one_round_is_reported_too` |
| ④ NEVER 直接改阈值 | `test_the_module_holds_no_threshold_constant`（AST 扫浮点字面量）、`test_the_module_never_writes_a_threshold_file` |

抽样可复现那一条：`test_the_sampling_method_is_written_down`——
**样本怎么挑的必须落盘**，不写的话这批金标复现不了，只能重挑一次。

**② 无冻结件偏离**：`contracts/`、`flint/domain/` 未触碰；
`assets/heldout_questions.yaml` 未读写；`assets/labels.yaml` 只读了结构、**一个字节没改**；
数据库**只读**（五张表全是 SELECT）；零新增依赖。

**③ 禁用词**：两个产物文件 + 本 trace 六词 0 命中。

**④ 复用**：provider 与账本走 JUDGE-01；「判准 + 被标的东西一起进判词」的形状
照 JUDGE-02 的判词；确定性序列化照 `gold_collect.py#to_jsonl` 的既有写法
（固定键序 / 编码 / 行尾）。

**⑤ 装载预算**：约 10k tokens。

## 9. 登记未做

1. **同一批数据没有连跑 3 轮**（acceptance② 提到「连跑 3 轮以上要说明为什么」）：
   本卡每类只标了 1 轮。`diff_rounds` 是为多轮准备的机制，**但没有真跑第二轮**——
   跑第二轮的价值是量「同判准下模型自身的稳定性」，那是 CAL-02 要用的数，
   本卡按「便宜不是多跑的理由」的口径没跑。
2. **血缘这批判不出错**（§5）：等 owner 的 30 天回放决定。
3. **relevance 与 same_topic 的样本对空间重叠**：两者现在都取关键词词表配对，
   因为 `docs` 表只有 1 行——**没有独立的文档语料可用来判「证据与主题相关吗」**。
   两份判准不同（一个问「同一件事吗」、一个问「能不能并成一条热点」），
   但被标的对基本同源。要分开，得先有真实文档语料。
4. **判准是我写的，不是 owner 定的**：三份判准里的取舍（「拿不准时选 irrelevant」
   这类）会直接影响标出来的分布。owner 若不认这个取舍，改判准后**必须重标**——
   有判据守着（`test_the_stored_rubric_matches_the_one_in_force`）。
5. **抽样脚本在 scratchpad，没进仓**：它是一次性取证入口；可复现性由
   `manifest.json` 里写死的抽样口径保证（零随机、固定切片）。
