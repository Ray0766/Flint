# GAUGE-04 · F-08 修复：vitest 混合过滤器静默少跑

**卡** `docs/steward/tasks-v041-b2.json#GAUGE-04` · **批次** v0.4.1 第 2 批 · **开工** 2026-08-03T22:04Z

## 1. 装载清单（inputs 来源）

| 装载物 | 来源 | 用途 |
|---|---|---|
| 卡面 GAUGE-04 | `tasks-v041-b2.json` | acceptance / outputs / verify_cmd |
| `docs/review/终检-v04.md#F-08` 全节 + C1 段 | context_refs | 缺陷判词、两组实测数字 |
| `WORKORDER-v04.md` 里 27 条 `npm test` 行（grep，未整本读） | context_refs | 扫描面与被改的两行 |
| `docs/PRINCIPLES-v04.md:37/51` | 追加 | 另一处 vitest 命令（GAUGE-01 已修好重映射） |
| `web/vitest.config.ts` + 58 个测试文件清单 | 追加 | 匹配语义与标定 |
| `tools/_scan_lib.mjs` / `tools/no_hardcoded_models.mjs` 头部 | 追加 | .mjs 扫描器的房规（用法行、判据段、注释密度） |
| `tools/check_principles_doc.py` / `check_techplan_delta.py` 的工单读取面 | 追加 | 判定改工单是否波及既有尺子 |

装载约 19k tokens，未超 40k。

## 2. 实测：文档写的应跑数 vs 实际跑到数（acceptance②）

本机真跑 vitest（`cd web && npm test -- --run …`，2026-08-04），**与终检 F-08 的数字逐个一致**：

| 门 | 按修前写法 | 按重映射本意 | 静默漏掉 | 退出码 |
|---|---|---|---|---|
| V3（`WORKORDER:527`） | **21 文件 / 143 tests** | 31 文件 / 225 tests | **82 tests** | 两种写法都 EXIT=0 |
| V4（`WORKORDER:528`） | **1 文件 / 6 tests** | 16 文件 / 128 tests | **122 tests** | 两种写法都 EXIT=0 |
| 前端全量（无过滤器） | — | 58 文件 / 524 tests | — | EXIT=0 |

**V4 图谱工作台的里程碑门按修前的文档跑，只跑到 128 条里的 6 条——4.7%——并且报绿。**

病灶不是「过滤器写错了」，是**vitest 对匹配不到的过滤器静默丢弃、只要有一个命中就 exit 0**。
终检实测过两种形状的对照，本卡照跑复现：

```
A 只给不存在的过滤器：  npm test -- --run src/views
  → No test files found, exiting with code 1     ← 大声失败，这种没问题
B 混合过滤器（文档里的形状）：npm test -- --run components src/views
  → Test Files 21 passed / Tests 143 passed，EXIT=0   ← 静默丢掉 src/views，报绿
```

`--passWithNoTests=false` 之类的兜底判的是「一个文件都没匹配到」，而混合过滤器**匹配到了**，
只是少了一大半。**挡得住的判据只有一个：逐个过滤器数它的匹配数。**

## 3. 产物

### 3.1 `tools/check_vitest_filters.mjs`（acceptance①）

扫描文档里每条 `npm test -- --run …`，逐个过滤器求它匹配到的测试文件数；**任一为 0 即红并点名**，
并给出补救建议（逐段砍掉开头找能命中的那一截——`src/lib/undo` → `lib/undo`）。
`--json` 供 pytest 消费。默认扫描面 = `WORKORDER-v04.md` + `docs/PRINCIPLES-v04.md`。

**匹配语义是对着真 vitest 标定的，不是照文档猜的**——四个点逐个对上：

| 过滤器 | 校验器数出 | 真 vitest |
|---|---|---|
| `components` | 21 文件 | Test Files 21 |
| `components/graph-node` | 1 文件 | 1（6 tests） |
| `components views` | 31 文件 | 31（225 tests） |
| V4 本意的五个过滤器 | 16 文件 | 16（128 tests） |

判据 = 过滤器是**测试文件相对 `web/` 路径**的子串。**只拿相对路径比**：仓库目录名里若含
`web` / `components` 这类词，绝对路径会让任何过滤器都「匹配得到」——那正是这把尺子要防的假绿。

**「扫到 0 条命令」也判红**：文档改名、章节重排、命令换写法都会让扫描器一条都扫不到，
那时候报绿等于说「我检查过了，没问题」而其实什么都没检查——F-11 就是这么长出来的
（`check_principles_doc.py` 红了三天，因为它根本不在全局门里）。

