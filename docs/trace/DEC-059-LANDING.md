# DEC-059-LANDING · trace

**卡**：裁决落地——新增计划书主工作台，AI 设计工作台改名退居次要（DEC-059）
**日期**：2026-08-12 ｜ **cycles**：1 ｜ **verify_cmd**：`pytest tests/v041/test_decisions_landed.py -q`

## 装载清单（inputs 来源）

- `docs/steward/tasks-v041-b14.json`（10 卡 + 11 条 rules）
- `DECISIONS-v04.md`（追加前 73003 字节，水位 058）
- `tests/v041/test_decisions_landed.py`（追加前 25147 字）
- owner 第 14 批工单原文——**从本会话 transcript 里逐字取回**
  （`~/.claude/projects/…/ddd5462b-….jsonl` 第 7391 行），
  上下文压缩后我手上只剩摘要，而落地要的是**原话**，摘要不能拿来当原文用。

## 断点一：卡要「原文」，而 owner 没贴 DEC 块

工单卡 acceptance 写「DEC-059 **原文**一字不改追加」，
而 owner 第 14 批那条消息里没有 `DEC-059（…，owner）` 那样一段独立文本——
前四条（`DEC-055`~`DEC-058`）都有。

**没有停下**，理由写在 `docs/blocked/DEC-059-TEXT-CAME-FROM-THE-WORK-ORDER.md`：
卡自己点名要断言的三句话逐句都在工单【2】【3】两节里，裁决内容是齐的，
缺的只是「被贴成一块」这个形式；而 owner 同一条消息里写着**一批做完**。
于是照抄那两节、一字未改，并**把出处如实写进条目第一行**，
且**NEVER 写「owner 粘贴的原文」那一句**——那句话在这里会是假的。
这一点由 `test_dec_059_says_where_its_text_came_from` 钉着。

## 断点二：我自己写进去的一个错路径

条目里我把单号写成 `docs/tickets/…`，而本仓的单一直在 `docs/blocked/`。

改法：**只改本次追加的那一段自己**，改完重量前缀——
`n[:73003] == head` 为 `True`（既有 73003 字节逐字节未动）。
append-only 护的是**已经被别人引用过的行**；这一段还在本卡手里、
台账事件都没写，不属于那一类。**任何一条既有 DEC 一个字没动。**
（换成「加一条 DEC-060 去修一个路径笔误」是把纪律用成了仪式。）

## 顺手补的三处（不是本卡的活，但它们看不住的正是本卡这种落地）

`tests/v041/test_decisions_landed.py` 三处上界写死在旧水位上：

| 处 | 改前 | 实况 |
|---|---|---|
| `LANDED` 表 | 到 `DEC-056` 为止 | 第 12 批落的 `DEC-057`/`DEC-058` **正文没有任何判据在看** |
| 全序判据 | `range(35, 57)` | 057~059 插到哪儿都不会红 |
| 逐批判据 | `batches` 手写到第 9 批 | 10~12 批之间的先后没人看 |

三处一并补齐：两条挂进 `LANDED`（各带四个必现关键词）、
全序上界改成**跟着文件里的最高编号走**（水位每涨一次自己纳入新条目）、
`batches` 补到 `BATCH_14`。

## 先红后绿（实测）

```
红：AssertionError: DEC-059 没落进 DECISIONS-v04.md   （test_every_landed_decision_is_present）
绿：50 passed in 0.09s
```

追加前后：**73003 → 76929 字节（+3926）**，`after[:73003] == before` 为 `True`；
水位 **058 → 059**；`DEC-035`~`DEC-059` 全序无洞、无重号。

## 本条落地之后，谁在看着这三句

| 三句要害 | 判据 |
|---|---|
| 新增一屏而不是替换 | `test_dec_059_says_it_adds_a_screen_rather_than_replacing_one` |
| `DESIGN-01~03` 的成果一点不丢 | `test_dec_059_protects_what_design_01_to_03_already_built` |
| 生成走 compose 真链，NEVER LLM 直吐 HTML | `test_dec_059_bans_the_blueprint_way_of_generating_by_name` |
| （加的一条）原文出处说得清 | `test_dec_059_says_where_its_text_came_from` |

第三条**点名两样东西**才拦得住：要走的那条链（`flint/jobs/compose.py`）
与不许出现的那个动作（用正则从 LLM 输出里抠 `<block` / `<part`）。
只写「要走真链」的话，照蓝本抄一遍的人也会自认为走了真链——
而绕开之后**屏上什么都不缺**，只是那些引用不再指向任何一条 `Fact`。
全仓那条 `never_html_regex` 判据在 `WB-03` 建。
