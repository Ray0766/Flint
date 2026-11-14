# REGION-03 trace — unknown-tier 判定前置门（**并发会话产出，本会话复核采纳**）@2026-08-02

## 0 归属声明（先写清楚谁写的）

`flint/region/tier_gate.py` 与 `tests/v04/region/test_unknown_tier_gate.py`
**不是本会话写的**——它们由 21:0x 时段并行运行的第二个 worker（owner 的外层循环拉起）产出，
台账里有它自己的 `REGION-03 started/verified` 两行。

本会话（收尾方）做的是：**跑其 verify_cmd 复核 → 判定采纳 → 返工两处缺陷**。
我 NEVER 把它的产出记成自己的。

## 1 复核结果

| 复核项 | 结果 |
|---|---|
| verify_cmd `pytest tests/v04/region/test_unknown_tier_gate.py -q` | **11 passed**（复核当时） |
| acceptance ① 仅 unknown 支撑时判 A/B 被拒 | ✅ 真实覆盖：全 unknown → blocked；含一条已知 tier → 放行；**100 条 unknown 仍 blocked**（门不可累加，这条抓得准） |
| acceptance ② 门为前置检查、评分权重不动（K3） | ✅ 但**断言偏弱**，见 §2 |
| C/D 不受门约束 | ✅ 覆盖 |
| 空证据 → A/B 被拒 | ✅ 覆盖 |
| `mypy --strict` | ✅ 净 |
| **`ruff check`** | ❌ **4 处红**：`Sequence` 从 `typing` 导入（应 `collections.abc`）、import 未排序、两个未使用导入 |

**判定：逻辑正确、覆盖真实 → 采纳；lint 不过全局门 → 按返工修掉。**

## 2 本会话补强的一处断言

原测试证明「门独立于评分」的方式是 `not hasattr(result, "score")` ——
只看**结果对象**上没有 score/weight 属性。这不够：门内部完全可以读评分、按分数决定 blocked，
而结果对象照样干净。

我手工核过源码（零评分符号），并把这条核查**写成断言**
`test_gate_module_references_no_scoring_symbol`（源码层扫 `EvidenceScore`/`strength`/`axis`/
`.score`/`weight`）。K3 未决期间，authority 轴权重待 owner，门 NEVER 碰评分——现在这条由测试守着。

复核+返工后 **12 passed**，`ruff check --no-cache .` 全绿，`mypy --strict flint` 230 文件净。

## 3 对其实现判断的评价（我认可的部分）

它把门做成**布尔前置门**而不是评分权重，理由写在模块 docstring 里：
「评分权重是连续量……遇上数量多的 unknown 证据还是能凑出高分通过 A/B 门槛」。
这个判断是对的，与我原本要写的口径一致——所以我没有重写它，只补了断言强度。

## 4 产出归属一览

| 文件 | 谁写的 |
|---|---|
| `flint/region/tier_gate.py` | 并发会话（本会话只改 import 风格，零逻辑改动） |
| `tests/v04/region/test_unknown_tier_gate.py` | 并发会话 + 本会话补 1 条断言、修 3 处 lint |
