# COMP-01 · 上线前合规手续清单单独成文

**卡** `docs/steward/tasks-v041-b2.json#COMP-01` · **cycles 1** ·
**self_review = true** → §6 · **owner_review = true** → §7
**依赖** K2-01（verified）

## 1. 装载清单

卡面 COMP-01 · `docs/blocked/K2-COMPLIANCE-BEFORE-LAUNCH.md` 全文 ·
`assets/source_legal_status.yaml` 全文（8 条）· `flint/region/legal_policy.py` 全文 ·
`flint/region/legal_probe.py`（docstring + `MeasuredStatus` + `derive_fetch_legal_status`
+ `load_measured_status`）· `tests/v041/test_legal_status_recorded.py` 的第五节。
约 9k tokens，预算 40k 以内。

## 2. 顺序（§4.2）

测试先落盘先跑红（**12 failed / 1 passed**）→ 用 `__main__` 从数据生成表 →
写文档 → 搬走问题单那份表并加指针 → 撞上 K2-01 的一条判据（§4.3）→ 改指向 →
**14 passed**（本卡）/ 52 passed（本卡 + K2-01）。

## 3. 五列里哪三列是机器的、哪两列是人的

| 列 | 来源 |
|---|---|
| `source_id` | `assets/source_legal_status.yaml` |
| robots 实测态 | 同上（`state` 字段） |
| 派生合规态 | `flint/region/legal_probe.py#derive_fetch_legal_status` 现算 |
| 上线前要办的手续 | 人写，钉在 `tests/v041/test_launch_compliance_doc.py#FORMALITIES` |
| 办成的判据 | 同上 |

**「NEVER 手抄」唯一可执行的形式是逐字比**：整张表由
`python tests/v041/test_launch_compliance_doc.py` 生成，
`test_the_table_is_exactly_what_the_data_produces` 拿生成结果与文档里的表**逐字比**。
只判「表里有这些源」的话，把 `disallowed` 手抖写成 `allowed` 照样绿——
而那正是上线那天会出事的那种错（变异考① 实测：手改一个格子，3 条红）。

**人写的两列为什么放在测试文件里**：放文档里就没法说「文档 = 数据 + 这张表」，
逐字比也就无从比起。放测试文件里，这句话可被逐字验证，且新增源时
`build_table` 直接抛 `KeyError`——**NEVER 给新源填一行「待定」**，
那一行在上线清单上与「已办」长得一模一样。

## 4. 改既有文件：两处

### 4.1 `docs/blocked/K2-COMPLIANCE-BEFORE-LAUNCH.md`

- **改前**：自带一张 8 行的逐源表（source_id / robots 实测 / 派生态 / 上线前要做什么），
  外加「ToS 一条都还没读」一节。
- **改后**：顶部加指针横幅；逐源表**删掉**，换成两句不含逐源数据的要点
  （所以它漂不起来）；切档那一节原样保留。
- **为什么非改不可**：acceptance④ 原话「两处 NEVER 各写一份会漂移的清单」。
  `assets/source_legal_status.yaml` 会随重测变，手抄的表不会——留着就是留一份
  迟早说反话的清单，而读的人分不出哪份是真的。判据
  `test_the_blocked_doc_no_longer_carries_its_own_per_source_list` 钉着这件事，
  它判的是**成行的表**（带 `|` 且点到源名或同时出现两种合规态的行），
  不是「不许提源的名字」——问题单讲怎么切档时提到某个源是正常的。

### 4.2 `tests/v041/test_legal_status_recorded.py`（**超出本卡 outputs，单独交代**）

- **改前**：`test_the_paperwork_names_every_source_that_needs_it` 判
  「每个非 allowed 的源都要在**问题单**里点名」。
- **改后**：判两件事——问题单里有指向清单的指针，**且**清单里逐源点名。
- **为什么非改不可**：这条判据与本卡 acceptance④ 直接冲突——清单一搬走它必红。
  两条路只能选一条：要么不搬（违 acceptance④），要么让判据跟着搬。
