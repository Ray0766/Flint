# JUDGE-03 · 用 DeepSeek 重判旧基线，得一套自洽可比的新基线

**卡** `tasks-v041-b2.json#JUDGE-03` · **cycles 1** · **owner_review = true** → 见 §7
**依赖** JUDGE-01（verified）

## 1. 装载清单

卡面 JUDGE-03 · `docs/M4-出口报告.md#6.2`（旧基线三个数与「统一判官」口径）·
`assets/prod_caliber/unified_judge/*.json` ×3（258 条录制判定）·
`assets/prod_caliber/{claude-sonnet-5,gemma4_31b,qwen3.6_27b}.json`（12 份组稿产物的逐节正文）·
`harness/judge_alignment.py`（JUDGE-02 的 `load_items` / `build_judge_prompt` / `parse_verdict`）·
`flint/llm/deepseek.py`。约 8k tokens。

## 2. 顺序（§4.2）

测试先落盘先跑红（24 failed / 4 passed，缺全部新产物与文档）→ 重判跑批 →
文档 → 28 passed → 变异考补判后仍 28 passed。

## 3. 结果

| 被判产出 | 新（DeepSeek） | 旧（claude-sonnet-5） |
|---|---|---|
| claude-sonnet-5 | 144/256 = **0.5625**（判词坏 2） | 0.434 |
| gemma4:31b | 118/258 = **0.4574** | 0.395 |
| qwen3.6:27b | 117/258 = **0.4535** | 0.357 |

（**这张表只出现在 trace 里**——产物文档 `docs/新基线-v041.md` 把两套数分两节写，
且有一条判据钉着「没有任何一行同时出现新旧两套数」。trace 是给执行留痕的，
产物是给人读的，两者的读者不同。）

**排序不变，但二三名之间的结论要改**：旧尺子下 gemma4 比 qwen3.6 高 3.8 个百分点，
新尺子下只高 **0.4** 个百分点（118 vs 117，**一条之差**）——在这个样本量下
说不上谁更好。M4 出口报告那句「真实排名」在新尺子下**头名不变，二三名不再可靠**。

**为什么新数普遍高十几个百分点**：不是产物变好了（本卡**只重判、不重跑组稿**，
组稿产物的 sha256 记在每份新产物里、测试逐份核），而是 DeepSeek 的判准更宽松——
JUDGE-02 的分歧清单已经指出它在「叙述体里能不能推出清单」这类题上更松。

## 4. 跑批经过与一条账的教训

774 条判定分**两个进程**跑完：

1. 第一个进程跑完两家（516 条）后**被 10 分钟超时杀掉**。产物已落盘，
   但**它的用量账本随进程一起没了**（`UsageLedger` 是内存实现）；
2. 第二个进程续跑第三家（258 条），实测 **$0.0315**，命中缓存 43,776 token。

所以文档里 `deepseek_spend_usd: 0.15` **只有 $0.0315 是实测**，其余约 $0.12 是
按第二段单价估的。**这一条在文档里照实写了**——NEVER 把估算写成实测。

**教训**：账在进程里，进程被杀账就没了。用量账本要**落盘（增量写）**才经得起长跑。
已补进 JUDGE-01 的登记未做。

**跑批脚本放在 scratchpad**（不进仓）：它是一次性取证入口，产物才是交付物。
第二次跑时脚本自带「产物已在盘上就跳过」，所以续跑没有重复花钱。

## 5. 变异考：十九个，五个先活了下来（其中两个是近似惰性）

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 旧基线那节没了 | acceptance② | **1 failed** ✓ |
| ② 新基线那节没了 | acceptance③ | **1 failed** ✓ |
| ③ 新旧数并进同一行 | acceptance② | **1 failed** ✓ |
| ④ 不写判官是谁 | acceptance③ | **1 failed** ✓ |
| ⑤ 不写什么时候判的 | acceptance③ | **1 failed** ✓ |
| ⑥ 不写题库版本 | acceptance③ | **1 failed** ✓ |
| ⑦ 花费超预算 | acceptance④ | **1 failed** ✓ |
| ⑧ 排序行删掉 / 写反 | acceptance③ | **28 passed** ✗ → 三轮补判后 **1 failed** ✓ |
| ⑨ 不说明为何不可比 | acceptance③ | **28 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑩ 组稿指纹对不上 | acceptance① | **1 failed** ✓ |
| ⑪ 新旧判官混了 | acceptance② | **1 failed** ✓ |
| ⑫ 分母把坏掉的条数也算进去 | 分母纪律 | **1 failed** ✓ |
| ⑬ 判了答却没抽出原句 | 证据 | **1 failed** ✓ |
| ⑨'' 那节删掉「产物没改」那句 | — | **28 passed** —— 近似惰性：同节里「产物一个字没改」还在 |

**⑧ 花了三轮才钉住，每一轮都是同一类错**：

