# JUDGE-02 · DeepSeek 与 Claude 的判官对齐检验

**卡** `tasks-v041-b2.json#JUDGE-02` · **cycles 1** · **owner_review = true** → 见 §7
**依赖** JUDGE-01（verified）

## 1. 装载清单

卡面 JUDGE-02 · `assets/heldout_questions.yaml`（只读：题库口径、抽取式题面的理由、
`known_limitations`）· `docs/M4-出口报告.md#6.1`（统一判官口径与三家实测）·
`assets/prod_caliber/unified_judge/claude-sonnet-5.json`（258 条录制判定）·
`assets/prod_caliber/claude-sonnet-5.json`（12 份组稿产物的逐节正文）·
`flint/llm/deepseek.py`（JUDGE-01 的 provider 与账本）·
`flint/llm/production.py#MeteredAnthropicProvider` / `load_anthropic_tier`。约 10k tokens。

## 2. 顺序（§4.2）

测试先落盘先跑红（`ImportError: harness.judge_alignment`）→ 实现 →
**第一次真跑** → 发现键塌缩缺陷（§4）→ 修 + 补两条判据 → **第二次真跑** →
Claude 复判 → 文档 → 25 passed。

## 3. 结果：一致率 82.35%，而分歧里有 42.9% 是判官自己不稳

| 项 | 值 |
|---|---|
| 样本 | 120 条（从既有统一判官跑批取，带被判正文） |
| 可比 | **119**（1 条 DeepSeek 判词坏了，记 `available=False`，不进分母） |
| 一致 | **98 / 119 = 0.8235** |
| 分歧 | **21 条**（清单在 `docs/判官对齐-v041.md`） |
| 分歧复判 | Claude 对这 21 条**重判一次**：**9 条改了口**（42.9%） |
| 等价一致率 | (98+9)/119 = **0.8992** |
| 花费 | DeepSeek $0.007592 + Claude **$0.088590** = **$0.096**（预算 $1，用掉 9.6%） |

**把额度花在哪是本卡的主要设计**：Claude 那一票**取自既有录制**（那次跑批实录
$1.21，重跑一遍就把整个储备花光），新花的钱**只用在 21 条分歧上**。
买到的信息比「再算一遍同一个一致率」直接得多——它回答的是
**「同一个判官对同一条样本两次判得一样吗」**，答案是 21 条里有 9 条不一样。

**分歧集中在四节**（`timeline` / `budget` / `evaluation_plan` / `resources`，21 条里 9 条）。
共同点：题面问的是**结构化清单**（谁在什么时候做什么、多少钱花在哪），
而正文常是叙述体。判准没写清「叙述体里能推出清单算不算作答」——
**这就是分歧清单的价值**：它指出了判准要补的地方，而不是给一个分数。

## 4. 跑第一次才发现的缺陷：键塌缩

第一次跑出来 77.1%（91/118）。看分歧清单时发现 **`generic/plan/q2` 出现了不止一次**——
同一个 `question_id` 在 12 份组稿产物里各答一遍，**它们是 12 条不同的样本**，
而我把投票表按 `question_id` 做键，**12 条互相覆盖成 1 条**。

覆盖是**无声的**：一致率照样算得出来，只是分母悄悄少了一个数量级，
而且比的是「最后一份产物的判定 vs 另一份产物的判定」——那是两件不同的事。

修法：`JudgeItem.item_key = composition/section/question`。补两条判据：
同一 `question_id` 在两份产物里必须是两个键、真样本里**没有重复键**。
修完重跑：**82.35%（98/119）**，与错的那次差 5 个百分点。

**这条值得记的地方在于：错的那个数字看起来完全正常。** 没有第二次看清单，
它会作为「一致率 77%」写进文档。

## 5. 第三票（GPT-5.6）没用上——这里我写错过一次

**初稿写的是**「本机没有配 `FLINT_OPENAI_API_KEY`，第三票不可用」。
**那句是错的**：我查的是 `.env.example` 模板（那五项确实空着），**没查运行环境**。
实际环境里 key 是配好的（做 JUDGE-04 时发现，owner 已授权、余额 $20）。

