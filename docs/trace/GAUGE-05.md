# GAUGE-05 · F-12 修复：卡面 outputs 声明 ↔ 仓库实况 对账器

**卡** `docs/steward/tasks-v041-b2.json#GAUGE-05` · **批次** v0.4.1 第 2 批 · **开工** 2026-08-03T22:23Z

## 1. 装载清单（inputs 来源）

| 装载物 | 来源 | 用途 |
|---|---|---|
| 卡面 GAUGE-05 | `tasks-v041-b2.json` | acceptance / outputs / verify_cmd |
| `docs/review/终检-v04.md#F-12` 全节 + 5.2 隔离带段 | context_refs | 缺陷判词、三处确证、修法三条 |
| `tasks-v04.json` 的 `tasks[].outputs` + `isolation` 块（脚本读，未整本装载） | inputs | 声明面与隔离带名单 |
| `flint/**/*.py` 的 **AST**（273 个文件，只取 docstring 与 import 段） | 追加 | C 类自述判据与 B 类 import 图 |
| `tests/v041/test_ledger_pairing_v041.py` 的白名单写法 | 追加 | 冻结闭集白名单的房规（逐条对、带理由、NEVER 增补） |

装载约 17k tokens，未超 40k。

## 2. 对 104 张卡跑出的真实清单（acceptance②）

```
卡 104 张；隔离带 ['GRAPH-16','DESIGN-27','DESIGN-28','DESIGN-29','DESIGN-31','DESIGN-32']
outputs 条目 185 条 → 路径形态 175 · 带注解路径 5 · 非路径 5

A 类（声明了但仓库没有）        0 条
B1 类（无卡认领、被多卡共用）    1 条 —— flint/design/mock_syntax.py
B2 类（隔离卡产物被带外 import）  0 条
C 类（docstring 自述某卡、无人声明） 8 条
```

**A 类 0 条**是个值得单独说的结论：175 个路径形态的产物**全部在磁盘上**。
终检对 `verify_cmd` 的 122 个路径 token 验过同一件事（MISSING: 0），本卡把同样的验证
搬到了 `outputs` 面——**两个面都干净**，v0.4 的问题不是「写了没做」，是「做了没写」。

### C 类 8 条逐条（终检确证 3 条，本卡机械扫出另 5 条）

| 文件 | 自述的卡 | 该卡 outputs 原文 | 终检 |
|---|---|---|---|
| `flint/graph/roles.py` | GRAPH-06 | `['web/components/graph-roles/', 'tests/v04/graph/test_primary_unique_runtime.py']` | ✔ 确证 |
| `flint/design/mock_syntax.py` | DESIGN-28 | `['flint/design/solidify.py', 'tests/v04/design/test_solidify_pipeline.py']` | ✔ 确证 |
| `flint/design/comment_job.py` | DESIGN-12 | `['web/design/comments/', 'tests/v04/design/test_comment_job.py']` | ✔ 确证 |
| `flint/design/mock_syntax.py` | **DESIGN-27** | `['web/design/mock-identity/']` | 本卡新增 |
| `flint/api/graph_edges.py` | GRAPH-07 | `['web/components/graph-edge/', 'tests/v04/graph/test_edge_hypothesis.py']` | 本卡新增 |
| `flint/registry/npm.py` | I18N-01 | `['web/lib/i18n/', 'docs/deps_v04.md(…)']` | 本卡新增 |
| `flint/graph/__init__.py` | GRAPH-01 | `['web/views/workbench-shell/']` | 本卡新增 |
| `flint/i18n/__init__.py` | I18N-01 | 同上 | 本卡新增 |

**最值得记的一条是 `mock_syntax.py` 被两张卡认领**：它的 docstring 原话是
「样板占位语法的**唯一真相**（DESIGN-27 定表，DESIGN-28 复用）」——**一个文件在自己的
docstring 里认了两张卡，而两张卡都没在 outputs 里认它**。这正是 F-12 说的「产权未定」，
也解释了 B1 那条为什么必然存在。

后两条（两个 `__init__.py`）的自述是**里程碑范围**而非单卡（「v0.4 图谱层（GRAPH-01~16）」
「v0.4 语言层（I18N-01~08）」），归属天然模糊；它们进白名单时理由里写明了这一点，
NEVER 把「范围引用」说成「卡号认领」。

## 3. 判据设计（三条选择，逐条给理由）

