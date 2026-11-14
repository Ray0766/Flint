# GAUGE-02 · acceptance ↔ 尺子专项清点

> verify_cmd `pytest tests/v041/test_gauge_map.py -q` → **10 passed**。卡上 cycles=2，实际 1。
> `owner_review=true`：按 DEC-000 默认照做、完成打标继续；开工前复查 `DECISIONS-v04.md` 无划除记录。

## 装载清单（实际）

| 来源 | 用途 |
|---|---|
| `docs/steward/tasks-v041-b2.json#GAUGE-02` | 卡面 |
| `docs/review/终检-v04.md`（一句话病理 + F-05/F-08/F-12 三节） | 已知答案的来源 |
| `tasks-v04.json`（全 104 张卡的 id/verify_cmd/acceptance/outputs 字段） | 被清点对象 |
| `pyproject.toml#tool.pytest.ini_options` | `testpaths=["tests"]` —— 「pytest 路径算在门内」这条判据的依据 |
| `worker.md` §5 | 全局门三条命令的逐字口径 |
| `tests/v041/test_doc_gates.py`（GAUGE-01 产出） | 阴性对照要模拟"它还不存在"那一刻 |

约 18k tokens，未超 40k。

## 结论（这张卡的产品）

**104 张卡 / 169 条 acceptance**：

| 类 | 条数 |
|---|---|
| 有尺子且在门内 | **102** |
| 有尺子但不在门内 | **67** |
| **查不到尺子** | **0** |
| （正交信号）弱关联 | **3** |

**「查不到尺子」为零是一条阴性结论，不是「没查」**——解析器对 pytest 路径 / vitest 过滤器 / 工具脚本三种形态各有分支，四个构造反例（不存在的测试路径、空 verify_cmd、不存在的工具、匹配不到任何文件的 vitest 过滤器）证明这一格真的会落条目。终检那 122 个路径 token「MISSING: 0」的结论在这里被独立复算并扩展到了 vitest 过滤器与工具脚本。

**真正的问题在第二格：67 条 acceptance 的尺子在门外。** 拆开看是两类：

| 子类 | 条数 | 形态 |
|---|---|---|
| 前端 vitest | 51 | 由 `npm test` 守，而全局门是 `ruff && mypy && pytest` 三条命令——忘了单独跑就没人知道 |
| 工具脚本 | 17 | `tests/` 下没有任何文件起它，`pytest -q` 碰不到 —— **F-11 的形态原样还在** |

工具那 17 条落在 `check_impact_doc.py`（MIGRATE-05/06/07 各 2 条）与五把 `.mjs` 扫描器上。GAUGE-01 只被授权接六把文档尺，这批不在其内——**登记在此，是 F-11 的同款残留**。

## 弱关联三条（正交信号，不参与三分类）

| 卡 | # | acceptance 说要断言的东西 | 在它那把尺子的正文里 |
|---|---|---|---|
| `MIGRATE-05` | 1 | `tabular-nums`、`DESIGN-05` | 零命中 |
| `SCHEMA-00` | 2 | `CONFLICTS-v04.md` | 零命中 |
| `I18N-01` | 1 | `RegistryValidator` | 零命中 |

三条都是「登记类 acceptance 由通用校验器守」的形态：校验器查的是小节齐全与引用存在，查不到这三个具体名字。**这是提示不是判决**——本工具只查标识符出现与否，不理解语义。

## 判据设计（为什么是这几条）

**尺子归属只认 `verify_cmd` + `outputs`，且目标必须在磁盘上真解析得到**。acceptance③ 写死了 NEVER 人肉判断，而人肉判断在这里恰恰最危险：读一条 acceptance 然后"想起来"某个测试大概覆盖了它，得到的覆盖率是自我安慰。

**「在门内」三条判据**：pytest 目标在 `tests/` 下 → 在门内（依据是 `pyproject.toml` 的 `testpaths=["tests"]`，不是印象）；vitest → 恒不在门内；工具脚本 → 在门内当且仅当 `tests/` 下有文件逐字提到它的路径。第三条正是 F-11 那一格。

**弱关联为什么不并进三分类**：三分类是机械判定，弱关联是启发式。混成一锅的话，一条启发式误判就会污染机械结论，而机械结论是这张卡唯一能拍板的东西。

## 一次实测返工：弱关联从 8 条降到 3 条

