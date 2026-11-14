# REGION-CN-HK · trace

**卡**：`DEC-056` 两区分家——CN = 微博热搜，HK = Google 趋势，两区都可切。
**结果**：verified · 2 cycles · 新判据 16 条全绿（零 skip）· 两张单开给 owner。

## 装载清单

| 来源 | 用途 |
|---|---|
| `DECISIONS-v04.md#DEC-054` · `#DEC-056` | 代理口径与它的撤销 |
| `flint/sources/gtrends.py` | `FETCH_GEO` / `EMIT_REGION` / 署名 |
| `flint/region/version_scope.py` · `#region_of_members`（`backfill.py`） | 范围记录 · 跨区口径 |
| `flint/api/views.py#plaza` | `_selectable_regions` · `region_in_scope` |
| `contracts_v04/models_v04.py#Region` · `tools/check_frozen_additive.py` | 清单真相 · 加成员的合法性 |
| `tests/v041/test_cn_only_scope.py` · `test_regions_from_backend.py` · `test_cn04_source_repair.py` | 被本卡推翻前提的三把尺子 |

## 断点一：`EMIT_REGION` 改成 HK 之后，HK 区一条都取不到

改完常量、跑完迁移，广场 `region=HK` 回 **400 `unknown region 'HK'`**。

**根因不是接线，是清单**：`_selectable_regions()` 取 `contracts_v04.Region`，
而那是一个**九个成员的 Literal，里面根本没有 HK**：

```
Region = Literal["CN", "US", "AU", "SG", "JP", "KR", "GB", "IT", "FR"]
```

`DEC-056` 写「两区都可切」，而 HK **原本不是一个可选区**。这件事 DEC 文本里没有出现——
owner 大概默认它在九区里。

### 为什么这不是 S9 的「冻结件不够用」

先核了三件事，三件都成立才动手：

1. **`Region` 不在原冻结件里**。`contracts/models.py` 里没有 `Region`
   （`grep` 零命中），它是 `contracts_v04` 的 **v0.4 纯新增**块。原件零触碰。
2. **加成员是校验器明确允许的**。`tools/check_frozen_additive.py` 自述：
   「模块级类型别名（`Literal[...]`）——成员集合 base ⊆ v04」「加别名成员：全部允许」。
   改后实跑：`保留了全部 87 类 / 443 字段 / 1 函数签名 / 31 别名；新增 17 类、18 字段、10 枚举/联合成员`。
3. **改动来源合法**。该文件头写着「改动只能来自 ⑧ 对抗性推演产出的 v0.4 修订 ∨ **owner 变更**」，
   `DEC-056` 就是 owner 变更。

所以这是「冻结件够用、且这条路是它自己开的」，不是「不够用」。**没有停**。

## 断点二：`DEC-056` 说「其余七区」，而实际是八区

九区去掉 CN 剩八个；HK 加进来一共十区，CN 与 HK 之外**还是八个**。
「七」只有在 HK 本来就在九区里时才成立。

处置（开单 `docs/blocked/REGION-CN-HK-COUNT-SAYS-SEVEN.md`）：

- `DECISIONS-v04.md` **原文一字不改**——那是记录，改它等于修改 owner 说过的话；
- 代码里写**真数**——那是执行，写错数下一版解除收窄时会漏一个区；
- **NEVER 为了对上「七」去删掉一个区**：裁决是「其余各区照旧暂无内容」，
  那句在八个区上照样成立，而删区会真的拿掉一个下一版要用的能力。

没有因此停下：裁决本身零歧义（CN、HK 在内，其余全部在外），
七还是八**不改变任何一行行为**。要 owner 确认的只有「清单 A2 纸面写九区、而代码今天是十区」。

## 断点三：迁移只动无歧义的那些簇

实测 demo 库：只有 gtrends 的簇 35 条 · **混源 1 条** · 不含 gtrends 233 条。

那 1 条（`c-20260629-108` `brain-computer interface`，`ghtrend`+`gtrends`）成员真的跨区。
`region_of_members` 的既有口径写死：跨区 **MUST 停下上报，NEVER 取众数**。
迁移因此**不给它挑区**，留在 `NULL`（未归区，`REGION-11` 给了它去处），
开单 `docs/blocked/REGION-CN-HK-ONE-CLUSTER-SPANS-BOTH.md` 列三条处置路给 owner。

## 断点四：两条判据在**空集**上恒绿

首版写完 16 条，跑出 **2 skip**（测试库里的簇一条都没归区）。其中
`sources <= {"gtrends"}` 在空列表上**恒真**——它红或绿都与两区分家无关。

改法不是放宽，是**自带数据**：`two_regions_seeded` 各种一条 CN/weibo、HK/gtrends 簇，
按外键顺序删干净（`WIRE-VERDICT` 那次的教训：红出现在别人的文件里、根因在我这里）。
种的时候第一版编了个 `category_id='tech'`，**外键当场拦下**——换成库里真有的 `cat-ai`。

