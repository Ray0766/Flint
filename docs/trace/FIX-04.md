# FIX-04 · 间歇红：一条前端用例 5 次红 1 次

**卡** `docs/steward/tasks-v041-b4.json#FIX-04` · **cycles 1（oneshot）** ·
**self_review = true** → §5 · **owner_review = false** · **依赖** 无

## 1. 装载清单

卡面 FIX-04 · `docs/blocked/UI07-LOCALE-TEST-IS-FLAKY.md` ·
`web/vitest.config.ts` · `web/vitest.setup.ts` ·
`web/__tests__/app/ui07.test.tsx` 全文 · `web/app/settings/locale/page.tsx` ·
`web/lib/useScreenData.ts` 与 `web/lib/ScreenFetchState.tsx` ·
`web/__tests__/` 下十个 stub 全局的文件清点。约 12k tokens。

## 2. 先连跑 10 次（acceptance①）：没红

```
第 1 次: Tests  754 passed (754)
第 2 次: Tests  754 passed (754)
第 3 次: Tests  754 passed (754)
第 4 次: Tests  754 passed (754)
第 5 次: Tests  754 passed (754)
第 6 次: Tests  754 passed (754)
第 7 次: Tests  754 passed (754)
第 8 次: Tests  754 passed (754)
第 9 次: Tests  754 passed (754)
第 10 次: Tests  754 passed (754)
```

**到这一步唯一诚实的结论是「这 10 次没复现」。**
原报是 5 次红 1 次；若真是 20% 的红率，10 次全绿的概率约 11%——
这组数据削弱那个率，但**既不证明修好了，也不证明本来没问题**。
所以没有停在这里。

## 3. 嫌疑面逐个处理

**单子怀疑的 `vi.stubGlobal` 不还原**：清点属实——

```
stub 全局的文件：10 个（全部 stub "fetch"）
自己还原的（unstubAllGlobals）：0 个
```

但它**不是这次的因**：vitest 默认按文件隔离环境，一个文件的 stub 传不到另一个文件。
同文件内确实会跨用例活着，而 `ui07` 里每条要用 fetch 的用例都自己重设了 stub。

**真正的因在 `renderLoadedPage` 自己**。屏上到位要**两拍**：

| 拍 | 发生了什么 | 下拉的值 |
|---|---|---|
| 一 | 数据 ready → `ScreenFetchState` 放行 → 下拉渲染出来 | 仍是声明的默认 `zh`/`CN` |
| 二 | 对齐草稿的 `useEffect` 冲刷 | 变成后端给的 `en`/`JP` |

`waitFor(下拉存在)` 在**第一拍**就满足了。断言值的那条用例于是在两拍之间抢跑。
默认值那条用例看不出来——`zh`/`CN` 恰好就是它的期望值。

**实测复现**（把那个等法放进 40 次循环）：

```
STALE at 29: zh
× 第 29 次：selects 一出现时的值
  Tests  1 failed | 39 passed (40)
```

**这才是把因指出来的证据**——它复现了单子记的那个形状（值是 `zh` 而非 `en`）。

## 4. 改后：同一个循环三轮全绿 + 再连跑 10 次

```
40 次循环第 1 轮: Tests  40 passed (40)
40 次循环第 2 轮: Tests  40 passed (40)
40 次循环第 3 轮: Tests  40 passed (40)

修后第 1 次: Tests  754 passed (754)   …  修后第 10 次: Tests  754 passed (754)
```

**那 10 次连跑不构成证据**（修前也是 10 次全绿）——记它是因为卡面 acceptance③
要求，且它至少排除了「修改本身引入了新的间歇红」。
真正判别的是 40 次循环那一组：改前红、改后三轮全绿。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_no_flaky_globals.py -q → 6 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 301 source files
            pytest -q               → 见收卡时那一行
