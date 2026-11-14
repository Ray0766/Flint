# JUDGE-01 · DeepSeek 接入（LLMProvider 适配器 + 用量账本）

**卡** `tasks-v041-b2.json#JUDGE-01` · **cycles 1** · **owner_review = true** → 见 §7
**依赖** 无

## 1. 装载清单

卡面 JUDGE-01（含 steward 2026-08-04 实测确认的模型 id / 端点 / 变量名）·
`flint/domain/protocols.py#LLMProvider`（冻结协议逐字）·
`flint/llm/local.py` 全文（既有 OpenAI 兼容适配器：请求体、错误分类、栅栏剥离、
`structured_loop` 接法）· `flint/llm/production.py` 的 `ModelPricing` / `UsageMeter` /
`CloudTier` / `load_deepseek_tier` / `ProviderWiringError` ·
`flint/llm/registry.py` 全文 · `flint/billing/ledger.py`（append-only 账的既有形状）·
`flint/sources/provenance.py`（NET-02 三件套）· `.env.example`。约 11k tokens。

## 2. 顺序（§4.2）

测试先落盘先跑红（`ImportError: flint.llm.deepseek`）→ **真调一次录响应** →
实现 → 25 passed / 4 failed（两条判据自己写错 + `.env.example` 还没改）→
修 → 29 passed → 变异考补判后 30 passed。

## 3. 真调了一次（C 档付费，最小调用）

```
POST https://api.deepseek.com/chat/completions   model=$FLINT_DEEPSEEK_MODEL
→ HTTP 200，usage: prompt 9 / completion 1
```

录进 `fixtures/deepseek/chat_completion_minimal.json`（NET-02 信封 + manifest，
`verify_fixture` 核过）。**录制件里没有 key**：只存响应体与 URL，请求头不入库，
有断言守着（`test_the_recorded_manifest_carries_no_key`）。

**只有真录了才知道的两件事**：

1. 缓存字段确实叫 `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`，
   **另有** `prompt_tokens_details.cached_tokens` 一份（两处同源，本卡读前者
   ——那是 DeepSeek 文档里计费口径用的名字）；
2. **环境里的 `FLINT_DEEPSEEK_MODEL` 是 `deepseek-chat`，而响应回的
   `model` 是 `deepseek-v4-flash`**——`deepseek-chat` 是解析到 v4-flash 的别名。
   卡面写的模型 id 是 `deepseek-v4-flash`，两者**不矛盾但也不是同一个字符串**。
   本卡**没有改环境变量**（那是 owner 的配置），适配器原样透传配置里的 model。
   这一条记进 §7 让 owner 决定要不要把别名换成实名。

## 4. 为什么继承而不是新写一条路径（acceptance①）

DeepSeek 是 OpenAI 兼容端点，而 `flint/llm/local.py#LocalProvider` 已经是一个
OpenAI 兼容适配器。再写一条 POST 就是卡面禁的「另建调用路径」——
两条路径的重试语义、错误分类、栅栏剥离迟早会分叉，分叉之后没人知道哪条是对的。

> **订正（2026-08-04，做 JUDGE-04 时发现）**：本卡第一版继承的是 `LocalProvider`，
> 而仓里已经有 `flint/llm/cloud.py#CloudOpenAIProvider`——它自己继承 `LocalProvider`，
> 加的正是「api_key 必填 + 按注入价目真实计费」这两件事，也就是我又写了一遍的那两件。
> **「复用」要复用到最贴的那一层，差一层就是一份影子实现。** 已改为继承
> `CloudOpenAIProvider`，判据也从「是不是 LocalProvider 的子类」收紧到那一层
> （松的那条对错误的实现照样绿）。30 条测试改前改后都通过。

`DeepSeekProvider(CloudOpenAIProvider)` 只加它没有的两件事（原文写三件，
其中「真价目」那件 `CloudOpenAIProvider` 本来就有）：

