# HOTSPOT-04 trace — AI 深度分析按钮 → 既有 JobRunner（计费落点为配置开关）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#HOTSPOT-04`；
- context_refs：`contracts/protocols.py#JobRunner`（第 115~130 行）、
  `WORKORDER-v04.md#5-C`（C8 一行）、`WORKORDER-v04.md#7`（K7 行）、
  `WORKORDER-v04.md#6`（H7 行）、`contracts_v04/models_v04.py#JobKind/AnalysisContext`；
- 前置产物（按 inputs 定位）：`flint/jobs/runner.py`（PgJobRunner.submit 面）、
  `flint/config.py`（FeatureFlags + DEFAULT_FLAGS.billing_enabled）、
  `flint/i18n/name_display_job.py`（H7 同款「只产 payload、不新写 runner」先例）、
  `flint/jobs/gate1.py` 首 20 行（编排在哪、provider 怎么注入）、
  `flint/llm/production.py` 首 60 行（既有计价口径：价目由配置给、NEVER 内置价表）。
- 实测装载 ≈ 26k tokens，未超 40k 预算。

## 2 关键设计判断

**深度档不是新 JobKind**：契约 `JobKind` 没有 `deep_analysis`，加一个就要改冻结件
（S2-1 NEVER）。而「深度」本来就是同一条 `gate1_analysis` 链路的**档位差异**，
故 `kind` 保持契约值、`tier="deep"` 写进 payload。

**提交面零 LLM**：按钮按下到作业入队之间一次模型调用都没有——模型工作在
`flint/jobs/gate1.py` 的 worker 内发生。`provider` 参数保留为**显式接口缝**
（`del provider` 明写不调用），是为了让接线处有一个落点，而不是让人到别处去
new 一个真 provider。

**计费三条纪律**（都对应一种事后很难查的坏状态）：
1. 开关开、落点没接 → 抛 `ChargeLandingMissing` 且**作业未提交**。静默跳过等于把
   付费运行免费送出去，而这些运行一条记录都没有；「既不计费又照跑」比报错糟得多。
2. 金额**只能由配置给出**（`DeepAnalysisPricing` 两字段无默认值）。内置默认价会在
   没人注意时变成实际收费口径，而它的出处只有代码本身。
3. 落点抛错时异常里**带 job_id**：作业已经建好，不带的话它就成了一次无人认领的运行。

**为什么先检查落点再提交**：顺序反过来的话，开关打开而落点缺失时会留下一个
已入队、无账可查的作业——而它照样会花掉模型钱。

## 3 test-first 顺序（§4.2）

1. 先写 `tests/v04/hotspot/test_deep_job.py`（12 条）→ 跑 → 红
   （`ModuleNotFoundError: No module named 'flint.analysis'`）；
2. 实现 `flint/analysis/{__init__.py,deep_job.py}` → 11 passed / 1 failed；
3. 唯一一条红是 `test_module_never_writes_its_own_runner` 抓到 `_RunnerLike`（Protocol）。
   **返工方向选的是改测试的判据而不是删 Protocol**，理由写在明处：该条 acceptance 的
   语义是「不新写 runner **实现**」，而描述注入面的 Protocol（体恒为 `...`）不是第二套
   runner；按名字匹配是把语义做窄了。改后断的是「非 Protocol 类不得实现 submit +
   Protocol 体不得藏实现 + 不碰 jobs 表/arq」——**比原判据更严**，不是为过测放水（§4.4）。
   仓库先例：`flint/llm/router.py#_ProviderLike` 同款结构类型。
4. 12 passed。

## 4 自审报告（§4.6，本卡 self_review=true）

**① 测试真实覆盖 acceptance（测试名 ↔ acceptance 条目映射）**

acceptance ①「job 提交走既有 runner（H7）；LLM 恒 mock 注入 NEVER 真实调用」：

| 测试名 | 覆盖点 |
|---|---|
| `test_kind_is_a_contract_jobkind_never_a_new_one` | kind 是契约 `JobKind` 成员且 == `gate1_analysis`（`get_args` 逐值核对） |
| `test_submit_goes_through_the_injected_runner` | 提交经注入 runner 恰一次，kind/payload/tier/lang/initiated_by 逐字核对 |
| `test_module_never_writes_its_own_runner` | 无 submit 实现、Protocol 体只许 `...`、无 `INSERT INTO jobs`/`asyncpg`/`arq`/`enqueue_job` |
| `test_submit_path_makes_zero_llm_calls` | 注入 SpyProvider 断言**零调用** + 阴性对照 `len(runner.calls)==1`（防空转绿） |
| `test_module_imports_no_real_provider_or_network` | import 面无 anthropic/httpx/openai/flint.llm.{production,cloud,provider} |
| `test_payload_rejects_empty_cluster` | 空 cluster_id 拒绝入队（否则会照常计费） |