**「模板里没有」与「环境里没有」在盘上长得像，含义完全相反**——
前者是「没人写模板」，后者是「这台机器不能用它」。查错了对象，
结论就从「我没用」变成了「用不了」。

**订正后的事实**：第三票当时**可用**，但本卡**没有用**它——本卡没有 GPT 适配器
（`flint/llm/openai_compat.py` 是 JUDGE-04 的产物），临时手搓一个客户端等于
另建一条调用路径，那是 JUDGE-01 acceptance① 明令禁掉的。

文档 `docs/判官对齐-v041.md` 的对应段落已同步订正，并留了待办：
JUDGE-04 落地之后拿这 21 条分歧跑一次真正的第三票。

## 6. 变异考：十六个，三个先活了下来

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 键退回 `question_id` | §4 那个缺陷 | **2 failed** ✓ |
| ② 一边没判也算一致 | 分母纪律 | **1 failed** ✓ |
| ③ 空比较记 1.0 | 无意义的 1.0 | **1 failed** ✓ |
| ④ 抽不出原句也算答了 | 抽取式判定 | **1 failed** ✓ |
| ⑤ 判词坏了记成「未作答」 | 故障 ≠ 判不同 | **1 failed** ✓ |
| ⑥ 只剩一家也标校准过 | acceptance⑤ | **1 failed** ✓ |
| ⑦ 打平也出结论 | acceptance③ | **1 failed** ✓ |
| ⑧ 全不可用时抛错停机 | **NEVER 停机** | **2 failed** ✓ |
| ⑨ 判词删掉「抽不出即未答」 | 判词完整性 | **25 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑩ 判词不禁止判官自己作答 | 判词完整性 | **1 failed** ✓ |
| ⑪ 判词不给正文 | 判的是同一段 | **1 failed** ✓ |
| ⑫ 花费超预算（记 1.5） | acceptance② | **1 failed** ✓ |
| ⑬ 没有分歧清单 | acceptance④ | **1 failed** ✓ |
| ⑭ 第三票那节的标题改掉 | acceptance③ | **25 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑮ 那节不说用没用上 | — | **25 passed** —— **近似惰性**，见下 |

**⑨ 第一次打偏、第二次才是真洞**：第一版变异只删了半句，而
「did not answer」在**另一个字符串字面量**里还在，所以判据当然不该红。
按行删掉整句之后，判据（只查 `"extract" in prompt`）**果然没反应**——真洞。
修法：三条子句各判一次（禁止自答 / 要求抽取 / 抽不出即未答）。

**⑭ 为什么能活**：判据是「全文提到过第三票」。把小标题改掉、内容散在别处时，
按词判照样绿，而**读的人再也找不到这件事写在哪**。
修法：判据钉在**有没有这一节**上（`## ` 开头且含「第三票」），
再在那一节的范围内判内容。本仓第十六次同型。

**⑮ 是近似惰性**：把那节里写「不可用」的句子换掉之后，同一节里
「要真正用上三判官，owner 需要配 key」这句仍然把状态说清楚了，
判据的 `不可用 or 用上` 因此仍然成立——**判据没被骗，是那节本来就说了两遍**。
不再收紧：收紧成「必须出现某个词」会把判据变成对措辞的考试。

十六次变异后两个产物文件的 sha256 与变异前逐位相同；
**题库 `assets/heldout_questions.yaml` 的 sha256 全程未变**
（`a80c8c73…`，文档里记了全值，测试逐次核）。

## 7. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_judge_alignment.py -q → 25 passed
全局门: ruff check . --no-cache → All checks passed!
        mypy --strict flint → 287 files, no issues
        pytest -q → 2825 passed
        tools/gauge_map.py → 查不到尺子 0