| 加的 | 为什么 `CloudOpenAIProvider` 没有 |
|---|---|
| 缓存命中分两栏 | 它沿用 `LocalProvider` 的解析，把 usage 压成 input/output 两项，丢掉了缓存字段 |
| 用途标签 + append-only 账本 | 它只有累计计量（`UsageMeter`），没有逐笔账 |

（**真价目**那件原本也列在这里，实为误记：`CloudOpenAIProvider` 的
`self.meter = UsageMeter(pricing=pricing)` 本来就做了。本卡真正多出来的，
是命中价那**第三档**——`ModelPricing` 只有两个字段，放不下它。）

**拿原始 usage 的办法**：注入一个转发并记住上一次响应体的 client
（`_RecordingClient`），**而不是去 `local.py` 里开钩子**——改它超出本卡 outputs。
请求路径因此一个字没变。

## 5. 缓存命中：账的那半条命

DeepSeek 的命中价比未命中低两个数量级（v4-flash 公开价 $0.0028 vs $0.14 /Mtok）。
所以：

- 命中与未命中**分两栏记**，`hit + miss != prompt_tokens` 直接抛错
  （对不上就是解析错了，NEVER 静默放行）；
- 响应里没有缓存字段时两栏记 0 / 全部算未命中——**NEVER 编一个命中数**，
  编出来的数会让账看起来比真实更省；
- **没配命中价却出现了命中 → 抛 `CachePriceUnknown`**，NEVER 按未命中价顶上：
  顶上去的账会**高于**真实账单，而账对不上时最难查的正是这种「差一点」。
  配套一条阴性对照：没有命中时缺命中价**不该**报错，否则这道门会拦住正常调用。

**口径版本由单价算出**（`deepseek:{in}/{out}/{hit}`）：写死一个 `v1` 的话，
`mixed_pricing` 那道对账门就永远报不出混用——两次改价之间的账混在一起，
而对账表上看起来只有一个口径。

## 6. 改既有文件：一处

**`.env.example`**（acceptance⑥ 点名的那处不一致）：

- **改前**：`# ANTHROPIC_API_KEY=`（无前缀），且 DeepSeek / OpenAI 两档一个变量都没有。
- **改后**：统一 `FLINT_` 前缀（`FLINT_ANTHROPIC_API_KEY` / `FLINT_PAID_TIER_MODEL` /
  两项单价），补齐 DeepSeek 六项与 OpenAI 五项，另补 `FLINT_Z_LINE`（Z-01 刚加的）。
- **为什么非改不可**：代码读的是带前缀的名字
  （`production.py#load_anthropic_tier` 等），照旧模板配**会配不上**，
  而**失败形态是「key 读不到」而不是「模板写错」**——人会去查代码，
  不会去查自己那行模板。这正是卡面点它的理由。

`flint/llm/local.py`、`production.py`、`registry.py` **一个字没动**（它们是本卡的
inputs，不是 outputs）。

## 7. 变异考：十六个，两个先活了下来

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 没配命中价也放行 | acceptance⑤ | **1 failed** ✓ |
| ② 命中按未命中价计 | acceptance⑤ | **1 failed** ✓ |
| ③ 两栏加不出总数也放行 | 解析自检 | **1 failed** ✓ |
| ④ 无缓存字段时不把输入算作未命中 | 不编数 | **1 failed** ✓ |
| ⑤ 账本可被改写 | acceptance③ | **1 failed** ✓ |
| ⑥ 返回值不再是副本 | 账本隔离 | **30 passed** —— **变异是惰性的**，见下 |
| ⑦ 口径版本写死在记录上 | 对账 | **1 failed** ✓ |
| ⑧ 版本不随价目变 | 对账 | **29 passed** ✗ → 补判后 **1 failed** ✓ |
| ⑨ 口径混用不报 | 对账 | **1 failed** ✓ |
| ⑩ 不记原始响应（缓存字段丢掉） | acceptance⑤ | **10 failed** ✓ |
| ⑪ 报错回显整个环境（含 key） | acceptance② | **1 failed** ✓ |
| ⑫ 模板退回无前缀写法 | acceptance⑥ | **1 failed** ✓ |
| ⑬ 模板漏一个变量 | acceptance⑥ | **1 failed** ✓ |
| ⑭ 版本只含输入价 | 对账 | **1 failed** ✓（补判顺带） |