### 3.2 `tests/v041/test_vitest_filters.py`（acceptance③ + 接进全局门）

10 条。**NEVER `pytest.skip`**：`node` 找不到时这条门红，不是消失——一把会自己消失的尺子
正是 F-08 的成因（GAUGE-02 清点出 17 条 acceptance 由工具脚本守着而没有任何 `tests/` 文件起它，
本卡把其中一把接进了 `pytest -q`）。

## 4. 用三个变异体反过来考自己的测试（本卡最值得记的一段）

写完发现顺序反了（工具先于测试落盘，§4.2 要求相反），于是没有走「先跑一次红」的形式，
而是用 GAUGE-03 刚建的那条判据反过来考自己：**把机制抽掉，守它的测试必须红**。
三个变异体逐个真跑（改真文件 → 跑 → 从备份还原，还原后 sha256 逐字节复原）：

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① `if (false && dead.length > 0)` | 0 命中不再判红 | **1 failed** ✓ 被 `test_a_filter_that_matches_nothing_is_named` 抓住 |
| ② 只扫裸文本、不认反引号内联段 | 扫描面塌掉（文档里的命令全在反引号里） | **8 failed** ✓ |
| ③ 匹配改成「绝对路径也算」 | 相对路径语义没了 | **9 passed —— 活了下来** ✗ |

**变异 ③ 是本卡真正的收获**：那一刻我的十条断言里没有任何一条量得出「匹配必须相对」，
而工具头部的注释白纸黑字写着这件事。**注释声称的、测试没量的，就是下一个 F-08。**

补法：`test_matching_is_relative_to_web_not_absolute` —— 用 `web` 当分界样本。这一串必定在每个
测试文件的**绝对**路径里（它就是 web 根的目录名），却不在任何**相对**路径里（相对路径以
`components/` `design/` `lib/` `stores/` `views/` 开头）。于是：相对语义 → 0 命中（红，正确）；
绝对语义 → 58 命中（绿，假的）。补完重考变异 ③：**1 failed** ✓。

还原核对：`tools/check_vitest_filters.mjs` sha256 前缀 `60654e9233e2595d`，与三次变异前的备份一致。

## 5. 改既有文件（本批 §2 要求逐处写「改前 / 改后 / 为什么非改不可」）

### 5.1 `WORKORDER-v04.md:527/528`（两行文本、5 个 token）

**改前**
```
527: … `cd web && npm test -- --run components src/views`
528: … `cd web && npm test -- --run components/graph-node src/components/graph-edge src/lib/undo src/lib/graph-layout src/views`
```
**改后**
```
527: … `cd web && npm test -- --run components views`
528: … `cd web && npm test -- --run components/graph-node components/graph-edge lib/undo lib/graph-layout views`
```
**为什么非改不可**
1. **终检 F-08 的修法逐字就是这两行**（原话「两行文字替换，`src/views`→`views`、…」）；卡名即「F-08 修复」。
2. 不改，这把新尺子在真文档上恒红，于是它会被当成「已知红」绕过去——**而「有尺子但没人拿起来」
   正是本批 A 组要治的病**（GAUGE-02 清点出的第二格）。修好之后
   `test_the_repo_milestone_gates_are_clean` 把它变成常绿不变量：将来任何人往门里写一个匹配零文件的
   过滤器，`pytest -q` 当场红。
3. 无语义改动：改的是路径前缀，命令的意图（跑哪些前端测试）一字未变，且修后实跑数与本意一致
   （21→31 文件、1→16 文件，与真 vitest 对上）。

**波及面已核实，不是假设**：
- `tools/check_principles_doc.py` 只哈希工单 **§3**（`extract_section` 取 `## §3 ` 到下一个 `## `）——
  527/528 在 §8，**区外**；
- `tools/check_techplan_delta.py` 只从工单收 CamelCase 类型名与 `Literal` 定义——本次没动任何类型名；
- 改后复跑 `pytest tests/v041/test_doc_gates.py tests/v04/principles -q` → **14 passed**（六把文档尺 + 旧 5 条）。

**卡面 outputs 只列了两个新文件**，本次改动超出 outputs 一处，故按 worker.md §4.3③
（≤3 行影响）登记 **DEC-030** 一行继续，NEVER 埋在 trace 里不上报。

### 5.2 `DECISIONS-v04.md`（追加 DEC-030 一条）

**改前**：末条为 DEC-029。**改后**：追加 DEC-030（内容即 §5.1 的登记）。
**为什么非改不可**：worker.md §4.3③ 指定的就是这个通道；append-only，历史条目一字未动。