- **强度对比（这是关键，NEVER 只说「改好了」）**：改前判 1 件事，改后判 2 件事。
  清单被搬走而指针没跟上、或指针在而清单里漏了源，两个方向现在都红；
  改前只挡得住后者的一半。**没有放宽任何一条**。
- **越界登记**：卡上 outputs 只有两项（新文档 + 新测试），本处是第三个文件。
  改动面 3 行判据、语义只增不减，未走 blocked。**这一条列进 owner_review（§7）**。

**未改**：`assets/source_legal_status.yaml`（K2-01 的实测产物，本卡只读它）、
`flint/region/legal_policy.py`、`flint/region/legal_probe.py`、
`harness/probe_robots.py`。`contracts/` · `flint/domain/` · `requirements.lock` ·
`assets/heldout_questions.yaml` 一字未动。

## 5. 判据不是「文档里有这个词」

「办成的判据」那一列每一行都要给出**一个可以去看的地方**（反引号里的路径或代码符号），
由 `test_every_row_names_a_place_to_look` 机械查。只写「确认合规」的判据等于没有判据：
上线那天没人知道该看哪里才算办成了（变异考③ 实测：改成「确认合规即可」，2 条红）。

八条源的判据落到三类可去看的地方：`docs/legal/tos-readings/*.md`（人读结论）、
`docs/legal/contracts/*.md`（签约回执）、重跑 `harness/probe_robots.py` 让数据带上新实测。
这三个目录现在还不存在——它们是**上线前要产出的东西**，不是本卡的产物。

## 6. 变异考：十三个，四个先活了下来（三个真洞）

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 把 `arxiv` 的实测态手改成 allowed | acceptance① | **3 failed** ✓ |
| ② 删掉 `reddit_data_api` 那一行 | acceptance①③ | **4 failed** ✓ |
| ③ 判据一列改成空话 | 可去看之处 | **2 failed** ✓ |
| ④ 文档头去掉触发条件 | acceptance② | **51 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑤ 文档头去掉失效条件 | acceptance② | **51 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑥ `scope` 手抄成别的值 | acceptance② | **51 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑦ 文档不写裁决日期 | acceptance② | **1 failed** ✓ |
| ⑧ 问题单顶部指针删掉 | acceptance④ | **1 failed** ✓ |
| ⑨ 问题单又长回第二份逐源表 | acceptance④ | **1 failed** ✓ |
| ⑩ 代码改了裁决范围而文档没跟上 | acceptance② | **2 failed** ✓ |
| ⑪ 数据新增一个源而清单没跟上 | acceptance③ | **2 failed** ✓ |
| ⑫ 生成器对缺手续的源不抛错，改填「待定」 | acceptance③ | **1 failed** ✓ |
| ⑬ 把搬过家的那条 K2-01 判据改成恒真 | §4.2 | **52 passed** ✗ 不可杀，登记 |

**④⑤ 为什么能活**：判据按「文档头三十行里有这个词」判，而失效条件那一节顺口
又提了一次「商用上线」、标题里本身就带着「不再覆盖」——**把要判的那句整句删掉，
毫无反应**。改成**按节判、且不含标题行**（`_section_body`）。
这是 DARK-02 变异考⑭ 的同一形态换了个载体：判据的取值范围里混进了别处同一个词。

**⑥ 为什么能活**：判据是「文档里有一处 `scope="non_commercial"`」，而文档写了两处，
只改一处照样绿——那是「一半文档已经在说另一件事」的状态。改成
`re.findall` 取**每一处**，全部必须等于代码里读出来的值。

**⑬ 为什么不可杀**：这个变异改的是**判据本身**（把 `assert x` 改成 `assert x or True`）。
测试测不了自己被人改弱——这一层在本仓靠 review 与 trace 挡，不靠判据挡。
如实登记，NEVER 假装它被杀掉了。

十三次变异后四个被改文件的内容与变异前逐字相同（baseline 52 passed）。

