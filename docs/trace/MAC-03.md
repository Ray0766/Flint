# MAC-03 · ruff 与 mypy 回零（@2026-11-14）

出处：`docs/trace/MAC-02.md` §三丙类前四行。

## 一、装载清单

`tools/validate_dag_v04.py:1` · `harness/fe_smoke.py:275-285` · `eval/gate1.py:110-140` ·
`flint/gate/rule_d.py:25-56` · `flint/gate/engine.py:28-36` · `flint/jobs/gate1.py:640-680` ·
`harness/e2e_stack.py:60-82` · `flint/jobs/runner.py:25,61` · `pyproject.toml`。

## 二、判据先行的实况

本卡的 verify_cmd 就是两条门本身，起点是红的（`docs/trace/MAC-01.md` §7.3 的原样输出）：
ruff 1 条、mypy 3 条 / 371 文件。没有另写测试文件。

## 三、四处改动

| 位置 | 改了什么 | 为什么这么改 |
|---|---|---|
| `tools/validate_dag_v04.py` | 索引里的模式 `100644` → `100755` | 它有 shebang、文件头写着「单文件零依赖」，本来就是给人直接执行的。删 shebang 也能让 ruff 绿，那是为了过检查改掉文件的用法 |
| `eval/gate1.py:135` | `gaps=gaps` → `gaps=[d.hint for d in gaps]` | `derive_gaps` 回 `list[DerivedGap]`，`decide` 收 `list[GapHint]`。生产侧 `flint/jobs/gate1.py:654` 早就是这个写法，评测侧漏了 |
| `harness/e2e_stack.py:81` | 删掉 `# type: ignore[arg-type]` | `cfg.enqueue` 的类型是 `Callable[..., Any]`，传给 `EnqueueHook | None` 本来就过 |
| `pyproject.toml` | 新增一段 mypy override：`playwright.*` → `ignore_missing_imports` | playwright 按纪律不进 `.venv`。写在配置里而不是行内 `type: ignore`：行内那种写法在装了 playwright 的解释器里会反过来报 unused-ignore |

## 四、验证

- `ruff check .` → `All checks passed!`
- `mypy --strict flint eval harness` → `Success: no issues found in 371 source files`
- `eval/gate1.py` 那一行是评测金标 20 例走的路。改后跑
  `tests/m2/test_m2_045.py tests/m2/test_m2_047.py tests/m2/test_m2_052.py tests/m3/test_m3_025.py`
  全过；重新生成的 `docs/trace/goldcases/*.md` 与入库那份 `git diff --ignore-cr-at-eol` 无差异
  （判定结果一个字没变，只有换行不同，已还原，见 `MAC-07`）。

## 五、登记、没有动的

`.github/workflows/ci.yaml:31` 跑的是 `mypy --strict flint`，不含 `eval` 与 `harness`；
`Makefile` 的 `gate` 与 `docs/macOS-安装.md` §六写的是三个包。两处口径不一，这三条 mypy 红
就是从那道缝里攒出来的。CI 里还钉着 Python 3.11（`docs/blocked/CLAUDE-S3-LAG.md` 那件未决事），
本卡没有碰 CI。
