# MIGRATE-04 trace — 基线 tasks.json 补丁 + 合并校验 @2026-08-02

## 1 装载清单

| 装了什么 | 字符 |
|---|---|
| MIGRATE-04 卡 + `WORKORDER-v04.md#2-J5` | ~900 |
| `tools/validate_dag_v04.py` 全文（162 行，owner 交付件，要按它的 patch 格式产出） | ~5,600 |
| `tasks.json` 的**结构与计数**（脚本统计） | ~500 |
| **合计** | **~7,000**（≈7k tokens，占 17.5%） |

`tasks.json` 232 卡 **NEVER 整本装载**（172,065 字符）——只用脚本取字段名与计数。

## 2 数字先核实，再动手

acceptance 给了两个数字，先各自核对真件：

| acceptance 说 | 真件实测 | 一致 |
|---|---|---|
| 77 张 review_gate 卡 | `review_gate == true` 恰 **77** | ✅ |
| FE/FE-CORE/FV 15 卡 | 前缀匹配恰 **15** | ✅ |

**额外发现**：这 15 张 FE 卡**全部落在那 77 张 review_gate 之内**（合并后 patch 条数是 77 而非 92）。
这不是漏打，是两个集合本身有包含关系——已在断言里显式验证（`FE 卡是否全在 77 张 review_gate 之内: True`）。

## 3 test-first

verify_cmd 先跑 → **红**：`FileNotFoundError: tasks-m1m4-v04-patch.json` → 生成补丁 → **exit 0**。

## 4 补丁规则（写进补丁文件本身，可逐字复现）

- **规则一**：base 中 `review_gate == true` 的每张卡 → `self_review=true` + `review_gate_deprecated` 说明；
  **原 `review_gate` 字段原样保留，NEVER 删**（acceptance 要求「原字段保留 deprecated」）。
- **规则二**：`task_id` 以 `FE-` / `FE-CORE-` / `FV-` 开头的每张卡 → `impacted_by_v04=true`。
- 两条规则纯按 base 判定，同时命中的卡合并为一条 patch。规则原文写在补丁的 `rule` 字段里，
  所以补丁**不依赖某个一次性脚本**也能复现。

## 5 验收实测

```
exit: 0 | acyclic: True | errors: [] | coverage: 1.0
nodes: 232 | edges: 412 | total_cycles: 270.0
self_review 卡数（合并后）: 77
review_gate 原字段仍在且已转 self_review: 77 张
带 deprecated 说明: 77 张 | impacted_by_v04: 15 张
```

「原字段保留」这条不是看补丁写法推断的，是**把补丁真的合并进 base 之后**去数合并结果里
`review_gate` 与 `self_review` 同时为真的卡（77 张）。

## 6 self_review（self_review=true）

① **acceptance 映射**：三条 acceptance 各有实测数字（§5），且「原字段保留」走的是合并后取数、
不是读补丁自证。合并 DAG 的 acyclic / coverage 由 owner 交付的校验器判定，不是我自己写的断言。
② **无冻结件偏离**：本卡不碰 `contracts/`；`tasks.json` **零修改**——补丁是独立文件，
合并只发生在校验器内存里（这也是 owner 交付件的设计），基线文件 mtime 未变。
③ **无禁用词**：补丁与工具均无命中。
④ **复用**：DAG 校验**完全复用** owner 交付的 `tools/validate_dag_v04.py`，NEVER 自写第二个校验器。
⑤ **装载**：~7,000 字符 ≈ 7k tokens，占 17.5%。

## 7 顺手收掉的既存红（本卡 outputs 之一）

`tools/validate_dag_v04.py` 是本卡 outputs、由 owner 预先交付，进仓时带两处 ruff 红：
`UP009`（多余的 `# -*- coding: utf-8 -*-`）与 `I001`（`import argparse, json, sys` 未拆未排序）。
两处都只动 import 排版，**零行为变更**——修完复跑 verify_cmd，输出与修前逐字一致（exit 0 / errors []）。

至此 `ruff check --no-cache .` **全仓 All checks passed**。

## 8 产出

| 文件 | 说明 |
|---|---|
| `tasks-m1m4-v04-patch.json` | 77 条 patch（含 15 张 FE 卡的 `impacted_by_v04`），带规则说明与计数 |
| `tools/validate_dag_v04.py` | owner 交付件，本卡只修 ruff 排版 |

**未动**：`tasks.json`（基线，零修改）、`contracts/`。
