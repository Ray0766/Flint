# PAY-02 · 计费基准落地（按对话 API 用量算钱，价格从配置读）

**卡** `docs/steward/tasks-v041-b2.json#PAY-02` · **cycles 2** ·
**self_review = true** → §6 · **owner_review = true** → §7
**依赖** SHIP-01（verified）· JUDGE-01（verified）

## 1. 装载清单

卡面 PAY-02 · `flint/billing/quota.py` 全文（「配置留空 = 路径关闭」的既有口径）·
`flint/billing/ledger.py` 全文（`BillingEvent` 八字段与 append-only 纪律）·
`flint/llm/deepseek.py` 的 `UsageRecord` / `UsageLedger` 两段 ·
`DECISIONS-v04.md#DEC-024` · `flint/domain/models.py#Principal`。
约 10k tokens，预算 40k 以内。

## 2. 顺序（§4.2）

判据先落盘先跑红（`ModuleNotFoundError: flint.billing.meter`）→ 写 `meter.py` →
**27 passed** 一次过 → 变异考 19 例零存活。

## 3. 钱怎么算出来的

```
settle = input_tokens / 1_000_000 × price_per_mtok_input
       + output_tokens / 1_000_000 × price_per_mtok_output
```

token 数取自 `UsageRecord`——**调用真发生之后从响应体 `usage` 里读出来的**，不是估的。
按次收费的话，一次问「今天几号」与一次跑满上下文的深度分析收一样的钱：
用户看不出自己为什么被收这么多，我们也说不清。

判据里那笔账逐位可复核：`150000 tok × 2.00/MTok = 0.30`、`10000 tok × 8.00/MTok = 0.08`，
合计 `0.38`。

## 4. 四条不肯含糊的地方

### 4.1 配置留空 = 整条路径关闭，且「配成 0」与「没配」分得开

四项（输入单价 / 输出单价 / 币种 / 口径版本）**任缺其一**都算未配置，
`price_usage` 返回 `None`——一分钱不算、一条账不记。
沿用 `quota.py#BillingConfig` 的既有口径：半套配置比没有更危险，
它会让一半的运行被算钱、另一半不算，而两边都以为自己是对的。

**默认值是 `None` 不是 `0`**：配成 0 是一次决定（这一档免费），它照样出一笔 0 元的账；
没配是还没决定，它什么都不出。分不开的话，「我们决定这一档免费」与「定价还没定」
在账上长得一样。

关闭这件事**说得出来**（`BILLING_OFF_NOTE`）：静默返回 `None`，
调用方分不出「没配」与「这次是 0 元」。

### 4.2 金额恒服务端计算——不是「不信前端」，是**它没有入口**

`price_usage` 的签名里没有 `amount` / `price` / `total` 这类参数，
模块里也没有任何从请求体读数的路径。判据两条：一条读 `inspect.signature`，
一条扫源码里有没有 `request.` / `payload[` / `json()`。

### 4.3 空对话算 0 元，**但仍出一笔账**

一次调用都没发也要有账——不出的话，对账时那次运行凭空消失，
而「没花钱」与「没跑过」是两回事。

### 4.4 汇率四件套，显示价与结算价分离

`FxRate(rate, source, at, quote)` 四样必填，构造期就校验：
出处为空即拒（`NEVER 用一个来路不明的汇率算钱`）、汇率非正即拒、
报价方向要写成 `USD/CNY` 这种形状。

**结算价不换汇，显示价才换**。账本里记的**恒是结算价**——
记显示价的话，汇率一变历史账就跟着变了。
另有一条：报价方向要对得上结算币种，拿 `EUR/CNY` 去换 USD 结算的账是错的，直接抛。

## 5. 复用：不另起一本账

算完的钱落成 `flint/billing/ledger.py#BillingEvent`，进既有的 `BillingLedger`。
**NEVER 另起一本账**：两本账迟早对不上，而对账时谁也说不清该信哪一本。

`event_id` **由作业决定**（`sha256(owner|job_id|pricing_version)` 前 16 位），
不是每次算钱新造一个。新造的话，同一次作业重放会写进两条账（重复扣费）；
由作业决定之后，第二次落账在 `BillingLedger.append` 那里直接被 `LedgerImmutable` 拒。

**幂等的完整形态在 PAY-03**，这里先把 id 钉死——判据实测了「同作业两次算钱得到同一个
`event_id`，且账本拒绝第二次」。

