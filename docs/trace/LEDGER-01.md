# LEDGER-01 · 台账配对守门扩到新台账 — trace

批次：v0.4.1 第 1 批。台账：`docs/progress-v041.jsonl`。

## 装载清单（实际）

| 来源 | 用途 |
|---|---|
| LEDGER-01 卡 | 卡面真相 |
| `eval/ledger_pairing.py` 全文 | 既有规则（`PAIRED_EVENTS` / `_CARD_ID` / `PRE_CONVENTION_LEGACY` / 存在性判据） |
| `eval/ledger_append.py` 全文 | `load_ledger` / `malformed_lines` |
| `docs/progress-v04.jsonl`（机读，200 行） | 历史未配对事件采集 |
| `tests/m4/test_ledger_pairing.py`（只读确认未改） | 既有测试面 |

实际装载约 9k tokens（≤40k）。

## 断点与决策

1. **旧守门盖不住新台账的根因**：`eval/ledger_pairing.py` 的
   `_CARD_ID = re.compile(r"M\d-\d{3}\Z")` 只放行 `M1-033` 这种卡号，其余 `continue`。
   v0.4 的卡号是 `SCHEMA-09`、v0.4.1 是 `ASM-01`——**一张都匹配不上**，两本台账整本被
   跳过。这一条不是推测：`test_the_existing_gate_still_skips_new_style_card_ids` 直接喂它
   一条 `ASM-01` 的孤儿 `verified`，旧守门返回空清单。
2. **规则复用、不放宽**：新覆盖面复用 `PAIRED_EVENTS` 与「存在性而非位置序」判据，只是
   去掉了卡号正则过滤。`eval/ledger_pairing.py` 与 `tests/m4/test_ledger_pairing.py`
   一字未动（工单 §3），并有一条测试直接读这两个文件断言里面没有 v0.4.1 的痕迹。
3. **白名单按 `(task_id, event)` 对，不按 task_id**：后者会让同一张卡将来新增的未配对
   事件跟着蒙混过关。有构造用例证明这一点
   （`test_a_new_gap_on_an_already_whitelisted_card_is_still_red`）。
4. **实测数与卡面数的差异（如实记录）**：卡面写「实测 71 个事件、涉 60 张卡」，本次采集
   得到 **70 个事件 / 59 张卡 / 67 个 (task_id, event) 去重对**。采集命令：

   ```python
   from eval.ledger_pairing import load_ledger, PAIRED_EVENTS
   e = load_ledger(Path("docs/progress-v04.jsonl"))
   started = {str(x["task_id"]) for x in e if x.get("event") == "started"}
   bad = [(str(x["task_id"]), str(x.get("event"))) for x in e
          if str(x.get("event")) in PAIRED_EVENTS and str(x["task_id"]) not in started]
   ```

   差 1 的来源没查到（台账 append-only，只会长不会缩）。**没有为了对上卡面的数字去凑**——
   白名单以实测为准，acceptance 要的是「清单在文件里列全」，这一点由
   `test_v04_legacy_gaps_match_the_frozen_whitelist_exactly` 双向断言（既不许有白名单外的，
   也不许白名单里有台账中已不存在的条目）。这个差异留给 owner / supervisor 判。
5. **本会话自己的一处漏拍已补**：`E2E-REALSOURCE` 先落了 `blocked` 才落 `started`
   （留卡时顺序写反）。按既有模块 docstring 的「存在性而非位置序」判据，补一条 started
   即合规，note 里写明了后置补录的缘由。这条是本卡守门的第一次真实捕获。

## 自审报告（self_review=true）

### ① 测试真实覆盖 acceptance

| acceptance | 测试 |
|---|---|
| `docs/progress-v041.jsonl` 每个 verified/blocked/review_passed/review_failed 必有前置 started，违反即红 | `test_v041_ledger_has_no_unpaired_event` + `test_v041_ledger_is_well_formed_json_lines`（顺带守 JSON 行合法性）+ **反例** `test_the_v041_check_would_catch_a_fresh_gap` |
| v0.4 历史未配对事件以显式白名单豁免，清单在文件里列全，NEVER 放宽规则本身 | `test_v04_legacy_gaps_match_the_frozen_whitelist_exactly`（**双向**：白名单外的红、白名单里过期的也红）+ `test_the_whitelist_is_listed_in_full_not_summarised`（67 条逐条、event 值必在 `PAIRED_EVENTS` 内） |
| 白名单不是通配：新增的未配对事件仍然红 | `test_a_new_gap_on_an_already_whitelisted_card_is_still_red`（同卡新事件）+ `test_a_brand_new_card_gap_is_still_red`（新卡） |
| NEVER 改 `tests/m4/test_ledger_pairing.py` 与 `eval/ledger_pairing.py` 的既有语义 | `test_the_existing_gate_keeps_its_card_id_filter`（正则、事件集、35 条 legacy 全对）+ `test_the_existing_gate_still_skips_new_style_card_ids` + `test_the_existing_gate_still_catches_old_style_gaps`（旧守门没被弄坏）+ `test_this_card_did_not_touch_the_frozen_gate_files`（读两个文件断言无本卡痕迹） |

11 条用例，无 `assert True`；反例用例 4 条。另外把既有 `tests/m4/test_ledger_pairing.py`
单独跑了一遍确认仍 9 passed。

### ② 无冻结件偏离

本卡零新增/修改产品代码，唯一产出是测试文件。`eval/` 与 `contracts/` 一字未动。

### ③ 无禁用词

```
$ grep -nE "适当|合理|必要时|大约|尽量|若干" tests/v041/test_ledger_pairing_v041.py
（无输出）
```

### ④ 复用断言在位

- 复用 `eval.ledger_pairing.PAIRED_EVENTS`（未另定义事件集）→ `test_the_whitelist_is_listed_in_full_not_summarised` 断言白名单的 event 值都取自它。
- 复用 `eval.ledger_pairing.load_ledger`、`eval.ledger_append.malformed_lines`。
- 复用 `eval.ledger_pairing.pairing_violations` 做对照（证明旧守门的行为没变）。

### ⑤ 装载未超预算

约 9k tokens < 40k。

## 产出文件

- `tests/v041/test_ledger_pairing_v041.py`（新增，11 条用例）

## verify

```
$ python -m pytest tests/v041/test_ledger_pairing_v041.py -q
11 passed in 0.04s
$ python -m pytest tests/m4/test_ledger_pairing.py -q
9 passed in 0.11s
$ python -m ruff check tests/v041/ --no-cache
All checks passed!
```
