# JUDGE-05 · 全仓口径对齐总账

**卡** `tasks-v041-b2.json#JUDGE-05` · **cycles 2** · **owner_review = true** → 见 §7
**依赖** JUDGE-03（verified）

## 1. 装载清单

卡面 JUDGE-05 · `assets/` 全目录扫描（15 份带判官痕迹的 JSON 逐个打开看结构）·
`assets/goldcases/goldcases.json` 与 `golddocs/golddocs.json` 的 `generated_by` 字段 ·
`assets/topic_caliber/*.json` 的键集 · `assets/heldout_questions.yaml`（只读，取题目表）·
`docs/M4-出口报告.md#6.1`（自评为何不可比的既有结论）· `eval/` 各模块的常量 ·
`harness/judge_alignment.py`。约 9k tokens。

## 2. 顺序（§4.2）

测试先落盘先跑红（14 failed / 4 passed）→ 建机读总账 → 18 条里 14 通过 →
重判三份 → 渲染文档 → 18 passed → 变异考补判后仍 18 passed。

## 3. 扫出来是什么样

全仓 **31 项**：`usable=19` · `rejudge=9` · `historical=3`。

**最要紧的一条发现：「判官判出来的数」比看上去少得多。**
31 项里真正有判官参与的只有 12 项，其余 19 项是：

- **构造件**：`goldcases.json` / `golddocs.json` 是 fixture 脚本生成的**期望值**——
  它们是**基准本身**，不是谁判出来的。把它们归进「需重判」，
  重判出来的东西会**顶掉本来当基准用的那份**。这是本卡最容易做错的地方，
  单列了一条判据（`test_the_constructed_goldsets_are_not_called_judge_output`）；
- **确定性工具产物**：`gauge_map.json`（重跑即重现）、`gate1_live/scripted.json`
  （写死的剧本，`verdict` 不是判定结论）；
- **生成侧计数**：`topic_caliber/*.json` 记的是 `generations` / `schema_misses` /
  `cost_usd`，没有判官参与。

## 4. 重判了三份（花 $0.104）

| 产物 | DeepSeek 重判 |
|---|---|
| `claude-sonnet-5.thinkoff-repairoff` | 146/254 = **0.5748**（判词坏 4） |
| `qwen3_30b` | 72/258 = **0.2791** |
| `v3_no_spec/gemma4_31b` | 70/258 = **0.2713** |

**为什么只重判这三份**：另外六份「需重判」的 JUDGE-03 已经做过了——
总账里**指过去**（`realigned_to` 指向 `deepseek_judge/`），
**不复制一份到 `deepseek_realign/`**：复制就有了第二份真相。

**样本是从「组稿产物 × 题库」重建的**，不是从旧判定文件里抄的——
那三份没有对应的 `unified_judge` 记录。重建出来 258 题，与旧跑批记的 258 逐数对上。

## 5. 两条省钱与一条补不回来

1. **两份产物是逐字节重复的**：`qwen3_30b.v3-backup.json` 与
   `v3_no_spec/qwen3_30b.json` 的组稿产物与 `qwen3_30b.json` **完全相同**
   （`v3_no_spec` 这个变体对该模型没产生任何差异）。先按内容指纹去重再重判，
   **省下两次 258 条**。总账里用 `duplicate_of` 标出来，并有判据要求
   「重复件必须被标出来」；
2. **`gemma4_26b.json` 里没有 compositions**——被判的东西已经不在盘上，
   **任何重判都做不到**，只能作历史。这一条写进了 `why_not`。

## 6. 改既有文件：一处

**`tests/v041/test_answer_line_scope.py`** 的 `ALLOWED_CODE_REFS`：

- **改前**：三条（定义处、既有范围守卫、它自己）。
- **改后**：加第四条 `tests/v041/test_caliber_realign.py`，写明角色。
- **为什么非改不可**：本卡的「没动阈值」判据要读 `CHECK_ANSWER_LINE` 的当前值，
  而那条守卫要求**代码面**引用它的文件逐个报到（名单是闭集）。
  不加就红——**而它红得对**：新增一个引用点本来就该说清它属于哪一面。
  两条守的是同一件事的两半：那条守**范围**（别把结构考核面当生产口径），
  这条守**值**（别顺手改 0.90）。

## 7. 变异考：十四个，一个先活了下来

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 漏掉一份产物不归类 | acceptance①（不许漏项） | **2 failed** ✓ |
| ② 归类越界（第四类） | 三类闭集 | **2 failed** ✓ |
| ③ 不写判官是谁 | acceptance④ | **2 failed** ✓ |
| ④ 说不可比却不说为什么 | acceptance④ | **1 failed** ✓ |
| ⑤ 新值落回旧目录 | acceptance③ | **2 failed** ✓ |
| ⑥ 把构造件当判定结论去重判 | §3 那条区分 | **3 failed** ✓ |
| ⑦ 重复件不标出来 | §5-1 | **1 failed** ✓ |
| ⑧ 补不回来的那份标成还能用 | §5-2 | **2 failed** ✓ |
| ⑨ 还能用的不写理由 | acceptance② | **1 failed** ✓ |
| ⑩ 总账里写盘上没有的项 | 反向 | **2 failed** ✓ |
| ⑪ 文档少一节 | acceptance② | **1 failed** ✓ |
| ⑫ 文档漏列一项 | acceptance② | **1 failed** ✓ |
| ⑬ 文档与机读条数对不上 | 一致性 | **18 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑭ 小节标题处条数改错 | 一致性 | **1 failed** ✓（补判顺带） |

