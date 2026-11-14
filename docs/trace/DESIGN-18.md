# DESIGN-18 trace — 用量与耗时记录（token/时长入 job 元数据）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-18`；
- context_refs：`WORKORDER-v04.md#5-G`（G24 一行）；
- 前置产物：`flint/llm/production.py#UsageMeter/ModelPricing`（M4-039 的计价口径）、
  `flint/design/session.py`（DESIGN-01）、`tests/v04/_source_scan.py`。
- 实测装载 ≈ 6k tokens，未超 40k。

## 2 关键设计判断

**用量挂在 job 上**：「这次生成花了多少」，用户问的是**那一次**。用量若与 job 分开存，
两边要靠时间窗对齐——对不齐的那些会变成无主的账，而账单上却有数。

**计价只有一处**：走既有 `UsageMeter`（价目由配置给、cost = tokens × 价目）。
本模块再乘一遍，就会出现「两处算出不同的钱」，而账单只能有一个数（有 import 断言）。
价目**没有内置默认**：一个猜出来的价会变成账单上的真数字（inspect 签名断言）。

**没记录过是 None，不是全 0**：全 0 看起来像「这次没花钱」，而事实是
「我们不知道这次花了多少」——与 DESIGN-13 的 `unreported ≠ passed` 同一条纪律。

**多轮累加而不是覆盖**：一次 job 可能有多轮模型调用；后一次覆盖前一次的话，
账面上只剩最后一轮的钱。耗时同样累加。

**两种坏数据直接拒**：负 token（接线错了，不是一次便宜的调用）、
结束早于开始（时钟或接线错了，NEVER 记一个负耗时）。

**读出去的是副本**：调用方改返回值不该改到账上。

## 3 acceptance ↔ 测试映射

acceptance「用量与耗时随 job 落库并可查询」：

| 测试名 | 覆盖点 |
|---|---|
| `test_usage_and_duration_land_on_the_job` | 落库 + 可查（token / 耗时 / 读回相等） |
| `test_cost_comes_from_the_existing_meter` | 计价数值 + import 断言（既有 UsageMeter） |
| `test_pricing_must_be_given_explicitly` | 价目无默认 |
| `test_unknown_job_reads_none_not_zero` | 没记录过 ≠ 没花钱 |
| `test_recording_twice_for_one_job_accumulates` | 多轮累加（token / calls / 耗时三项） |
| `test_usage_of_one_job_never_leaks_into_another` | 按 job 隔离 |
| `test_negative_or_backwards_duration_is_rejected` / `test_negative_tokens_are_rejected` | 两种坏数据 |
| `test_read_returns_a_copy` | 副本读 |
| `test_usage_is_a_dataclass_not_free_dict` | 有形状（自由 dict 会让「少记一项」很久以后才被发现） |

## 4 verify

```
$ pytest tests/v04/design/test_usage_metrics.py -q  → 10 passed
$ pytest tests/v04/design -q                         → 72 passed
$ ruff check . --no-cache                            → All checks passed!
$ mypy --strict flint                                → 263 source files, no issues
```

禁用词 0。

## 5 产出

- `flint/design/usage.py`
- `tests/v04/design/test_usage_metrics.py`（10 条）
