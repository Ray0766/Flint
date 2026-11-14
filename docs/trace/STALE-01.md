# STALE-01 · trace

**卡**：陈旧槽——恒不显示 + 把时间戳捷径钉死（`DEC-039`）
**verify_cmd**：`pytest tests/v041/test_no_fake_staleness.py -q` → **13 passed**
**cycles**：1（卡面估 2）
**owner_review**：true —— 按 `DEC-000` 事后补审，完成后打标继续

---

## 装载清单（实际）

| 来源 | 用途 |
|---|---|
| `docs/blocked/SLOT-02-A-CLUSTER-HAS-NOTHING-THE-REVALIDATOR-CAN-JUDGE.md` 全文 | 四选一、三处禁令出处、库里 stale 的全部落点 |
| `DECISIONS-v04.md#DEC-039` | 本卡刚落的裁决 |
| `web/components/hotspot-card/HotspotCard.tsx` | 槽的现状 |
| `web/components/plaza/clusterToCard.ts` | 搬运层现状（本来就不传 `stale`） |
| `web/components/graph-node/GraphNode.{tsx,test.tsx}` | 判「在组件层隐藏」会撞什么 |
| `flint/fav/stale.py` · `flint/analysis/stale_adapter.py` | acceptance④ 的语义基线 |
| `flint/signals.py` · `flint/lineage/s4.py` · `flint/hotness.py` 相关行 | **库里正当的时间戳算术**（尺子的精度边界） |
| `tests/v041/test_plaza_stale.py` | 第 6 批交付的判据，本卡改其中一条 |

估算约 18k tokens，未超 40k 预算。

---

## 断点与决策日志

### 一、开工第一件事：查清「正当的时间戳算术」有哪些

卡面 acceptance② 写的是「全仓禁止用 `last_active` 或 `first_seen` 做算术得出陈旧」。
**照字面写一把「禁时间戳算术」的尺子，会当场废掉三个正确实现**：

| 出处 | 表达式 | 它算的是 |
|---|---|---|
| `flint/signals.py:33` | `(today - first_seen).days <= config.novelty_days` | `novelty` 新颖度信号（规格 `#3.3`） |
| `flint/lineage/s4.py:29` | `(today - last_active).days >= dormant_after_days` | `dormant` **沉寂**（血缘状态机 S4） |
| `flint/hotness.py:78` | `age_days = max(0, (today - series.first_seen).days)` | 热度衰减的年龄项 |

这正是 `SLOT-02` 单 §六 乙那句话的机器形态：
**「沉寂」是个有用的东西，但它不叫「陈旧」。**

所以尺子的规则是**两个条件同时成立**才算违规：
① 时间戳字段参与算术或比较；② 结果被绑到一个**陈旧词**上。

一把误报的尺子会在第一次误报之后被人整条注释掉——**那时它一条都不再守**。
`test_novelty_and_dormancy_and_decay_are_not_flagged` 把这条边界钉死。

### 二、「恒不显示」放在哪一层：不放在组件里

第一直觉是在 `HotspotCard` 里加一个 `false` 常量把槽关死。**查了两件事之后否掉**：

1. `HotspotCard` 不只广场在用——`GraphNode`（设计图谱节点）复用它，
   而 `web/components/graph-node/GraphNode.test.tsx` 是 **v0.4 已 verified 的判据**
   （`GRAPH-03`），第 29 行逐字断言「四个辅助槽齐全（region/日期/stale/判定）」。
   在组件层关死 = 那条判据当场红。`worker.md` §9.2：**v0.4 已 verified 的文件要改，停下报 owner**。
2. 更要紧的是语义：`GraphNode` 的 `sourceKind` 含 `deliverable`，
   而**交付物的 stale 是真能判的**（`deliverables.stale_reasons` 就是为它建的）。
   在组件层一刀切，会把一个**判得出来**的记号也关掉。

`DEC-039` 与单子 §六 甲的原话都是「本槽**在广场上**恒不显示」——范围就是广场。
广场这一侧今天已经是隐藏的（`clusterToCard` 不传 `stale`），
所以本卡不改隐藏行为，改的是**让这个「不传」从此有人守**：

- 尺子挡住「顺手用 `last_active` 补上」这条最可能的路；
- `test_the_plaza_never_borrows_the_favorite_mark` 挡住借收藏那个记号；
- `HotspotCard` 的槽注释写清**恢复条件**，让它是一次「改那一处即可」而不是考古。

