# DEC-060-LANDING · trace

**卡**：裁决落地（v4 调色板并入 `_ds` · 保路由局部吸收 · 本轮出卡不直接改码）
**日期**：2026-08-12 ｜ **状态**：verified

## 上岗（本会话第 15 批首次）

- `docs/FLINT-V041-B15-DONE` 不在 → 继续；
- **`docs/FLINT-V041-B14-DONE` 在**（09:39 落盘）→ 批次闸开（`batch_14_first`）；
- `docs/WORKER.lock` 不在（第 14 批收工时按 §7 删掉的）→ 建新锁 `worker b15 <UTC>`；
- 台账末行 = `SHIP-14 verified`，第 14 批十张卡全部收敛 → 本批从首卡领起；
- 真栈：`:3000` PID 57596（07:59 起，带 `FLINT_API_BASE`）· `:8000` PID 59248（07:32 起）。

## 先红后绿（顺序不可倒）

判据先写：水位断言 `59 → 60`、全序上界 `range(35, 60) → range(35, 61)`、
`LANDED` 加一行、`BATCH_15` 加进逐批相对判、三句要害各一条 + 出处一条。
**落盘前实测 9 红**（含水位那条与四条新判据），落盘后 **54 passed**。

## 落地的形状

既有 76929 字节**逐字节不动**（`前缀逐字节相等: True`），追加后 81358 字节；水位 059 → 060。

**出处这一格与前两种都不同**，条目第一行如实写：
「以下文字是 **steward 拟的选项文本**，owner 从三组选项里各选定一项」——
**NEVER 写「owner 原文」或「owner 粘贴的」**。开单
`docs/blocked/DEC-060-TEXT-IS-STEWARD-AUTHORED-OPTIONS.md`（不阻断，等 owner 一句
「措辞照落」或「我另写一版」）。单里把本仓已经出现过的三种出处并排列出来：
owner 贴的 DEC 块（055~058）· owner 工单原话（059）· steward 拟的选项文本（060）。

## 三句要害，各一条判据

| 句 | 掉了会怎样 | 判据 |
|---|---|---|
| 「换的是**值**不是位置」 | 有人把 v4 变量搬进 `app/globals.css` 当唯一层 → 退役 `_ds`、重映射约 80 组件 | `test_dec_060_says_the_palette_changes_values_not_the_layer` |
| 「保 29 条路由与 7 个导航入口」 | 有人照 v4 收成三屏，或**新建一个合并屏**（加一屏同样是改架构） | `test_dec_060_keeps_every_route_and_every_nav_entry` |
| 「12 个变量名 NEVER 引进本仓」 | `--bg`/`--panel`/`--accent` 与 `--paper`/`--surface`/`--sulfur` 两套并存，各自漂移 | `test_dec_060_bans_the_design_files_variable_names` |

三句的共同点：**任何一句掉了，剩下两句读起来仍然通顺**，而实现会走岔——
这正是「三句各断言一次」这条 acceptance 的由来。

## self_review

① 判据 ↔ acceptance：水位 + 全序（1）· 出处（1）· 三句要害（3）· 逐批相对序（1）·
   既有字节不动（既有判据 1）· 影响面/署名/日期（既有判据 3）= 本卡新增 4 条、复用 6 条。
② 无冻结件偏离：`contracts/` 未读未改。
③ 无禁用词：新增文字 grep 命中 0。
④ 复用断言在位：沿用 `test_decisions_landed.py` 既有的 `LANDED` / `BATCH_*` / `_entry` 三样，
   NEVER 另起一个判据文件。
⑤ 装载未超预算：约 7k tokens。

## 产出文件

```
DECISIONS-v04.md                                          追加 DEC-060（4429 字节）
docs/blocked/DEC-060-TEXT-IS-STEWARD-AUTHORED-OPTIONS.md  新单
tests/v041/test_decisions_landed.py                       水位/全序推一格 + 4 条新判据
```