**⑧ 为什么能活（真洞）**：唯一盯版本的断言是「记录上的版本 == provider 的版本」，
两边都换成常量它照样成立。补 `test_the_version_changes_when_the_price_changes`：
三种价目必须给出三个不同版本。⑭ 再验一次（只含输入价也红）。

**⑥ 是惰性变异，不是测试有洞**：账本的存储是 `dict` + `order list`，
`records()` 每次都由它们**现构造**一个新列表——想让返回值不是副本，
得先把存储改成「持有一个 list 并直接返回它」，那是重写不是变异。
也就是说这条性质由**存储结构本身**保证，断言在这里是把它写下来，
不是在守一个能被一行改掉的东西。**本批第四次遇到「惰性变异 ≠ 测试有洞」。**

**另有两条判据是我自己先写错的，一并记下**：

1. `isinstance(provider, LLMProvider)` —— 冻结件的 `LLMProvider` 没有
   `@runtime_checkable`，直接抛 `TypeError`。给冻结件加装饰器是改冻结件（S2-1 禁），
   所以改成**签名逐字比对**（方法名 + 形参名 + 顺序）。
2. 「模块里没有 `.post(` 调用」—— 包装层的**转发**本来就该有一个，判据把它也算进去了。
   改成两条结构判据：代码面无 `/chat/completions` 字面量（拼端点是另建路径的第一步）+
   唯一的 `.post(` 对象是被注入的那个 client（`self._inner`）。

十六次变异后两个产物文件的 sha256 与变异前逐位相同。

## 8. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_deepseek_provider.py -q → 30 passed
全局门: ruff check . --no-cache → All checks passed!
        mypy --strict flint → 287 files, no issues
        pytest -q → 2778 passed
        tools/gauge_map.py → 查不到尺子 0
