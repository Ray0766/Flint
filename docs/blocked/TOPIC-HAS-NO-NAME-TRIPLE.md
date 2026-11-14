# 规格要主题屏上名称三元组，而冻结件 `Topic` 里没有那两个字段

**状态** closed · `DEC-036`（owner 2026-08-08）· 落地 `SPEC-01`

> 发现者：worker，v0.4.1 第 5 批 `CHAIN-03`（主题列表与主题详情两屏）。
> 属 `CLAUDE.md#S2-1`「冻结件类型不够用 → 停下写问题单」的形状。

## 现象

卡面 acceptance② 与规格 `docs/前端功能说明-v2.md#2.4` 逐字写着：

> 名称三元组上屏：主行 `name_native`，机翻译名为**次要行**（`PRINCIPLES#B8`），译名带机翻标记。

而冻结件 `contracts/models.py:222` 的 `Topic` 全部字段是：

```python
topic_id / seed_id / one_liner / target_user_tag / form_factor_tag
why_now / keyword_mapping / embedding
```

**没有 `name_native`，也没有任何机翻派生字段。** 前端类型镜像
（`web/lib/topicClient.ts#Topic`）与它逐字一致，端点回的也是这些。

## 为什么不拿 `one_liner` 顶上

`one_liner` 是**一句话描述**，不是名称。把它塞进 `NativeName` 的 `nameNative` 槽，
屏上会出现一个「原文名」，而它其实是一句描述——
那正是本批 `DEC-034` 刚立下的同一条：**NEVER 借一个已经有主的字段去说另一件事**。

更实际的坏处：`NativeName` 的次要行是机翻派生物且必带机翻标记（`PRINCIPLES#B8`）。
主题没有译文，那一槽恒空。于是屏上是一个「有原文名、永远没有译名」的三元组——
它看起来像是翻译服务坏了（A7 降级形态），而真相是**这个实体从来就没有名称三元组**。
两者在屏上长得一模一样，正是本仓一路在禁的那件事。

## 本卡怎么交付的

两屏**照 `Topic` 真有的字段渲染**：`one_liner` 作标题、两维 tag、`why_now`
（含 `speculative` 记号与逐条证据 + `citation_id`）、keywords。
**不画名称三元组那两槽**（逐槽隐藏的同一条纪律）。

## 需要 owner 的什么（二选一）

1. **给 `Topic` 加名称三元组**——那是**动冻结件**，走 owner 的变更通道（`CLAUDE.md#S2-1`）。
   加了之后前端只需在两屏里各接一个 `NativeName`（组件早就有）；
2. **判定规格 #2.4 那一行对主题不适用**——它可能是从热点簇那边抄过来的
   （热点簇确实有名称三元组，`HotspotCard` 就在用）。若是，改的是**规格**而不是代码，
   并把卡面 acceptance② 一并订正。

在两者取定之前，本卡按上面的实况交付，**NEVER 编一个名称出来**。

---

## 结案（`SPEC-01` · v0.4.1 第 6 批）

owner 2026-08-08 裁 `DEC-036`：**改规格，不动冻结件**。

理由逐字在 `DECISIONS-v04.md#DEC-036`：给 `Topic` 补两个没人产出的字段，
只会让屏上出现一个永远没有译名的三元组——那看起来像翻译服务坏了，
而真相是这个实体从来就没有名称。

**关单的条件是事情做完了**，不是「那张卡跑完了」。三处都已订正：

| 处 | 改成什么 |
|---|---|
| 规格 `#2.4` 正文 | 主行 `one_liner`；次要行 `target_user_tag` + `form_factor_tag`（**不是译文**）；作废原文进引述块并挂 `DEC-036` |
| 规格屏总表 2.4 行 | 同上 |
| `CHAIN-03` 卡面 acceptance② | 逐字订正并写明出处——那张卡已 verified，**没人会再去看它的 trace** |

**另建了一条不会漂移的判据**（`tests/v041/test_spec_topic_naming.py`）：
规格里凡提名称三元组的行 MUST 点名实体，且该实体在冻结件里 MUST 真有
`name_native` 与 `name_display` 两个字段。**下一次抄错会被当场拦住**——
只判「#2.4 那一行没了」的话，同一句话抄到别的屏上照样绿。
