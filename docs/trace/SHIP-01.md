# SHIP-01 · 支付骨架（免费额度计数 + 配额门 + 计费事件账）

**卡** `tasks-v041-b2.json#SHIP-01` · **开工** 机器 UTC 2026-08-04T03:55Z · **cycles 2**
**owner_review = true** → 见 §6「要 owner 定的那两个数」

## 1. 装载清单

卡面 SHIP-01 · `flint/analysis/deep_job.py` 全文（`ChargeLandingMissing` / `ChargeIntent`
/「先于提交检查」的既有形状）· `flint/config.py#DEFAULT_FLAGS` 的 `billing_enabled` ·
`CLAUDE.md#S1`（免费额度 + 按次）· `flint/design/checkpoints.py#HistoryImmutable`
（append-only 同款纪律）。约 7k tokens。

## 2. 顺序（§4.2）

测试先落盘先跑红（`ModuleNotFoundError: flint.billing.ledger`）→ 两个模块 →
21 passed。连续第二十九张。

## 3. 只建三样：算得清 / 拦得住 / 记得下

**定价与真实支付都不在本卡面上。**

| 建了 | 没建（也 NEVER 建） |
|---|---|
| 免费额度计数与配额门（`quota.py`） | 任何支付网关接入 |
| 计费事件账 append-only + 按 owner 隔离（`ledger.py`） | 任何默认价 / 币种 / 额度数字 |
| 「配置留空 = 路径关闭」的阴性对照 | 付费开通（S2-10 红线） |

`test_no_payment_gateway_anywhere_in_the_package` 扫九个词
（httpx / requests / wechat / alipay / stripe / paypal / api_key / secret / merchant），
包里一个都不许出现。

## 4. 零定价：四项**任缺其一**就算未配置

`BillingConfig` 四个字段默认值都是 `None`：

- **「没配」与「配成 0」必须分得开**——默认成 0 的话，「免费额度 0 次」与
  「还没定价」长得一模一样；
- **半套配置比没有更危险**：它会让一半的运行被拦、另一半照跑，而两边都以为自己对。

未配置时 `check_quota` 放行且 note 写「计费路径未配置（零定价）」，
`guard_before_submit` **一次都不抛**——行为与今天逐字相同（acceptance② 的阴性对照）。

## 5. 拦在 submit 之前，且说清还差多少

`guard_before_submit` 抛 `QuotaExceeded`，异常里带 owner 与 **shortfall**。

**本模块够不着提交面**：没有 runner、不构造 job_id、不 import 任何作业模块。
`test_the_guard_never_touches_a_runner` 从代码面禁 `.submit(` / `runner` / `JobRunner`——
「拦在提交之前」这件事靠的正是它根本不认识那一侧。

## 6. 要 owner 定的那两个数（owner_review）

本卡**一个数都没编**。要跑起来需要 owner 给四项（K7/K8 的面）：

1. **免费额度上限**（几次）；
2. **单价**与 **3. 币种**；
4. **计费口径版本号**（改价时递增——账本会把口径混用报出来）。

在这四项配齐之前，整条计费路径是关闭的，系统行为与今天**逐字相同**。

## 7. 变异考：九个，两个先活了下来

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 半套配置也算配好 | §4 | **1 failed** ✓ |
| ② 未配置也拦 | acceptance② | **2 failed** ✓ |
| ③ 超额不说还差多少 | acceptance① | **21 passed** ✗ → 补判后 **1 failed** ✓ |
| ④ 边界差一（用满也放行） | 边界 | **2 failed** ✓ |
| ⑤ 门不抛（只报告） | acceptance① | **1 failed** ✓ |
| ⑥ 账可覆盖 | append-only | **1 failed** ✓ |
| ⑦ `for_owner` 不隔离 | D7 | **2 failed** ✓ |
| ⑧ 口径混用不报 | acceptance④ | **1 failed** ✓ |
| ⑨ 返回内部列表（非副本） | 返回副本 | 首版变异体**惰性** → 真变异体 **3 failed** ✓ |