结果：**16 条全绿，零 skip**。

## 阴性对照（卡面两条，都真跑了变异体）

| 对照 | 造法 | 实测 |
|---|---|---|
| ① 口径退回代理 | `EMIT_REGION` 改回 `"CN"` | **3 红**，话是「gtrends 又落回 CN 区了：它采的是 geo=HK，而微博采的是大陆——两个地区被混进同一个区，屏上却只写一个区名」 |
| ② 空态两句合并 | `zh.json` 把 `empty.no_data_today` 换成 `out_of_scope.line` | **1 红**：「两态共用了同一句话」 |

两次变异都**按字节还原**（`read_bytes` 存、`write_bytes` 复原并断言相等），还原后复跑 16 绿。

> 第一次跑变异体时 `subprocess` 用了相对路径的解释器，`CreateProcess` 崩在
> **变异已写入、还原还没执行**的那一刻——gtrends.py 当场留在 `EMIT_REGION = "CN"`。
> 立刻单独还原并核了常量，再把还原放进 `finally`。
> **一个只在成功路径上还原的变异器，崩一次就把仓库改坏了。**

## 八条红，逐条点名（NEVER 按族小结）

跑完受影响面 `tests/v041 + tests/v04/schema`：**8 failed**，全部是本卡的账。

| 红的判据 | 归谁 | 处置 |
|---|---|---|
| `test_cn04_source_repair::…region_is_cn_while_the_url…` | **前提被 `DEC-056` 推翻**（它钉着「落 CN」） | 翻面：落 HK，而「URL 必须是真的那一份」原样守着 |
| `test_cn04_source_repair::…display_name_says_it_is_hong_kong` | 同上（钉着「署名带港区」） | 翻面成「必须不带」——同一件事的两面：署名 MUST 与 region 说同一件事 |
| `test_locale_seam_regions::…all_nine_regions…` | 数目写死在判据里 | 改成**集合包含**，数目只作下界 |
| `test_unassigned_region::…locale_vocabulary_is_untouched` | 断言「词表逐字等于那九个」 | 改成守它真正要守的：**未归区没混进地理词表**（加真地区照旧绿） |
| `test_blocked_sheets_state::…declares_its_state…` | **我新开的两张单**格式写错（`**状态**：` 多了冒号） | 按既有形状改 |
| `test_gauge_map::…disk_copies_are_current` | 我加了新判据文件 | 重跑 `tools/gauge_map.py` |
| `test_line_endings` ×2 | **我的 `write_text` 把 5 个 web 文件整体转成了 CRLF** | 按字节改回 LF |

> 行尾那两条值得记：`pathlib.write_text` 在 Windows 上默认把 `\n` 翻成 `\r\n`，
> 于是**只改了一行注释的文件，整份行尾都变了**。判据说的是「剥刀会失效」——
> 前端扫描器按 `\n` 切行，CRLF 下它会把注释与代码切错。
> 之后写文件一律带 `newline="\n"` 或直接 `write_bytes`。

## 实测（改后 · demo 库 · `:8000` PID 61432 起于 23:43，晚于全部改动）

```
region=CN → 50 簇 · 源 ['weibo']   · in_scope True · 马嘉祺严浩翔男人和男孩的区别 / 蔡磊不想做第二个冰桶挑战
region=HK → 10 簇 · 源 ['gtrends'] · in_scope True · 馬國明 / 美食博覽2026
region=JP →  0 簇 · 源 []          · in_scope False
地区选项 → ['AU','CN','FR','GB','HK','IT','JP','KR','SG','US']
```

**HK 那两条是繁体、港区、香港本地商展**——它们此前就坐在「中国大陆」那一屏上。
`DEC-056` 的 60→50 在这里对上了：分家前 CN 区 60（微博 50 + 港区 10），分家后 CN 50 · HK 10，
**和仍然是 60**，一条没丢。

回填量：`trend_items_raw` gtrends 170 行（flint）/ 140 行（flint_test）全部 CN→HK；
`clusters` 35 条 CN→HK；`clusters.region='CN'` 165 → 130。

## 五条门里跑过的

`ruff check .` 通过 · `pytest tests/v041 tests/v04/schema -q` → **3425 passed, 2 skipped, 0 failed**
· `npx tsc --noEmit` 退 0 · `npm test -- --run` 85 files / 858 tests 全过
· `check_design_constraints.mjs` 11 条规则 0 违规 · `check_reachability` / `check_fe_api_contract` 通过
· `check_fe_be_parity` 仍是 **16 条已装配未调用**（与第 10 批同数，既有分诊，非本卡回归）。

全量 `pytest -q` 与 mypy 留到本批收尾一并跑。
