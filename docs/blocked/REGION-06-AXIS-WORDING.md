# 登记（非阻塞）· REGION-06 的「authority 轴接 EvidenceScore.axis」与冻结件冲突（**已关闭** @2026-08-03）

**状态** closed · 2026-08-03 · `DEC-019`

**裁决（owner 2026-08-03 · DEC-019）：认可登记结论，照登记关闭。**

卡名与 acceptance ① 已按登记的第一选项改为「authority 轴**接入 axis 体系、记于 `EvidenceScore.components`**」，`WORKORDER-v04.md` 同口径两行（L39、L390）同步；`EvidenceOrigin` **维持两值**，实现与金标零漂移测试一字未动。

---

**性质**：卡的 acceptance 措辞与 `contracts/` 冻结件冲突。按 `worker.md` §1.4
以 `contracts/` 为准并留痕。卡已按冻结件口径实现并 verified，**不阻塞**。

## 冲突两侧

| 来源 | 说法 |
|---|---|
| `tasks-v04.json#REGION-06` acceptance ① | 「axis 体系新增 authority 轴且权重 1.0」，卡标题写「authority 轴接 `EvidenceScore.axis`」 |
| `contracts/models.py` 真件 | `EvidenceScore.axis: EvidenceOrigin`，而 `EvidenceOrigin = Literal["retrieved", "user_provided"]` —— **只有两值** |

## 为什么不能照字面加第三值

`axis` 的语义是**双尺判别**（审7）：retrieved 用 B4 族公式、user_provided 用 40/35/25 尺，
**跨尺不比较分数**，UI 也按 axis 分区展示。往这个字段塞 `"authority"` 会让
「按 axis 分区」的既有逻辑多出一个不该存在的区，且 authority 本身不是一把**尺**，
是一个**维度**——同一份证据既有 retrieved 尺，又有 authority 权威度。两者正交。

## 实现（已 verified）

authority 记进 `EvidenceScore.components` 三个键
（`authority_tier` / `authority_weight` / `authority_revisit`），`axis` 保持不动。
权重恒 1.0，金标分数零漂移（测试守着）。

## 需要 owner 的什么

一句话即可：**把 acceptance ① 的「接 EvidenceScore.axis」改成「接入 axis 体系（记于 components）」**，
或明确要求扩 `EvidenceOrigin` 为三值（那需要一张新的 SCHEMA 卡改 contracts_v04，
并评估既有「按 axis 分区展示 / 跨尺不比较」逻辑的影响）。