## 6. 变异考：十九个，零存活

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 未配置也照算 | §4.1 | **2 failed** ✓ |
| ② `configured` 只查一项 | 半套配置 | **1 failed** ✓ |
| ③ 按次收费（不看 token 数） | acceptance① | **6 failed** ✓ |
| ④ 只算输入不算输出 | 同上 | **4 failed** ✓ |
| ⑤ 空对话不出账 | §4.3 | **1 failed** ✓ |
| ⑥ 不带用量明细 | acceptance③ | **1 failed** ✓ |
| ⑦ 上游混口径不报出来 | 对账 | **1 failed** ✓ |
| ⑧ `Charge` 不再 frozen | 金额不可改写 | **1 failed** ✓ |
| ⑨ 汇率没出处也放行 | acceptance④ | **1 failed** ✓ |
| ⑩ 0 或负汇率也放行 | 同上 | **1 failed** ✓ |
| ⑪ 报价方向不校验 | 同上 | **1 failed** ✓ |
| ⑫ 结算价也跟着换汇 | §4.4 | **2 failed** ✓ |
| ⑬ 不换汇时凭空造一个显示价 | 同上 | **1 failed** ✓ |
| ⑭ `event_id` 每次新造 | §5 | **1 failed** ✓ |
| ⑮ `event_id` 不含作业 | §5 | **1 failed** ✓ |
| ⑯ 账本记显示价而不是结算价 | §4.4 | **1 failed** ✓ |
| ⑰ 另起一本账 | §5 | **4 failed** ✓ |
| ⑱ 计费函数接受外来金额 | §4.2 | **1 failed** ✓ |
| ⑲ 模块里接网关 | 红线 | **1 failed** ✓ |

十九次变异后 `meter.py` 与变异前逐字相同（baseline 48 passed，含 SHIP-01 的 21 条连坐）。

**本卡零存活，且判据一次写对**——与前几卡不同，这里没有出现「判据取值范围混进别处
同一个词」的那种洞。原因大概是本卡的判据几乎全打在**返回值与签名**上，
而不是打在文本上：文本判据才容易被别处的同一个词喂饱。**这条经验值得带到后面的卡。**

## 7. verify、全局门与 owner_review

```
verify_cmd: pytest tests/v041/test_billing_meter.py -q → 27 passed
            （基线：ModuleNotFoundError，收集期就红）
连坐面:     + tests/v041/test_billing_skeleton.py（SHIP-01） → 48 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: no issues found in 289 source files
            pytest -q               → 3164 passed（PAY-01 收卡时 3137，本卡 +27）
```

**owner_review 三件**：

1. **单价的口径是「每百万 token，输入/输出分两栏」**。这是照 DeepSeek 与 GPT
   的计价形态定的（`UsageRecord` 本来就分这两栏）。owner 若要按「每次对话一口价」
   或「按字数」，改的是 `MeterConfig` 的字段，判据钉的是关系（跑得多花得多、
   未配置即关闭），不钉具体字段名。
2. **计费单位是「一次作业」**（`job_id`）。一次对话若跨多个作业，
   现在会出多笔账。要合并成「一次对话一笔」的话，需要一个对话 id——
   本仓现在没有这个概念。
3. **`event_id` 只含 owner + job + 口径版本**。同一作业**换了口径版本重算**会得到
   新 id，于是能再落一笔账。这是有意的（改价后重算是一次新的计费事实），
   但它意味着**口径版本是幂等键的一部分**——owner 若认为重算不该再扣，
   那要在 PAY-03 把口径版本从键里去掉。

## 8. 登记未做

1. **没有任何调用点**。`meter.py` 现在没人调——把它接进作业收尾那一步
   （算钱 → 落账）要动 `flint/analysis/deep_job.py` 一类文件，超出本卡 outputs。
   登记在此，接线属后续卡。
2. **免费额度与计费没有联动**。`quota.py` 管「还能不能跑」，`meter.py` 管「这次多少钱」，
   两者现在各算各的。「免费额度用完之后按用量收费」这条链路没有接。
3. **汇率没有来源**。`FxRate` 只规定了形态（必须带出处与时间戳），
   **没有实现任何取汇率的东西**——取汇率要联网，且属 K8 未决项。
4. **`tier` 取的是上游用量的口径版本**（没有用量时写 `no_usage`）。
   这是我按「一次对话用了哪个档，账上要看得出来」定的，卡面没有逐字规定，
   列进 §7 供 owner 过目。
5. **零网关、零密钥**（判据钉着）。真实网关接入仍是红线，等 owner 在场。