```

**① acceptance 映射**

| acceptance | 测试 |
|---|---|
| ① 按既有协议实现、走既有 registry、NEVER 另建调用路径 | `test_it_satisfies_the_frozen_provider_protocol`（签名逐字）、`test_it_reuses_the_existing_openai_compatible_adapter`、`test_the_module_does_not_build_its_own_request_path`（AST）、`test_it_hits_the_chat_completions_path`、`test_it_registers_through_the_existing_registry`、`test_registering_twice_is_refused` |
| ② key 只从环境读，永不进代码/仓库/日志 | `test_the_key_never_appears_in_the_source`、`test_a_missing_key_names_the_variable_not_its_value`、`test_the_ledger_never_stores_the_key`、`test_the_recorded_manifest_carries_no_key` |
| ③ 每次调用记账（token / 金额 / 用途），append-only 可对账 | `test_every_call_lands_one_ledger_record`、`test_two_calls_land_two_records_in_order`、`test_the_ledger_refuses_to_be_rewritten`、`test_the_returned_records_are_copies`、`test_the_cost_comes_from_the_configured_price_not_a_built_in_table`、`test_the_pricing_version_travels_with_the_record`、`test_the_version_changes_when_the_price_changes`、`test_the_ledger_reconciles_and_flags_mixed_pricing` |
| ④ 测试恒回放，真实调用按 NET-02 留痕 | `test_the_recorded_response_is_on_disk_with_its_manifest`（`verify_fixture`）、`test_the_recorded_response_has_the_fields_the_parser_reads`、`test_the_test_module_makes_no_live_call`（BL-09 的尺子扫本测试文件） |
| ⑤ 缓存命中分开记、按命中价计 | `test_cache_hit_tokens_are_recorded_separately`、`test_a_cache_hit_is_charged_at_the_hit_price`、`test_a_hit_without_a_configured_hit_price_is_refused`、`test_no_hit_without_a_hit_price_is_fine`（阴性对照）、`test_a_usage_without_cache_fields_does_not_invent_them`、`test_the_two_halves_add_up_to_the_input_total` |
| ⑥ `.env.example` 与代码统一 `FLINT_` 前缀并补两档 | `test_the_env_template_uses_the_prefix_the_code_reads`、`test_the_template_covers_every_var_the_loaders_read`、`test_the_template_holds_no_real_value` |

**② 无冻结件偏离**：`contracts/`、`flint/domain/` 未触碰（`LLMProvider` 只读比对，
**没有**给它加 `@runtime_checkable`）；`local.py` / `production.py` / `registry.py`
一个字没动；零新增依赖（`httpx` / `decimal` 都在）。

**③ 禁用词**：两个产物文件 + 本 trace 六词 0 命中。

**④ 复用**：请求路径与云端纪律继承 `CloudOpenAIProvider`（订正后，见 §4）；计量继承 `UsageMeter`；
配置读取用既有 `load_deepseek_tier` 与 `ProviderWiringError`；
账本形状照 `flint/billing/ledger.py`（append-only + 副本 + `mixed_pricing`）；
录制件走 NET-02 的信封与 `verify_fixture`。

**⑤ 装载预算**：约 11k tokens。

## 9. owner_review：三件要 owner 拍板的

1. **`FLINT_DEEPSEEK_MODEL` 现在配的是别名 `deepseek-chat`**，实际解析到
   `deepseek-v4-flash`（见 §3-2）。别名的好处是官方换代时自动跟随，坏处是
   **账上的 model 名与价目对不上**——价目是按 v4-flash 配的，哪天别名指向别的模型，
   价还是旧的。要不要换成实名，是 owner 的配置决策。
2. **命中价现在没配**（`FLINT_DEEPSEEK_USD_PER_MTOK_CACHE_HIT` 未设）。
   本卡的处置是「出现命中就报错」而不是猜一个价。真跑判官之前要么配上，
   要么接受一旦命中就中断。公开价（v4-flash $0.0028/Mtok）在 §5 有出处，
   但**填进环境是 owner 的动作**，我没有替他填。
3. **本卡花了多少钱**：一次最小调用，9 输入 + 1 输出 token。
   按 v4-flash 公开价算约 $0.0000016。JUDGE-02 的 ≤$1 判官校准预算未动用。

## 10. 登记未做

1. **适配器还没有调用方**：`register_deepseek` 得由上游装配处调用，而装配处
   （谁在什么档位选哪个 provider）是 owner 决策③的面，本卡没动。
2. **账本只有内存实现**：与 `flint/billing/ledger.py` 一样，SQL 实现随 E2 接入。
   **JUDGE-03 撞上了它的实际后果**：一个跑了 516 次调用的进程被超时杀掉，
   产物已落盘而**账本随进程一起没了**，那段花费只能按单价估。
   要经得起长跑，账本得**增量落盘**（每笔写一行），不能只活在内存里。
3. **`structured_with_purpose` 的重试计费记的是最后一次的 usage**：
   重试次数记在 purpose 标签里（`(structured×N)`），但**前几次的 token 没有单独累加**——
   `_RecordingClient` 只留最后一次响应。要精确到每次重试得让包装层攒一个列表，
   那会改本卡刚定的形状；先照实登记，并在 purpose 上留下了次数，账不会假装只调了一次。
4. **没测真实的缓存命中**：录制件里 `prompt_cache_hit_tokens` 是 0（首次调用必然没命中）。
   命中路径的判据走的是构造 usage，**不是录制件**——真命中要连着发两次同前缀的请求，
   属再花一次钱的事，本卡没做。
