# SHIP-07 · trace

**卡**：收尾——第 7 批完成态报告 + 出口全局门
**verify_cmd**：`pytest tests/v041 -q` → 全绿
**cycles**：1

## 装载清单

`docs/progress-v041.jsonl` 全量 · `docs/steward/tasks-v041-b7.json` ·
对账器实跑 · `docs/blocked/*.md` 的状态行 · 本批十一份 trace 的结论段。约 16k。

## 出口门与判据

五道门逐字贴进报告 §1，三条出口判据贴进 §2。**`pytest -q` 4648 passed 零 failed。**

## 收卡前清掉的四条连带红

跑全量时红了四条，逐条都是本批改动的连带：

1. **A3 把纯类型声明文件当成渲染件**（`web/lib/derefTypes.ts`）。
   这条规则治的是「留位处显示了假内容或空白」——那是一件**渲染时**的事，
   而一个只有 `export interface` 的文件连一个能显示那句话的位置都没有。
   要它写上「接口未提供」，写出来的是**一句它并不执行的承诺**，比不写更坏。
   改法：`appliesTo` 之后再判**有没有运行时**（函数 / 箭头 / JSX / 取数），
   **按后缀判不行**——`.ts` 里塞进真逻辑就能顺带免检。
   剥注释也是必需的：一段解释「这里为什么不需要 return」的注释会让纯类型文件
   被当成有运行时（第 12 次同一形状）。

2. **`\b=>` 永远匹配不上**。第一版写成 `/\b(function|=>|fetch\(|return\s)/`——
   `\b` 对 `=>` 无效（两侧都不是单词字符），于是箭头函数全都漏过。
   **A3 的阴性对照当场抓到了它**（`components/DerefValue.tsx` 那条应红没红）。
   这正是那条对照存在的理由。

3~4. `test_common_states` 与 `test_ds_bundle_wired` 是同一处 A3 的连带。

另有 `test_parity_dynamic_path::test_both_kinds_are_genuinely_zero_now` ——
它钉着 `7 / 8`，而 `TYPE-05/06` 把两类清零了。**这条判据的名字说的正是这件事**：
「真归零」与「因误分类而归零」不是一回事。所以改判「零 **+ 尺子仍然分得清**」，
并在原地列出四次零各自是怎么来的（`TYPE-02` 误分类 / `TYPE-04` 盲尺子 /
`GAUGE-14` 看见十五条 / `TYPE-05-06` 逐条建类型）。

## self_review

**① acceptance**：五道门逐字贴出 ✓（报告 §1）· `pytest` 零 failed ✓ ·
三条出口判据 ✓（§2）· open 单据逐条点名且说明卡在谁那里 ✓（§4，7 张分两组）·
未解决逐条列名 ✓（§5，五条，NEVER 用一句「其余无异常」）。

**② 无冻结件偏离**：本卡只写文档 + 修两把尺子的判定面。
**③ 无禁用词**：报告与 trace 扫过，无命中。
**④ 复用**：报告结构照 `docs/V041-BATCH6-COMPLETION.md`。
**⑤ 装载**：约 16k / 40k。

## 产出

- `docs/V041-BATCH7-COMPLETION.md`
- `tools/check_design_constraints.mjs`（A3 收窄，**outputs 外，供复核**）
- `tests/v041/test_parity_dynamic_path.py`（两类计数第三次换值，**outputs 外**）
- `docs/trace/SHIP-07.md`（本文件）
