# DEC-039-041-LANDING · trace

**卡**：裁决落地——owner 2026-08-08 的三条逐字进 `DECISIONS-v04.md`
**verify_cmd**：`pytest tests/v041/test_decisions_landed.py -q` → **13 passed**
**cycles**：1

---

## 装载清单（实际）

| 来源 | 用途 |
|---|---|
| `worker.md` 全文 | 启动序列 · §9 并行纪律 |
| `docs/steward/连跑工单-v041-第7批.md` 全文 | §2 三条裁决的原文 · §3 `LOCK-01` 由来 · §9 steward 假设 |
| `docs/steward/tasks-v041-b7.json` | 12 卡 id / 依赖 / 本卡字面 |
| `docs/progress-v041.jsonl` 末 20 行 | 断点定位（第 7 批 0/12） |
| `DECISIONS-v04.md` 尾部 + 编号水位 | 接号（现有最高 `DEC-038`） |
| `tests/v041/test_decisions_landed.py` 全文 | 第 6 批建的同名判据，本卡在其上扩 |
| `tests/v041/test_ledger_pairing_v041.py` | 确认台账只被守配对与格式，无时间戳尺子 |

估算约 14k tokens，未超 40k 预算。

---

## 做了什么

`DECISIONS-v04.md` 尾部追加三条，编号接 `DEC-038` 水位：

- **DEC-039** 热点卡的陈旧槽恒不显示（走 `SLOT-02` 单的甲）
- **DEC-040** `global` 与 `NULL` 归入显式的「未归区」
- **DEC-041** demo 库种一条主题（走 `DEMO-TOPIC` 单的甲）

既有 38 条**一个字节都没动**——判据 `test_the_existing_decisions_were_not_rewritten`
逐条钉住 `DEC-032/033/034` 的关键词，`test_new_entries_are_appended_after_the_existing_ones`
判 035~041 的文件顺序与编号顺序全序一致。

## 改既有文件：`tests/v041/test_decisions_landed.py`

这是本卡唯一一处改既有文件。**改前 / 改后 / 为什么非改不可**逐处如下。

### ① 模块 docstring

- **改前**：标题写「`DEC-035-038-LANDING`：owner 2026-08-08 的**四条**裁决逐字落地」。
- **改后**：改成「七条」，并写明**两批共用这一个文件**（两张卡的 `verify_cmd` 都指着它），
  判据按「全部已落的条」写而不是按「本批那几条」写。
- **为什么非改不可**：第 7 批的 `verify_cmd` 与第 6 批指的是同一个文件路径。
  不改的话，文件开头会一直说自己只管四条——**而它实际上是七条的唯一看守**。
  按批写判据更糟：上一批的条目会随着那张卡的收工失去看守。

### ② `test_all_four_decisions_landed` → `test_every_landed_decision_is_present`

- **改前**：名字里带「four」。
- **改后**：改名，并在 docstring 里写明改名缘由。
- **为什么非改不可**：条数从四变七，名字里的「四」过期了。
  **判据的名字是它被读到的第一句话**——留着旧名字，下一个人会以为只落了四条。

### ③ `test_the_numbers_continue_the_existing_watermark`

- **改前**：`assert numbers[-1] == 38`；缺号检查是硬写的 `(35, 36, 37, 38)`。
- **改后**：`assert numbers[-1] == 41`；缺号检查改成 `range(35, 42)`。
  docstring 里写明「改前钉的是 38，第 7 批落了 039~041 之后它红了——
  **红的是自己描述的那个水位过去了，不是有人乱编号**」。
- **为什么非改不可**：这条判据的**意图**是「不许跳号、不许重号」，那一条一字未动；
  过期的只是它当时记下的水位。**钉死一个过期的水位，只会让下一次正常落号被判成错。**

### ④ `test_the_four_are_appended_after_the_existing_ones` → `test_new_entries_are_appended_after_the_existing_ones`

- **改前**：钉两对相对位置（035>034、038>037）。
- **改后**：改名去掉「四」，并从「钉两对」改成**逐对判全序**（035~041 的文件位置递增）。
- **为什么非改不可**：改名同 ②。改判法是因为钉死两对**判不住插队**——
  把 `DEC-040` 插到 `DEC-036` 前面，旧判法照样绿。

### ⑤ 新增五条判据

`LANDED` 表加三行（各挂 4 个必须出现的关键事实），另加：

| 判据 | 守什么 |
|---|---|
| `test_dec_039_bans_the_timestamp_shortcut_by_name` | 禁令 MUST 点名 `last_active` 与 `first_seen`，且写明范围是**全仓** |
| `test_dec_040_keeps_null_and_global_distinguishable_in_the_database` | 合并只在**呈现层**；`NEVER 把 NULL 回填成 global` 那句 MUST 在正文里 |
| `test_dec_041_requires_the_404_allowance_to_be_withdrawn` | 点名 `CONSOLE_BASELINE`、点名 `404`、写明**撤掉**、写明种的是**夹具** |
| `test_the_three_new_ones_say_which_sheet_they_close` | 三条各自点名关掉的那张 `docs/blocked/` 单 |
| `test_the_batch_seven_entries_are_the_last_three` | 本批三条全部落在既有条目之后 |

