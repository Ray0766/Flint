# SPEC-01 · `DEC-036` 落地：主题名称三元组，改规格不动冻结件

> v0.4.1 第 6 批第五张。`depends_on: ["DEC-035-038-LANDING"]`（已 verified）。

## 装载清单

`tasks-v041-b6.json#SPEC-01` · `DECISIONS-v04.md#DEC-036` ·
`docs/前端功能说明-v2.md`（屏总表 + #2.4 + #2.14）·
`contracts/models.py#Topic` 与 `contracts_v04/models_v04.py#Cluster` ·
`docs/blocked/TOPIC-HAS-NO-NAME-TRIPLE.md` ·
`docs/steward/tasks-v041-b5.json#CHAIN-03` · `tests/v041/test_topic_screens.py`。
约 8k tokens，**未超 40k**。

## 一、改了什么

| 处 | 改前 | 改后 |
|---|---|---|
| 规格 `#2.4` 正文 | 「名称三元组上屏：主行 `name_native`，机翻译名为次要行」 | 主行 `one_liner`；次要行 `target_user_tag` + `form_factor_tag`（**不是译文**）；`why_now.speculative` 要标出来；选主题落 `chosen_topic_id`。作废原文进引述块并挂 `DEC-036` |
| 规格屏总表 2.4 行 | 同一句话的一行版 | 同上 |
| 规格 `#2.14` 两行 | 只说 `name_native` | 点名是 **`Cluster`** 的 `name_native`（新判据要求点名实体） |
| `CHAIN-03` 卡面 acceptance② | 抄的同一句话 | 逐字订正 + 出处 |
| `TOPIC-HAS-NO-NAME-TRIPLE.md` | open | **closed**，附结案段 |

**为什么连 `#2.14` 一起改**：新判据要求「凡提名称三元组的行 MUST 点名实体」。
不点名的话，读的人只能从上下文猜是哪个实体——**而 `#2.4` 那次抄错，
正是因为「名称三元组」这句话可以脱离实体独立成立**。

**为什么连第 5 批那张卡一起改**：`CHAIN-03` 已经 verified，
**没人会再去看它的 trace**。卡面留着旧话，下一个照卡做的人会把它再实现一遍。

## 二、本卡最值钱的一条不是「那句话改了」

是 `tests/v041/test_spec_topic_naming.py` 那两条：

```
凡提名称三元组的行 → MUST 点名实体
点名的实体        → 冻结件里 MUST 真有 name_native 与 name_display
```

**这就是 `DEC-036` 的机器形态。** 只判「#2.4 那一行没了」的话，
同一句话抄到 `#2.6` 上照样绿。

另加一条**判据自己的阴性对照**：`Topic` 必须缺**两个字段都缺**、
`Cluster` 必须**一个都不缺**——没有它，`_entity_fields` 哪天解析不出字段
（改了缩进、换了 dataclass 写法）就会让每个实体都「没有缺字段」，
而它看起来仍然是绿的。

## 三、一次返工：判据把我自己的解释当成了问题

第一版把作废原文直接写进 `#2.4` 正文，于是判据在**解释那句话的段落**上红了——
`docs/blocked/SCANNERS-DO-NOT-STRIP-COMMENTS.md` 的同一形状，本仓栽过多次。

**修法不是放宽判据，是给「引述」一个位置**：作废原文进 Markdown 引述块（`>`），
判据跳过「引述块里且点着 `DEC-` 的行」。

**为什么不是「凡 `>` 都跳过」**：那就成了一条谁都能用的逃生口——
把主张塞进引述块即可绕过。要求同一行点着裁决号，等于要求**每一次豁免都有出处**。

## 四、动了一条既有判据（前提过期，不是事情没做完）

`tests/v041/test_topic_screens.py::test_the_gap_stays_registered_until_the_contract_grows_it`
写的是「冻结件里还没有 `name_native` ⇒ 单据必须还开着」。

那句话背后有个**没说出口的假设**：这个缺口只可能靠冻结件长出字段来关。
`DEC-036` 恰恰选了另一条路——于是缺口关了而冻结件一个字没动，
旧条件把这件事判成了「单据不该关」。

改成裁决自己的形状：`Topic` 仍然没有名称（冻结件没被动过）**且**
规格不再要求它有（那才是缺口消失的地方）。**两者缺一都不该关单**，
并保留「冻结件长出 `name_native` 就来重开 `DEC-036`」那条反向出口。

## 五、verify

```
pytest tests/v041/test_spec_topic_naming.py -q                     → 8 passed
pytest tests/v041/test_topic_screens.py test_doc_gates.py -q       → 33 passed
pytest tests/v041/test_screen_{coverage,composition}.py -q         → 通过（屏对照未受影响）
ruff check . --no-cache                                            → All checks passed
python tools/check_line_endings.py                                 → 219 个文件全是 LF
python tools/check_screen_coverage.py                              → 缺屏 0 · 端点对不上 0
```

## 六、self_review

① 判据覆盖 acceptance 五条，含两条防漂移的通用判据与两条阴性对照；
② **零冻结件改动**——本卡反而断言 `Topic` 的字段集**逐字相同**（加一个就红）；
③ 无禁用词；④ 改动面：规格 + 卡面 + 单据 + 两份判据，全在 outputs 或由卡面点名；
⑤ 装载 ≈8k tokens。

## 七、留给下游

主题屏（`TopicListView` / `TopicDetail`）**本来就没有**渲染名称三元组
（第 5 批停得对），所以本卡零前端改动。规格与实现现在第一次说的是同一件事。
