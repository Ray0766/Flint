# COMBO-ECHO · 前端类型描述了一份不存在的形状

**结论**：改**前端**（不给后端补三个字段）。
`ComboSubmitEcho` → `ComboCreateResponse{project_id, topic_ids, degraded}`，
`AnalysisSubmitEcho` → `AnalysisSubmitResponse{job_id}`（同一处病的另一半）。
判据**拿真响应比对**。`verify_cmd` 7 条全绿。

装载：`docs/steward/tasks-v041-b10.json#COMBO-ECHO` ·
`docs/blocked/PARITY-READS-A-REQUEST-PAYLOAD-AS-A-RESPONSE.md` ·
`web/lib/types.ts` · `flint/api/schemas.py` · `flint/api/combo.py` ·
`web/components/chain/chainClient.ts`
（实测装载 ≈ 12k tokens，预算 40k）

---

## 1 病灶（acceptance② 逐字，原样进 trace）

> **两边对着一份虚构的形状达成一致，尺子报绿**——
> 这比报错更坏：它把「没人核对过」伪装成「核对过、没问题」。

`/projects/combo` 的 `card_ids` / `hypothesis` / `n` **一个都不在响应里**：
前两个来自 `runner.submit(payload={…})`（调用方**发出去的**东西），
`n` 来自 `flint/api/combo.py` 里一个局部计数器 `counter = {"n": 0}`。

## 2 哪一半是真的（acceptance③ 要的决定与理由）

**响应不该有那三格，所以改前端。** 三条理由：

1. **补上就是让虚构变成事实**——acceptance③ 逐字禁掉；
2. `card_ids` 与 `hypothesis` 是调用方**自己刚发出去的**。回声一份只会让人
   去信回声而不信自己的入参——而两者不一致时，错的一定是回声那条路；
3. `n` **从来就不是一个响应字段**，它是一个局部计数器。

旁证：真调用方 `chainClient.submitCombo` 的注释**一直写的就是真形状**
（「成功回 `{project_id, topic_ids, degraded}`」），
而 `types.ts` 那两个接口**全仓没有一处 import**——
错的只有那两行声明，没有任何代码在照着它们做事。

## 3 判据拿**真响应**比，不比两份人写的声明

比对的对象是 `ComboCreateResponse(...).model_dump()` 的**键**——
端点最后那一句就是 `JSONResponse(ComboCreateResponse(...).model_dump())`，
所以这些键**字面上就是会走到线上去的那些**。

比两份声明（TS 接口 vs pydantic 源码文本）的话，**两边一起写错时判据照样绿**——
而那正是本卡要治的病，用同一种形状的判据去治它没有意义。

另有两条钉住「这个决定不会被悄悄反悔」：
后端 `ComboCreateResponse.model_fields` **判等值**（有人补上第四格就红）；
`n` 那个计数器仍然只是计数器（它出现在函数体里、**不在交出去的那一句里**）。

## 4 我自己写错的一处

`code.index("return JSONResponse")` 找到的是 `_error()` 里那一句——
它排在计数器**之前**，于是切出来的段落把计数器整个圈了进去，
判据报「交出去的那句里有 counter」。改成 `rindex`。
**本轮第二次撞上「锚点选错了那一个」**（`WIRE-VERDICT` 那次是从 `useEffect` 这个词起切，切到了 import 行）。

## 5 改前 / 改后 / 为什么非改不可

| 文件 | 改前 | 改后 | 为什么 |
|---|---|---|---|
| `web/lib/types.ts` | 两个描述虚构形状的接口 | 两个真响应形状 + 病灶与决定写在段头 | §1 §2 |
| `docs/blocked/PARITY-…-AS-A-RESPONSE.md` | 状态行点的是引入者 | 点关它的那张卡，历史进括号 | 状态行要说得出**是谁关的** |

**后端一行没动**——这是本卡的主要决定，不是遗漏。

## 6 自审（`self_review=true`）

**① 判据覆盖 acceptance**（六条）：①实况已钉（计数器那条判据就是证据）；
②那句话原样在 §1；③决定与理由在 §2，且有一条判据钉住后端**没被补上**；
④走的是②（改前端）；⑤比的是 `model_dump()` 的键；⑥单据按新规矩关。
**先红后绿**：7 条里 2 条在改前红。

**② 无冻结件偏离**：四件未触碰。**③ 无禁用词**：0 命中。
**④ 旧名字只作为记录留在注释里**——判据判的是「有没有以那个名字导出的接口」，
NEVER 判「文件里有没有这个词」（那会误伤记录改动理由的注释，本轮已踩过六次）。
**⑤ 装载未超预算**：≈12k / 40k。

## 7 门

```
pytest tests/v041/test_combo_echo.py -q   7 passed
ruff check . --no-cache                   All checks passed!
npx tsc --noEmit                          0
```