**产出面因此全部落在卡上 outputs 之内**（`web/components/hotspot-card/` · `tools/` ·
`tests/v041/test_no_fake_staleness.py`），没有触碰 v0.4 封版面，无需走 `docs/blocked/`。

### 三、尺子第一版误报了三处

第一版 TS 侧按 `;` 切块、整块判「块里有时间戳字段 + 有运算符」。跑全仓报了三处：

```
web/components/graph-node/GraphNode.test.tsx:24
web/components/hotspot-card/HotspotCard.test.tsx:21
web/components/hotspot-card/HotspotCard.tsx:78
```

三处都是**假的**，根因两个：

1. `firstSeen: "2026-08-01"` 里那两个连字符长得和减法一模一样——**字符串没抹**；
2. `const full = { firstSeen: "…", stale: true }` 与解构参数
   `{ nameNative, …, firstSeen, region, stale, … }` 里两个词都在，
   **而它们之间没有任何关系**——判整块而不是判右值。

改法：剥注释 → **抹掉单双引号字符串** → 按绑定名取右值（按括号深度收边，
这样箭头函数换行也收得住）→ 只判右值。反引号模板**留着**：`${}` 里可能是真代码，
抹掉会把真违规藏起来。

### 四、判据 NEVER 把说明问题的那句话当成问题本身（本仓第八次）

`flint/fav/stale.py` 的 docstring 逐字写着「更 NEVER 按时间戳推断新鲜度」，
`StaleNotEvaluated` 抛出的中文里带着「不陈旧」。**它们是禁令的解释。**

Python 侧走 AST，只看真的把表达式绑到陈旧名上的节点（docstring 是 `Expr`、
异常消息是 `Call` 的实参，天然不在其列）；TS 侧先剥注释。
`test_the_ruler_does_not_flag_prose_that_explains_the_ban` 用一份**逐字复刻**
这两种写法的临时文件钉住这件事。

### 五、词按 token 比，不按子串

`refresh_snapshot` 里有 `fresh`，`expires_at` 里有 `expire`。
按子串比的话，一次正当的刷新逻辑会被判成伪造陈旧。
名字先按下划线与驼峰切 token 再逐个比；中文词（陈旧 / 过期 / 新鲜）没有 token 边界，按子串比。

---

## 改既有文件

### ① `web/components/hotspot-card/HotspotCard.tsx`（在 outputs 内）

- **改前**：`stale` 的文档注释是一行——「陈旧标记，来自后端 Revalidator 统一口径（§6-H1）；undefined = 未判定过」。
- **改后**：扩成一段，写明 `DEC-039`、为什么这一槽在广场上恒不显示、**槽为什么保留不删**、
  **恢复条件**（哪天产出方开始传 `stale`，改那一处即可，本文件不用动）、
  以及那条禁令与守它的尺子路径。
- **为什么非改不可**：acceptance⑤ 要求「注释写明恢复条件」。
  更实际的理由是：**一个永远不显示的槽，读起来与一个忘了接线的槽长得一模一样**。
  不写的话，下一个人要么把它删掉（删掉的代价是重新决定挂哪一格、什么记号、什么文案，
  那些当初都是照素材 `CardStack.dc.html` 定过的），要么顺手用 `last_active` 把它填上。

**渲染行为一字未改**：`stale === true` 这个条件、`data-testid`、文案 key 全部原样。
`npx vitest run components/hotspot-card components/plaza components/graph-node` → 6 文件 54 通过。

### ② `tests/v041/test_plaza_stale.py`（第 6 批交付，在 outputs 外——**唯一一处**）

- **改前**：`test_the_sheet_is_open_and_names_the_options` 断言单据**仍然 open**。
- **改后**：改名为 `test_the_sheet_is_closed_by_a_ruling_and_keeps_the_options`，
  断言 closed **且**留下了答复（点名 `DEC-039` 与 `STALE-01`），四个选项仍在单子里。
- **为什么非改不可**：owner 挑了甲、单据随之关闭，那条判据的**前提过期了**。
  不改的话它会一直红，而**红的是自己描述的那个状态过去了，不是有人偷偷关单**——
  钉死一个过期的状态，只会让下一次正常结案被判成错。

  判据的**意图**一字未改，只是换了要守的那件事：改前守「别在没答复时把单子关掉」，
  改后守「关单必须留下答复」——关了却不说 owner 挑的是哪一项，
  与悄悄关掉的**后果完全一样**。四个选项仍然要在：答案是「甲」，
  而「甲相对乙丙丁好在哪」是这次裁决唯一的推理过程，**删掉选项等于把推理擦掉只留结论**。

