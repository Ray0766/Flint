# 「空假设」在两条端点上是两个码、两句话

**状态** closed @2026-08-08 · `FIX-10`（v0.4.1 第 6 批）

> 发现者：worker，v0.4.1 第 5 批 `CHAIN-04`（combo 入口屏）。

## 现象

规格 `docs/前端功能说明-v2.md#2.3` 写着：

> 空假设由服务端判 `EMPTY_HYPOTHESIS`（F8/F9 同一判据），前端本地预检话术与之一致。

实测两条端点对**同一件事**（假设是空的）的答复并不一样：

```
POST /projects/combo   {"card_ids":["a","b"],"hypothesis":""}
→ 400 {"code":"VALIDATION_FAILED","message":"hypothesis required (non-empty str)"}

flint/api/graph_edges.py:71
→ 422 EMPTY_HYPOTHESIS
```

`flint/api/graph_edges.py:14` 的注释自己就写着这条风险的形状：
「**两份实现就是两种口径，用户会遇到**…」——今天它已经发生了。

## 它挡住了卡面 acceptance② 的哪一半

acceptance② 要「前端本地预检话术与服务端**逐字一致**」。
前端要逐字一致就得存一句，而**存哪一句都会与另一条端点对不上**。

## 本卡怎么交付的

**前端一句拒绝话都不写。** 提交键的禁用只做物理约束（假设为空、卡数越界），
**不解释「为什么会被拒」**；被拒时把服务端的 `message` 原样带回屏上。

这样做的好处是它对两条端点都成立，且端点哪天统一了口径，屏上自动跟着变。
代价是**屏上出现的话不是我们写的**——那正是本仓「后端自己的说明原样带出来」的既有纪律
（`ErrorState` 的 docstring 逐字写着这一条）。

## 需要 owner 的什么

统一那两处：`POST /projects/combo` 的空假设改回 `422 EMPTY_HYPOTHESIS`
（或反过来，把规格改成 `VALIDATION_FAILED`）。要动 `flint/api/`，
**不在本批 18 卡的触碰面内**。

统一之后前端**一行都不用改**——它本来就不存那句话。

---

## 结案（`FIX-10` · v0.4.1 第 6 批）

**分叉从来不在校验器上。** 两条端点走的是同一个 `_require_str`
（`flint/graph/store.py` 逐字写着「H8: 复用 combo 的 hypothesis 校验语义」），
抛的是同一个异常、同一句话——**分叉只在 HTTP 映射那一层**。

新建 `flint/api/errors.py`，映射**只此一处**：

| 输入 | 答复 |
|---|---|
| 假设是空的 | **422 `EMPTY_HYPOTHESIS`** + 校验器那句原话 |
| combo 其余校验失败（卡数不对、卡不存在…） | 400 `VALIDATION_FAILED` |

**统一到 `EMPTY_HYPOTHESIS` 而不是并回 `VALIDATION_FAILED`**：
`ErrorCode` 的注释逐字说明了它为什么单列——前端要据此把光标送回假设输入框。
并回去就是把那句注释作废。

### 那句话从校验器身上取，NEVER 手抄

`flint/api/errors.py` 在导入期真调一次 `_require_str({}, "hypothesis")`，
把它抛出来的消息捕获下来当唯一真相。校验器改措辞，映射与判据自动跟着走。
前端预检（`web/lib/topicClient.ts`）用的是同一句，判据逐字比对。

### 判据里两条最值钱的

- **阴性对照**：combo 的其余失败仍是 `VALIDATION_FAILED`——
  没有它，把整个异常一律映成 `EMPTY_HYPOTHESIS` 也能让「两处一致」为真，
  而那时「卡数不对」会告诉用户「假设是空的」；
- **扫全仓**：凡接住 `OriginValidationError` 的端点都要走这个映射，
  **新增端点漏了则判红**（卡面 acceptance③）。
