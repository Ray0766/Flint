# SHIP-15 · trace

**卡**：本批收尾 ｜ **日期** 2026-08-12 ｜ **状态** verified

## 顺序照卡面写死的那条

先写 trace 与台账 → 再跑五条门 → 最后只改完成态报告里的数字。

## 五条门（**单跑**，逐字）

```
ruff    All checks passed!
mypy    Success: no issues found in 323 source files
pytest  5716 passed, 2 skipped, 12 warnings in 540.91s
tsc     （无输出 = 干净）
vitest  Test Files 85 passed (85) · Tests 858 passed (858)
```

## 一条流程上的教训：**两个 pytest 并跑会互相清空测试库**

收尾时我先起了一次全跑，等它跑的时候又起了第二次——两者共用 `flint_test`，
于是第二次报 `2 failed / 6 errors`（`clusters` 表没有 `region` 列）。
那不是缺陷，是 `worker.md §9.1` 逐字警告过的形状：**测试会清空测试库**。
单跑立刻全绿（5716 passed）。**贴出去的那一份必须是单跑的。**

vitest 也遇到一次同源的抖动（一次 `1 failed`，随后连跑两次 858/858 全绿，
失败那次的输出没抓到）——同样是并跑期间那一次，报告里按实况写。

## 红的逐条点名归属

见 `docs/V041-BATCH15-COMPLETION.md#二`，三类分开数：
**判据钉着旧板/旧口径 7 条** · **真碰坏了东西 3 条** · **判据自己的缺陷 5 条**，
另加一条流程上的红（并跑）。

## 台账成对

八张卡的 `started` 与终态成对；本批**零 blocked**——五处矛盾/缺口都以
`docs/blocked/` 开单 + 卡面其余部分照做的形式收敛，不占卡的终态。
