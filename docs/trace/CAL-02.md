# CAL-02 · 参数落值（θ_rel / δ / hotness 从初值改为标定值）

**卡** `tasks-v041-b2.json#CAL-02` · **cycles 1** · **owner_review = true** → 见 §6
**依赖** CAL-01（verified）

## 1. 装载清单

卡面 CAL-02 · `assets/goldsets/`（CAL-01 的三份各 60 条）·
`flint/retrieval/relevance.py`（θ_rel 判的到底是什么）·
`flint/topic/differentiate.py`（δ 的提取方式：成对距离 10 分位 + floor）·
`flint/config.py` 的调参通道（BL-05）· `harness/tune_hotness.py` ·
`CLAUDE.md#S4`（≥90%/50 簇的出口线）· postgres `flint` 库的 keywords.embedding。
约 9k tokens。

## 2. 顺序（§4.2）

**先定口径**（`CALIBRATION_CALIBER` 写进 config 并落指纹）→ 测试先落盘先跑红 →
扫参取数 → 状态表 + 文档 → 23 passed → 变异考补判后 23 passed。

**顺序在本卡是纪律不是习惯**：「NEVER 反推阈值凑指标」这条红线，
落法就是**口径先写、指纹先落**，扫参在后。调完再改口径，指纹对不上，测试红。

## 3. 结论：今天一个参数都标定不了，四条各有实测

| 参数 | 结论 | 证据 |
|---|---|---|
| `theta_rel` | 标不了 | **形状不对**：θ_rel 是**每个查询**的 `hit_rate`（top-k 里被判相关的比例）的阈值，而金标是**逐对**标注。逐对标注再多也换不出「每个查询该不该接受」这个真值 |
| `delta` | 标不了 | **分数没有区分力**：扫遍所有阈值最优 F1 **0.22**（口径要 ≥0.80），且 `same` 对的距离**比** `different` 对**还远**（中位 1.0319 vs 0.9943） |
| `hotness.*` | 标不了 | 没有任何金标热度序列，`tune_hotness.py` 一直是 report_only |
| 血缘 ≥90%/50 簇 | 测得出但判不了 | 实测 **60/60 = 1.00**、簇数 60 ≥ 50，数字上过线；但那批语料**一次簇漂移都没有**（每条 `continued` 两天挂的关键词逐字相同），**判不出错不等于没错** |

**δ 那一条查到了根因**：demo 库的关键词嵌入是**随机向量**——任取 40 个词两两算距离，
`n=780 均值=1.0001 标准差=0.0314`。1024 维随机向量两两近似正交，
余弦距离恰好聚在 1.0，这就是它的特征。**在这种分数上定出来的 δ 是噪声。**

## 4. 所以本卡改的是「标定状态」，不是参数值

`flint/config.py` 新增两张表（**参数值一个没动**，有判据逐个钉着）：

- `CALIBRATION_CALIBER`：先写好的评价口径（用哪批金标 / 算什么指标 / 多少算过线）+ 指纹；
- `CALIBRATION_STATUS`：逐参数写明**标没标定 / 为什么 / 证据在哪 / 样本量 / 日期**。

**BL-05 的未标定标记不清除**（acceptance③ 的反面）：清除它等于宣称标定过了，
而本卡的结论恰恰相反。有判据守着 `load_tuning().calibrated is False`。

**为什么不顺手改一个「看起来更好」的值**：改一个没有证据支持的值，
比留着初值更糟——**初值至少标着「未标定」，而改过的值看起来像是标定出来的**。

## 5. 变异考：十四个，三个先活了下来（补判后全红）

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① δ 自称已标定 | 本卡结论 | **1 failed** ✓ |
| ② 调完之后放宽口径（把 F1 线从 0.80 改成 0.20） | acceptance② 红线 | **1 failed** ✓ |
| ③ 没标定却不写为什么 | acceptance③ | **23 passed** ✗ → 整段删掉后 **1 failed** ✓ |
| ④ 不给证据 | acceptance③ | **1 failed** ✓ |
| ⑤ 证据指向不存在的文件 | 证据可核 | **1 failed** ✓ |
| ⑥ 不写样本量 | acceptance③ | **1 failed** ✓ |
| ⑦ 口径表与状态表参数不一致 | 覆盖 | **1 failed** ✓ |
| ⑧ 没有改前改后对照 | acceptance① | **1 failed** ✓ |
| ⑨ 证据不给实测数 | acceptance① | **1 failed** ✓ |
| ⑩ 血缘不写实测 | acceptance④ | **23 passed** ✗ → 两处都删后 **1 failed** ✓ |
| ⑪ 不说清为什么这个 100% 不能对线 | acceptance④ | **23 passed** ✗ → 补判后 **1 failed** ✓ |

