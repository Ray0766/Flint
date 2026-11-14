# AUD-PACK-01 · trace

**卡**：受众选择与 vibe_pack 两屏——补 v4 的说明文字（**其余一个字不重写**）
**日期**：2026-08-12 ｜ **状态**：verified

## 一、改前实况（先核后动，本卡 NEVER 重写这两屏）

三条语义**今天已经成立**，不是本卡做的：

| 语义 | 落点 | 实况 |
|---|---|---|
| 无默认 | `useState<Audience \| null>(null)` | 已成立 |
| 强制单选 | `type="radio" name="audience"` | 已成立 |
| 不选不能提交 | `disabled={audience === null …}` | 已成立 |
| 缺字段即 422 | `flint/api/compose.py` 的 `Literal[...]` | 已成立（本卡**实测**） |

`PackViewer` 也已经是只读清单形态、带 `for_ai_context` 标记、
`not_generated` 不冒充空骨架（`data-pack-state="not_generated"`）。

**这一节写下来是为了不把既有成果记成本批的活。**

## 二、422 是**实测**出来的

```
POST /projects/proj-demo-fixture/proposal  {report_id: …}                   → 422
POST /projects/proj-demo-fixture/proposal  {report_id: …, audience: "ai_executor"} → 非 422
```

两次都发。只发第一次的话，「这个端点永远 422」也会绿——
那时受众这一格根本没被读到，而判据看起来很有说服力。

## 三、本卡真正补的：v4 的三处说明文字

| 处 | 文案 |
|---|---|
| 人类那张卡 | 五套模板（通用 / 毕设 / 创业 BP / 工程交付 / 科研基金）· 字数配比（words）· 说服怀疑者：关键信息重复三次 · 评审会 / 导师验收 |
| AI 那张卡 | vibe_pack 单一执行包（计划书 + spec 合并）· token 预算 · MUST / SHOULD / NEVER 规范力 · verify_cmd 机器验收 · cycle 计时 |
| 按钮（未选） | 选择受众后才能提交 |

判据**从设计稿现场比对**（`zh[key] in 设计稿原文`），不是拿我抄的一份去比。

### 一处偏离：人类侧按钮那句去掉了「→ 设计台」

v4 原文是「生成计划书（五模板）**→ 设计台**」。「设计台」是 v4 自己那一屏的名字；
本仓对应的屏 `WB-07` 刚改名叫「模板工具」，而计划书的主工作台是另一屏。
照抄会在按钮上印一个**本仓不存在的去处**，所以只抄语义那一半。

## 四、两处「先核后动」，结论一个是开单一个是不用动

**① `sibling_deliverable_id`：冻结件里没有 → 开单，NEVER 前端编一个**

`grep -c sibling contracts/models.py` → **0**。`Deliverable` 今天的关系只有
`supersedes`（纵向：这一份接替了哪一份），没有任何一格表达
「这一份与那一份是同一材料的两个受众版本」（横向）。

`S2-1`：类型不够用 → 停止实现、写问题单。
单：`docs/blocked/SIBLING-DELIVERABLE-ID-IS-NOT-IN-THE-CONTRACTS.md`（两种口径各写一条：
甲 = 加字段要开冻结件修订窗口；乙 = 由 `project_id` + `ledger_version` 推导，
代价是「推导规则改一次，历史产物的关系跟着变」）。

判据两个方向各钉一次：字段确实不在冻结件里（在了就该销账）· `web/app` 下
**没有任何一处**出现 `sibling_deliverable_id`。

**② RegistryValidator 那句：后端已经有这条通道 → 不用动**

v4 第 317 行那句「RegistryValidator 不可用 →『依赖校验暂不可用，执行包暂缓导出』」，
核下来后端**早就有**：`flint/registry/gate.py#registry_pack_gate` 在
`report.available` 为假时给出 violation 与 `GapHint`，原话点名
「**不可用 ≠ 不存在，不走替换**」；`vibe_export_gate` 把它并进 409 的 `violations`；
导出屏 `data-export-violations` 逐条印出来。

所以前端**一个字都不用自己写**——那句话的措辞出自后端，屏上印的是它原样带回来的。
（这正是「先核后动」的价值：不核的话，这里会多出一句前端自己写的、
与后端措辞不一致的话。）

## 五、顺带记一处实况（本卡没改）

`.pack` 这一族在 `web/app/globals.css` 里**零 CSS**（`grep -c pack` → 0）。
今天「vibe_pack 正文是等宽的」靠的是 `<pre>` 的浏览器默认，
不是 `_ds` 的 `--font-mono`。判据因此钉的是 `<pre>` 这个结构本身。
**这一屏的样式面是空的**——与 `F-09` 记过的坑同形（DOM 里有 ≠ 屏幕上有），
但它今天不影响可读性，登记在这里与完成态报告里。

## 六、出 outputs 一处

卡面 outputs 只列了两份词典与判据文件，而**三处文案不渲染就到不了屏上**
（卡面自己的正向判据要求它们在屏上）。所以动了
`web/app/projects/[id]/proposal/page.tsx`：加两句说明的渲染 + 按钮文案随受众变，
**既有三条语义一个字没碰**（判据钉着）。这一处写进完成态报告。

## self_review

① 判据 ↔ acceptance：422 两次实测 2 · 三处文案逐字 3 + 出处 1 + 上屏 1 ·
   既有语义没动 1 · pack 三样 1 + not_generated 1 · sibling 开单 1 ·
   registry 通道已在 1 = **12 条**（另 `test_audience_and_intervention_screens.py` 既有 19 条照旧全绿）。
② 无冻结件偏离：`contracts/` 只读；读出来的结论是「字段不在」→ 开单。
③ 无禁用词：命中 0。
④ 复用断言在位：`PackViewer` / 导出屏 / `registry_pack_gate` 三处都是**核**而不是改。
⑤ 装载未超预算：约 11k tokens。

## 产出文件

```
web/messages/zh.json · en.json                     5 条新 key（两份对称）
web/app/projects/[id]/proposal/page.tsx            两句说明上屏 + 按钮文案随受众变（出 outputs）
tests/v041/test_audience_pack_v4.py                12 条判据
docs/blocked/SIBLING-DELIVERABLE-ID-IS-NOT-IN-THE-CONTRACTS.md   新单
```
