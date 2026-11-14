# DEC-045-LANDING · owner 2026-08-09 五条裁决落地

**结论**：`DEC-045`~`DEC-049` 追加进 `DECISIONS-v04.md`，判据 30 条全绿（改前 19）。

装载：`docs/steward/连跑工单-v041-第9批.md#0 #2 #3 #4 #9` ·
`docs/steward/tasks-v041-b9.json`（本卡 + 相邻卡的 acceptance） · `DECISIONS-v04.md` ·
`tests/v041/test_decisions_landed.py` · `worker.md` 全文 · `CLAUDE.md#S2 #S3`
（实测装载 ≈ 21k tokens，预算 40k）

---

## 1 开工前的三件事

### ① 单实例闸（`worker.md` §2.0）

`docs/WORKER.lock` 在盘上，内容 `worker b9 2026-08-09T05:05:43.886598`。
按 §2.0 读 → 等 180 秒 → 再读：

```
05:20:29  worker b9 2026-08-09T05:05:43.886598
05:23:44  worker b9 2026-08-09T05:05:43.886598   ← 一字未变
```

**遗留锁**（上一个 worker 会话在 `DEC-043-LANDING` 收卡后未走停机四步就结束了），
覆盖为当前时间接管。

### ② 台账断点（NEVER 依赖上一轮记忆）

`docs/progress-v041.jsonl` 末 20 行：第 8 批 11/11 全 verified；
第 9 批已有 `DEC-043-LANDING` 一张 verified，其 note 写的是「第9批 1/11」。

**这里有一处口径差，记下来免得下一个会话再判一次**：那张卡收在
**11 卡口径**的第 9 批下；现在盘上的 `docs/steward/tasks-v041-b9.json` 是
**15 卡口径**，且**不含 `DEC-043-LANDING`**（它落的 043/044 已经在 `DECISIONS-v04.md` 里）。
台账 ∩ 任务文件取交集 → 15 卡里第一张未完成的就是本卡。**两个口径不矛盾**：
043/044 已落地这件事本身没变，变的是这一批还剩哪几张卡。

### ③ `:8000` 的 PID 与启动时间

本卡只写文档，不打真栈，所以没有重核——`DEC-043-LANDING` 的 trace 记的是
`PID=54640 Start=2026-08-09 04:54:36`，且**匿名走网络仍回 200**，
那一条留给 `FIX-20`。

## 2 五条裁决各自写了什么

五条是同一次对话里说的，**落成五条而不是一条**，为的是让影响面各自归位：
合成一条的话，下一个人改其中一件时无从知道另外四件是不是也跟着变。

| 条 | 核心 | 最容易在转述时掉的那一句 |
|---|---|---|
| `DEC-045` | 本版只做中国区，多源多区推迟下一版 | 推迟的是**「不同地区用不同信息源」**，不是「地区」这个功能——九区的列与 query **NEVER 删代码** |
| `DEC-046` | 地区与语言下拉挪到右上角 | 真正的约束是**两条轴各自独立**（`PRINCIPLES#A3`），不是「挪个位置」 |
| `DEC-047` | 补白天/夜间三态切换 | 「跟随系统」**MUST 是显式选项**——两态会把「我没选过」与「我选了白天」混成一个 |
| `DEC-048` | 八张缺表一次建齐 | 根因是**持久层从没建**，**不是接线没做** |
| `DEC-049` | 活入口走甲的落地口径 | 它是 `DEC-043` 的**落地口径**，不是新裁决——两者影响面不同 |

## 3 三处**没有照抄工单**的地方（本卡最实的产出）

工单与卡面上有三句话，实查之后**与事实有出入**。照抄的话它们会变成
「被判据钉住的假话」，而假话一旦进了 `DECISIONS-v04.md` 就会被后续 trace 引用。

### ① 「全仓非测试文件里 `data-theme` / `toggleTheme` / `ThemeToggle` 零命中」——范围说过头了

实查（ripgrep 全仓，排除 `node_modules`）：

```
web/…                                       ← 应用代码 0 命中（只有 _ds 的调色板与一句注释）
V0 files 前端设计/components/theme-toggle.tsx:18   export function ThemeToggle() {   ← 有
V0 files 前端设计/components/shell/app-shell.tsx:16 import { ThemeToggle } …          ← 有
```

