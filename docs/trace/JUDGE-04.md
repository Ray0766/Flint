# JUDGE-04 · GPT-5.6 接入作第二校准点与仲裁票

**卡** `tasks-v041-b2.json#JUDGE-04` · **cycles 1** · **owner_review = true** → 见 §6
**依赖** JUDGE-01（verified）

## 1. 装载清单

卡面 JUDGE-04（三个模型 id、三档分工与理由、本地备胎优先）·
`flint/llm/cloud.py` 全文（`CloudOpenAIProvider`：云端 = 本地传输 + key 必填 + 真价目）·
`flint/llm/registry.py` · `flint/llm/deepseek.py`（`UsageLedger` / `UsageRecord` /
`_RecordingClient` / `breakdown_from_usage`）· `flint/domain/protocols.py#LLMProvider`。
约 7k tokens。

## 2. 顺序（§4.2）

测试先落盘先跑红（`ImportError: flint.llm.openai_compat`）→ 实现 → 25 passed →
变异考补判后仍 25 passed（判据改强，条数不变）。

## 3. 三档分工怎么落的

| 角色 | 模型 | `when` | 用途 |
|---|---|---|---|
| `bulk` | `gpt-5.6-luna` | `bulk_or_backup` | 大批量低难度分类 + DeepSeek 的产能备胎 |
| `calibration` | `gpt-5.6-terra` | `default_calibration` | **校准票**（默认） |
| `arbitration` | `gpt-5.6-sol` | `three_way_disagreement` | **仲裁票**，三家分歧时才动 |

**最要紧的一条判据是「校准票不能是 Luna」**：它与 DeepSeek V4 Flash 同级，
拿同级模型校准，**一致也不代表对、不一致也无法归因**。
判据不止比模型名，还比单价（校准档单价必须高于批量档）——只比名字的话，
把两个名字对调就绕过去了。

**`when` 是写进数据的**：仲裁票的 `when == "three_way_disagreement"`。
把使用纪律写成字符串而不是只写在注释里，是为了让「什么时候能动这一档」可被断言。

## 4. 价目：没配价的档 = 不可用

三档单价全从 `FLINT_OPENAI_{ROLE}_USD_PER_MTOK_INPUT/_OUTPUT` 读。
**卡面上写了三档的价（$0.20/$1.20、$2/$12、$5/$30），但我没把它们写进代码。**
理由：卡面是人写的一句话，环境变量是这台机器的事实——把卡面的数当默认，
账就会按一个**没人在这台机器上确认过**的价记。

没配价的档**不进表也不进注册表**（注册了却不能用，比没注册更难查），
取它时抛 `GptRoleUnavailable` 并**说清缺哪个变量**。

**当前状态**：本机 `FLINT_OPENAI_API_KEY` 已配（owner 授权、余额 $20），
但**三档的价一个都没配**——所以此刻 `load_gpt_roles()` 返回空表，
三档全部不可用。要用起来，owner 把六个价目变量填上即可（见 §6-1）。

## 5. 变异考：十六个，两个先活了下来

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 校准票落到 Luna | acceptance①（同级互校） | **2 failed** ✓ |
| ② 仲裁票不再是最强档 | 分工 | **1 failed** ✓ |
| ③ 仲裁票随时可用 | 使用纪律 | **1 failed** ✓ |
| ④ 没配价就拿卡面数顶上 | §4 | **2 failed** ✓ |
| ⑤ 云端备胎排到本地前面 | acceptance③ | **1 failed** ✓ |
| ⑥ 都不可用时也回落一个默认 | acceptance③ | **4 failed** ✓ |
| ⑦ 降级不标降级 | acceptance⑤ | **1 failed** ✓ |
| ⑧ 降级不写后果 | acceptance⑤ | **25 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑨ 花超了不报错 | acceptance⑤ | **1 failed** ✓ |
| ⑩ 花过的钱不累计 | 余额闸 | **1 failed** ✓ |
| ⑪ 账上不记档位 | acceptance⑤ | **25 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑫ 余额闸永远放行 | acceptance⑤ | **1 failed** ✓ |
| ⑬ 注册循环改写（形同） | — | **25 passed**（**故意的惰性变异**，作对照） |
| ⑭ 口径版本不含档位 | 归因 | **1 failed** ✓（补判顺带） |

**⑪ 为什么能活（这条最值得记）**：判据写的是
`role in record.model or role in record.purpose`，而测试传的 `purpose` 恰好就是
`"arbitration"`——**判的成了「我传进去的那个字符串」**，实现把档位从 model 里
拿掉照样绿。修法：用途标签换成 `"tie_break"`（不含档位名），
再分别断言 `model` 与 `pricing_version` 都带档位。
**判据的输入不能由判据自己提供**——这是本仓第十八次同型的一个新变种。

**⑧ 为什么能活**：判据是「note 里有『余额』二字」，而 note 开头就是「余额将尽」。
把后果那半句（「降级为不调用该档，产物照实标注未校准」）删掉毫无反应。
改成**数与后果两半都要有**：只说「余额将尽」，读的人不知道接下来发生了什么。