```

**① acceptance 映射**

| acceptance | 测试 / 证据 |
|---|---|
| ① 50~200 条样本、两家各判、算一致率、给分歧清单 | `test_the_sample_size_is_in_the_range_the_card_names`、`test_items_carry_the_text_that_was_judged`、`test_the_loaded_items_have_unique_keys`、`test_alignment_counts_agreements_and_lists_disagreements`、`test_the_disagreement_carries_both_sides`；实跑见 §3 |
| ② Claude 花费 ≤ $1 且记进 trace | `test_the_document_records_the_actual_spend`（**从文档里读数并判 ≤1**）；实测 $0.0886 |
| ③ 不达标 NEVER 停机 + 三级降级链 | `test_two_of_three_wins`、`test_all_three_disagreeing_goes_to_the_owner_list_and_keeps_running`、`test_no_judge_at_all_is_still_not_an_exception`、`test_the_module_never_raises_to_stop_the_run`（**AST 断言：模块里一个 `raise` 都没有**）、`test_the_document_says_what_the_third_judge_did` |
| ④ 分歧清单是真正的产品 | `test_the_document_lists_the_disagreements`；21 条逐条在文档里，含两边判定 + 复判 |
| ⑤ 三家全不可用时降级为「只用 DeepSeek + 标未校准」 | `test_a_single_available_judge_is_marked_uncalibrated`、`test_two_agreeing_judges_are_calibrated`（阴性对照） |
| ⑥ 题库只读 | `test_the_bank_is_untouched`（sha256 逐次核，指纹记在文档里而不是写死两处） |

判词与解析那一组：`test_the_prompt_asks_for_an_extraction_not_a_yes_no`（三条子句）、
`test_the_prompt_carries_the_section_text`、`test_a_verdict_parses_into_a_bool_and_a_quote`、
`test_an_unparseable_verdict_is_unavailable_not_false`、
`test_answered_true_without_a_quote_is_refused`。

**② 无冻结件偏离**：`contracts/`、`flint/domain/` 未触碰；
`assets/heldout_questions.yaml` **一个字节没动**；
`assets/prod_caliber/**` 只读；零新增依赖。

**③ 禁用词**：三个产物文件 + 本 trace 六词 0 命中。

**④ 复用**：DeepSeek 侧走 JUDGE-01 的 provider 与账本；Claude 侧走既有
`MeteredAnthropicProvider` + `load_anthropic_tier`（**没有新写一个 Claude 客户端**）；
样本与参考判定全部取自既有录制产物。

**⑤ 装载预算**：约 10k tokens。

## 8. owner_review：三件要 owner 拍板的

1. **82.35% 这个数收不收**。卡面没给达标线（owner 明说不达标也不停机）。
   我的读法是：**扣掉判官自身不稳的那 42.9% 之后等价 89.9%**，
   而剩下的分歧集中在四节判准不清的地方——**先补判准再谈换判官**。
2. ~~要不要给 OpenAI key~~ —— **这条问题作废**：key 早就配好了（见 §5 的订正）。
   替换成真正要问的：**三判官降级链什么时候补验**。JUDGE-04 落地适配器之后，
   拿本卡这 21 条分歧跑一次真第三票即可，成本按 GPT-5.6 Terra 档估约 $0.1。
3. **判准补哪两条**（文档 §从这张表里看出来的三件事）：
   ① 一句概括性的阶段说明算不算回答了「支出的时间分布」；
   ② 叙述体里能推出清单，算不算作答。这两条是 owner 的口径决定，不是我能定的。

## 9. 登记未做

1. **只比了 120 条**（可比 119）：录制里有 258 条。加到全量要再花约 $0.01 的
   DeepSeek 钱与更多 Claude 复判，本卡按卡面上限（50~200）取了 120。
2. **只用了一份组稿产物的判定作参考**（`claude-sonnet-5.json`）：
   另外两家（gemma4 / qwen3.6）的录制没进对比。它们是**被判方**不是判官，
   混进来会把两件事搅在一起。
3. **复判只做了分歧条目**：一致的 98 条没有复判，所以「Claude 自身稳定性」
   这个数（42.9%）**只在分歧集上成立**，不能外推到全集——
   全集上的自洽率要另花钱测。这一条在文档里没有明写，**在这里补上**。
4. **`resolve_votes` 还没有调用方**：降级链是接口，接进真实判官流水线是 M2 的面。
5. **`.judge/` 是临时产物目录**，没进版本控制口径。本卡的结论已全部落进
   `docs/判官对齐-v041.md`，那份才是可复看的产物。
