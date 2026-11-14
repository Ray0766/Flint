# 登记（非阻塞）· SCHEMA-05 acceptance 的「frozen」与真件冲突（**已关闭** @2026-08-03）

**状态** closed · 2026-08-03 · `DEC-019`

**裁决（owner 2026-08-03 · DEC-019）：认可登记结论，照登记关闭。**

`tasks-v04.json#SCHEMA-05` acceptance ① 已按登记的第一选项改为「name_native 写后读回字节等同（**写路径**拒二次赋值）」，对齐真件（`Cluster` 非 frozen dataclass，写一次由 `__setattr__` 守）。实现与测试**一字未动**；改后复跑 `test_i4_names.py` + `test_scorer_axis.py` 17 passed、`validate_dag_v04 --file` acyclic / nodes 104 / errors []。

---

**性质**：`tasks-v04.json` 的 acceptance 措辞与 `contracts/` 真件冲突。按 `worker.md` §1.4，
以 `contracts/` 为准并**必须留痕**——本文件即留痕。卡已按真件口径实现并 verified，**不阻塞**。

## 冲突两侧

| 来源 | 说法 |
|---|---|
| `tasks-v04.json#SCHEMA-05` acceptance ① | 「name_native 写后读回字节等同（**frozen 拒二次赋值**）」 |
| `contracts/models.py` 真件 | `Cluster` 是**非 frozen** 的 `@dataclass` |
| `docs/schema_reconcile_prefill_v04.md` 注记 2 | 「真件非 frozen dataclass → 『name_native 拒改写』由**写路径校验与测试**保证」 |
| `WORKORDER-v04.md#3-B7`「违反时」 | 「**写路径校验**拒绝对 name_native 的改写（真件为非 frozen dataclass，权威性由校验与测试保证）」 |

四份里有三份（真件 + 预填表 + 工单 §3）口径一致，只有 tasks-v04.json 的 acceptance 措辞滞后。

## 为什么不能照 acceptance 字面把 Cluster 改 frozen

`Cluster` 有 `status` / `last_active` / `merged_into` / `aliases` 等**本来就要变**的字段
（簇活跃度、合并血缘每日更新）。把整个类改 frozen 会改变这些既有字段的可变性语义——
那不是「增量」，是改既有契约，越过 §4.3① 的边界。

## 实现（已 verified）

**字段级写一次**：`Cluster.__setattr__` 拒绝对 `name_native` 的二次赋值，其余字段照常可变。
既满足 acceptance 的**意图**（拒二次赋值 + 字节等同），又不动既有字段语义。

测试 `tests/v04/schema/test_i4_names.py`：
- 三个真实原文样本（日文 / 全角字母与全角空格 / 韩文含连续空格）写后读回**字节**等同；
- 二次赋值抛 `AttributeError` 且原值保持不变；
- `test_other_fields_stay_mutable` 反向断言其余字段仍可变（防止我「顺手全钉死」）。

## 需要 owner 的什么

一句话即可：**把 acceptance ① 的「frozen 拒二次赋值」改成「写路径拒二次赋值」**（措辞对齐真件），
或明确要求整类 frozen（那样需要另开卡处理既有字段的可变性影响）。
在此之前按当前实现继续。
