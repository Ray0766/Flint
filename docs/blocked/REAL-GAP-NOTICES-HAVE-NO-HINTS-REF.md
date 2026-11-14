# 真跑产出的 `gap_notice` 块 `hints_ref` 是空串——那块「缺什么」自己是空的

**状态** open · 2026-08-12 · `WB-04`（不阻断本卡：屏上如实说；阻断的是「资料不足绝不注水」这条铁律的**可用性**） · owner 已答复 `DEC-064`（2026-10-27），待落地

## 一、实况（2026-08-12 实测，真栈 + 真库）

第 12 批那次真跑的 report 作业产出 `del-job-4d22d6be-…`，22 个块里有
**5 个 `gap_notice`**，它们的 `hints_ref` 全是**空串**：

```
GET /deliverables/del-job-4d22d6be-c3dc-47cf-b334-70a573efb7f4/blocks
→ {"kind": "gap_notice", "hints_ref": ""}     ×5
```

于是右栏渲染它们时问的是 `GET /hints/`（路径尾部什么都没有）→ **404**，
屏上显示「接口未提供 」后面跟一个空 id。

**这一条与夹具那三条 404 不是一回事**
（`docs/blocked/DEMO-REFS-NO-STORAGE-FACE.md` 登记的
`chart-demo-cost-trend` / `qc-demo-fixture-01` / `sec-04-gap-hints`）：
那三条是「引用了一个真 id，而那类实体没有存储面」；
这一条是「**根本没有 id**」——连指向哪儿都没说。

## 二、根因（源码实查）

`flint/compose/llm_generator.py:110-113`：

```python
elif kind == "gap_notice":
    content = GapNoticeContent(
        kind="gap_notice", hints_ref=str(item.get("hints_ref", "")),
    )
```

模型那份结构化输出里没有 `hints_ref` 时，这里**取默认空串继续**。
落库、渲染、导出一路无人拦——空串是个合法字符串。

## 三、为什么这条要紧（不是一个 404 的事）

三条铁律里那条「资料不足绝不注水」，在产物上的形态就是 `gap_notice`：
它要说清**缺什么**与**该找哪些来源**。工单 `WB-03` acceptance 逐字写着：

> 「该出 `gap_notice` 的地方 MUST 出，判据断言 `gap_notice` 里写明了
> **缺什么**与**该找哪些来源**」

今天的实况是：**该出的地方出了**（5 块，位置对），
**而每一块都说不出缺什么**——一个空的 `hints_ref` 指不到任何提示。
读者看到的是一句「这里缺东西」，然后没有下文。

「不注水」这一半做到了，「说清缺什么」那一半是空的。

## 四、三条修法，各自的代价（**没有自己择一**）

| 口径 | 做法 | 代价 |
|---|---|---|
| 甲 · 生成期拒绝 | `_parse_blocks` 遇到空 `hints_ref` 的 `gap_notice` **抛**（与「未知块型跳过」并列的一条硬校验） | 一次生成会因为模型少写一个字段整体失败；要配重试 |
| 乙 · 生成期兜底 | 由 section 上下文**算**一个 ref（如 `f"{section_id}-gap"`），并同时保证那个 ref 查得到 | 要有 `gap_hints` 的存储面，而全库今天**没有** `section_states` / `gap_hints` 表（`DEMO-REFS-NO-STORAGE-FACE.md` 已登记） |
| 丙 · 把提示写进块里 | `GapNoticeContent` 除 `hints_ref` 外带上 `missing_what` / `why` 的**内容**（不是引用） | **动冻结件**（`contracts/models.py#GapNoticeContent`）——`S2-1` 说了：类型不够用就停下开问题单，NEVER 自己改 |

丙那条最贴近铁律的原意（提示是内容，不是一个要再问一次的 id），
但它要改冻结件——**这正是本单存在的理由**。

## 五、绕行现状（`WB-04` 已落盘）

右栏照旧渲染那 5 个 `gap_notice` 块（**NEVER 藏起来**：藏了就等于把
「这里缺东西」这句话也删了），`DerefValue` 如实显示「接口未提供」。
取证判据把这条 404 **逐条点名归属**到本单，而不是把它并进夹具那三条里。

## 六、需要 owner 的什么

甲 / 乙 / 丙 三选一。选丙的话同时要一个冻结件修订窗口（`S2-1` / `S9-1`）。

## owner 答复（`DEC-064` · 2026-10-27）

选**丙 · 提示写进块里**，并开冻结件修订窗口：`GapNoticeContent` 加 `missing_what` / `why`（只加带默认值的字段；三个文件同步，见 `DEC-064` 的落地口径更正）。

选项文本由 Claude 在会话里拟、owner 点选——出处与措辞的处置见 `DECISIONS-v04.md#DEC-064`。