### 5.3 `docs/progress-v041.jsonl`

追加 `started` / `verified` 两行（本卡）。append-only，历史行未动。

**除以上三处，零既有文件改动**——`flint/` 与 `web/` 下一个字节都没动。

## 6. verify 与全局门

```
verify_cmd: pytest tests/v041/test_vitest_filters.py -q
10 passed in 0.73s

node tools/check_vitest_filters.mjs        → 全部 27 条命令、32 个过滤器均有命中，EXIT=0
ruff check . --no-cache                    → All checks passed!
pytest tests/v041/test_doc_gates.py tests/v04/principles -q → 14 passed
```

## 7. self_review（§4.6）

**① 测试 ↔ acceptance 逐条映射**

| acceptance | 测试 | 判据 |
|---|---|---|
| ① 逐个过滤器求匹配数，任一为 0 即红并点名 | `test_a_filter_that_matches_nothing_is_named`、`test_a_mixed_filter_is_red_although_vitest_itself_exits_zero` | 后者钉的正是 F-08 的形状：vitest EXIT=0（21 文件 /143 tests）而校验器红，且 `dead == ["src/views"]` |
| ② V4 门真实数字写进 trace | 本 trace §2（真跑 vitest 五次） | `test_the_file_counts_agree_with_what_vitest_really_ran` 把那些数字钉成断言，不是写在文档里的自述 |
| ③ 阴性对照（含不存在路径 → 红）+ 正例（全命中 → exit 0） | `test_a_filter_that_matches_nothing_is_named` / `test_a_command_whose_filters_all_hit_exits_zero` | 两条一对：少了正例，一把见谁都报红的尺子也能过反例 |
| （自加）扫描面不塌 | `test_every_milestone_gate_command_is_scanned` | 不信扫描器自述，直接数原文里 `npm test -- --run` 的出现次数 |
| （自加）匹配语义 | `test_matching_is_relative_to_web_not_absolute` | 变异 ③ 暴露的洞，见 §4 |
| （自加）门恒清洁 | `test_the_repo_milestone_gates_are_clean`、`test_the_v4_gate_line_names_all_sixteen_files` | 把一次性修复变成常绿不变量 |

无 `assert True`、无只测 happy path：正例/反例成对，且三个变异体实测有两个被抓、第三个补断言后也被抓（§4）。

**② 无冻结件偏离**：本卡未碰 `contracts/`、`contracts_v04/`、`flint/domain/`，无新增依赖
（`node` 与 `web/node_modules` 都是既有的，`requirements.lock` / `package.json` 一字未动）。

**③ 禁用词**：两个产物文件扫描，六词 0 命中、收尾「等」0 命中。

**④ 复用断言**：复用 `tools/` 既有 .mjs 扫描器的房规（用法行 + 判据段 + 注释密度）。
未复用 `_scan_lib.mjs` 的 `codeOnly`——本卡扫的是 **markdown 文档**里的反引号内联代码段，
不是 JS 源码的注释剥离，两者判据不同；强行复用会把文档里的 `//` 当注释剥掉。此处记明理由。

**⑤ 装载预算**：约 19k tokens，未超 40k。

## 8. 顺序纪律如实记（§4.2）

工具先于测试落盘，与「先写失败测试」相反。GAUGE-03 的 trace 里我写了「下一张卡恢复顺序」，
**这一张没做到**，如实记。补偿手段是 §4 的三个变异体实跑（比形式上的红更强：它量的是
「测试能不能抓住实现变坏」，而不是「实现还没写时测试会不会报错」），且第三个变异体真的
抓出了一条缺失的断言。下一张卡把顺序摆正。

## 9. 登记未做（不自行扩面）

1. **另外五把 .mjs 扫描器仍在全局门外**：`i18n_scan` / `no_hardcoded_models` / `no_external_fonts` /
   `lint_no_confidence_viz` / `scan_ds_assets`（GAUGE-02 登记的 11 条 acceptance）。本卡只把
   `check_vitest_filters` 一把接进 `pytest -q`，其余不在本卡 acceptance 内。
2. **前端 51 条 acceptance 由 vitest 守、而全局门只有 `ruff + mypy + pytest`**：本卡让「命令写得对」
   可验，但「那些命令有没有被跑」仍是 GAUGE-02 登记的口径问题（扩门加一条 `npm test` 还是接受
   单独跑，属 owner 口径，不自决）。
3. **`--passWithNoTests` 未加**：加了也挡不住混合过滤器（§2 已论证），本卡不动 vitest 配置。
