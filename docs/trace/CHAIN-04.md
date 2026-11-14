# CHAIN-04 · 主链路②：发起分析与 combo 入口两屏（蓝本 P6/P3）

> v0.4.1 第 5 批第十二张。依赖 `CHAIN-03`（verified）。

## 装载清单

`tasks-v041-b5.json#CHAIN-04` · `docs/前端功能说明-v2.md#2.3` ·
`flint/api/analysis.py` + `flint/api/schemas.py#AnalysisSubmitRequest` ·
`flint/api/combo.py` · `flint/api/graph_edges.py`（`EMPTY_HYPOTHESIS` 的出处）·
`web/components/views/ComboEntryView.tsx` · `web/lib/viewsClient.ts#fetchEvidenceCards` ·
`web/lib/jobClient.ts` · 真栈两条端点的 curl。约 14k tokens，**未超 40k**。

## 一、改前实况

两条端点第 4 批就装配了，**而没有任何界面能触发它们**。
`ComboEntryView` 建好了，全仓只有 `DemoFlow` 在用；发起分析那屏连组件都没有。

## 二、一处规格与实况对不上（立单，按实况交付）

规格 `#2.3` 要「空假设由服务端判 `EMPTY_HYPOTHESIS`，前端本地预检话术与之**逐字一致**」。
实测两条端点对同一件事的答复**不是同一句**：

```
POST /projects/combo 空 hypothesis
  → 400 {"code":"VALIDATION_FAILED","message":"hypothesis required (non-empty str)"}
flint/api/graph_edges.py:71
  → 422 EMPTY_HYPOTHESIS
```

`graph_edges.py:14` 的注释自己就写着这条风险的形状：「两份实现就是两种口径，用户会遇到」
——**今天它已经发生了**。

**交付方式：前端一句拒绝话都不写。** 提交键的禁用只做物理约束（预算没填、
假设为空、卡数越界），**不解释「为什么会被拒」**；被拒时把服务端的 `message` 原样带回屏上。
这样对两条端点都成立，且端点哪天统一口径，屏上自动跟着变。
判据 `test_the_front_end_writes_no_refusal_sentence_of_its_own` 反向扫三处源码，
`EMPTY_HYPOTHESIS` / `hypothesis required` / 「假设不能为空」一个都不许出现。
单据 `docs/blocked/EMPTY-HYPOTHESIS-TWO-CODES.md`。

## 三、三处设计判断

**① 提交后进 Job 屏，NEVER 在本屏轮询。** 同一个作业有两处在看的话，
两处的进度**永远差一拍**，用户不知道该信哪一个。判据反向扫
`setInterval`/`setTimeout`/`fetchJobSnapshot`/`openJobStream` 一个都不许在这屏出现。

**② 没带簇 id 就一个请求都不发。** 猜一个簇去问，取回来的是**另一个热点的证据卡**，
而用户会拿它们去建项——与广场屏拒绝猜 `verdictJob`（`DEC-012`）是同一条。
屏上如实说该怎么进来（那是**用法**问题，不是故障）。

**③ 三种拒绝各说各的（`AUTH-03`）。** 403（没权限）· 带 `code` 的 404（这一条不存在）·
裸 404（能力没挂）。混成一句，用户会拿一个正确的 id 反复试，
或者去要一个他本来就有的权限。FastAPI 的 422 把说明放在 `detail` 数组里——
取不到那一条就等于把唯一的线索丢掉，所以 `read()` 专门读了 `detail[0].msg`。

## 四、A6 指出来的那件事是对的，而它的实现与自己的意图对不上

`check_design_constraints.mjs` 的 A6 判「每屏三态齐全」，报本屏「缺加载态、错误态」。

**它对的那一半**：提交在飞时屏上什么都不说——用户按下去之后无从知道有没有发生什么，
于是会再按一次，**而那会开出第二个作业**。已补一个可见的进行态（`DsStatusMark`）。

**它错的那一半**：它的读信号是 `fetch(|useEffect|await |Client\b`，
而本屏是一张**写**屏（进屏零请求，按键才 POST），只因 import 了 `chainClient`
就命中 `Client\b`，于是被要求写一个**它没有任何列表可空**的空态。
那正是该规则**自己上面那段注释**警告的「写出来的是一段永远进不去的死分支」。

