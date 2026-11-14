# DESIGN-07 trace — 澄清问题卡（由你决定 + 全部由你决定 + 未答禁输）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-07`；
- context_refs：`WORKORDER-v04.md#5-G`（G9 一行）、`contracts_v04/models_v04.py#DesignClarify`；
- 前置产物：`web/design/chat-panel/`（DESIGN-01）、
  `web/components/graph-generate-gate/`（GRAPH-08 的「置灰必须说明为什么」口径）、
  `web/test-utils/source.ts`。
- 实测装载 ≈ 6k tokens，未超 40k。

## 2 关键设计判断

**「由你决定」是一个正经答案，不是留空**。澄清问题里总有几条用户其实无所谓——
逼他在无所谓的事上做选择，他要么随便点一个（系统于是拿到一个**假答案**），
要么干脆放弃这一轮。所以点它会明确回一个 `{deferred: true, choice: null}`，
而不是什么都不发；测试专门断这个形状。

**全局一键是「剩下的你定」，不是「推翻我刚才说的」**：已答的题不进这一键的清单。
断言用一份已答 q1 的 fixture，回调收到的恰是 `["q2","q3"]`。

**未答禁续输，但必须说明为什么**：让用户一边留着没答的问题一边继续说，
系统就得猜「这句新话是不是在回答刚才那题」——猜错的代价是整轮生成基于一个错误前提。
禁用的同时给出理由（与 GRAPH-08 的置灰同一条纪律：一个灰着又不说话的控件
只会让人以为界面坏了）。

**deferred 也算答**：三题全按「由你决定」后输入框解禁——否则这个选项就成了摆设，
用户按完发现还是不能继续，只会回去随便点选项。

**答案由上层持有**：组件内部再存一份会与上层那份漂移，用户看到的与将要发出去的
不是同一份。两条源码断言盯着（无本地 answers state、无 `setAnswers`）。

## 3 acceptance ↔ 测试映射

acceptance 唯一条（三个分句）：**每题带「由你决定」；全局「全部由你决定」一键；未答复输入框禁用**。

| 分句 | 测试名 |
|---|---|
| 每题带 | `每题都带「由你决定」，一题不落`（逐卡 within 查）、`点某题的「由你决定」= 给出一个明确的答案`、`选了具体选项就带着那个选项回去` |
| 全局一键 | `全局「全部由你决定」一键把所有未答的题一起交出去`（已答不被覆盖）、`全部答完后全局按钮消失` |
| 未答禁输 | `有未答题时输入框禁用，且说明为什么`、`全部答完（含「由你决定」）输入框解禁`、`未答计数如实` |

另三条：零题不渲染空壳、答案单一真相（源码断言）、文案 key 化。

## 4 verify

```
$ cd web && npm test -- --run design/clarify-cards  → 11 passed
$ npm test -- --run                                   → 345 passed / 45 files
$ npm run typecheck                                   → 干净
$ node tools/i18n_scan.mjs web/design --fail-on-cjk   → exit 0
```

禁用词 0；产出均为 LF。

## 5 产出

- `web/design/clarify-cards/ClarifyCards.tsx`、`ClarifyCards.test.tsx`（11 条）
- `web/messages/{zh,en}.json`：各 +5 key（75 键，键集一致）