`V0 files 前端设计/` 是 `DEC-026` 划的**视觉蓝本**、NEVER 当工程目录，
所以「缺控件」这个结论**是对的**；错的只是范围。

**为什么非改口不可**：写成「全仓」的话，下一个人 grep 一次就会以为这条裁决的
前提是假的，**进而怀疑整条裁决**——而结论本身没问题。
**说过头的真话与假话一样会被推翻**。
`DEC-047` 正文把范围写成 `web/`（`DEC-007`/`DEC-026` 定的唯一前端工程根）
并**点名**那个蓝本文件，判据 `test_dec_047_says_the_palette_exists_and_scopes_the_zero_hit_claim`
钉住这一层。

### ② 「地区与语言当前两者只在 `/settings/locale` 那一屏里」——地区不止那一屏

```
web/app/settings/locale/page.tsx   LocaleSettings + RegionSwitch
web/app/plaza/page.tsx             RegionSwitch          ← 广场页上另有一个实例
```

真相是：**外壳右上角两者都没有**（这才是 owner 说的那件事），
而 `RegionSwitch` 在广场页上已经有一个实例。`DEC-046` 正文按实况写。
**这一条直接影响 `SHELL-01` 的做法**：那张卡不是「把控件从详情屏搬到右上角」，
而是「右上角新增 + 与既有两处共用同一个值」——**三处显示同一个值**，
搬的话会把广场那个实例弄丢。`SHELL-01` 接手时不必再查一次。

### ③ 八张表：不是照抄，是**自己复核过**

steward 查的是 `pg_tables`；worker 用 `asyncpg` 直连 `postgresql://…:55432/flint` 复核：

```
库里 38 张表
MISSING: ['favorites','share_links','prefs','templates',
          'workbenches','graph_nodes','graph_edges','cluster_verdicts']   ← 八张，一张不差
```

**结论与工单一致**。这一条之所以要自己跑一遍：`DEC-048` 是四张迁移卡的
唯一依据，而「八张表都不存在」若有一张说错，那张卡的迁移就会撞上已有表。

## 4 改前 / 改后 / 为什么非改不可

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `DECISIONS-v04.md` | 23995 字节，止于 `DEC-044` | 28054 字节，**追加** 五条 | 本卡的 outputs 就是它；**既有行一字未动**（追加式写入，前 23995 字节逐字节不变） |
| `tests/v041/test_decisions_landed.py` | 19 判据 | 30 判据 | 见下 |
| `docs/WORKER.lock` | `05:05:43`（遗留） | 接管为当前时间 | `worker.md` §2.0 / §4.1 |

`test_decisions_landed.py` 的改动分两类：

**基线跟着事实走（意图一字未动）**

- `LANDED` 加五条，各挂**它必须提到的关键事实**——只断言「编号出现了」的话，
  写一行「见工单」也能过；
- 水位 `44 → 49`，全序 `range(35,45) → range(35,50)`；
- `BATCH_9` 从 `("DEC-043","DEC-044")` 扩成七条。
  **为什么不新建一个 `BATCH_9B`**：`pairwise` 判的是**批与批**的先后，
  拆成两组会让它去判 044 与 045 的先后——那是同一批**内部**的顺序，
  已经由全序判据 `test_new_entries_are_appended_after_the_existing_ones` 看着了，
  两条判据判同一件事的话，改一处会红两处而只有一处是真的。

**新增 11 条**，每条钉一句「转述时最先掉的话」：
`DEC-045` 的推迟范围与不隐藏 · `DEC-046` 的两条轴与同一个值 ·
`DEC-047` 的显式「跟随系统」与零命中的范围 · `DEC-048` 的八张表名与根因层次 ·
`DEC-049` 与 `DEC-043` 的互相点名 · 五条各自点名实现它的卡 ·
`CN-01` 的红线属性（授权 ≠ 实跑）。

**为什么水位那条非改不可**：`test_the_numbers_continue_the_existing_watermark`
判的是「最高编号 == 当前水位」。落了新条目它必红——
**红的是它描述的那个水位过去了，不是有人乱编号**。
这是第 6→7、7→8、8→9(043)、9(043)→9(045) 第**五**次同一形状，
改因续写在它自己的 docstring 里。