收窄成三样**进屏就会跑**的东西：`useScreenData` / `useEffect` / 具名 `fetchXxx(`。
阴性对照跟着换成一屏进屏真取数的——**判的仍是同一件事**。
（**超出卡面 outputs，在此登记**；与上一轮修 UI-01 那把尺子是同一类：
实现与自述的意图对不上。）

## 五、改既有文件（工单纪律 4）

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `web/app/globals.css` | 无表单面样式 | +`chain-form` 一段（与设计台输入区同形制） | 结构与样式成对交付 |
| `web/messages/{zh,en}.json` | 无 | +12 键 ×2 | NEVER 在组件里写死中文 |
| `harness/fe_smoke.py`、`tests/v041/test_fe_smoke.py` | 18 屏 | **20 屏**（+`/combo`、`/projects/[id]/analysis`） | 那道绊线：新屏不登记就会被跳过取证 |
| `tools/check_design_constraints.mjs` | A6 读信号含 `Client\b` | 收窄成进屏取数的三样 | 见第四节 |
| `tests/v041/test_design_constraints.py` | A6 阴性对照是 `const d = fetch('/x')` | 换成 `useEffect(() => { fetch(...) })` | 跟着收窄，**判的仍是同一件事** |

## 六、取证

```
harness/fe_smoke.py 全量：**20 屏** × 2 主题 × 2 视口
  horizontal_overflow 0 · 噪声面 {'/deliverables/[id]': 3, '/jobs/[id]': 1, '/topics/[id]': 1}（未变）
.ui-probe/chain_entry_screens.json
  analysis  keywords/budget/submit 三件宽高非零；预算未填时 submit 点不动、填了之后能点
  combo     没带簇 id → 屏上说清该怎么进来，且**一张证据卡都没画**
  console_errors []
```

截图已看过：`/projects/[id]/analysis` 屏上是关键词输入、预算输入与黄色「发起分析」键
（填了预算之后才亮）；`/combo` 屏上是那句「从热点卡进来才有证据卡可选」。

## 七、verify

```
pytest tests/v041/test_analysis_entry_screens.py -q  → 19 passed
pytest tests/v041 -q                                 → 2416 passed / **1 failed**
                                                       （只剩那条 SSE 403，已立单，非本批）
cd web && npm test -- --run                          → 78 files / 794 tests passed
cd web && npx tsc --noEmit                           → 0
ruff check . --no-cache                              → All checks passed
node tools/check_design_constraints.mjs web          → 11 条规则，0 处违规
node tools/i18n_scan.mjs web --fail-on-cjk           → CJK 0
node tools/no_scaffold_on_screen.mjs web             → 产品面没有 A 类脚手架
python tools/check_line_endings.py                   → 216 个文件全是 LF
```

返工两轮：`ActionOutcome` 的 `unsupported` 分支没处理（tsc 当场报，**那正是判别联合的用处**）；
A6 与它自己的意图对不上（见第四节）。

## 八、self_review（worker.md §4.6）

① **测试覆盖 acceptance**：19 条。做不到的那半条 acceptance（前端预检话术逐字一致）
**不是跳过而是反向钉住**——三处源码里一句拒绝话都不许存，另配守单条。
② **无冻结件偏离**：`contracts/` 一字未动；请求体字段与 `AnalysisSubmitRequest` 逐字对齐。
③ **无禁用词**：grep 零命中。
④ **复用断言在位**：combo 屏复用 `ComboEntryView`，且反向断言它**没有**复刻选卡下界
（`COMBO_MIN`/`comboCountValid` 一个都不许出现在屏里）。
⑤ **装载未超预算**：≈14k tokens。

## 九、留给下游

- `CHAIN-05`（受众分叉 P11 + 干预页 P10）是六屏里最后两屏。
  同族端点已确认在：`POST /projects/{id}/{proposal,evidence,disputes}` 与
  `GET /projects/{id}/hypothesis`；干预四动作要找 `interventions` 族；
- 新屏**必须**登记进 `harness/fe_smoke.py` 与 `tests/v041/test_fe_smoke.py`
  ——本卡与上一卡都被这道绊线拦下来确认过；
- 后端缺口清单已到**六条**，`SHIP-05` 逐条列名。
