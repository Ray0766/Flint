# MIGRATE-02 trace — 技术方案 v1.2-delta 八节 @2026-08-02

## 1 装载清单（§2.3）

| 装了什么 | 字符 |
|---|---|
| MIGRATE-02 卡 | ~600 |
| `WORKORDER-v04.md#2-J2` 八节原文（50–60 行） | ~2,000 |
| §4 的 15 个类型名 + I1 枚举原文（脚本抽取） | ~900 |
| **合计** | **~3,500**（≈3.5k tokens，占预算 8.8%） |

`技术方案-v1.1.md` **未整本装载**（S6）——本卡是增量文档，只按 J2 点名的八节编号对照。
`contracts_v04/` 仍不存在（SCHEMA-00 才建）。

## 2 test-first

先写 `tools/check_techplan_delta.py` → **红**（`增量文档不存在`）→ 写八节文档 → **exit 0**。

## 3 中途两次自纠（都是「假红/假绿」问题）

1. **假绿**：初版把「引用 §4 类型名」写成「查这几个名字在不在文档里」——名单写死在校验器里，
   文档抄一遍就绿。改成**反向**：收集文档里所有 CamelCase 类型名，逐个回 §4 与 `contracts/` 核实。
2. **假红**：反向之后立刻误伤了 `CLAUDE`、`E10`、`E12`、`I12` —— 章节号被当成类型名。
   收紧候选口径为「**必须含小写字母**的 CamelCase」，缩写与章节号自然出局。
   另一个 `Translator` 经核实是工单 §5-A7 / §7-K4 的真词汇（由 I18N-03 定义、不在 §4），
   故合法性判据放宽为「§4/contracts 定义过 **或** 工单正文出现过」——笔误依然抓得到（见 t4）。

## 4 self_review（self_review=true）

### ① 测试真实覆盖 acceptance

| acceptance | 校验点 | 反证 |
|---|---|---|
| 八节各有增量条目 | 八个 `## E<n>` 齐全，且每节至少一条列表/表格行 | **t1**（删 E6 节）→ `缺 E6（故障降级矩阵）小节`；**t5**（E5 只留一句散文）→ `E5（LLM 调用层）没有增量条目（既无列表也无表格行）` |
| E2 七新表逐条在列 | 七个表名逐个字符串核对 | **t2**（`share_links` 改名）→ `E2 缺新表：share_links` |
| E6 三新降级行逐条在列 | 三条触发条件逐个核对 | **t3**（「单区源全灭」改名）→ `E6 缺降级行：单区源全灭` |
| 引用 §4 类型名 | 文档 CamelCase 全集 ∩ 已定义名 ≠ ∅；且差集必须为空 | **t4**（`SourceRegistry` → `SourceRegistery` 笔误）→ `引用了 §4 与 contracts/ 都没有定义的类型名：['SourceRegistery']` |

verify 输出实际列出被引用的 21 个类型名，均在 §4 或 `contracts/` 中。

### ② 无冻结件偏离

`contracts/` 只读（校验器只 `read_text`）。文档新增的七张表逐张标注承载类型，
全部来自 §4；既有 `price_entries` 只加列不改既有列。`contracts_v04/` 与 additive 校验器
尚不存在，**无输出可贴**。

### ③ 无禁用词

见下方命令输出（三件产出均无命中）。

### ④ 复用断言在位

H 组在本卡以**文档条款**形式落位（本卡不写代码）：E3 鉴权走既有 JWT 中间件（H2）、
E4 三种新 JobKind 注册进既有 runner 且 NEVER 新写 runner 类（H7）、E5 流式复用既有 SSE 通道（H4）、
E10 撤销栈复用既有 undo 链（H5）、E2 收藏 stale 复用 `Revalidator`（H1）、
图谱边假设复用 combo 的 hypothesis 通道（H8）。

### ⑤ 装载未超预算

~3,500 字符 ≈ 3.5k tokens，占 **8.8%**。

## 5 产出

| 文件 | 说明 |
|---|---|
| `docs/技术方案-v1.2-delta.md` | 八节增量；E2 七表 + `currency` 列 + P1 冲突处置；E6 三行 |
| `tools/check_techplan_delta.py` | 校验器，ruff 净 |

## 6 遗留（非本卡）

`tools/validate_dag_v04.py`（owner 交付、属 **MIGRATE-04** 的 outputs）仍有 `UP009` + `I001` 两处
ruff 报错，到 MIGRATE-04 处理。