## 5 自审（`self_review=true`）

**① 判据真实覆盖 acceptance**

| acceptance | 判据 |
|---|---|
| DEC-045 只做中国区 + 多源多区推迟 + 九区保留不拆 | `test_dec_045_defers_the_multi_source_question_by_name`、`test_dec_045_keeps_the_other_regions_visible_instead_of_hiding_them` |
| DEC-046 右上角下拉 + `/settings/locale` 保留详情页 | `test_dec_046_names_the_two_axes_that_never_move_together`、`test_dec_046_keeps_one_value_behind_the_two_places_that_show_it` |
| DEC-047 板已建 + 全仓零切换控件 | `test_dec_047_makes_follow_the_system_an_explicit_option`、`test_dec_047_says_the_palette_exists_and_scopes_the_zero_hit_claim` |
| DEC-048 八张表一次建齐 + 根因是持久层 | `test_dec_048_names_all_eight_tables_it_creates`、`test_dec_048_says_the_root_cause_is_persistence_not_wiring` |
| DEC-049 活入口走甲 | `test_dec_049_says_which_islands_it_opens_and_defers_to_dec_043` |
| 五条都写明来由与影响面 | `test_each_decision_gives_its_reason_not_just_the_verdict`（>200 字 + 关键事实）、`test_each_decision_names_what_it_affects`、`test_the_landing_says_who_decided_and_when`、`test_the_five_new_ones_each_name_a_card_that_implements_them` |
| 追加式写入，NEVER 回改既有 DEC 行 | `test_the_existing_decisions_were_not_rewritten`、`test_new_entries_are_appended_after_the_existing_ones`、`test_each_batch_landed_after_the_one_before_it` |

**先红后绿**：改完判据、未写正文时跑一次 —— `18 failed, 12 passed`；
写完正文 —— `30 passed`。**NEVER 先写正文再补判据**。

**② 无冻结件偏离**

```
additive 校验通过：models_v04.py 保留了 models.py 的全部 87 类 / 443 字段 / 1 函数签名 / 31 别名
additive 校验通过：protocols_v04.py 保留了 protocols.py 的全部 24 类 / 1 字段 / 40 函数签名 / 0 别名
b760c2eeb4e96a96 contracts/models.py
c5664938e16469ff contracts/protocols.py
51ec00cae3d4bdde contracts_v04/models_v04.py
dcb19e99463b06e4 contracts_v04/protocols_v04.py
```

本卡只碰 `DECISIONS-v04.md` 与它的判据，四件一字未动。

**③ 无禁用词**：新增正文里 `适当` / `合理` / `必要时` / `大约` / `尽量` / `若干`
均 0 命中；`等` 命中 1 处，是「停下**等** owner」这个动词，**不是列表尾的「等」**
（`worker.md` §4.3④ 的射程）。

**④ 复用断言**：本卡无 H 组命中（只写文档）。

**⑤ 装载未超预算**：≈21k / 40k。

## 6 门

```
pytest tests/v041/test_decisions_landed.py -q     30 passed（改前 19）
ruff check tests/v041/test_decisions_landed.py    All checks passed!
```

## 7 留给下游的三句话

1. **`SHELL-01`**：右上角是**新增**，不是搬家——广场页上已有一个 `RegionSwitch` 实例，
   三处 MUST 共用同一个值（见 §3②）。
2. **`SHELL-02`**：`web/app/globals.css` 文件头那句「`_ds` 目前只有一套明色
   （全目录零 `prefers-color-scheme` / `data-theme`）」是 `DARK-01` **之前**写的，
   `DARK-01` 之后已经过期，由那张卡一并订正——本卡 outputs 只有 `DECISIONS-v04.md`，
   **NEVER 顺手改到卡外的文件**（`worker.md` §5.3 的射程）。
3. **`CN-01`**：`DEC-045` 正文已把「授权 ≠ 首次实跑」写死并配了判据
   （`test_cn_01_is_recorded_as_needing_the_owner_in_person`），
   接手时**准备到位后停下**，NEVER 自行触发。
