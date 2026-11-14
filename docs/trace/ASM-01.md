# ASM-01 · 组稿生成器注入 — trace

批次：v0.4.1 第 1 批（`docs/steward/tasks-v041.json`）。台账：`docs/progress-v041.jsonl`。

## 装载清单（实际）

| 来源 | 用途 |
|---|---|
| `CLAUDE.md#S2+S3` | 不变量与契约纪律 |
| `worker.md` 全文 | 执行纪律（含 §9 并行） |
| `docs/steward/连跑工单-v041-第1批.md` 全文 | 本批口径与触碰边界 |
| `docs/steward/tasks-v041.json`（ASM-01 卡） | 卡面真相 |
| `flint/jobs/compose.py` 全文 | `ComposeDeps` / `_default_generator` / `build_offline_compose_deps` |
| `flint/compose/llm_generator.py` 全文 | `llm_generator_factory` 签名与闭包形状 |
| `flint/jobs/regenerate_job.py` 全文 | 既有的真生成器接线先例（复用其口径） |
| `flint/compose/draft_channels.py` | `draft_section_with_channels` 签名 |
| `tests/fe_core/test_prod_generator.py` | 录制回放 provider（MockTransport）先例 |
| `tests/conftest.py` | 测试库闸口径（确认 `FLINT_TEST_DSN` 未设 = 默认 `flint_test`） |
| `harness/demo_server.py` 1–200 行 | 生产装配的既有姿态（prompt/profile/template 取法） |
| `eval/ledger_append.py` | 台账写守卫 |

实际装载约 21k tokens（≤40k 预算）。

## 断点与决策

1. **零修改边界（工单 §3）守住**：本卡产出仅两个新增文件 —— `flint/jobs/compose_deps.py`、
   `tests/v041/test_asm_01.py`。`flint/jobs/compose.py` 一字未动，`build_offline_compose_deps`
   与 `_default_generator` 原样保留。
2. **模板默认取 `generic.yaml`**：`assets/templates/` 下无 `report.yaml`（`harness/demo_server.py:146`
   指向的那个文件其实不存在——**这是既有文件的既有问题，本批不碰**，只在此记一笔）。生产装配
   默认用真实存在的 `generic.yaml`，且模板缺失时抛 `FileNotFoundError` 并点名文件，NEVER 静默继续。
3. **prompt 取自锁定文件**：`load_prompt(repo_root/"prompts", "section_draft@1", enforce_lock=True)`，
   复用 `flint/llm/prompts.py` 既有实现（H 组复用），NEVER 在装配里内嵌一份 prompt 副本。
4. **缺件抛错的类型**：新增 `ComposeProviderMissing(RuntimeError)`。它不是冻结件类型，只是本模块
   的局部错误类，不进 `contracts/`。
5. **一次返工**：`test_production_assembly_never_references_default_generator` 首轮用文本 `in` 判断，
   被自己 docstring 里的说明字样判红（假红）。改为 AST 面判断（`ast.Name` / `ast.Attribute` /
   `ImportFrom` 三类标识符），并加反例断言——同款检查在 `compose.py` 上必须认得出那里确有引用，
   证明不空转。返工 1 轮，未触 §4.4 的 3 轮上限。

## 自审报告（self_review=true）

### ① 测试真实覆盖 acceptance（测试名 ↔ acceptance 映射）

| acceptance | 测试 |
|---|---|
| ① factory 绑 `llm_generator_factory`，NEVER 是 `_default_generator` | `test_generator_factory_is_bound_to_llm_generator_factory`（三重断言：不是占位对象 / `__module__` 是 `flint.compose.llm_generator` / `__qualname__` 是 `llm_generator_factory.<locals>.factory`） |
| ② 录制回放 provider 草拟一节 → 有 `type=="paragraph"` 且正文非空 | `test_drafted_section_contains_non_empty_paragraph`（正文取 `assets/prod_caliber/qwen3.6_27b.json` 已录制的真实 qwen3.6 产出）+ **反例** `test_placeholder_degradation_is_detected_by_the_same_assertion`（占位产出只有 heading 且 text == section_id，证明上一条断言认得出退化） |
| ③ 未注入 provider → 显式抛错说明缺什么，NEVER 静默回落 | `test_missing_provider_raises_and_names_what_is_missing`（断言报错点名 `provider` 与 `LLMProvider`）+ `test_missing_provider_never_falls_back_to_placeholder`（断言不以任何形式返回 deps）+ `test_missing_template_raises_instead_of_silently_proceeding`（模板缺失同款姿态） |
| ④ 占位保留但仅供显式 offline，其调用点不在生产装配路径 | `test_default_generator_kept_for_explicit_offline_use`（占位仍在，且离线装配仍绑它）+ `test_production_assembly_never_references_default_generator`（AST 面 + 反例）+ `test_default_generator_is_not_invoked_on_the_production_path`（monkeypatch 成会抛的函数，生产路径若还调它立刻红） |

无 `assert True`；反例用例 3 条（占位退化 / 缺 provider / 缺模板）。

### ② 无冻结件偏离

`contracts/` 与 `flint/domain/` 一字未动（本卡零修改既有文件）。装配返回的就是 `compose.py` 既有
的 `ComposeDeps`，未另立形状——`test_deps_is_the_frozen_compose_deps_shape` 断言 `isinstance`。

```
$ python -m mypy --strict flint/jobs/compose_deps.py
Success: no issues found in 1 source file
```

### ③ 无禁用词

```
$ grep -nE "适当|合理|必要时|大约|尽量|若干" flint/jobs/compose_deps.py tests/v041/test_asm_01.py
（无输出）
```

### ④ 复用断言在位

- 复用 `flint.compose.llm_generator.llm_generator_factory`（未新写生成器）→ `test_generator_factory_is_bound_to_llm_generator_factory` 断言其 `__module__`/`__qualname__`。
- 复用 `flint.llm.prompts.load_prompt` → `test_prompt_text_comes_from_locked_prompt_file` 断言生成 prompt 的开头逐字等于锁定 prompt 正文。
- 复用 `flint.compose.draft_channels.draft_section_with_channels` 门 → 两条草拟用例都经它。
- 复用 `flint.jobs.compose.ComposeDeps` → `test_deps_is_the_frozen_compose_deps_shape`。

### ⑤ 装载未超预算

约 21k tokens < 40k。

## 产出文件

- `flint/jobs/compose_deps.py`（新增）
- `tests/v041/test_asm_01.py`（新增，11 条用例）

## verify

```
$ python -m pytest tests/v041/test_asm_01.py -q
11 passed in 0.64s
$ python -m ruff check flint/jobs/compose_deps.py tests/v041/ --no-cache
All checks passed!
```
