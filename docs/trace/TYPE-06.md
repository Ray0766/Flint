# TYPE-06 · trace

**卡**：契约⑥——8 条端点前端根本没建类型
**verify_cmd**：`pytest tests/v041/test_type_gaps_untyped.py -q` → **13 passed**
**cycles**：1（卡面估 2）

---

## 装载清单（实际）

对账器 `--json` **重跑**（清单以实跑为准）· `flint/api/account.py` 的
`_profile` / `_memberships` / `account_json` · `flint/api/billing.py` 的
`_billing` / `_quota` / `_usage` / `event_json` / `reconciliation_json` 与信封 ·
`flint/api/design.py` 的 `template_json` / `my_templates` / replay 段 ·
`flint/api/interventions.py` 的 lock 段 ·
`tools/check_fe_be_parity.py#_frontend_interfaces` 与 `#_best_interface` ·
`docs/blocked/PARITY-WIDER-SCAN-REVEALS-FIFTEEN-TYPE-GAPS.md`。约 23k tokens。

---

## 断点与决策日志

### 一、卡面写八条，实际做**五条**

`TYPE-05` 收尾时 `/settings/locale` 与两条 deref（`/citations/{}`
`/price-entries/{}`）已经顺带建了：前者补完前六条之后**换了类别**
（untyped → mismatch），要让 `field_mismatch` 归零就得连它一起做；
后两条与那四条同住六条解引用通道，分两处建会让读的人只看到一半。

**差额如实记在单子与判据 docstring 里**——照卡面那个八去找，
会有三条怎么也找不到。

### 二、这一族的共同纪律：四种「没有」互不合并

后端在这五条上反复用同一组状态词，每一个说的都是不同的事（`DEC-032`）：
`not_checked`（没查过）· `no_record`（查过了没有）· `not_enabled`（能力在但没配）·
`not_provided`（这一族还没有后端）。

前端折成一个 `null`，屏上就只剩「没有」两个字，而这四件事要用户做的完全不同。
所以逐个建成判别联合——折叠会在 `tsc` 那一层就被拦下。

### 三、联合的分支**必须具名**（撞过一次）

第一版把分支写成匿名字面量（`type X = { … } | { … }`）。对账器
**只扫 `export interface`**，于是 `reconciliation`（只出现在 `checked` 那一支）
与 `status`（只出现在分支里）都被判成「前端没声明」，
`/billing` 与 `/design/templates` 当场从 untyped 变成 mismatch。

改成具名接口再组合联合。这不是迁就尺子——**具名分支本来就更好**：
调用方可以直接引用 `BillingEventsChecked`，而匿名分支只能重新写一遍。

### 四、`/interventions/lock`：尺子那道门**结构性地迈不过去**

这条端点成功时回 **204 无体**，`locked` 那个键来自它写进 `EditEvent.after`
的记录（`_handler_keys` 把处理函数里所有字面量 dict 的键都算作路由键）。
所以它的「响应键」只有一个。

而 `_best_interface` 的门槛是「至少两个字段重合」——
**单键响应无论前端怎么写都凑不出两个重合字段**，于是它恒被报成
「根本没建类型」，**而建了也不算**。

改法：单键响应时，要求**接口字段集与响应字段集完全相等**。
那不是巧合，是精确匹配；多键那道门**一字未改**。三条判据一起守：

- `test_a_single_key_response_is_matched_by_an_exact_interface`（精确命中）；
- `test_a_single_key_response_still_needs_an_exact_match`（**阴性对照**：
  一个更大的、恰好也有这个字段的接口仍然不算）；
- `test_the_two_key_threshold_is_untouched_for_bigger_responses`。

类型本身建成 `LockEditAfter`（**那条编辑事件的后像**），
**NEVER 编一个 `{ locked: true }` 的「响应」**——那种响应根本不存在，
照它去读 `res.locked` 拿到的永远是 `undefined`。

---

## 改既有文件

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `tools/check_fe_be_parity.py` | 单键响应恒判「没建类型」 | 单键 + 字段集相等 = 精确匹配 | acceptance③ 要求计数归零，而这条端点在改前**结构上不可能达成**。**outputs 外，供复核** |
| `tests/v041/test_types_complete.py` | 清单钉着剩余五条 | 改成空集，并写明「这一次的空与 `TYPE-04` 那次的空不是同一个空」（那次是盲尺子量的） | 前提第四次过期 |
| `docs/前后端对账表-v041.md` | 26 条 | 重跑生成，21 条 | 表是跑出来的。**outputs 外** |

---

## self_review

**① 覆盖 acceptance**

| acceptance | 判据 |
|---|---|
| ① 八条逐条建类型，清单以实跑为准 | 清单**重跑**取得；`test_each_of_the_five_is_clean_by_name`（逐条）+ 单子里记下八与五的差额 |
| ② 字段以后端真实 payload 为准 | `test_money_is_a_string_not_a_number`（后端 `str(amount)`）· `test_the_quota_numbers_are_the_backends_not_recomputed` · `test_the_four_kinds_of_absence_are_each_their_own_branch` |
| ③ `frontend_untyped_response` 归零并接成硬判据 | `test_no_endpoint_is_reported_as_untyped` + `test_the_other_type_class_is_still_zero_too`（本卡新增接口可能把别的端点从正确匹配上抢走）+ `test_the_checker_did_not_go_blind` |
| ④ 关闭那张单（两类均清零） | `test_the_ticket_is_closed_now_that_both_classes_are_zero` · `test_the_ticket_records_that_the_card_said_eight_but_five_were_left` |

**② 无冻结件偏离**：未触碰 `contracts/` 与 `flint/domain/`；后端一行未改。
**③ 无禁用词**：新增/改动文件扫过，无命中。
**④ 复用断言**：类型按「谁的 client 谁旁边」放（`accountTypes.ts` 与
`derefTypes.ts` 各成一族），NEVER 抄进 `types.ts` 再来一份。
**⑤ 装载**：约 23k / 40k。

**其它门**：`npx tsc --noEmit` exit 0；`ruff check . --no-cache` All passed；
`mypy --strict flint` 307 files Success；
对账器实跑 `field_mismatch = 0` · `frontend_untyped_response = 0`（总发现 36 → 21）。

---

## 产出文件清单

- `web/lib/accountTypes.ts`（新：account / billing / design / lock）
- `tools/check_fe_be_parity.py`（单键响应精确匹配，**outputs 外，供复核**）
- `tests/v041/test_type_gaps_untyped.py`（新，13 条）
- `tests/v041/test_types_complete.py`（清单第四次刷新，**outputs 外**）
- `docs/前后端对账表-v041.md`（重跑生成，**outputs 外**）
- `docs/blocked/PARITY-WIDER-SCAN-REVEALS-FIFTEEN-TYPE-GAPS.md`（closed）
- `docs/trace/TYPE-06.md`（本文件）