## 7. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_launch_compliance_doc.py -q → 14 passed
连坐面:     + tests/v041/test_legal_status_recorded.py          → 52 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: no issues found in 288 source files
            pytest -q               → 3010 passed（DARK-02 收卡时 2996，本卡 +14）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 五列逐源、数据取自 YAML、NEVER 手抄 | `test_the_document_exists`、`test_the_table_is_exactly_what_the_data_produces`、`test_the_table_has_the_five_columns_the_card_names`、`test_the_derived_column_comes_from_the_code`、`test_every_row_names_a_place_to_look` |
| ② 头部写触发条件与失效条件、`scope` 取自代码 | `test_the_doc_states_the_trigger_in_its_own_section`、`test_the_doc_states_when_the_decision_stops_covering`、`test_every_scope_string_in_the_doc_is_the_one_in_the_code` |
| ③ 机器守着不漂移、新增源没跟上判红 | `test_every_measured_source_has_a_row_and_no_row_is_invented`、`test_a_new_source_without_formalities_stops_the_build`、`test_the_restricted_sources_are_the_ones_the_data_says` |
| ④ 唯一入口、问题单只留指针 | `test_the_blocked_doc_points_here_from_the_top`、`test_the_blocked_doc_no_longer_carries_its_own_per_source_list`、`test_the_switch_back_procedure_is_still_reachable`、K2-01 的 `test_the_paperwork_names_every_source_that_needs_it`（改指向后同时守指针与清单） |

**② 无冻结件偏离**：`contracts/` · `flint/domain/` · `requirements.lock` ·
`assets/heldout_questions.yaml` 未触碰；零新增依赖；`assets/source_legal_status.yaml`
只读未写（本卡不重跑探测——那是真实网络，红线之一）。

**③ 禁用词**：六词 + 列表尾「等」在四个被改文件里 **0 命中**。

**④ 复用**：派生合规态直接调 `derive_fetch_legal_status`，读表直接调
`load_measured_status`，裁决范围直接读 `RECORD_ONLY.scope` 与 `.decided_on`——
三处都 NEVER 在文档或判据里另写一套；表的生成入口照抄本仓
`__main__` 取证入口的既有形状。

**⑤ 装载预算**：约 9k tokens，未超 40k。

## 8. owner_review：三件要 owner 拍板的

1. **人写的两列内容认不认**。八条源的「手续」与「判据」是我按问题单原有的
   「上线前要做什么」一列拆开写细的（谁去读哪份条款、结论写到哪个文件、
   回执里要有什么号）。它是**手续设计**，不是数据——owner 若不认，改的是
   `FORMALITIES` 那张表，机器面一行不用动。
2. **改了一个 outputs 之外的文件**（§4.2）。K2-01 的一条判据与本卡 acceptance④
   直接冲突，我选了「让判据跟着搬且只增不减」而不是走 blocked 停下来。
   若 owner 认为这类冲突一律该停机，请在 DECISIONS 里写死，我照办。
3. **`docs/legal/` 三类落地文件的位置**。判据里写的
   `docs/legal/tos-readings/*.md` 与 `docs/legal/contracts/*.md` 是我定的路径。
   owner 若另有归档规矩（比如法务文件不进代码仓），改 `FORMALITIES` 里的路径即可。

## 9. 登记未做

1. **ToS 一条都还没读**。本卡产出的是「要办什么、办成了怎么算」，
   **不是办本身**。八条人读结论仍然一条都没有——那是 owner/法务面。
2. **`restricted` 三条的处置未定**。清单写了三选一（签约取数 / 换源 / 走 E6 缺数据行），
   选哪条是 owner 的事。
3. **判据里指的那三类文件都还不存在**。`docs/legal/` 目录本卡没建——
   建一个空目录等于给「已开始办」一个假象。它们由真办成的那一天创建。
4. **清单不管非抓取类合规**。个人信息、版权、跨境数据这些不在本清单射程内，
   它守的是 `assets/source_legal_status.yaml` 覆盖的抓取合规这一面。
5. **⑬ 那类变异不可杀**：判据被人改弱这一层，本仓靠 review 与 trace 挡，不靠判据挡。