前端:       npm test -- --run → 754 passed（×10）；npx tsc --noEmit → 无输出
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 / 证据 |
|---|---|
| ① 先证因后修，10 次输出贴进 trace | §2 §3；`test_the_trace_records_both_runs_and_does_not_claim_a_proof_it_lacks`（**判据会检查 trace 没有把两次 10 连跑说成证明**） |
| ② stubGlobal 嫌疑面处置 | `test_stubbed_globals_are_restored_after_every_test`、`test_no_file_stubs_a_global_that_nobody_restores`（**覆盖判据**：文件自己还原或配置兜底，二者取一）、`test_the_detector_sees_a_file_that_stubs_without_restoring`（阴性对照） |
| ③ 修完再连跑 10 次全绿 | §4 |
| ④ 关闭单子 | `test_the_ticket_is_closed`；单子正文写明「怀疑的那处不是因」 |

**② 改既有文件两处**（`web/`，卡上 outputs）：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `web/__tests__/app/ui07.test.tsx` | `renderLoadedPage` 从「等下拉存在」改成「等下拉的值等于后端给的那个」 | **这是根因**（§3） |
| `web/vitest.config.ts` | 加 `unstubGlobals: true` | 单子点名要清的同类隐患；十个文件 stub、零个还原 |

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；`flint/` 一行未改；未新增依赖。

**③ 变异考 4 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 配置里去掉 `unstubGlobals` | 红 2 条 |
| ② 把 `unstubGlobals` 改成 `false` | 红 2 条 |
| ③ helper 退回「只等元素存在」 | 红（`test_the_helper_waits_for_the_value_not_for_the_element`） |
| ④ trace 里删掉 40 次循环那段 | **第一版假红**：只替掉一处，而「第 29 次」在 trace 里出现两次——判据照旧绿。全删之后才红（`没有把复现那一次的实测写下来`） |
| ⑤ trace 里抹掉连跑输出 | 红 |
| ⑥ 假变异对照：配置末尾加一行注释 | 全绿 |

变异④ 那次「绿」是**变异没造成功**，不是判据不咬——
本批第三次靠核对红/绿的**理由**发现假结果（前两次在 `WIRE-12` / `ROUTE-01`）。

**④** 装载约 12k tokens；**⑤** 禁用词六词 0 命中。

## 6. 这一处值得记住的

**「没复现」与「没问题」是两件事，「改完绿了」与「改对了」也是。**

本卡两组 10 连跑一模一样（修前全绿、修后全绿），它们对判别毫无贡献。
真正有用的是**把怀疑的那条路放进循环去逼它红**——40 次里第 29 次抓到。

一个间歇缺陷，要么能造出让它稳定红的条件，要么就还没被理解。
造不出来时诚实的说法是「没定位到」，NEVER 是「修好了」。

## 7. 登记未做

1. **`ui08.test.tsx:233` 有同形状的等法**（`waitFor(getByText(...)).toBeTruthy()`）。
   它等的是**文案本身**，而文案就是那条用例断言的东西——两拍问题不存在。
   本卡没动它，记在这里以备下次有人扫到这个形状。
2. **十个文件仍各自 stub `fetch`**：配置兜底之后没有泄漏隐患，
   但十份几乎一样的 `jsonOnce` 辅助函数可以合并到一处。属整洁范畴，不在本卡。
3. **同一天又观测到一次红，名字没抓到**：`FIX-05` 收卡前跑全局门时
   `Test Files 1 failed | 73 passed`，而当时的命令只 grep 了汇总行，
   把用例名过滤掉了（我的操作失误）。之后连跑 6 次全绿。
   **NEVER 由此推断本卡没修好、也 NEVER 推断它不存在**——
   登记在 `docs/blocked/ONE-UNNAMED-FRONTEND-RED-NOT-CAPTURED.md`，
   连同「下次怎么抓住它」的跑法。
4. **没有在 CI 上跑 N 次连跑**：本地 10 次是人工跑的。
   要让间歇红长期可见，得有一条定期重复跑的作业——那是 `SHIP` 面的事。
