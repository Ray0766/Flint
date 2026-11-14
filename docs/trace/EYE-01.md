# EYE-01 · ui_probe 加断言模式：让「看得见」能当 verify_cmd 用

**卡** `docs/steward/tasks-v041-b2.json#EYE-01` · **批次** v0.4.1 第 2 批 · **开工** 2026-08-03T23:02Z

## 1. 装载清单

| 装载物 | 来源 | 用途 |
|---|---|---|
| 卡面 EYE-01 | `tasks-v041-b2.json` | acceptance / outputs / verify_cmd |
| `scripts/ui_probe.py` 全文（166 行） | inputs | 被改的真件 |
| `docs/steward/连跑工单-v041-第2批.md#B 组` | 追加 | 「缺的不是工具，是把它变成机器能判的判据」 |
| `docs/review/终检-v04.md#F-09`（结论段） | 追加 | 「空 span 占 0 像素」——`visible:` 判据的由来 |
| `requirements.lock` / `pyproject.toml` / `web/package.json` 的 playwright 命中（grep） | acceptance④ | 基线：三处均 0 |

装载约 12k tokens。

## 2. 顺序纪律：本卡把 §4.2 摆正了

前三张卡（GAUGE-04/05/06）都是实现先于测试落盘，trace 里连记三次。本卡**先写测试、先跑红**：

```
写完 tests/v041/test_ui_probe_contract.py，动实现之前跑：
    16 failed, 1 passed
```

唯一那条绿的是 `test_playwright_is_absent_from_all_three_dependency_files`——它量的是一条
**既有不变量**（playwright 不在三处依赖清单里），本来就该是绿的。**红得对、绿得也对**。
实现完成后 17 passed。

## 3. 做了什么（acceptance 逐条）

### ① `--json`：结构稳定的观测报告

`SCHEMA = "ui-probe/1"`，顶层键固定为 `schema / pages / problems / assertions / ok / frontend_down`，
每屏观测键固定为 15 个（页高、scrollWidth、视口宽、横向溢出、控制台报错与计数、
html.class、data-theme、token 取值、选择器 boundingBox…）。
**键集即契约**：断言消费方照着它写，改键就是破约，`test_the_report_shape_is_the_documented_one`
把这份键集逐字钉住。

`--json` 时人读的行全部闭嘴（`quiet`）——一行人读文字混进去，输出就不再是 JSON。

### ② `--assert`：三种判据，逐屏判，点名

```
no-console-errors          该屏控制台 error 数 == 0
no-horizontal-overflow     该屏无横向溢出
visible:<css>              该选择器存在**且宽高均 >0**
```

`visible:` 是照着 F-09 那条缺陷设计的：`querySelector(...) !== null` 对一个
「DOM 里有、宽高是 0」的空 span 照样通过，而用户什么都看不见。所以判据要的是
**boundingBox 宽高均 >0**，并且「找不到」与「找到了但 0×0」给的是**两句不同的话**——
前者去查渲染没渲染，后者去查样式，修法不同。

**逐屏判**（主题 × 视口 × 页面），不是只判第一屏：横向溢出最容易出现在移动端，
只判桌面等于把它放走。`test_every_page_is_judged_not_just_the_first` 守着。

**认不出的判据当场报错**（`parse_criterion` 抛 `ValueError`），NEVER 当成通过——
默默跳过一条拼错的判据，等于让写它的人以为自己守住了某件事。

一处主动设计：**判据里点名的选择器自动进观测面**。写了 `--assert visible:.mark` 却忘了
`--selector .mark` 的话，它会恒判「找不到」——那是一条**假红**，它说的是探针没量，不是页面没有。

### ③ 三种红互不冒充（本卡最要紧的一条）

```
0  一切正常
1  判据不满足 / 观测到问题（横向溢出、控制台 error）
2  playwright 不在当前解释器里     → 修法：用 C:\pwenv 的解释器
3  前端没起（连接被拒）            → 修法：start-demo.bat
```

**3 的判定优先于 1**：前端没起时判据当然全不满足，但那时候报「选择器不可见」
会把人送去改一个并不存在的 bug。分类靠报错文本里的连接类标记
（`ERR_CONNECTION_REFUSED` / `ECONNREFUSED` / …）；**超时 NEVER 算进去**——
超时可能是页面自己卡住了，那是真 bug。

**真跑取证**（`C:\pwenv` 解释器，前端确实没起）：

```
$ C:\pwenv\Scripts\python.exe scripts/ui_probe.py --url http://localhost:3001/ \
      --theme dark --desktop-only --assert no-console-errors --assert=visible:body
前端未运行：连接被拒。**这不是判据不满足**——判据的红要改代码，这条红要起服务：
    start-demo.bat   （后端 :8000 + 前端 :3000）
[dark/desktop] url1: 打不开 http://localhost:3001/ -> Error（前端没起）
EXIT=3

$ …… --json
{"schema": "ui-probe/1", "pages": [], "problems": 0, "assertions": [],
 "ok": false, "frontend_down": true}
EXIT=3
```

