# SHIP-14 · trace

**卡**：本批收尾 ｜ **日期** 2026-08-12 ｜ **状态** verified

## 顺序照卡面写死的那条走

先写 trace 与台账 → 再跑五条门 → 最后只改完成态报告里的数字。
（反过来的话，报告里的数会是「跑之前以为的那个数」。）

## 五条门（逐字）

```
ruff    All checks passed!
mypy    Success: no issues found in 323 source files
pytest  5594 passed, 2 skipped, 12 warnings in 523.09s
tsc     （无输出 = 干净）
vitest  Test Files 85 passed (85) · Tests 858 passed (858)
```

## 红逐条点名归属（12 条，收尾全部归零）

见 `docs/V041-BATCH14-COMPLETION.md#二`。分三类：
**本批引入的**（i18n 不对称 ×6 · 裸 fetch 带出的类型与分诊 ×5 · 动态前缀 · 小标题撞车）、
**WB-07 有意改的**（顶栏次序与旧屏名字 ×3 —— 判据改判「那一屏还在」而不是「它还叫旧名字」）、
**环境的**（`:3000` 少一个环境变量 ×3，与本批改动无关）。

**三处一起改**那一条值得单记：`/deliverables/{}/quality` 接上之后，
两张分诊表的行、标题里的数、判据里的期望值三处都要动——
只改能让它变绿的那一处，就是把尺子改成量自己。

## 台账成对

每张卡的 `started` 与终态成对：`WB-03` 拆成 `-a`（verified）/`-b`（blocked），
父卡记 `blocked` 并点名两个子卡的去向；`blocked` 那两条也各有 `started`。
