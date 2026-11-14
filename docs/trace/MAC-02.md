# MAC-02 · 门禁红项三分类 + 开卡清单（@2026-11-14）

owner 2026-11-14 指令：全权接手，按队列往下跑；门禁红项分三类记下来，真问题逐个开卡修。
不在 `tasks.json` 的 DAG 里，卡号接 `MAC-01`。

## 一、装载清单

| 装了什么 | 为什么 |
|---|---|
| `docs/trace/MAC-01.md` §七 | 82 条红的逐条现象与原因，本卡只做归类 |
| 三遍全量 pytest 的输出（会话内，未入库） | 红项清单与 skip 原因的出处 |
| `docs/trace/B17-PLAN.md`、`docs/trace/REPORT-SRC-01.md` | 分清哪些红是第 17 批留下的 |

## 二、起点数字（最终树单跑，2026-11-14）

- `ruff check .`：1 条
- `mypy --strict flint eval harness`：3 条 / 371 文件
- `pytest -q`：`79 failed, 5364 passed, 354 skipped, 3 errors`

## 三、三分类

### 甲、环境造成的——6 条 pytest

| 条数 | 用例 | 缺什么 | 去向 |
|---|---|---|---|
| 3 | `test_job_denied_state` ×2、`test_sse_live` ×1 | 演示库里没有 `m1004-j` 与 `probe-owned-ingest` 两条作业 | `MAC-05` |
| 3 | `test_m3_035` ×3（setup error） | 本机没构建 `flint-pdf:69` 镜像 | `MAC-05` |

### 乙、缺 `.ui-probe/` 产物的——68 条红 + 354 条 skip

`.ui-probe/` 没有进仓。同样是缺产物，354 条按「本机没跑过取证」skip，68 条直接红：
`test_combo_wire` 7 · `test_eye04` 6 · `test_eye05` 11 · `test_fav_card` 6 ·
`test_palette_onscreen` 2 · `test_palette_v4` 1 · `test_tail_01` 3 ·
`test_theme_really_switches` 3 · `test_ui_mainchain` 6 · `test_ui_restyle` 7 ·
`test_wb_annotate` 2 · `test_wb_cards` 2 · `test_wb_generate` 2 · `test_wb_layout` 6 ·
`test_wb_preview` 2 · `test_wb_sections` 2。去向 `MAC-06`。

### 丙、真问题——ruff 1 + mypy 3 + pytest 8，另加 1 条不红的

| 来源 | 位置 | 问题 | 去向 |
|---|---|---|---|
| ruff | `tools/validate_dag_v04.py:1` | 有 shebang 而索引里没有可执行位 | `MAC-03` |
| mypy | `harness/fe_smoke.py:281` | playwright 没有类型桩 | `MAC-03` |
| mypy | `eval/gate1.py:135` | `list[DerivedGap]` 传给收 `list[GapHint]` 的 `decide` | `MAC-03` |
| mypy | `harness/e2e_stack.py:81` | 多余的 `type: ignore` | `MAC-03` |
| pytest | `test_theme_toggle` ×1 | 子进程直接叫 `python` | `MAC-04` |
| pytest | `test_workbench_persist` ×1 | 写死 `.venv/Scripts/python.exe` | `MAC-04` |
| pytest | `test_job_denied_state` ×1、`test_screen_data_refetch` ×1 | `shell=True` 配参数列表，POSIX 上参数丢失 | `MAC-04` |
| pytest | `test_translator` ×1 | 白名单前缀写的是反斜杠路径 | `MAC-04` |
| pytest | `test_gauge_map` ×1 | `sorted(Path)` 的顺序随平台不同 | `MAC-04` |
| pytest | `test_m3_058` ×1 | 判据钉着「PDF 引擎不可用 → 503」，本机引擎可用 | `MAC-04` |
| pytest | `test_decisions_landed` ×1 | 水位钉 DEC-060，实为 064 | `MAC-04` |
| 不红 | 回放与 pytest 的落盘 | 70 个入库文件每跑一遍被重写（CRLF → LF） | `MAC-07` |

6 + 68 + 8 = 82，与 pytest 的 79 failed + 3 errors 对得上。

## 四、要 owner 裁决、本卡不动的

1. `requirements.lock` 没钉 weasyprint / python-docx 的 13 个传递依赖，`pytest-asyncio` 不在锁里
   （`docs/trace/MAC-01.md` §7.5 第 2、3 条）。改锁文件属 owner 通道；
2. Python 3.11 与 3.13 的未决项（`docs/blocked/CLAUDE-S3-LAG.md`）。

## 五、卡单

| 卡 | 做什么 | verify_cmd |
|---|---|---|
| `MAC-03` | ruff 与 mypy 回到零条 | `ruff check . && mypy --strict flint eval harness` |
| `MAC-04` | 8 条判据自身的问题 | 那 8 条用例逐条点名跑 |
| `MAC-05` | 演示库两条探针作业 + PDF 镜像，进起栈流程或文档 | `pytest tests/v041/test_job_denied_state.py tests/v041/test_sse_live.py tests/m3/test_m3_035.py -q` |
| `MAC-06` | 缺 `.ui-probe/` 产物时的口径统一 | 乙类 16 个文件 |
| `MAC-07` | 落盘生成物的换行 | 跑完回放与全量 pytest 后 `git status` 干净 |
