# UI07-LOCALE-TEST-IS-FLAKY · 一条前端用例 5 次里红了 1 次，重跑不复现

**状态** closed · 2026-08-06 · `FIX-04`

**发现者** worker / `UIX-02` 收卡前的全局门 · **发现时间** 2026-08-05
**危害** 中 —— **间歇红比稳定红更坏**：它会训练人「重跑一遍就好」，
而那个习惯会让下一次真缺陷也被重跑掉
**为什么登记**：本卡改的是 `jobClient` 与两个 shell 组件，与 locale 屏无关；
但**「无关」是推断，不是证据**，而我没有证据能把这次红归因清楚。

## 实测

```
第 1 次：Tests  1 failed | 749 passed (750)
        FAIL __tests__/app/ui07.test.tsx > UI-07 · 没存过就说没存过，NEVER 猜
             > 后端给的不是默认值时，屏上跟着变（证明不是写死的 zh/CN）
单独跑： npx vitest run ui07  → 17 passed
第 2~5 次（全量）：750 passed × 4
```

**单独跑恒绿，全量跑偶红** —— 这个形状指向**跨文件污染**，不指向那条用例本身。

## 最像的一处（**未证实**）

那条用例（`TYPE-02` 加的）与同文件的另几条都用
`vi.stubGlobal("fetch", …)` 换掉全局 `fetch`。

- `vitest` 默认**不**在用例之间还原 `stubGlobal`（要 `unstubAllGlobals`
  或配置 `restoreMocks` / `unstubGlobals`）；
- `web/__tests__/app/` 下多个文件都在 stub 同一个全局；
- 并发跑（vitest 默认多线程 + 同文件内串行）时，
  **哪个 stub 生效取决于调度顺序**。

若属实，修法是给测试配置加 `unstubGlobals: true`（或在 `afterEach` 里
`vi.unstubAllGlobals()`），**而不是**去改那条用例。

## 为什么不在本卡修

1. 改的是 `vitest.config.ts` 或全局 setup —— 不在 `UIX-02` 的 outputs
   （`web/components/shell/` + 一个测试文件）；
2. **根因未证实**。上面那段是「最像」，不是实测出来的因果。
   照猜的去改，可能只是把现象挪走：下次它会以另一条用例的形态出现，
   而那时连这次的线索都没有了。

## 建议怎么查（给下一个人）

1. `npx vitest run --no-file-parallelism` 连跑 20 次，看是否恒绿——
   绿则并发嫌疑坐实；
2. 若坐实，加 `unstubGlobals: true` 后**再连跑 20 次**——
   **一次绿不算数**（`ASM-03` 那张卡的原话：本题就是「绿得不明不白」）；
3. 顺带清点 `web/__tests__/` 里所有 `stubGlobal` 的用法，
   **同一个全局被两个文件 stub** 的地方都记下来。

## 本卡怎么处置的

- 连跑 4 次全绿（`750 passed` × 4），**如实记在 trace 与台账里**；
- **NEVER 写成「全绿」了事**——那等于把一次真实观测抹掉。

---

## 关闭（`FIX-04` · 2026-08-06）

**单子里怀疑的那处不是因。** 清点属实（十个文件 stub 同一个 `fetch`、
`unstubAllGlobals` 用量为 0），但 vitest 默认按文件隔离环境，跨文件传不过去。

**真正的因在 `renderLoadedPage` 自己**：它 `waitFor(下拉存在)` 就返回，
而屏上到位要**两拍**——

1. 数据 ready、`ScreenFetchState` 放行、下拉渲染出来；**此时草稿仍是默认 zh/CN**；
2. 对齐草稿的 `useEffect` 冲刷，值才变成后端给的那个。

只等第一拍，断言值的那条用例就在两拍之间抢跑。默认值那条用例看不出来——
zh/CN 恰好就是它的期望值；非默认值那条才会红。

**实测复现**（把那个等法放进 40 次循环）：

```
STALE at 29: zh
× 第 29 次：selects 一出现时的值
  Tests  1 failed | 39 passed (40)
```

**改后同一个循环，三轮各 40 次全绿**：`Tests  40 passed (40)` × 3。

## 两件事都做了，但分得清

| 改动 | 是不是那次红的因 |
|---|---|
| `renderLoadedPage` 等的是**值**不是元素存在 | **是** |
| `vitest.config.ts` 加 `unstubGlobals: true` | **不是**——同类隐患，本单点名要清 |

把第二件写成「修好了 flaky」就是把一次真实观测抹掉。

**连跑记录**：修前 10 次全绿（754 passed × 10）、修后 10 次全绿。
**两组一样，所以它们不构成证据**——把因指出来的是上面那 40 次循环。

