# PriceBook 币种核实登记 v04

> 依据 `WORKORDER-v04.md#2-J9`。校验器：`tools/check_impact_doc.py --require-sections currency,defer`。
> 结论先行：**字段已存在，本轮不加字段**——清单预估的「加币种字段」经真件核实**无需执行**。

## currency — 字段既存核实

真件 `contracts/models.py` 的 `PricingRecord`（只读，本轮零触碰）实测已含：

| 字段 | 类型 | 说明 |
|---|---|---|
| `plan` | `str` | 档位 |
| `price` | `float \| None` | 价格，`None` = 未公开 |
| **`currency`** | `str` | **币种，已存在** |
| **`region`** | `str` | **地区，已存在** |
| `confidence` | `float` | 低置信 → 前端「定价待确认」[B5] |
| `captured_at` | `datetime` | 抓取时刻 |
| `url` | `str` | 出处 |

因此：

- **本轮 NEVER 修改 `contracts/`**，也无需在 `contracts_v04/` 里为币种加字段；
- SCHEMA-14 做的是**存在性断言**（断言这两个字段还在、类型没变），不是新增字段；
- 表列侧：`price_entries` 加 `currency` 列（默认 `"CNY"`），与 `docs/技术方案-v1.2-delta.md#E2`
  的登记一致——**字段层已有、表列层补齐**，两层对齐后不再有第三处口径。

## defer — 本轮明确不做的部分

| 不做什么 | 为什么 | 去向 |
|---|---|---|
| 汇率换算 | 需要汇率数据源与时点口径（同一价格换算时点不同结果不同），本轮无源 | **K8** |
| 多币种定价分档 | 分档策略是商业决策，NEVER 由执行侧代定 | **K8** |
| 跨币种比价展示 | 依赖上面两项 | **K8** |

**NEVER 本轮实现**：以上三项在 v0.4 内不写实现、不留半成品开关。
前端遇到非 `CNY` 的 `PricingRecord` 时，**按原币种原样显示**（带币种标记），
NEVER 折算成人民币——没有汇率来源时折算就是编数字。