**②「放宽口径」这一条最要紧**：它模拟的正是红线要防的动作——
先扫出 F1=0.22，再把过线标准从 0.80 改成 0.20，于是「标定成功」。
判据是**文档里记的口径指纹 = 代码里的当前口径**，一改就对不上。

**③⑩ 是我的变异打偏了**：③ 只清空了理由字符串的最后一个片段（前面几段还在，
长度仍 ≥20）；⑩ 只改了两处实测数中的一处（另一处顶上）。
按「真的把那件事拿掉」重做后都红。

**⑪ 是真洞**：判据写的是「文档里有『漂移』二字」，而那两个字在末尾
「下一步要什么」的表格里也有——把血缘那节讲原因的整句删掉照样绿。
改成**节内判**（`## 血缘` 那一节里必须同时有 S4 的线、实测数、原因）。
本仓第二十次「判据被别处的同一个词喂饱」。

十四次变异后两个产物文件的 sha256 与变异前逐位相同。

## 6. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_calibrated_params.py -q → 23 passed
全局门: ruff check . --no-cache → All checks passed!
        mypy --strict flint → 288 files, no issues
        pytest -q → 2957 passed
```

**① acceptance 映射**

| acceptance | 测试 |
|---|---|
| ① 用金标反推最优参数、改配置不改代码、改前改后对照写进文档 | `test_the_document_shows_the_before_after_table`、`test_the_delta_evidence_is_a_measurement_not_an_opinion`、`test_the_goldsets_used_are_named_with_their_sizes`、`test_the_initial_values_are_untouched`（3 例，**代码里的值一个没动**） |
| ② NEVER 反推阈值凑指标：先定口径，调完不许再动 | `test_the_caliber_is_written_down_before_any_number`、`test_the_caliber_carries_a_fingerprint`、`test_the_document_records_the_same_fingerprint`（**口径动了就红**）、`test_the_status_table_is_machine_readable_json` |
| ③ 标定后标注「已标定 + 样本量 + 日期」，与未标定态可区分 | `test_every_param_has_a_status_entry`（4 例）、`test_an_uncalibrated_param_says_why`（4 例）、`test_nothing_claims_to_be_calibrated_today`（**反向断言位**）、`test_the_uncalibrated_marker_is_still_on`、`test_the_evidence_files_exist`、`test_the_caliber_and_the_status_cover_the_same_params` |
| ④ 血缘对照 S4 的 ≥90%/50 簇，达不到照实说 | `test_the_lineage_line_is_reported_against_the_s4_gate`（**节内判**：线、实测数、原因三样都要在那一节里） |

**② 无冻结件偏离**：`contracts/`、`flint/domain/` 未触碰；
`assets/heldout_questions.yaml` 未读写；数据库只读；
`flint/retrieval/relevance.py` 与 `flint/topic/differentiate.py` **一个字没改**；
零新增依赖。

**③ 禁用词**：两个产物文件 + 本 trace 六词 0 命中。

**④ 复用**：金标来自 CAL-01；余弦距离用 `flint/topic/differentiate.py#cosine_distance`
（**没有另写一个距离函数**——另写一个，扫出来的数就与线上算的不是同一个量）；
标定状态表的形状照 `TuningProfile` 的「值 + 来由一体」写法。

**⑤ 装载预算**：约 9k tokens。

## 7. owner_review：三件要 owner 拍板的

1. **θ_rel 到底怎么定**。它的形状决定了「按对标注」永远标不出来。两条路：
   ① 换标注面——按**查询**标（每个查询的 top-k + 这次检索该不该接受）；
   ② 承认它是**产品决策**（「top-k 里多少算够」本来就带策略成分），由 owner 直接给值。
   我倾向 ②，因为 ① 需要先有真实检索日志，而那要等真源接入。
2. **δ 要等一个真的嵌入模型**。现库是随机向量（§3 有实测）。
   在换库之前，δ 的任何值都是占位——**包括现在的 0.05**。
3. **血缘那条出口线怎么算**。数字上 60/60 过线，但语料判不出错。
   我的判断是**不能算过线**，并把它记成「测得出但判不了」。
   若 owner 认为可以先按数字算过，那要连带记住：这个 100% 不含任何漂移样本。

## 8. 登记未做

1. **没有跑 `harness/tune_hotness.py` 的 A/B**：没有金标序列时，跑它只会得到
   「换一组数看排序变没变」，那不是标定。
2. **θ_rel 的判官一致性没测**：金标能测的是「LLM 逐条判相关」与人/机金标的一致率，
   那是**判官的准确率**，不是 θ_rel 的值。本卡没做——它属 JUDGE 线。
3. **δ 的扫参脚本在 scratchpad**：结论与实测数已进文档，脚本本身是一次性取证。
4. **没有动 `CHECK_ANSWER_LINE` 等别的阈值**：本卡只管卡面点的三个参数 + 血缘线。