**变异③ 为什么能活**：判据写的是 `"3" in str(err)`，而 `used=3, limit=3` 时
消息里的「已用 **3**/3」就把断言喂饱了。改成判**专有的数与词**
（`err.value.shortfall == 3` + `"还差 3 次"`）并把用例改成 `used=5`（shortfall=3，
与 used/limit 都不同的数）。重考 → 红。

**变异⑨ 首版是惰性变异**：那个变异体每次调用仍**重建**列表，所以「返回副本」这条
性质并没有被破坏。换成真会破坏的写法（账本维护一个长期存在的 `_live` 列表并直接
返回它）→ **3 failed**。

本批第八次同型（判据钉在一个恰好也被满足的更宽东西上）。

九次变异后两个模块的 sha256 与变异前逐位相同。

## 8. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_billing_skeleton.py -q → 21 passed
ruff check . --no-cache → All checks passed!
mypy --strict flint → 281 files, no issues
```

**① acceptance 映射**

| acceptance | 测试 |
|---|---|
| ① 计数 + 配额门 + 事件账，超额在 submit 之前拒绝并说还差多少 | `test_inside_the_free_quota_is_allowed`、`test_the_boundary_is_the_last_free_run`、`test_being_over_says_how_much_short`、`test_the_guard_raises_before_anything_is_submitted`、`test_the_guard_never_touches_a_runner` |
| ② 零定价：四项从配置读，留空 = 路径关闭 | `test_an_unset_config_is_not_configured`、`test_no_price_is_baked_into_the_code`、`test_the_config_fields_have_no_defaults_other_than_none`、`test_with_no_config_the_gate_lets_everything_through`、`test_with_no_config_the_guard_never_raises`（阴性对照） |
| ③ 零真实支付 | `test_no_payment_gateway_anywhere_in_the_package`（九个词全禁） |
| ④ 账 append-only 且可对账（五字段） | `test_an_event_carries_all_five_reconcilable_fields`、`test_appending_the_same_event_twice_is_refused`、`test_the_ledger_has_no_update_or_delete`、`test_one_owner_never_sees_another_owners_events`、`test_for_owner_returns_a_copy`、`test_reconcile_sums_only_that_owner`、`test_reconcile_reports_mixed_pricing_versions`、`test_a_single_version_is_not_flagged_as_mixed`（阴性对照）、`test_an_empty_ledger_reconciles_to_zero_not_an_error`、`test_currency_must_match_the_config_currency` |

**② 无冻结件偏离**：`contracts/`、`flint/domain/` 只读消费（`Principal`）；
零新增依赖；**未改任何既有文件**（新建 `flint/billing/` 包三个文件 + 测试）。

**③ 禁用词**：三个产物文件六词 0 命中、本 trace 收尾「等」0 命中。

**④ 复用**：append-only 与 `flint/design/checkpoints.py#HistoryImmutable` 同款；
「返回副本」与 `SnapshotPins` / FAV-01 同款；剥 docstring 的 `_code_face` 与 BL-03 同源；
「先于提交检查」的形状照 `deep_job.py` 的既有做法。

**⑤ 装载预算**：约 7k tokens。

## 9. 登记未做

1. **计数器没有持久化**：`check_quota` 收的是 `used`（调用方给），本卡**不管这个数
   从哪来**。真实计数要读账本或计数表，属接线卡的面。
2. **没有接进任何提交路径**：`deep_job.py` 的 `submit_deep_analysis` 还没调
   `guard_before_submit`。接它要改既有文件且改动面超出本卡 outputs——
   接线时那一处 MUST 放在 `runner.submit` **之前**。
3. **账是内存实现**：SQL 实现随 E2 接入（与 `SnapshotHistoryStore` 同一房规）。
4. **`unit_price` 只被配置带着走**：本卡的账记的是调用方给的 `amount`，
   **没有**「用 unit_price × 次数」这一步——那一步属计费口径落地（PAY-02 的面）。
