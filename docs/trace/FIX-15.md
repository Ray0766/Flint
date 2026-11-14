# FIX-15 · trace

**卡**：缺陷⑮——那次没抓到名字的前端红（**第三次尝试**）
**verify_cmd**：`pytest tests/v041/test_frontend_red_capture.py -q` → **13 passed**
**cycles**：1（卡面估 2）

---

## 装载清单（实际）

`docs/blocked/ONE-UNNAMED-FRONTEND-RED-NOT-CAPTURED.md` 全文（含 `FIX-08` 那一段）·
`tests/v041/test_frontend_red_capture.py` 全文 ·
`web/scripts/repeat-tests.mjs` 的用法段 · `docs/trace/FIX-04.md` §6 的口径。约 12k tokens。

---

## 结果：**30 次全绿，未复现。单据 NEVER 关。**

```
runs 30 | greens 30 | reds 0
每跑汇总行取值集合：{'Tests  831 passed (831)'}     ← 30 次逐字相同
失败用例名：[]（没有红，所以没有名字要记）
耗时 min/median/max：6421 / 6501 / 6618 ms
```

## 断点与决策日志

### 一、开工先确认：基建是上一轮建好的，本卡不重造

`FIX-08`（第 6 批）已经把脚本（`web/scripts/repeat-tests.mjs`）与判据文件建好。
本卡是**第三轮尝试**，`verify_cmd` 指向同一个判据文件。

所以判据按「**每一轮都要成立的性质**」扩，而不是按本轮的取值写——
按轮次写的话，上一轮的观测会随着那张卡的收工失去看守。
文件头因此改成 `FIX-08 / FIX-15` 两张卡共用，并写明这条理由。

### 二、这一轮**不是把同一件事又做一遍**

| | `FIX-08`（第 6 批） | `FIX-15`（本轮） |
|---|---|---|
| 每跑用例数 | 802 | **831**（本批新增 7 个判据文件） |
| `globals.css` | 那一批改过 | **本批又改过**（`REGION-11` 给 select 加宽度上闸） |
| Next dev server | 在跑 | **在跑**（`localhost:3000` 全程未停） |

第一次那条红发生在「`globals.css` 被反复改写 + dev server 监听着它」的时候。
**本轮的环境比上一轮更接近那个条件**，仍然没有复现——
这让「它与那个环境有关」这条猜想的可信度下降了一点，**但仍然不是证明**。

判据 `test_this_rounds_run_is_bigger_than_the_last_one` 把这件事机器化：
它要求本轮用例数 ≥ 831，且 30 次的汇总行**逐字一致**
（不一致说明树在跑的过程中变了，那时这 30 次不是同一个实验）。

### 三、连跑期间**不并行跑别的重活**

开跑之后我只做了两件事：读文件、打两条 HTTP 取证。
**NEVER 在连跑期间跑 pytest 全量或 playwright**——
那会自己制造一次 CPU 争抢，而抢出来的红是我自己造的，
追它等于追一个幻影。这条写在这里，因为它不写下来就会在下一轮被违反。

### 四、`NEVER 以「跑不出来就是没有」收口`（acceptance④）

三轮合计 **60 次**全绿，**仍然低于 `FIX-04` 那次的复现门槛**——
那处间歇红是 **40 次循环里第 29 次**才复现的。

`docs/trace/FIX-04.md` §6 的原话：造不出稳定红时，诚实的说法是
「**没定位到**」，NEVER 是「修好了」。

判据 `test_the_ticket_is_still_open_after_three_rounds` 断言单据仍 `open`
且单子里算出了那个合计数——**只写「本轮 30 次」的话，
下一个人无从判断还要不要接着跑**。

### 五、acceptance③ 那一半此前只做了一半

卡面要「固化成脚本**并写进 docs**」。脚本 `FIX-08` 建好了，
而说明只在**单据**与 **trace** 里——那两处是「出了什么事」的地方，
不是「该怎么做」的地方。**下一个人遇到间歇红时会去 `docs/` 找，
而不是去翻已关的单据。**

本轮新建 `docs/间歇红-连跑取证.md`：跑法 · 为什么只留汇总行不够 ·
绿多少次都不等于不存在（附 `FIX-04` 第 29 次那个实测依据）·
抓到名字之后怎么走 · **历次观测表**（三轮各自的跑数与那一轮的树）。

三条判据守它：文件在且写了跑法与那个实测依据、历次观测表里三轮都在、
用例数 802 与 831 都记着（树变过这件事本身是证据的一部分）。

---

## 改既有文件

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `docs/blocked/ONE-UNNAMED-…md` | 记到 `FIX-08` 第二轮 | 追加第三轮：跑数 / 汇总行 / 与上一轮的环境差异 / 三轮合计 60 次 / 为什么还开着 | acceptance②。**只跑不记等于没跑**：下一个人看不到你跑过 |
| `tests/v041/test_frontend_red_capture.py` | 只认 `FIX-08` 一轮 | 文件头改成两卡共用；单子判据加断言 `FIX-15` 在；新增四条（docs 那一份 / 历次表 / 本轮更大 / 三轮后仍开着） | 判据要跟着轮次长，否则第三轮跑完没有任何东西守着它 |

---

## self_review

**① 覆盖 acceptance**

| acceptance | 判据 |
|---|---|
| ① 连跑 30 次并**留下用例名** | `test_the_run_actually_happened_the_required_number_of_times` · `test_every_red_run_carries_its_test_names` · `test_the_script_captures_names_not_just_the_summary_line`（**阴性对照**：喂真实 vitest 输出，必须抽得出名字） |
| ② 全绿则写明「未复现」并保留单据 | `test_the_conclusion_matches_the_evidence` · `test_the_sheet_records_this_rounds_observation` · `test_the_ticket_is_still_open_after_three_rounds` |
| ③ 固化成脚本**并写进 docs** | `test_the_runbook_lives_in_docs_not_only_in_the_ticket` · `test_the_runbook_keeps_a_table_of_every_round` |
| ④ NEVER 以「跑不出来就是没有」收口 | 单据保持 `open`；单子与 runbook 各写一遍那个 60 次 / 第 29 次的对照 |

**② 无冻结件偏离**：本卡不碰产品代码——一行 `flint/` 与 `web/` 的实现都没改。
**③ 无禁用词**：新增/改动文件扫过，无命中。
**④ 复用断言**：脚本与判据文件均复用 `FIX-08` 的既有件，NEVER 另建一套连跑工具。
**⑤ 装载**：约 12k / 40k。

**其它门**：`ruff check tests/v041/test_frontend_red_capture.py --no-cache` All passed；
`pytest tests/v041/test_frontend_red_capture.py -q` → 13 passed。

---

## 产出文件清单

- `docs/间歇红-连跑取证.md`（新）
- `docs/blocked/ONE-UNNAMED-FRONTEND-RED-NOT-CAPTURED.md`（第三轮观测，**仍 open**）
- `tests/v041/test_frontend_red_capture.py`（9 → 13 条）
- `.ui-probe/frontend-red.json`（本轮 30 跑逐条记录）
- `docs/trace/FIX-15.md`（本文件）