**⑬ 为什么能活**：条数在文档里写了**两处**（摘要一次、小节标题一次），
判据是「文档里出现 `historical=3` 这个串」——改掉摘要那处，小节标题那处顶上。
**两处互相矛盾比只写一处更糟**：读的人不知道该信哪个。
改成把所有 `{类}=数` 都找出来，**每一处都要与机读面一致**。
本仓第十九次同型（判据只判「有一处对」）。

十四次变异后两个产物文件的 sha256 与变异前逐位相同。

## 8. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_caliber_realign.py -q → 18 passed
全局门: ruff check . --no-cache → All checks passed!
        pytest -q → 2896 passed
        tools/gauge_map.py → 查不到尺子 0
```

**① acceptance 映射**

| acceptance | 测试 |
|---|---|
| ① 先扫出全仓所有判官判出来的数 | `test_the_index_covers_every_artifact_on_disk`（**盘上有的总账里都有**——反向判挡不住漏项）、`test_the_index_lists_nothing_that_is_not_there` |
| ② 逐项判三类并落成总账 | `test_every_entry_has_a_class_from_the_closed_set`、`test_a_usable_entry_explains_why_it_is_still_usable`、`test_the_constructed_goldsets_are_not_called_judge_output`、`test_the_document_has_one_section_per_class`、`test_the_document_lists_every_entry`、`test_the_document_and_the_index_agree_on_the_counts` |
| ③ 第②类用 DeepSeek 重判、旧值原样保留 | `test_every_rejudge_entry_has_a_new_artifact`（**没有新产物的「需重判」是一句待办，不是一次对齐**）、`test_the_new_artifacts_never_overwrite_the_old_ones`、`test_byte_identical_duplicates_are_marked_as_such` |
| ④ 每项标判官/时间/题库/可不可比 + 说清为什么不可比 | `test_every_entry_says_who_judged_and_when`、`test_every_entry_states_comparability_with_a_reason`、`test_a_historical_entry_never_pretends_to_be_comparable` |
| ⑤ NEVER 改阈值 | `test_no_threshold_moved`（4 例：`CHECK_ANSWER_LINE` / `THETA_REL` / `Z_LINE_INITIAL` / `EXIT_LINE`）——**钉在值上而不是「本卡没改过文件」上**：后者对「别的卡顺手改了」无感 |

**② 无冻结件偏离**：`contracts/`、`flint/domain/` 未触碰；
`assets/heldout_questions.yaml` **只读**（重建样本用它的题目表，一个字节没写）；
旧产物目录一个字节没动；零新增依赖。

**③ 禁用词**：产物文档 + 本 trace 六词 0 命中。

**④ 复用**：判词与解析来自 JUDGE-02 的 `harness/judge_alignment.py`
（**与 JUDGE-03 同一套判词**——换一套判词，这两张卡的数就不可比了）；
provider 与账本来自 JUDGE-01。

**⑤ 装载预算**：约 9k tokens。

## 9. owner_review：三件要 owner 拍板的

1. **`qwen3_30b` 与 `v3_no_spec/gemma4_31b` 的新值只有 0.27~0.28**，
   比新基线里最低的 qwen3.6:27b（0.4535）还低一大截。这**符合预期**
   （它们是更早的模型 / 更早的组稿口径），但要不要把它们并进新基线那张表，
   是 owner 的判断——我**没有并**，它们留在总账的「需重判」一节里各自成行。
2. **`claude-sonnet-5.thinkoff-repairoff` 判出 0.5748**，略高于主跑批的 0.5625。
   两者是**同一模型的两个配置**（thinking/repair 开关不同），
   在同一把新尺子下这个差是可比的——但 254 vs 256 的分母不同（判词坏的条数不同），
   **差 0.012 是否显著我没算**。
3. **总账里 19 项「还能用」中有 15 项是「根本没有判官」**。
   若 owner 认为这类不该进这张总账（它本来是「判官判出来的数」的清单），
   可以把它们移出去——但我的意见是**留着**：正因为它们看起来像分数，
   才需要一行字说清「这不是判出来的」。

## 10. 登记未做

1. **没有重判 `unified_judge` 那三份**：JUDGE-03 已经做过，总账里指过去。
2. **没有算显著性**（见 §9-2）。
3. **`eval/` 各模块本身没有跑批结论可对齐**：它们是确定性判定器（纯函数），
   盘上没有它们的历史结论文件——所以总账里没有 `eval/*.py` 的条目。
   卡面把它们列进了 inputs，我逐个看过，**确认没有需要对齐的存量数**。
4. **`prod_caliber/` 下还有 `answer_run_*.stdout.json` 等日志件没进总账**：
   它们是跑批的 stdout 转储，不是产物；扫描按「JSON 里有判官痕迹的键」取，
   它们没有那些键。若 owner 认为日志也该归类，扫描面要放宽——那会把
   十几份日志拉进来，我按「产物 vs 日志」的分界把它们排除了。
