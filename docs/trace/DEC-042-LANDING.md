# DEC-042-LANDING · trace

**卡**：裁决落地——卡片点击去向（owner 2026-08-09）
**verify_cmd**：`pytest tests/v041/test_decisions_landed.py -q` → **16 passed**
**cycles**：1

---

## 装载清单（实际）

`worker.md` 全文 · `docs/steward/连跑工单-v041-第8批.md` 全文（§2 实测 · §3 裁决 · §9 假设）·
`docs/steward/tasks-v041-b8.json`（11 卡 / 依赖 / 本卡字面）· `docs/progress-v041.jsonl` 末 6 行 ·
`DECISIONS-v04.md` 尾部与编号水位 · `tests/v041/test_decisions_landed.py` 全文。约 13k tokens。

---

## 做了什么

`DECISIONS-v04.md` 追加 `DEC-042`，编号接 `DEC-041` 水位。既有 42 条**一个字节都没动**。

裁决正文按 owner 原话拆成三条可执行的：

1. **卡片主体是导航** → 这个热点的分析界面；
2. **三个动作按钮是动作**，其中「入台」才把人带去图谱工作台；
3. **打开分析界面只是查看，NEVER 顺手跑一次分析**。

---

## 断点与决策日志

### 一、把「一句话裁决」拆成三条，而第三条 owner 没说

owner 的原话只有前两条。第三条（进入不触发）来自
`web/views/analysis/AnalysisView.tsx` 的文件头——**它是那个组件自己立的规矩**。

写进裁决而不是留在文件头，理由是：`NAV-02` 要给它建承载屏，
而**建承载屏的人最容易顺手加一句「进来先跑一次，不然屏是空的」**。
那句话看起来是在改善体验，代价是 owner 每点开一次付一次钱、
且同一个热点每次显示不同的判定——**判定本身就不再可被引用**。

这一条 `≤3 行影响` 判不了（它约束的是下一张卡的实现方向），
所以**不走 `DEC-NNN` 一行了事**，而是作为本条裁决的第三款写进去，并配判据。

### 二、点击排除区那条**已经存在**，本条只是点名它

`HOTSPOT-02` 建过点击排除区判据。裁决里点名它，是因为
「给卡片主体加个 href」是这条裁决最容易被做成的样子——
而那样做，三个动作按钮会连带变成导航热区。

判据 `test_dec_042_separates_the_card_body_from_the_action_buttons` 要求正文里
出现 `HOTSPOT-02`：不点名的话，下一个人不知道有一条现成的判据在守这件事。

### 三、`DEC-042` 不关任何单

前三批的裁决各自关掉一张 `docs/blocked/`，而这一条是**一条新的走法**，
不是对某张单的答复。`test_the_three_new_ones_say_which_sheet_they_close` 的表里
**刻意不加它**——硬塞会逼出一个不存在的单号。这条理由写在那张表的注释里。

---

## 改既有文件：`tests/v041/test_decisions_landed.py`

这是本卡唯一一处改既有文件。三批共用它（三张卡的 `verify_cmd` 都指着它）。

| 处 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| 模块 docstring | 「七条 / 两批共用」 | 「历次 / 三批共用」 | 不改的话文件开头会一直说自己只管七条，而它是八条的唯一看守 |
| `LANDED` 表 | 七条 | +`DEC-042`（挂四个必须出现的关键事实） | 新条目要有人守 |
| 水位 | `numbers[-1] == 41`、`range(35, 42)` | `== 42`、`range(35, 43)` | **红的是自己描述的那个水位过去了**。「不许跳号、不许重号」两条意图一字未改 |
| `test_the_landing_says_who_decided_and_when` | 硬写 `"2026-08-08" in body` | 改成 `re.search(r"20\d\d-\d\d-\d\d")` | `DEC-042` 是 **08-09** 裁的，硬编日期当场红。**日期本来就该跟着裁决走**——判「有一个日期」而不是「有那一个日期」 |
| `test_the_batch_seven_entries_are_the_last_three` | 「本批三条在最后」 | 改名 `test_each_batch_landed_after_the_one_before_it`，逐批相对判 | 「最后三条」过期了。改成相对判之后，**下一批再加时不用回来改** |
| 全序判据 | `range(35, 42)` | `range(35, 43)` | 同水位 |
| 关单表 | 三条 | 加注释说明 `DEC-042` 刻意不在表里 | 见断点三 |

**这一处仍在卡上 outputs 之外吗**：不在——outputs 是 `DECISIONS-v04.md`，
而判据文件是 `verify_cmd` 指定的落点，属本卡必需产物。**在此点名，供 steward 复核。**

---

## self_review（卡上 `self_review=true`）

**① 测试真实覆盖 acceptance**

| acceptance | 判据 |
|---|---|
| ① `DEC-042` 逐字追加（两个去向各自写清） | `test_every_landed_decision_is_present` · `test_the_numbers_continue_the_existing_watermark` · `test_dec_042_says_where_each_of_the_two_goes`（分析界面 / 图谱工作台 / 入台 三个词各判一次） |
| ② 影响面：主体是导航、按钮是动作，NEVER 混为一谈，点名 `HOTSPOT-02` | `test_dec_042_separates_the_card_body_from_the_action_buttons` |
| ③ 追加式，NEVER 回改 | `test_the_existing_decisions_were_not_rewritten`（钉住 032/033/034 的关键词）· `test_new_entries_are_appended_after_the_existing_ones`（全序）· `test_each_batch_landed_after_the_one_before_it`（逐批相对） |
| （附）进入不触发 | `test_dec_042_forbids_running_an_analysis_on_open`（要求正文写出**代价**：付一次钱 / 不再可被引用） |

test-first 顺序有据：判据先跑 **10 failed / 6 passed**，实现后 16 passed。

**② 无冻结件偏离**：未触碰 `contracts/` 与 `flint/domain/`。四件哈希未验（本卡不碰它们，
且第 8 批开跑实况里 steward 已核过）。

**③ 无禁用词**：对新增 703 字扫 `适当/合理/必要时/大约/尽量/若干` 与列表尾的「等」——

```
banned: []          list-tail 等: []
```

**④ 复用断言在位**：判据文件复用既有结构（`_entry` 取正文、`LANDED` 表、逐批常量），
未另起一套。

**⑤ 装载未超预算**：约 13k / 40k。

**其它门**：`ruff check . --no-cache` → All checks passed
（`RUF007` 一处：`zip(batches, batches[1:])` 改 `itertools.pairwise`）；
`python tools/check_line_endings.py` → 全 LF。

---

## 产出文件清单

- `DECISIONS-v04.md`（+1 条，追加式）
- `tests/v041/test_decisions_landed.py`（13 → 16 条，四处前提刷新）
- `docs/trace/DEC-042-LANDING.md`（本文件）