acceptance ②「计费落点为配置开关（K7 两态皆可运行）」：

| 测试名 | 覆盖点 |
|---|---|
| `test_billing_flag_defaults_off` | 走既有 `DEFAULT_FLAGS['billing_enabled'] is False`，未新写开关系统 |
| `test_billing_off_charges_nothing_but_still_runs` | 关态：落点零调用、`billed is False`、作业照常提交、预算取免费档配置值 |
| `test_billing_on_charges_exactly_once_with_configured_amount` | 开态：落点恰一次、金额逐字来自配置、`job_id` 与本次运行对得上 |
| `test_billing_on_without_landing_fails_loudly` | 开关开而落点缺 → 抛错**且 `runner.calls == []`**（不能既不计费又照跑） |
| `test_billing_landing_failure_reports_the_created_job` | 落点抛错 → 异常里带 job_id |
| `test_pricing_has_no_builtin_price_table` | `DeepAnalysisPricing` 两字段无默认值（inspect 签名断言） |

无 `assert True`、无只测 happy path：两条 acceptance 各带反例（空 cluster、开关开而落点缺、
落点抛错）与一条阴性对照（提交确实发生过）。

**② 无冻结件偏离**（additive 校验输出原样）：

```
$ python tools/check_frozen_additive.py contracts/models.py contracts_v04/models_v04.py
additive 校验通过：models_v04.py 覆盖了 models.py 的全部 87 类 / 443 字段 / 1 方法签名 / 31 常量，新增 17 类、13 字段、10 枚举/联合成员
$ python tools/check_frozen_additive.py contracts/protocols.py contracts_v04/protocols_v04.py
additive 校验通过：protocols_v04.py 覆盖了 protocols.py 的全部 24 类 / 1 字段 / 40 方法签名 / 0 常量，新增 0 类、0 字段、0 枚举/联合成员
```

冻结件本体零改动：`contracts/models.py` md5 `380d7b5a7dae…`、
`contracts/protocols.py` md5 `eb19b73e176e…`（与 SELFCHECK-V2 记录一致）。
`submit_deep_analysis` 的调用面与 `contracts/protocols.py#JobRunner.submit`
五参数逐字对齐（kind/payload/budget/owner_scope/initiated_by）。

**③ 无禁用词**（本回合产出逐文件扫描，含「列表尾的等」正则）：

```
$ python - <<'EOF'  # 扫 S2-8 全部六个禁用词 + 列表尾的那一个（词表写在脚本里，不抄进本文）
BANNED_HITS= 0
EOF
```

扫描面：`flint/analysis/{deep_job.py,__init__.py}`、`tests/v04/hotspot/{test_deep_job.py,
test_analysis_view_api.py}`、`web/views/analysis/{AnalysisView.tsx,AnalysisView.test.tsx}`、
`docs/trace/HOTSPOT-03.md`、`docs/blocked/HOTSPOT-03.md`。

**④ 复用断言在位**（H 组命中项 → 断言测试名）：

- **H7 任务/作业系统**：`test_submit_goes_through_the_injected_runner`（走注入 runner）
  + `test_module_never_writes_its_own_runner`（无 submit 实现 / 不碰 jobs 表 / 不进 arq）
  + `test_kind_is_a_contract_jobkind_never_a_new_one`（不造新 kind）。
- **既有配置开关（flint/config.py）**：`test_billing_flag_defaults_off` 直接断言
  `DEFAULT_FLAGS[BILLING_FLAG] is False` 并用既有 `FeatureFlags`/`InMemoryFlagStore`
  ——本模块未新写任何 flag 存取。

**⑤ 装载未超预算**：实测 ≈26k tokens（上限 40k）。

## 5 verify

```
$ pytest tests/v04/hotspot/test_deep_job.py -q        → 12 passed
$ pytest tests/v04/hotspot -q                          → 19 passed（含 HOTSPOT-03 的 7 条）
$ ruff check . --no-cache                              → All checks passed!
$ mypy --strict flint                                  → 252 source files, no issues
```

一次 ruff 自纠：`from flint.analysis.deep_job import (...)` 的成员未按字典序，
`ruff --fix` 归位（I 规则）。

## 6 产出

- `flint/analysis/__init__.py`、`flint/analysis/deep_job.py`
- `tests/v04/hotspot/test_deep_job.py`（12 条）
