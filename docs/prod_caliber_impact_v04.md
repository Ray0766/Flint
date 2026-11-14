# harness/prod_caliber.py 影响声明 v04

> 依据 `WORKORDER-v04.md#2-J7`。校验器：`tools/check_impact_doc.py --require-refs 12`。
> **本轮 NEVER 修改 `harness/prod_caliber.py`**（重构属 §10-①）。本文件只声明影响面。

## scenarios — 12 金标场景逐条声明

场景 id 取自真件 `harness/prod_caliber.py` 的 `TOPICS`（实测 12 条，非清单转抄）。
六个模板 × 两种口径（`plain` / `channels`）：

| # | 场景 id | 模板 | 口径 | v0.4 是否改其断言 |
|---|---|---|---|---|
| 1 | `golddoc-generic-plain` | generic | plain | **否** |
| 2 | `golddoc-generic-channels` | generic | channels | **否** |
| 3 | `golddoc-thesis-plain` | thesis | plain | **否** |
| 4 | `golddoc-thesis-channels` | thesis | channels | **否** |
| 5 | `golddoc-startup-plain` | startup | plain | **否** |
| 6 | `golddoc-startup-channels` | startup | channels | **否** |
| 7 | `golddoc-engineering-plain` | engineering | plain | **否** |
| 8 | `golddoc-engineering-channels` | engineering | channels | **否** |
| 9 | `golddoc-grant-plain` | grant | plain | **否** |
| 10 | `golddoc-grant-channels` | grant | channels | **否** |
| 11 | `golddoc-vibe_pack-plain` | vibe_pack | plain | **否** |
| 12 | `golddoc-vibe_pack-channels` | vibe_pack | channels | **否** |

**逐条声明**：v0.4 不改动上述任何场景的断言、阈值与判定口径。

## why — 为什么不改

12 金标场景**只验中文产出**。v0.4 引入 `SystemLanguage ∈ {zh,en}` 之后，
中文路径的输入、模板与判据都没变，故这 12 条断言在 v0.4 下**继续成立且继续有效**。
新增的英文路径属新增覆盖面，**NEVER 挤占**这 12 条既有断言的位置。

## k7 — 免费档路线判断的数据基础改变

免费档路线判断（`0.44 vs 0.90` 悬置中）建立在**只有中文**的口径上。
双语之后，同一判断的数据基础发生改变——**这不是本轮能定的事**：

- 需要 harness **重跑**（含英文路径）才能给出新口径下的数字；
- 本轮 NEVER 改 harness、NEVER 重跑、**NEVER 拿旧数字冒充双语口径下的结论**；
- 去向：**K7**（未决项，待 owner 安排重跑）。

## scope — 本轮边界

- 不改 `harness/prod_caliber.py` 一个字符；
- 不改 `assets/golddocs/golddocs.json`；
- 不新增场景、不删场景；
- 本文件是声明，其正确性由「12 个 id 在仓库中可查」这条机器断言守着。
