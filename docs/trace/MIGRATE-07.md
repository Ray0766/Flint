# MIGRATE-07 trace — PriceBook 币种核实登记 @2026-08-02

## 1 装载

与 MIGRATE-05/06 共用一次装载；本卡另读 `contracts/models.py` 的 `PricingRecord` **真件字段**。

## 2 test-first

verify_cmd `--require-sections currency,defer` 先跑 → **红** → 落盘 → **exit 0**。

## 3 核实结论：不用加字段

清单预估「PriceBook 要加币种字段」。**真件核实推翻了这个预估**——
`PricingRecord` 实测已含 `currency: str` 与 `region: str`（两字段逐字贴在文档表格里）。
所以：本轮不加字段、`contracts_v04/` 里也不为币种加字段；SCHEMA-14 做的是**存在性断言**。

表列侧另有一处：`price_entries` 加 `currency` 列（默认 `"CNY"`）——
这与 `docs/技术方案-v1.2-delta.md#E2` 的登记同源，**字段层已有、表列层补齐**，
两层对齐后不再有第三处口径。

## 4 self_review

① acceptance 映射：`## currency` 登记字段既存 + 表列与 E2 对齐；`## defer` 三项
（汇率换算／多币种分档／跨币种比价）逐条写明 **NEVER 本轮**并指向 **K8**。
反证复用同一校验器的两条断言（缺小节 / 空小节），已在 MIGRATE-05 实测。
② 无冻结件偏离：`contracts/` 零触碰——本卡只读取字段名贴进文档。
③ 无禁用词。
④ 复用共用校验器。
⑤ 装载见 MIGRATE-05。

**一条我明确写死的判断**：前端遇到非 `CNY` 的 `PricingRecord` **按原币种原样显示**，
NEVER 折算成人民币——没有汇率来源时折算就是编数字。

## 5 产出

`docs/pricebook_currency_v04.md`。
