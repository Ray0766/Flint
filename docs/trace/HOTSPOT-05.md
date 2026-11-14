# HOTSPOT-05 trace — 分析结果缓存（同参二次 0 新 job、0 计费）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#HOTSPOT-05`；
- context_refs：`WORKORDER-v04.md#5-C`（C9 一行）、
  `contracts_v04/models_v04.py` 的 `FactsLedger` 与 `ledger_version` 三处落点；
- 前置产物（按 inputs 定位）：`flint/analysis/deep_job.py`（本卡直接复用其提交面）、
  `flint/ledger/store.py` 首 12 行（版本从哪来：`SELECT version … ORDER BY version DESC`）、
  `flint/config.py#FeatureFlags`。
- 实测装载 ≈ 14k tokens（本卡与 HOTSPOT-04 同区，多数上下文已在手），未超 40k。

## 2 关键设计判断

**四要素少一个都会出事**（写进模块 docstring 与测试 docstring，各带后果）：
少 lang → 中文点过一次、切英文再点回中文那份，用户拿到一份读不懂的报告；
少档位 → 免费档点过之后点深度档直接回免费档结果，**钱花了、深度没给**；
少账本版本 → 账本前进意味着事实变了，还回旧结果等于让用户拿着**过期判定**做决定，
而界面上没有任何迹象说明它是旧的。

**账本版本未知 → 整条缓存路径跳过**（不查、不写、每次新作业）。版本未知就无从证明
缓存里那份是否过期；宁可多跑一次（用户看到的是当下事实），也不回一份**无法证明时效**
的结果。这与 A7/E6 的降级口径同源：缺就是缺。

**跨租户 NEVER 复用**（DEC-011）：缓存回的是**别人那次运行的 job_id**。把 owner 塞进键
会偏离 acceptance 写死的四要素，故改为**命名空间隔离**——键的四要素一字未动，
查表带 owner。

**指纹分隔符转义**：不转义的话 `("c-1|zh", "")` 与 `("c-1", "zh")` 会撞同一个键，
于是两个不同热点/语言的组合共用一份结果。测试里专门有一条伪造键的断言。

**forget 是必需的缝**：不留它的话，一次失败的运行会被永久回放——用户每次点开都拿到
同一个失败作业，而按钮看起来是好的。

## 3 test-first 顺序（§4.2）

1. 先写 `tests/v04/hotspot/test_analysis_cache.py`（12 条）→ 跑 → 红
   （collection error：`flint.analysis.cache` 不存在）；
2. 实现 `flint/analysis/cache.py` → 12 passed；
3. `ruff --fix` 归位一处 import 排序（I 规则），无其它返工。

## 4 自审报告（§4.6，本卡 self_review=true）

**① 测试真实覆盖 acceptance（测试名 ↔ acceptance 条目映射）**

acceptance 只有一条，两个分句各自成组：

| 分句 | 测试名 | 覆盖点 |
|---|---|---|
| 二次请求 0 新 job | `test_second_click_same_params_creates_no_job_and_no_charge` | 二次点击 `runner.calls` 仍为 1、`charged` 仍为 1、回同一 job_id、`reused/billed` 标记正确；**且先断言第一次确实提交、确实计费**（阴性对照） |
| 二次请求 0 新 job | `test_third_click_still_reuses` | 连点第三下同样 0 新 job（不是只挡住第二下） |
| 键含 cluster | `test_each_key_element_breaks_reuse[cluster_id-c-2]` | 变 cluster → miss → 新作业 + 新计费 |
| 键含 lang | `test_each_key_element_breaks_reuse[lang-en]` | 同上 |
| 键含档位 | `test_each_key_element_breaks_reuse[tier-free]` | 同上 |
| 键含账本版本 | `test_each_key_element_breaks_reuse[ledger_version-8]` | 同上 |
| 键的形状 | `test_fingerprint_covers_exactly_the_four_elements` | 四要素相同即同键、任一不同即异键、**分隔符不可被内容伪造** |
| 时效不可证时不复用 | `test_unknown_ledger_version_never_reuses` | 版本 None → 两次点击两个作业且缓存为空 |
| 时效不可证时不复用 | `test_cache_key_rejects_unknown_ledger_version` | 键本身拒绝 None（不留「先建键回头补版本」的口子） |
| 复用边界 | `test_never_reuses_another_owners_run` | 同键不同租户 → 不复用（D7） |
| 复用边界 | `test_forgotten_entry_submits_again` | forget 后重新提交（失败运行 NEVER 被永久回放） |
| 不新写 | `test_module_never_writes_its_own_runner_or_flag_system` | 提交仍走 deep_job；无 jobs 表写、无 arq、无第二套 flag 默认表 |

无 `assert True`、无只测 happy path：反例四条（四要素各变一次）+ 边界三条
（版本未知 / 跨租户 / forget）+ 阴性对照两处（第一次真的提交且计费）。

**② 无冻结件偏离**：本卡零触碰 contracts/ 与 contracts_v04/；additive 校验沿用本回合
HOTSPOT-04 的输出（双通过），冻结件 md5 `380d7b5a7dae…` / `eb19b73e176e…` 未变。
`submit_or_reuse` 的提交面转调 `submit_deep_analysis`，参数逐字沿用
`contracts/protocols.py#JobRunner.submit` 的五参数口径。

**③ 无禁用词**：

```
$ python - <<'EOF'   # 扫 S2-8 六词 + 列表尾的那一个；面：cache.py / test_analysis_cache.py / trace / DECISIONS
BANNED_HITS= 0
EOF
```

（同一轮扫描顺手抓到 `docs/trace/HOTSPOT-04.md` 第 96 行 6 处命中——那是自审报告里
**把词表原样抄了进去**。已改写为「S2-8 全部六个禁用词」不再列举；这属于报告写法，
不是规格用词，但留着会让下一次扫描每次都亮红，等于把哨兵训练成噪音。）

**④ 复用断言在位**：`test_module_never_writes_its_own_runner_or_flag_system`
正向断言 `from flint.analysis.deep_job import`（提交走 HOTSPOT-04 的既有通道，H7 传递），
反向断言无 `INSERT INTO jobs` / `asyncpg` / `arq` / 第二套 `DEFAULT_FLAGS`。
计费开关仍是 `flint/config.py` 的 `billing_enabled`，缓存层零新增 flag。

**⑤ 装载未超预算**：实测 ≈14k tokens（上限 40k）。

## 5 verify

```
$ pytest tests/v04/hotspot/test_analysis_cache.py -q  → 12 passed
$ pytest tests/v04/hotspot -q                          → 31 passed
$ ruff check . --no-cache                              → All checks passed!
$ mypy --strict flint                                  → 253 source files, no issues
```

## 6 产出

- `flint/analysis/cache.py`
- `tests/v04/hotspot/test_analysis_cache.py`（12 条）
- `DECISIONS-v04.md#DEC-011`（键保持四要素、查表走 owner 命名空间）