**这一处在卡上 outputs 之外**（outputs 是 `web/components/hotspot-card/` · `tools/` ·
`tests/v041/test_no_fake_staleness.py`）。判断为不必走 `docs/blocked/`：
改动面是一条判据的前提刷新，由本卡的关单动作直接引发，且不改任何产品行为——
但**在此点名，供 steward 复核**。

### ③ `docs/blocked/SLOT-02-…md`

- **改前**：`**状态** open`，末尾是「在 owner 挑之前，本槽维持隐藏」。
- **改后**：状态改 closed 并写明挑的是甲、落为 `DEC-039`、由 `STALE-01` 执行；
  新增一节记下交付的三样与**那条精度边界**；立单原文**一字未改**地留在下半部分。
- **为什么非改不可**：acceptance⑥ 要求关单。原文保留是因为
  那四个选项是这次裁决唯一的推理过程。

---

## self_review（卡上 `self_review=true`）

**① 测试真实覆盖 acceptance**

| acceptance | 判据 |
|---|---|
| ① `DEC-039`：陈旧槽恒不显示 | `test_the_slot_is_kept_and_says_how_to_restore_it` · `test_the_mark_still_requires_an_exact_true` · （第 6 批 `test_plaza_stale.py` 的实屏探针 `withStaleMark == 0` 仍绿） |
| ② **本卡的产品**：钉死时间戳捷径 | `test_the_repo_has_no_timestamp_derived_staleness` · `test_the_ruler_runs_clean_as_a_command` |
| ③ 阴性对照：插一处减法据此置 stale，**点名文件与行** | `test_a_python_timestamp_shortcut_is_caught_with_file_and_line`（断言 `:4:`）· `test_a_shortcut_hidden_in_a_dict_literal_is_caught`（断言 `:6:`）· `test_a_shortcut_in_a_typescript_file_is_caught`（断言 `:2:`）· `test_the_camel_case_spelling_is_caught_too` |
| ④ `Favorite.snapshot_stale` 语义一字不动 | `test_the_favorite_snapshot_stale_semantics_are_untouched` · `test_the_plaza_never_borrows_the_favorite_mark` |
| ⑤ 槽位保留但恒隐藏 + 恢复条件 | `test_the_slot_is_kept_and_says_how_to_restore_it` |
| ⑥ 关闭 `SLOT-02` 单 | `test_the_sheet_is_closed_and_records_which_option_won` |
| （精度，acceptance② 的另一半） | `test_novelty_and_dormancy_and_decay_are_not_flagged` · `test_the_ruler_does_not_flag_prose_that_explains_the_ban` |

test-first 顺序有据：判据先跑 **10 failed / 3 passed**，实现后 13 passed。

**② 无冻结件偏离**：未触碰 `contracts/` 与 `flint/domain/`。
`contracts_v04/models_v04.py#Favorite` 只被**读**（判据断言 `snapshot_stale` 字段与类型还在）。

**③ 无禁用词**：

```
$ grep -nE "适当|合理|必要时|大约|尽量|若干" tools/check_no_timestamp_staleness.py \
      tests/v041/test_no_fake_staleness.py
（无输出）
```

**④ 复用断言在位**：尺子不重写任何既有判定——它**只读**，不参与产品路径。
`flint/fav/stale.py` 仍 `import analysis_stale`（判据断言）；
广场仍走 `clusterToCard`，未新起一条搬运。

**⑤ 装载未超预算**：约 18k / 40k。

**其它门**：
`ruff check tools/ tests/v041/ --no-cache` → All checks passed（第一版有 `S112` + `BLE001`
两处：兜了个空 `except Exception: continue`。**改成不兜**——
兜住之后，一个真的解析不出来的模块会被静静跳过，而**跳过与干净长得一模一样**）；
`mypy --strict tools/check_no_timestamp_staleness.py` → Success。

---

## 产出文件清单

- `tools/check_no_timestamp_staleness.py`（新）
- `tests/v041/test_no_fake_staleness.py`（新，13 条）
- `web/components/hotspot-card/HotspotCard.tsx`（`stale` 槽注释）
- `tests/v041/test_plaza_stale.py`（一条判据前提刷新，**outputs 外，供复核**）
- `docs/blocked/SLOT-02-A-CLUSTER-HAS-NOTHING-THE-REVALIDATOR-CAN-JUDGE.md`（closed）
- `docs/trace/STALE-01.md`（本文件）
