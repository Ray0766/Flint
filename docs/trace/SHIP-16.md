# SHIP-16 · 停机收尾

**第 16 批第三张卡**（`oneshot`）。1 cycle。

## 一、顺序照卡面写死的那条走

> 先写 trace 与台账 → 再跑五条门 → 最后只改完成态报告的数字。

这条不是形式：第 9 批的教训是**收工四步里只有完成态报告与收工标记没有任何判据读**
（本仓 68 个判据文件在读 `docs/blocked/*.md` · `docs/progress-v041.jsonl` ·
`docs/trace/*` · `docs/*.md`）。贴出「0 failed」之后再动其中任何一个，
owner 复跑就会得到不同的数。

## 二、跑门途中收到的一处观测，与它引出的**重跑**

跑五条门时，`vitest` 全量那一发红了一条：

```
FAIL __tests__/app/ui07.test.tsx > UI-07 · 两轴正交（A3） > 屏上改一根轴，另一根原样不动
AssertionError: expected 'CN' to be 'FR'
Test Files 1 failed | 84 passed (85) · Tests 1 failed | 857 passed (858)
```

单独连跑三次 18 passed × 3。机理是 `FIX-04` 已经证过的**两拍竞态**，
只是活在「默认回包」那条路上（那条路上「等值」区分不了两拍——
`FIX-04` 的关闭节自己写着「默认值那条用例看不出来」）。
**本批不修**（`no_new_fronts`），开单 `docs/blocked/UI07-FLAKY-AGAIN-ON-THE-DEFAULT-BODY.md`。

**开这张单意味着盘上多了一个判据读得到的文件**，而那时全量 pytest 正跑到 74%。
按第 9 批那条教训：**要动，就重跑**。所以本卡的 pytest 数字来自**第二遍**——
那一遍看到的是最终的树。第一遍的数字不作数，也没有贴出去。

同理，跑门那一发 vitest 是**与 pytest 抢机器**时跑的。
贴出去的数取**单跑**那一遍（第 15 批立过同一条规矩：并跑得到的数不能贴）。

## 二b、第一遍 pytest 的四条红，逐条点名归属

第一遍（`4 failed / 5758 passed / 2 skipped`，525.71s）——**四条全是本批引起的**，
且**没有一条是产品缺陷**：四条量的都是「源码长什么样」，而本批把源码的样子改了。

| 红 | 归属 | 为什么红 | 怎么改的 |
|---|---|---|---|
| `test_theme_toggle::test_an_explicit_choice_beats_the_system_preference_both_ways` | `TAIL-01` | **尺子读了注释**：它用 `text.index('[data-theme="dark"]')` 比先后，而我在 `colors.css` 的注释里解释「哪条规则管暗色」时写了这个选择器 → 量到注释的位置（4348 < 5265）判出假红 | 先剥注释再比位置 |
| `test_compose_e2e::test_the_demo_hands_the_queue_to_the_app` | `COMBO-WIRE-01` | 它比的是**字面量** `"create_app(DSN, redis_url=REDIS_URL)"`，而本卡给同一发调用补了 `combo_provider=` → 那一行的**格式**变了，队列那条缝一个字没变 | 改判 AST：那一发 `create_app` 的关键字参数里 MUST 有 `redis_url` |
| `test_network_discipline::test_the_repository_has_no_unguarded_live_network_today` | `COMBO-WIRE-01` | 新建的 `harness/local_model.py:54` 造 `httpx.Client(...)` 而没有 `transport=` → 守门器如实报「无护栏的真实外部请求」 | 进 `LIVE_COLLECTORS` 白名单并写明理由（本机 Ollama、零 key）。**名单反而短了一格**：这只客户端此前在 `demo_server` 与 `run_worker` 里各造一份，两处都在名单上 |
| `test_network_discipline::test_the_cli_exits_zero_on_a_clean_tree` | 同上 | 同一件事的 CLI 那一侧 | 同上 |

**三条的共同形状**：判据钉的是**源码的样子**（一行字面量 / 一个位置 / 一处客户端构造），
而不是那件事本身。本批把源码的样子改了，它们就红——**红得对**，
但改法是把它们瞄回那件事（AST / 剥注释 / 名单写明理由），
NEVER 把断言删掉或放宽成「有就行」。

## 三、五条门（逐字见完成态报告 §二）

| 门 | 结果 |
|---|---|
| ① `ruff check --no-cache .` | All checks passed |
| ② `mypy --strict flint` | 323 files, no issues |
| ③ `PYTHONIOENCODING=utf-8 pytest -q` | 见报告（第二遍，单跑） |
| ④ `npx tsc --noEmit` | exit 0 |
| ⑤ `npm test -- --run` | 见报告（单跑） |

**跑法两条**（每批都要）：`pytest` MUST 带 `PYTHONIOENCODING=utf-8`；
**NEVER 同时跑两个 pytest**（共用 `flint_test` 会互相清空，假红与真红长得一模一样）。

## 四、报告首节 =《回来时从哪接》

owner 要停约一周，所以完成态报告的第一节不是「本批做了什么」，而是
**「回来时从哪接」**：① 今天点得通到哪一步（六张截图逐屏路径 + 后两段各卡在哪张单）；
② 20 张 open 单里哪 7 张归 owner；③ 下一批最该做的三件事与各自理由。

## 五、`docs/怎么测-v041.md` 补的一节

《工作台 ·「按你选的卡建项」》：从哪进（四步）· 该看到什么（四个时刻各一行，带实测数）·
**看不到时是谁的问题**（五行表：旧进程 / 没注 provider / Ollama 慢 / 张数与假设不满足 /
右栏空态）。并把上一节里那条已经修好的排障项**划掉而不是删掉**——
删掉的话，下一个人不知道它曾经是个坑。

## 六、本批**没有**做的事（如实列在报告 §六）

主链第二三段一个字没动 · 20 张 open 单一张没做 · 支付零实现 ·
广场空态那句 v4 原文里的「2~5」没有改（被另一条已 verified 的 verbatim 判据钉着）。

**NEVER 把既有成果记成本批的活**：报告里凡提到「能点通」，只有第一段是本批接的。
