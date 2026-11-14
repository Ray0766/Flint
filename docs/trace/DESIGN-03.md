# DESIGN-03 · 工作台③：固化为模板 + 那个缺的第四态

> v0.4.1 第 5 批第十张。依赖 `DESIGN-02`（verified）。

## 装载清单

`tasks-v041-b5.json#DESIGN-03` · `docs/blocked/UI-DESIGN-SCREEN-NEEDS-A-FOURTH-STATE.md`（全文）·
`flint/api/design.py` 的 `POST /design/templates` 一节 · `web/components/design-workbench/*` ·
`web/__tests__/app/ui04.test.tsx` · `tests/v041/test_ui04.py` · 真栈 `GET /design/templates`。
约 8k tokens，**未超 40k**。

## 一、第四态是什么，为什么塞不进已有的三种

后端 `WIRE-12` 之后给的是：

```
200 /design/templates {"status":"not_provided","reason":"模板注册表不可用（迁移里没有 templates 表）…"}
```

那张单逐条列过（本卡照它执行）：

- 塞进 `false`（坏了）→ 屏上写「不可用，请稍后重试」，而真相是**重试一万次也不会有**；
- 塞进 `null`（没查过）→ 我们**明明查过了**，那是另一个方向的谎；
- 写死一句「接口未提供」→ 话碰巧对，但后端哪天真上了那张表，**这一屏不会知道**。

## 二、四态与它们各自的那句话

| 值 | 说的是 | 屏上 | 固化 |
|---|---|---|---|
| `not_checked` | 还没查过 | 「还没查过模板注册表…这不是『注册表不可用』，是我们还没问过」 | 阻断 |
| `not_provided` | 查过了：这套部署根本没有那张表 | 「…这不是『坏了』，是这里根本没有——**重试也不会有**」 | 阻断 |
| `down` | 查过了：坏了 | 「模板注册表不可用：固化与生产渲染已阻断」 | 阻断 |
| `ok` | 查过了：可用 | —— | 放开 |

**「重试也不会有」那半句是判据钉着的**（`test_the_not_provided_line_says_retrying_will_not_help`）：
不说这句的话，用户会照着「不可用」的直觉去重试。

四态是**查回来的**（`probeRegistry` 打 `GET /design/templates`），不是写死的。
初值 `not_checked`——**NEVER 初成 `down`**：那是替后端下结论，而我们还没问过。
连不上时回 `down` 而不是 `not_checked`：我们确实查过了。

## 三、固化：真打端点，且**前端不预判**

`solidifyTemplate` 打 `POST /design/templates`。能不能固化由服务端答复决定，
屏那侧只做置灰与说明（规格 #2.17 第二条：**固化与生产渲染阻断、探索期不阻断**）。
判据反向盯着客户端里 NEVER 出现 `watermark` 之类的后端校验复刻——
复刻的那份会与后端各自漂移：后端哪天补上了校验，屏上仍按旧规则放行。

屏上按下固化时传的是**空串**（今天还没有产物，`preview` 恒 `null`），
端点会照实拒（缺水印），而那句拒绝是真的。
**NEVER 编一份样板送过去**：编出来的那份会被固化成一个没人要求过的模板。

## 四、改既有文件（工单纪律 4）

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `web/components/design-workbench/DesignWorkbench.tsx` | `registryAvailable: boolean \| null` | `RegistryState` 四态；判别位就是那四态本身 | 卡面 acceptance①；判别位共用一个的话，三种阻断在取证里长得一模一样 |
| `web/components/design-workbench/designSession.ts` | 只有生成与 replay | +`solidifyTemplate` +`probeRegistry` | acceptance② |
| `web/app/design/page.tsx` | 传 `null` | 进屏查一次注册表；固化真打端点 | 四态要**查回来的**才算数 |
| `web/messages/{zh,en}.json` | 缺第四句 | +2 键 ×2 | 那张单的第 2 条要求 |
| `web/__tests__/app/ui04.test.tsx` | 用 `null`/`false`/`true` 传参；一条判「一个请求都不发」 | 换成四态的名字；那一条翻成「进屏只查，NEVER 提交作业」 | **判的还是同一件事**，只是入参换了名字；翻过来的那条见 `DESIGN-02` trace 的 3.1 |
| `tests/v041/test_ui04.py` | 钉 `registryAvailable === null` / `={null}` | 钉四态的具名值 | 同上 |
| `docs/blocked/UI-DESIGN-SCREEN-NEEDS-A-FOURTH-STATE.md` | open | **closed · DESIGN-03** + 关闭记录三条 | 卡面 acceptance④ |

## 五、判据分两层

- **阴性对照四条在 vitest**（`registryStates.test.tsx`，10 条）：每一态单独构造，
  **逐条断言另外三态的话不在场**——只断言「本态的话在」的话，
  一个把四句话全渲染出来的实现照样全绿；
- **pytest 11 条**判源码结构、四句话互不相同（中英各一次）、四态是查回来的、
  以及**关单的条件**：`test_the_fourth_state_sheet_is_closed`
  **先验四态在位、再验状态行**——关单的条件是事情做完了，不是「那张卡跑完了」。

## 六、取证（真栈 `/design`）

截图已看过：固化键下那句话现在是
「这套部署没有模板注册表，所以固不了。这不是「坏了」，是这里根本没有——重试也不会有。」
——改前那里是「还没查过模板注册表…」。**话变了就说明探针真查过了**，
四态不是写死的。控制台仍然只有那条登记过的 404（生成入口没挂）。

## 七、verify

```
pytest tests/v041/test_design_solidify.py -q  → 11 passed
pytest tests/v041 -q                          → 2378 passed / 4 failed（仍是那条 403）
cd web && npm test -- --run                   → 78 files / 794 tests passed（新增 10 条对照）
cd web && npx tsc --noEmit                    → 0
ruff check . --no-cache                       → All checks passed
node tools/i18n_scan.mjs web --fail-on-cjk    → CJK 0
python tools/check_line_endings.py            → 210 个文件全是 LF
```

返工两轮：`ui04.test.tsx` 八处入参是三态的字面量（TS 当场报类型不符——**那正是扩类型的用处**）；
判别位从 `registry_down` 改成四态本身之后，一条既有断言要跟着改名。

## 八、self_review（worker.md §4.6）

① **测试覆盖 acceptance**：四条 acceptance 各有落点；阴性对照是「另外三态不在场」的强断言，
不是「本态在场」的弱断言；关单那条**先验事情做完**再验状态行。
② **无冻结件偏离**：`contracts/` 一字未动。
③ **无禁用词**：grep 零命中。
④ **复用断言在位**：结果形状仍是 `ActionOutcome`（与 `PLAZA-04`、`DESIGN-02` 同一份）；
前端不复刻后端校验（反向断言）。
⑤ **装载未超预算**：≈8k tokens。

## 九、留给下游

- 固化今天必然被拒（没有产物、注册表也没有那张表）。产物那一端由生成端点决定
  （`docs/blocked/DESIGN-GENERATE-HAS-NO-SUBMIT-ENDPOINT.md`），
  templates 表那一端要迁移——**两条都不在本批触碰面内**；
- 两条都通之后，本屏**一行都不用改**：`ok` 那一支与固化调用早已备好。