1. 判据是「文档里有『排序』二字」——那两个字在小标题里也有，删掉排序行照样绿；
2. 改成「有一行含三个模型名与 `>`」——文档里**有两处**写了排序，删一处另一处顶上；
   把第二处写反也不红（判据只看 `stated[0]`）；
3. 改成「**每一行**都要与实测一致」——这下写反会红了，但**两处都删掉仍然绿**：
   因为「旧基线」那节里引用 M4 出口报告的那句排名**也含三个名字与 `>`**，
   把断言喂饱了。**本仓第十七次「判据被引文喂饱」。**

最终判据两条并用：**新基线那一节里**至少有一行写了排序（节内定位）+
**全文任何一行**写的顺序都不能与实测相反（矛盾比缺失更糟）。

**⑨ 为什么能活**：判据是「全文有『判官』且有『尺子』」，两个词在别处都有。
改成**节内判**（`## ` 含「不可横比」的那一节），并要求那节里说清
「产物本身没改」——不写这句，读的人会以为分数差是产物变了。

十九次变异后四个产物文件的 sha256 与变异前逐位相同。

## 6. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_new_baseline.py -q → 28 passed
全局门: ruff check . --no-cache → All checks passed!
        pytest -q → 2853 passed
        tools/gauge_map.py → 查不到尺子 0
```

**① acceptance 映射**

| acceptance | 测试 |
|---|---|
| ① 只重判、不重跑组稿 | `test_there_is_a_new_judgement_for_every_model`（3 例）、`test_the_new_run_judged_the_same_items_as_the_old_one`（**逐条对键**）、`test_the_compositions_were_not_regenerated`（**sha256 现算现比**）、`test_every_record_carries_its_evidence`、`test_unavailable_verdicts_are_not_counted_as_unanswered` |
| ② 旧数原样保留、NEVER 混表 | `test_the_old_numbers_are_still_there`（3 例）、`test_the_new_artifacts_live_in_their_own_directory`、`test_the_old_directory_gained_nothing`、`test_the_document_keeps_the_two_baselines_in_separate_sections`、`test_no_single_table_row_holds_both_baselines`（**钉在表格行上**） |
| ③ 文档写清判官/时间/题库版本/为何不可横比 | `test_the_document_says_who_judged_and_when`、`test_the_document_explains_why_the_two_are_not_comparable`（**节内判**）、`test_the_ranking_is_stated_not_left_to_the_reader`（**节内 + 全文一致性**） |
| ④ 成本记进 trace | `test_the_document_records_the_cost`；实测与估算的分界见 §4 |

新基线自洽那一组：`test_the_three_new_rates_are_all_present_and_in_range`
（三家判出同一个数是**故障的样子**）、`test_the_new_baseline_is_internally_comparable`。

**② 无冻结件偏离**：`contracts/`、`flint/domain/` 未触碰；
`assets/heldout_questions.yaml` 未读写；**旧产物目录一个字节没动**；零新增依赖。

**③ 禁用词**：产物文档 + 本 trace 六词 0 命中。

**④ 复用**：判词与解析全部来自 JUDGE-02 的 `harness/judge_alignment.py`
（**没有第二套判词**——两套判词会让两张卡的数不可比）；
provider 与账本来自 JUDGE-01；样本重建走既有 `load_items`。

**⑤ 装载预算**：约 8k tokens。

## 7. owner_review：三件要 owner 拍板的

1. **新基线取代旧基线到什么程度**。我的读法：**头名结论不变**（claude-sonnet-5 最高），
   **二三名之间的排序作废**（0.4 个百分点 = 一条之差）。M4 出口报告要不要跟着改，
   属里程碑文书，本卡没动。
2. **新数普遍高十几个百分点，接不接受**。它反映的是判官更宽松，不是产物更好。
   若要拿它当「作答率达标线」的基准，**先补 JUDGE-02 指出的两条判准**，
   否则线会被判官的松紧牵着走。
3. **$0.12 的估算要不要重跑成实测**。重跑两家 516 条约 $0.03（缓存已热），
   代价很低；但产物已在盘上，重跑只为把账补实。我的建议是**不重跑**，
   把账落盘的机制补上（见 §4 教训），下次自然就是实测。

## 8. 登记未做

1. **两家的花费是估的**（§4）。
2. **判词坏掉的 2 条没有重试**：`claude-sonnet-5` 那份有 2 条判词解析失败，
   本卡按「不进分母」处理，**没有重发**。重试会让分母回到 258，
   但也会引入「第二次判的结果算不算同一次跑批」的问题——留给 owner。
3. **没有做新基线内部的置信区间**：三家差 0.4 个百分点这件事，
   我按「一条之差」定性说不可靠，**没有算显著性**。要算得先定检验方法。
4. **M4 出口报告没改**：那份文书里 §6.2 仍是旧表。本卡产出的是新文档，
   两份并存，`docs/新基线-v041.md` 里写清了两者关系。