首版 tokenizer 把 `created_at/region/verdict_at_save/in_workbench` 当成**一个**标识符——那是四个字段名并列，斜杠在中文 acceptance 里常当顿号使。整串当然在测试里搜不到，于是 `FAV-03`、`GRAPH-08`、`I18N-07`、`DESIGN-05`、`MIGRATE-07` 五条被误报成弱关联。

改法：整串与切分后的每一段都收进标识符集（整串留着是为了真路径 `docs/x.md` 仍能整体命中）。**误报会让弱关联表迅速失去可信度，而它唯一的用处就是被人真的看一眼**——8 条里 5 条是噪声的表，第二次就没人看了。

## 自证（acceptance ④）

阴性对照是这张卡最要紧的一条测试：`test_control_prin01_flips_to_outside_gate_at_the_moment_f11_happened` 用 `Repo(REPO_ROOT, tool_invokers={})` **构造 GAUGE-01 之前那一刻的仓库索引**——同一张真卡（`PRIN-01`）、同一条真 acceptance（哈希比对），唯一变量是"有没有测试起这把工具"，分类必须从 `in_gate` 翻成 `gauged_outside_gate`。

翻不过去 = 这把清点器只会说「都挺好」，那它就是它自己要防的那种东西。用构造的假卡做对照证明不了这件事，因为真卡的形态（一条 verify_cmd 同时含工具与 pytest、acceptance 全中文无标识符）才是它要处理的。

另两条：`GRAPH-06`（vitest 尺子解析得到但 in_gate=False，且不因为同卡有 pytest 就把 vitest 那格也涂绿）、`SCHEMA-00`（正常卡）。

## 顺序偏离（如实记）

本卡**工具骨架先于测试文件落盘**，与 `worker.md` §4.2「先写失败测试」相反。已观察到完整红→绿：测试首跑 3 red（报告与 json 未生成、弱关联断言不符），修完 10 passed；其中一条红是**测试自己写错了**（我断言 `key` 会被当停用词丢掉，实际规则是「<3 字符 + 停用词」，`key` 三字符应当保留）——按真规则改测试，NEVER 为迁就测试去改工具的口径。

## self_review 五条

① **测试真实覆盖 acceptance**

| acceptance | 测试 |
|---|---|
| ① 104 张卡每条 acceptance 出四元组 | `test_every_acceptance_of_every_card_gets_a_quadruple`（逐条比原文逐字、断 (卡号,序号) 无重复） |
| ② 三类落 json，第三类逐条进报告 | `test_three_classes_partition_the_entries` + `test_disk_copies_are_current` + `test_report_lists_class_three_line_by_line`（第三类为空时强制报告写明是阴性结论并指向构造用例，NEVER 留空表） |
| ③ 机械推出，推不出进第三类 | `test_control_unresolvable_gauge_lands_in_class_three`（四种形态各一个反例） |
| ④ 三条已知答案自证 | `test_control_prin01_*` ×2、`test_control_graph06_*`、`test_control_a_plain_card_lands_in_gate` |

② **无冻结件偏离**：本卡零触碰 `contracts/` 与 `contracts_v04/`；`check_frozen_additive` 双通过（由 `tests/v041/test_doc_gates.py` 在同一次 `pytest -q` 里跑）。

③ **无禁用词**：`grep -nE "适当|合理|必要时|大约|尽量|若干" tools/gauge_map.py tests/v041/test_gauge_map.py docs/尺子清点-v041.md` → 零命中。

④ **复用断言在位**：零新写校验逻辑；`tasks-v04.json` 是唯一输入真相，门的口径取自 `pyproject.toml` 与 `worker.md` §5 而非硬编码印象。

⑤ **装载未超预算**：约 18k tokens < 40k。

## 遗留（登记，不自行扩面）

1. **17 条工具类 acceptance 仍在门外**（`check_impact_doc.py` 6 条 + 五把 `.mjs` 扫描器 11 条）。接进门的动作超出本卡 outputs，按本批 §2 不自行扩面——登记给后续卡（`AUDIT-02` 的「接进全局门」是自然承接点）。
2. **51 条前端 acceptance 在门外**是结构性的：全局门按定义只有三条 Python 命令。要么扩门（加一条 `npm test`），要么接受「前端要单独跑」并写进 SELFCHECK 清单。这是 owner 口径问题，登记不自决。
3. 本工具**看不见 F-05 那一类**（尺子在门内但压力够不到机制），已写进报告末节并指向 `GAUGE-03`。