### ④ playwright 恒在项目外

`test_playwright_is_absent_from_all_three_dependency_files`：`requirements.lock` /
`pyproject.toml` / `web/package.json` 三处命中恒为 0（实测 0/0/0）。
另有 `test_the_cli_reports_frontend_down_without_a_browser`：用**项目解释器**跑 CLI，
必须退 2 并指向 `C:\pwenv`——真把 playwright 装进项目 .venv 的话，这条会红。
两条一正一反地钉住同一件事。

## 4. 变异考

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① `for page in pages[:1]` | 逐屏判 | **1 failed** ✓ `test_every_page_is_judged_not_just_the_first` |
| ② `if False:` 取消 frontend_down 优先 | 三种红的分层 | **1 failed** ✓ `test_frontend_down_beats_assertion_failure` |

两次均从备份还原，还原后 17 passed。

## 5. 改既有文件（`scripts/ui_probe.py`，本卡 outputs 内）

**改前**：只有人读输出，`probe()` 返回一个 `problems` 计数，`main()` 按它 `exit 1`。
判据、结构化报告、选择器量测、前端没起的分类**全都没有**。
**改后**：新增 `SCHEMA` / 四个 `EXIT_*` 常量 / `looks_like_frontend_down` / `parse_criterion` /
`evaluate` / `build_report` / `exit_code` 七个**纯函数面**（与浏览器解耦，故项目 .venv 下可测），
`probe()` 改为返回 `(每屏观测, 前端是否没起)`，`main()` 增 `--json` / `--selector` / `--assert`。
**为什么非改不可**：卡面 outputs 第一项就是它；工单 B 组原话「缺的不是工具，是把它变成能当
`verify_cmd` 用的判据」。
**兼容性**：不带新参数时的行为与改前一致（人读输出 + 干净退 0 / 有问题退 1），
默认 URL、视口、token 清单一字未动。

## 6. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_ui_probe_contract.py -q   → 17 passed
ruff check . --no-cache → All checks passed!
```

**① 测试 ↔ acceptance 映射**

| acceptance | 测试 |
|---|---|
| ① `--json` 结构稳定 | `test_the_report_shape_is_the_documented_one`、`test_a_selector_observation_carries_its_box_and_visibility`、`test_the_json_report_round_trips` |
| ② `--assert` 不满足即非零并点名 | `test_visible_criterion_fails_a_zero_sized_element_and_names_it`、`test_visible_criterion_passes_a_real_box`（正例）、`test_a_missing_selector_is_red_and_says_it_was_not_found`、`test_console_and_overflow_criteria_bite`、`test_every_page_is_judged_not_just_the_first`、`test_an_unknown_criterion_is_rejected_at_parse_time` |
| ③ 前端没起单独报、单独码 | `test_a_refused_connection_is_classified_as_frontend_down`、`test_a_real_page_error_is_not_classified_as_frontend_down`（反向）、`test_the_three_failures_have_three_different_exit_codes`、`test_frontend_down_beats_assertion_failure` + §3 真跑输出 |
| ④ playwright 三处命中 0 | `test_playwright_is_absent_from_all_three_dependency_files`、`test_the_cli_reports_frontend_down_without_a_browser`、`test_the_probe_module_imports_without_playwright` |

每条判据都配了**正例**（不只测红）：`visible:` 有真尺寸的绿、控制台与溢出干净时的绿、
「页面自己报错不算前端没起」的反向分类。

**② 无冻结件偏离**：`contracts/`、`flint/domain/`、`requirements.lock`、`pyproject.toml`、
`web/package.json` 一字未动（后三者本卡还专门断言了它们不含 playwright）。零新增依赖：
新代码只用 stdlib `json` / `argparse` / `typing`。

**③ 禁用词**：两个文件扫描，六词 0 命中、收尾「等」0 命中。

**④ 复用断言**：复用既有 `probe()` 的观测口径（页高/溢出/控制台/token 一字未改），
只把它们**结构化**；NEVER 另写一套量测。

**⑤ 装载预算**：约 12k tokens。

## 7. 登记未做

1. **正向真跑（前端起着、判据全绿）本卡没做**：真起栈逐屏取证是 EYE-03 的面
   （「起真栈、逐屏 200、零控制台报错、截图存档」）。本卡验的是判据面本身，
   真起栈那半在 EYE-03 里跑，届时这把尺子会被第一次真正用上。
2. **默认 URL 仍是 `localhost:3001`**，而工单说本机栈是 `:3000`（后端 :8000）。
   改默认值会影响 supervisor 既有跑法，属口径面，本卡 NEVER 顺手改——EYE-03 起栈时
   按实际端口传 `--url`，若届时确认 3001 是旧值，由那张卡带着证据改。
3. **判据只有三种**：颜色对比度、字号、焦点可见性这类无障碍判据没做（EYE-02 的面）。
