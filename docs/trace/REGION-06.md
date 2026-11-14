# REGION-06 trace — authority 轴接入（中性 1.0）@2026-08-02

## 1 装载
REGION-06 卡 + `contracts/models.py` 的 `EvidenceScore`/`EvidenceOrigin` 真件
+ `flint/scoring/scorer.py` 的 `DualScaleScorer` 头部。~1,800 字符 ≈ 1.8k tokens（4.5%）。

## 2 test-first
先写测试 → collection error → 实现 → **8 passed**；ruff 净、mypy 232 文件净。

## 3 与冻结件的冲突（已留单，按 §1.4 以 contracts/ 为准）
卡标题写「authority 轴接 `EvidenceScore.axis`」，但真件
`EvidenceOrigin = Literal["retrieved","user_provided"]` **只有两值**。

不能照字面加第三值：`axis` 的语义是**双尺判别**（审7）——retrieved 用 B4 族公式、
user_provided 用 40/35/25 尺，**跨尺不比较分数**，UI 按 axis 分区展示。
塞 `"authority"` 会让「按 axis 分区」多出一个不该存在的区；而且 authority 不是一把**尺**，
是一个**维度**：同一份证据既有 retrieved 尺、又有权威度，两者正交。

处置：authority 记进 `components` 三键，`axis` 不动。单见
`docs/blocked/REGION-06-AXIS-WORDING.md`（非阻塞）。

## 4 权重为什么必须是 1.0
K3 未决——authority 轴该多重要 owner 定。在那之前**唯一诚实的权重是 1.0**：
既不悄悄抬高「官方源」，也不悄悄压低 unknown。任何非 1.0 的值都是替 owner 拍板，
而且拍完金标分数会漂移，之前所有评测结论都要重来。
K3 落地时只改 `AUTHORITY_AXIS_WEIGHT` 一个常数，调用点不动。

## 5 acceptance 映射
| acceptance | 测试 |
|---|---|
| 新增 authority 轴、权重 1.0、带 K3 revisit 标记 | `test_authority_weight_is_neutral_one` / `test_weight_carries_a_k3_revisit_marker` / `test_authority_axis_is_recorded_in_components` |
| （不越界） | `test_axis_field_keeps_dual_scale_semantics`：authority NEVER 挤进 `axis` 字段 |
| 金标回归子集分数不漂移 | `test_gold_scores_do_not_drift_for_any_tier`：4 条金标 × 5 种 tier = 20 组，逐组断言 `strength` 不变——**分数不漂移正是「1.0 生效了」的证据** |
| （不改既有分量） | `test_original_components_are_preserved`：既有 components 逐键相等，新增键恰好三个（改了质量卡口径就变了） |
| （幂等） | `test_applying_twice_is_stable`：重复接轴不叠乘、不重复追加 |
| （双尺两侧都能接） | `test_user_provided_scale_also_accepts_the_axis`：authority 是第三个**维度**，不是 retrieved 专属 |

## 6 与 REGION-03 的分工（写进模块 docstring）
门是**布尔**的（仅 unknown 支撑时判 A/B 直接拒）；轴是**连续**的（将来给不同权威度不同权重）。
两者互不替代：门挡的是「来路不明的东西堆数量」，轴调的是「已知来路者之间的相对分量」。

## 7 产出
`flint/region/authority_axis.py`、`tests/v04/region/test_scorer_axis.py`（8 条）、
`docs/blocked/REGION-06-AXIS-WORDING.md`。