### 3.1 C 类用「docstring 自述」而不是 mtime

终检对此有过一次自我更正：按「v0.4 期间被写入」筛出 14 个 `.py`，核下来必须剔除两类——
worker 同时在跑的 v0.4.1 ASM 产物、以及**既有文件被修改**（mtime 区分不了新建与修改）。
自述能区分：**写 docstring 的人当时就说明了这个文件是哪张卡的产物**。
本卡照这个标准做成机械判据，得到 8 条（含终检那 3 条，一条不漏）。

代价写明：自述判据看不见「建了但 docstring 没写卡号」的文件。这不是本卡能补的洞——
补它需要 git 历史或台账逐条回源，属另一张卡的面（§7 登记）。

### 3.2 两条「看起来像豁免、其实不是」的规则

1. **非路径形态的 outputs 不进 A 类**：`api: POST /favorites` 声明的是端点不是文件，
   `os.path.exists` 只会得到假红。但它们**必须出现在报告里**（`non_path` 段逐条列出）——
   悄悄丢掉就等于这把尺子替它们盖了章。5 条：REGION-04/05、FAV-01/02、GRAPH-02。
2. **`__init__.py` 由同包兄弟带进来**：卡声明 `flint/profile/prefs.py` 时不可能不建
   `flint/profile/__init__.py`。**同包内没有该卡任何声明时不适用**——仓库里
   `flint/graph/__init__.py` 与 `flint/i18n/__init__.py` 就是后一种，它们仍然是 C 类。
   （这条规则清掉 5 个 `__init__.py`，留下 2 个；用构造用例两侧都测了。）

### 3.3 带注解路径按去注解后的路径判存在

`contracts_v04/models_v04.py(增量区)` 说的是同一个文件的一段区域。按原样 `exists()` 会得到
一条**永远修不好的假红**，而那种红最后总是被人整条忽略掉——尺子就是这么失效的。
5 条带注解路径去注解后全部命中（测试钉住）。

## 4. 白名单：冻结闭集 + 一条反向断言（acceptance③）

`LEGACY_UNDECLARED` 按 **`(路径, 卡号)` 逐条**豁免，每条带理由；`LEGACY_SHARED` 同理。
**按对而不是按路径**：`mock_syntax.py` 恰恰是被两张卡认领的那种文件，按路径整条豁免的话，
将来第三张卡再认领它也会跟着蒙混过关。构造用例证明了这一点（同一个已豁免路径 + 新卡号 → 仍红）。

**反向断言 `test_every_whitelisted_row_is_still_a_real_finding`**：白名单里的每一条
今天仍然必须能被检出。一条豁免如果它豁免的东西已经不存在，剩下的就只有它盖住的口子——
这种「过期豁免」是规则被悄悄放宽的最常见形态，**而它看起来永远是绿的**。

规则本身一个字没放宽：三类判据对新差异照旧红，四个构造用例逐类证明（A / B1 / B2 / C）。

## 5. 用四个变异体反考自己的测试

沿用 GAUGE-03/04 的做法（改真文件 → 跑 → 从备份还原，还原后 sha256 复原为 `905c865e553b0ecd`）：

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① `if False and not (repo/path).exists()` | A 类检查 | **1 failed** ✓ |
| ② 白名单改成按路径豁免 | 「按对豁免」这条语义 | **1 failed** ✓（被 §4 那条新加的构造用例抓住） |
| ③ `_owners` 退化成「同名文件被声明过就算覆盖」 | 路径精确性 | **findings 9→9，惰性** |
| ④ B1 去掉「无卡认领」条件 | B1 的收窄条件 | **findings 9→9，惰性** |

③④ 判**惰性**不判「活下来」，依据是实测：两次变异后 `audit()` 的发现数与 live 数都没变
（9 / 0），也就是说这两处改动在当前数据上根本没有产生行为差异——**一个什么都没改变的变异
证明不了任何关于测试的事**。真要考住它们需要构造「同名文件」与「有主且被多卡共用」的数据，
本卡未做，如实登记（§7）。这一条本身就是 F-05 的教训：**别把「没红」当成「守住了」**。

## 6. verify 与全局门

```
verify_cmd: pytest tests/v041/test_outputs_declared.py -q
13 passed in 1.45s

python tools/check_outputs_declared.py   → 三类差异都只剩白名单里的历史条目，EXIT=0
ruff check . --no-cache                  → All checks passed!
```