**为什么这三句要各挂一条判据**：三条裁决里真正在约束后续实现的**不是结论，是结论附带的那句禁令**，
而禁令恰恰是转述时最先掉的东西。掉了之后条目读起来仍然通顺——
「陈旧槽不显示」「global 归入未归区」「demo 库种一条主题」三句话各自都成立，
**而下一个实现的人拿不到边界**。

---

## 断点与决策日志

### 台账时间戳：前六批的尾部跑在了墙钟前面

开工写 `started` 事件时发现：台账最后一行是 `2026-08-09T03:10Z`，
而本机墙钟是 `2026-08-08 20:04`（本地）/ `10:04`（UTC）。**两个都对不上。**

查清了三件事再动手：

1. **台账里的 `Z` 是这本文件的书写约定，不是真的 UTC 声明**——
   全部 378 行都是「本地时间 + `Z`」，`ENTRY-02 verified` 那行 `19:40Z`
   与工单里 steward 写的「2026-08-08 19:40 核过」逐字对得上。
2. **没有时间戳尺子**：`tests/v041/test_ledger_pairing_v041.py` 只守
   ①配对（每个 `verified`/`blocked` 有前置 `started`）②JSON 行格式。单调性无人守。
3. 前六批尾部的几行**跑在了墙钟前面**（叙述性时间戳），append-only 改不动。

**处置**：本批照实写墙钟本地时间，格式沿用这本文件的约定。
后果是第 7 批第一行看起来比第 6 批最后一行**早**——
**这里写下来，是因为那个「倒退」是真的，掩盖它才是错的**。

### 编号：接 038，没有跳号

现有最高是 `DEC-038`（`re.findall(r'DEC-0(\d{2})')` 实扫，59 处引用、38 个编号）。
新落 039/040/041 连号。`DEC-002` 那条自述过一次编号顺延的先例（`DEC-001` 被 `PRIN-01` 占用），
本卡不需要顺延。

### 三条正文的取材

**逐字取自工单 §2**，没有自行改写口径。三处 steward 已经替我查过、本卡直接引用的实况：

- 全库带 stale 语义的只有 `deliverables.stale_reasons` 与 `pricebook.stale_after_months`；
- `fav/store.py:35` 自述是内存实现，`favorites` 表不存在；
- 地区分布 `global = 103` · `CN = 89` · `NULL = 1`。

---

## self_review（卡上 `self_review=true`）

**① 测试真实覆盖 acceptance**

| acceptance | 判据 |
|---|---|
| 三条逐字追加，编号接现有水位 | `test_every_landed_decision_is_present` · `test_the_numbers_continue_the_existing_watermark` |
| 每条写明来由与影响面，NEVER 只记结论 | `test_each_decision_gives_its_reason_not_just_the_verdict`（>200 字 + 各 4 个关键事实）· `test_each_decision_names_what_it_affects` · `test_the_three_new_ones_say_which_sheet_they_close` · 三条禁令各一条 |
| 追加式写入，NEVER 回改既有 DEC 行 | `test_the_existing_decisions_were_not_rewritten` · `test_new_entries_are_appended_after_the_existing_ones` · `test_the_batch_seven_entries_are_the_last_three` |

test-first 顺序有据：写完判据先跑一次，**11 failed / 2 passed**，再写正文到 13 passed。

**② 无冻结件偏离**：本卡未触碰 `contracts/` 与 `flint/domain/`。四件哈希（sha256 前 16 位）：

```
contracts/models.py            b760c2eeb4e96a96  30783 B
contracts/protocols.py         c5664938e16469ff  11099 B
requirements.lock              962d012d8ccbe3e6   1461 B
assets/heldout_questions.yaml  a80c8c73af03c8db  16286 B
```

**③ 无禁用词**：对新增 1815 字扫 `适当/合理/必要时/大约/尽量/若干` 与列表尾的「等」——

```
banned hits: []
list-tail 等: []
```

**④ 复用断言**：本卡无 H 组命中（只写文档 + 判据）。
判据文件复用第 6 批既有结构（`_entry` 取正文、`LANDED` 表），未另起一套。

**⑤ 装载未超预算**：约 14k / 40k。

**另**：`python tools/check_line_endings.py` → 「结尾一致：220 个文件全是 LF」。

---

## 产出文件清单

- `DECISIONS-v04.md`（+3 条，追加式）
- `tests/v041/test_decisions_landed.py`（扩到 13 条判据）
- `docs/trace/DEC-039-041-LANDING.md`（本文件）
