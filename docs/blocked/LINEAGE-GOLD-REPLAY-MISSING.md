# LINEAGE-GOLD-REPLAY-MISSING · 金标 50 簇齐了，但没有任何库装着它们对应的 30 天回放

**状态** open

**发现者** worker / BL-10 建度量器后对 demo 库实跑 · **发现时间** 2026-08-04
**危害** 中高 —— **S4 的 M1 出口断言「血缘准确率 ≥90%（50 簇）」今天无法评测**
**改动面** 需要一次 30 天回放灌库（资源触点 + 可能的真实源抓取）→ 归 owner / 部署面

## 实测（两把尺子互相印证）

```
$ python harness/lineage_accuracy.py --labels assets/labels.yaml --dsn …/flint
血缘准确率 0/50 = 0.00%   （**report_only**）
  样本 50 够 50；未达线（参考，判定归 owner）

$ python -m eval.lineage --labels assets/labels.yaml --dsn …/flint
lineage accuracy: 0/50 = 0.00%
expected events by kind: continued=914, dormant=5, new=50, revived=5
```

**两把尺子给出同一个数**（BL-10 的新度量器与 M1-039 的既有评测器），
所以这不是某一把尺子算错了。

## 根因不是代码，是数据

```
lineage_audit 行数: 1027
天数: 7           ← 只有 7 天
最早/最晚: 2026-06-29 .. 2026-07-05
```

而 `assets/labels.yaml` 描述的窗口是 **2026-06-24 .. 2026-07-23（30 天）**：

```yaml
window: {start: '2026-06-24', end: '2026-07-23'}
dormant_after_days: 14
```

**标注里 914 条 continued、5 条 dormant、5 条 revived 的时间线，落在库里只有 7 天**。
dormant 判定需要 14 天静默——7 天的库**structurally 不可能**产出 dormant/revived 事件。

所以：**金标（50 簇）齐了，缺的是把那 30 天真的回放进某个库**。

## 为什么这条要单独立

1. **S4 的出口断言悬着**：`CLAUDE.md#S4` 的 Open Question 行写着「血缘准确率
   ≥90%（50 簇）· M1 出口断言」。今天这条断言**既没通过也没失败——它没被评过**；
2. **0% 很容易被误读成「血缘算法坏了」**。它不是：`flint/lineage/` 的四个阶段
   （s1 延续 / s23 分合 / s4 休眠复活 / s5 新簇）各自有自己的用例且全绿。
   0% 说的是「库里没有可对照的数据」；
3. **既有评测器在 CI 里是绿的**：`tests/m1/test_m1_039.py` 显式传自己的 `--dsn`
   （测试用小库 + 构造数据），所以这个缺口**不会在任何一道门上显形**。

## 要做什么（不是 worker 能自决的）

1. 把 `assets/labels.yaml` 的 30 天窗口**回放进一个库**（`daily_ingest` × 30 天，
   或 fixture 直灌 `lineage_audit`）——这是资源触点（可能触真实源抓取，§7 红线）；
2. 回放后跑 `python harness/lineage_accuracy.py --labels … --dsn …` 取真实数字；
3. 拿那个数字对 S4 那条线做判定——**判定归 owner**，度量器恒 report_only。

## 本卡当场做了什么

- 交了度量器（**恒 report_only**，样本不足 50 就报「不判定」）；
- 把上面这次实测写进 `docs/trace/BL-10.md#5`；
- **没有**去灌库、**没有**改任何血缘代码、**没有**替 owner 判定。
