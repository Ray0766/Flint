# HYG-02 · owner_review 复核摘要——38 张压着没人看

**卡** `docs/steward/tasks-v041-b3.json#HYG-02` · **cycles 2（卡面 oneshot=false）** ·
**self_review = true** → §5 · **owner_review = false** · **依赖** 无

## 1. 装载清单

卡面 HYG-02 · `docs/steward/tasks-v041-b2.json` 的 89 张卡（只取 `owner_review` 位与标题）·
38 张卡 trace 的 **owner 面那一节**（按 `^##.*owner|要你|请你|待定|裁决` 抽取，
逐张截 ≤420 字；全文 21 万字 **NEVER 整本装载**）· `DECISIONS-v04.md` 的
`DEC-031/032/033` 三条 · `flint/api/app.py` 的 `UNWIRED_FAMILIES`。
约 22k tokens，预算 40k 以内。

## 2. 卡面写 37，机器真相是 38

`tasks-v041-b2.json` 里 `owner_review == true` 的是 **38** 张。
差的那张是 `NET-03`：它按 `DEC-033①` 记 `skipped_by_owner`，**从没写过 trace**，
所以按「有 trace 的张数」数就是 37。

摘要按**机器真相**收 38 行。理由：卡面 acceptance③ 要的正是
「摘要里的卡号集合与 `owner_review=true` 的集合**逐字相等**」，
而**漏收一张就等于替 owner 决定那张不用看**。
那一行如实写着「无 trace · `skipped_by_owner` · `DEC-033`」——
判据要求这三样**同时**在场（少一样，那一行读起来就像一张正常结案的卡）。

## 3. 覆盖 10 张，剩 28 张要 owner 看

| 裁决 | 覆盖了什么 |
|---|---|
| `DEC-032` | `UI-01~11` 十一张的**共同问题**（未装配期间一律「接口未提供」）。其中 `UI-03~11` 九张的 owner 面**只有**这个问题 → 整张覆盖；`UI-01`/`UI-02` 各另有 3 条卡上特有的点 → 标「部分覆盖，余 3 条待看」 |
| `DEC-033` | `NET-03` 整张 |
| `DEC-031` | **不直接覆盖任何一张**。它让 `UI-03~11` 那句「未装配期间」开始逐屏失效（第 3 批 `WIRE-01/03/04` 已挂上大部分族），但四族仍未挂——摘要 §二如实写了这条差别 |

**NEVER 把 `DEC-031` 也算成覆盖**：它改变的是前提，不是那些卡的问题本身。
算进去，owner 会以为那些屏的口径问题已经消失，而其实是**它正在逐屏消失**。

## 4. 三张 trace 里根本没有 owner 面

`EYE-03` / `FB-09` / `FB-10` 三张标着 `owner_review=true`，但 trace 里
**没有任何一节是写给 owner 的**。摘要给它们写的是「§登记未做」里那条最像决策的事，
并在 §三逐字标注「**这是如实标注，不是替它们编一个问题**」。

编一个问题填进去，owner 会花时间去定一件本来没人在等的事；
留空则那三张会看起来像漏了。两者都比「说清楚它没有」更坏。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_owner_review_digest.py -q → 8 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3888 passed（HYG-01 收卡时 3880，本卡 +8）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 逐张压成一行（卡号·结论·要看的点·锚点） | `test_every_row_carries_all_four_fields`、`test_every_trace_anchor_resolves_on_disk`（**锚点要在盘上真解析得到**：指向不存在文件的锚点比没有锚点更坏，它看起来是有出处的） |
| ② 已被裁决覆盖的逐条标出 | `test_covered_rows_name_a_decision_that_really_exists`（裁决号要在 `DECISIONS-v04.md` 里真存在）、`test_both_covered_and_open_rows_exist`（**判等值**：覆盖名单就是那 10 张） |
| ③ 卡号集合与机器真相逐字相等 | `test_the_card_set_is_word_for_word_the_machine_truth`、`test_the_one_card_without_a_trace_says_so` |
| ④ NEVER 替 owner 下结论 | `test_the_digest_never_decides_for_the_owner`（禁「不必看／无需确认／已替 owner」）、`test_every_open_row_says_what_the_decision_is`（**NEVER 只写「待定」**——待定是把问题原样退回去） |

**② 改既有文件 0 处**；新增两个（都在卡上 outputs）：
`docs/owner复核摘要-v041.md` · `tests/v041/test_owner_review_digest.py`。
`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；未新增依赖。

**③ 变异考 9 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 少收一张（删掉 `K3-01`） | 红 |
| ② 多收一张（塞进一张非 `owner_review` 卡） | 红（2 条） |
| ③ **全标已覆盖** | **第一轮绿 → 改窄后红** |
| ③b 只把一张 UI 悄悄移出覆盖名单 | 红 |
| ④ 锚点指向不存在的文件 | 红 |
| ⑤ 替 owner 下结论（写「不必看」） | 红 |
| ⑥ `NET-03` 那行不说 `skipped_by_owner` | **第一轮绿 → 改窄后红** |
| ⑦ 一行只写「待定」 | 红 |
| ⑧ 假变异对照：改一句无关正文 | 全绿 |

**③ 与 ⑥ 第一轮都是判据的洞，两个洞是同一种**：

- ③ 原判据只要求「至少有一张仍待看」。把 26 行一次性翻成「已覆盖」之后，
  `UI-01`/`UI-02` 那两行的「部分覆盖…**余 3 条待看**」把非空对照喂饱了，照样绿。
  改成**判等值**（覆盖名单就是那 10 张）后当场红——这与 `GAUGE-09` 那条
  「查不到尺子的正好是 `NET-03` 那 4 条」是同一种写法。
- ⑥ 原判据写的是 `"skipped_by_owner" in row **or** "无 trace" in row`。
  把结论里的 `skipped_by_owner` 删掉之后，第四栏那个「（无 trace）」把它接住了。
  改成三样**同时**在场后当场红。

**一个 `or` 与一个「至少有一个」，是同一类松**：判据允许了「换一种方式说」，
于是被判的那件事可以整个消失而没人发现。

**④** 装载约 22k tokens；**⑤** 禁用词六词 0 命中。

## 6. 登记未做

1. **摘要没有排优先级**。排序会变成一次隐含的建议，而哪件事更要紧取决于
   owner 打算先上线哪一块。这条写进了摘要 §三，不是漏了。
2. **28 张「待看」里可能还有已被别处解决的**。本卡只对着
   `DEC-031/032/033` 三条裁决核，**没有**去对第 3 批 20 张卡的落地实况逐条核。
   举例：`GAUGE-02` 的「51 条前端 acceptance 在门外」在 `FIX-03` 之后
   仍然成立（tsc 进门了，`npm test` 没有）——这一条我核过；其余没有。
3. **摘要是快照，不是活页**。第 2 批的卡不会再变，所以卡号集合那条判据能守住；
   但「已被覆盖」这一栏会随新裁决过期——它由 `COVERED` 那个常量钉着，
   下一条裁决落地时**判据会红**，那时来这里更新。这是有意的。
