# SHIP-10 · 第 10 批收尾

**结论**：12/12 卡 verified · 0 blocked；五条全局门全绿，**pytest 零 failed**。
广场今天显示的是**真词面**。

---

## 1 收工顺序（第 9 批两次返工换来的，一次都没破）

> **全局门跑完之后 NEVER 再动任何被判据读的文件。真要动，重跑。**

本卡执行的顺序：**先写 trace 与台账 → 再跑五条门 → 最后只改完成态报告的数字**。
理由：本仓有大量判据在读 `docs/blocked/*.md` · `progress-v041.jsonl` ·
`docs/trace/*` · `assets/*.json`——收工四步里
**只有完成态报告与收工标记没有任何判据读**（第 9 批 `SHIP-09` 数过一遍）。

台账那一行落下之后**单独重跑它的读者判据**再进下一步。

## 2 每张卡的 `started` 与终态成对

`blocked` 也是一次「开始过」的记号。本批 12 张全部成对，
其中三张走了返工环：

| 卡 | 事件序列 | 为什么 |
|---|---|---|
| `CN-04` | started → blocked ×3 → verified | 两半各撞一次 owner 决策点（`DEC-053` / `DEC-054`），第三次撞 outputs 边界 |
| `CN-06` | started → verified → blocked → started → verified | 收尾时暴露另一条红（探针读缓存），如实记 blocked 再收 |
| `CN-05` | started → verified ×2 | 第二条是**补记**（跑全量才发现合成夹具要跟着加一格、K1-02 关早了） |

## 3 本批的产品

**第 9 批把路接通了；这一批治的是「点了有没有反应」与「广场上是不是真数据」。**

对账器 `backend_unused_by_frontend` **21 → 16**，且剩下 16 条**逐条判过**
（`TRIAGE-02`：甲 4 条带卡号、乙 12 条各写清等哪件事，**一条排除都没有**）。

## 4 pytest 的红：**一条都没有**

逐条点名归属见完成态报告 §〇。本批一路上红过的每一条都在那张表里有主。

## 5 门

```
ruff check . --no-cache        All checks passed!
mypy --strict flint            Success: no issues found in 320 source files
pytest -q                      （见完成态报告，逐字贴出）
npx tsc --noEmit               0
npm test -- --run              85 files / 858 passed
```