## 7. self_review（§4.6）

**① 测试 ↔ acceptance 逐条映射**

| acceptance | 测试 | 判据 |
|---|---|---|
| ① 报两类差异：声明了但仓库没有 / 隔离带产出被共用 | `test_a_declared_output_that_is_missing_is_red`（A）、`test_the_isolation_crack_is_reported_with_both_cards_named`（B1 真仓库）、`test_a_new_shared_orphan_between_isolation_cards_is_red`（B1 构造）、`test_an_isolation_output_used_from_outside_is_red`（B2 构造） | B1 那条同时断言**两张卡都被点名**——owner 要执行「划掉哪一张」就得知道另一张是谁 |
| ② 对 104 张卡跑出真实清单写进 trace | 本 trace §2 | `test_the_three_files_the_review_confirmed_are_all_caught` 把终检确证的三处钉成回归断言 |
| ③ 历史差异走显式白名单并列全、规则不放宽、新差异仍红 | `test_the_repo_has_no_new_difference`、`test_every_whitelisted_row_is_still_a_real_finding`、`test_the_whitelist_exempts_a_pair_not_a_path` + 四个构造用例 | 反向断言挡「过期豁免」，按对豁免挡「整路径开口子」 |

另有三条守判据设计不被悄悄改掉：`test_endpoint_shaped_outputs_are_listed_not_swallowed`、
`test_annotated_paths_resolve_to_real_files`、`test_a_package_marker_rides_along_with_its_sibling`
（后者两侧都测：有兄弟的放行、没兄弟的仍然红）。

**② 无冻结件偏离**：本卡零代码改动，只新增两个文件；`contracts/`、`contracts_v04/`、
`flint/domain/`、`requirements.lock` 一字未动，无新增依赖（只用 stdlib `ast`/`json`/`argparse`）。

**③ 禁用词**：两个产物文件扫描，六词 0 命中、收尾「等」0 命中。

**④ 复用断言**：白名单形态逐点复用 `tests/v041/test_ledger_pairing_v041.py` 的房规
（冻结闭集 + 逐条对 + 每条带理由 + NEVER 增补），并补了那里没有的反向断言（过期豁免检测）。
未复用 `tools/validate_dag_v04.py`：它校的是 DAG 结构（依赖环、单位、就绪性），
与「声明 ↔ 实况」是两件事，没有可复用的判据面。

**⑤ 装载预算**：约 17k tokens。

## 8. 顺序纪律（§4.2）

本卡**顺序仍然是工具先于测试**（GAUGE-04 的 trace 里我写了「下一张卡把顺序摆正」，又没做到）。
补偿仍是变异实测（§5），且这次变异 ② 真的抓出了一条缺失的断言（按对豁免），当场补上。
如实记两次：**连续两张卡在同一条纪律上偏离，这本身是个信号**——工具类卡的自然写法是
「先有工具才知道断言什么」，但 §4.2 没有为工具类卡开例外。这一条留给 owner/supervisor 裁决：
要么我改工作方式（先写一条最小失败断言再动工具），要么工单为工具类卡写明允许的顺序。

## 9. 登记未做（不自行扩面）

1. **三处少声明不补进 `tasks-v04.json`**：F-12 修法 1 说「把三个文件补进对应卡的 outputs」，
   但本卡 acceptance③ 明确要求历史差异走白名单，且 `tasks-v04.json` 是 v0.4 封版的机读真相
   （改它属 owner 面）。本卡只让差异**一直可见**，NEVER 自行改卡面。
2. **`mock_syntax.py` 的产权不定**：F-12 修法 2 是二选一（升为基线件 / 明确挂靠一张卡并在
   另一张卡面写明依赖），两条都要改 `tasks-v04.json` 或建新卡——owner 决定，本卡不代劳。
3. **「建了但 docstring 没写卡号」的文件看不见**：本卡判据的已知盲区（§3.1），
   补它需要 git 历史或台账逐条回源。
4. **变异 ③④ 未被真正考住**：需要构造「同名文件」与「有主且被多卡共用」的数据面（§5）。
5. **对账器未接进里程碑门清单**：`WORKORDER-v04.md#8` 的出口命令清单里没有这一条；
   它已经在 `pytest -q` 里（测试文件即入口），加不加进文档清单属 owner 口径。