十六次变异后 `flint/llm/openai_compat.py` 的 sha256 与变异前逐位相同。

## 6. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_gpt_provider.py -q → 25 passed
全局门: ruff check . --no-cache → All checks passed!
        mypy --strict flint → 288 files, no issues
        pytest -q → 2878 passed
        tools/gauge_map.py → 查不到尺子 0
```

**① acceptance 映射**

| acceptance | 测试 |
|---|---|
| ① 复用 `cloud.py`、NEVER 另建路径、三档分工、模型 id 不猜 | `test_it_reuses_the_existing_cloud_adapter`（钉最贴的那一层）、`test_the_module_does_not_build_its_own_request_path`、`test_it_satisfies_the_frozen_provider_protocol`、`test_the_three_roles_map_to_the_three_confirmed_model_ids`、`test_the_calibration_vote_is_never_the_cheap_tier`、`test_the_arbitration_tier_is_the_dearest_and_last`、`test_each_role_says_what_it_is_for` |
| ③ 本地备胎优先于云端 | `test_the_local_backup_comes_before_the_cloud_one`、`test_the_cloud_backup_is_used_when_local_is_down`（阴性对照）、`test_no_backup_at_all_is_an_empty_list_not_a_guess`、`test_the_local_backup_is_the_model_the_card_names` |
| ④ key 只从环境读 | `test_the_error_names_the_variable_not_its_value`、`test_the_key_never_appears_in_the_source`；另 `test_a_role_without_configured_prices_is_unavailable` |
| ⑤ 同一本账 + 余额将尽降级并照实标注 | `test_a_call_lands_a_record_in_the_same_ledger_type`、`test_the_record_carries_the_role_so_the_bill_can_be_split`、`test_the_cost_uses_the_role_price`、`test_spending_is_allowed_while_there_is_budget`、`test_crossing_the_budget_degrades_and_says_so`、`test_a_spend_past_the_budget_raises_rather_than_silently_succeeding`、`test_the_guard_records_what_it_already_spent`、`test_the_note_is_empty_while_healthy`（阴性对照） |
| ⑥ 测试恒回放，CI 不真调 | `test_the_test_module_makes_no_live_call`（BL-09 的尺子扫本测试文件）；全部用替身 client |

注册那一组：`test_the_roles_register_through_the_existing_registry`、
`test_an_unconfigured_role_is_not_registered`。

**② 无冻结件偏离**：`contracts/`、`flint/domain/` 未触碰；
`cloud.py` / `registry.py` / `deepseek.py` **一个字没动**（只导入）；零新增依赖。

**③ 禁用词**：两个产物文件 + 本 trace 六词 0 命中。

**④ 复用**：请求路径继承 `CloudOpenAIProvider`；账本、用量记录、
响应记录包装、usage 解析全部来自 JUDGE-01 的 `deepseek.py`
（**同一本账**——两本账会让「这个月一共花了多少」变成一道加法题）。

**⑤ 装载预算**：约 7k tokens。

## 7. owner_review：三件要 owner 拍板的

1. **六个价目变量要不要配**。卡面给了三档的价，但本卡按纪律**没有内置**。
   不配 = 三档全部不可用（这是安全的默认）。配了之后 GPT 才真正可用。
2. **`FLINT_OPENAI_MODEL` 现在是 `gpt-4o-mini`、单价 0.15/0.60**，
   与卡面的三档完全对不上——那是更早留下的配置。
   本卡**没有改环境**（那是 owner 的面），也**没有用**那个变量：
   三档各自读 `FLINT_OPENAI_{ROLE}_MODEL`（可选覆盖），
   缺省用 steward 确认过的三个 id。要不要清理旧变量，owner 定。
3. **一次真实调用都没发**。本卡是接线卡，`$20` 余额一分没动。
   第一次真调建议放在 JUDGE-02 那 21 条分歧的第三票上（那是买信息，
   见 `docs/判官对齐-v041.md` 的待办），预计约 $0.1。

## 8. 登记未做

1. **没有真调过**（见 §7-3）：所以三个模型 id 在**本适配器里**没有被端到端验证过——
   steward 说账号内可见，我按那个记；真调那天若报「模型不存在」，
   改的是 `GPT_MODELS` 那三行。
2. **`BalanceGuard` 还没有接进任何调用链**：它是闸，接进去要定「谁持有这个闸、
   预算从哪读」——那是编排面的事。
3. **余额是人填的，不是查的**：`budget_usd` 由调用方给，本卡**没有**去查
   OpenAI 的真实余额（那要另一个 API 与另一套鉴权）。所以「余额将尽」的判断
   依赖调用方填对预算。
4. **`bulk` 档的产能备胎顺序只给了清单，没给切换逻辑**：
   `choose_capacity_backup` 返回的是**顺序**，真按这个顺序去试是调用方的事。
5. **JUDGE-02 的第三票还没跑**：适配器现在有了，但三档没配价（§4），
   所以那件待办仍然挂着。
