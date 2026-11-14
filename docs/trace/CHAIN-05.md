# CHAIN-05 · 主链路③：受众分叉与干预页两屏（蓝本 P11/P10）

> v0.4.1 第 5 批第十三张。依赖 `CHAIN-04`（verified）。**六屏补齐了。**

## 装载清单

`tasks-v041-b5.json#CHAIN-05` · `CLAUDE.md#S2`（受保护 block）·
`flint/compose/audience.py`（`HUMAN_TEMPLATES` 与 `plan_proposal`）·
`flint/api/compose.py` + `flint/api/interventions.py` 的四个请求体 ·
`web/lib/interventionClient.ts` · `web/components/BlockInterventionPanel.tsx` ·
`web/lib/types.ts#isProtected` · 真栈 `GET /deliverables/{id}/blocks`。
约 14k tokens，**未超 40k**。

## 一、改前实况

四条干预动作的客户端与 `BlockInterventionPanel` **都建好了**，
`POST /projects/{id}/proposal` 也早就装配了——而 `web/app/` 下**没有任何屏在用它们**。
这是本批第四次遇到同一形状（`TopicListView`/`ComboEntryView`/`BlockInterventionPanel`：
组件在、屏不在）。

## 二、两条硬约束怎么落的

### 2.1 `S2-5`：受保护 block NEVER 被 regenerate 改写

**判断只有一处**：`lib/types.ts#isProtected`（`locked ∨ author=="user" ∨ user_modified`），
`availableBlockInterventions` 据它给出可用动作（受保护 → **空表**）。
屏里 NEVER 再判一次——判两次的话两处规则会在某天分叉，
**而分叉的那天用户会看到一个能点的重生成键，点下去改写了他自己写的段落**。
判据反向扫屏里 NEVER 复刻那三条件，也 NEVER 自己列四个动作名。

受保护时**不渲染动作面板**——渲染了再逐个禁用，等于给了四个能看见的诱饵。

**三种受保护各说各的话**（acceptance② 的「屏上明说拒绝原因」）：
锁着的要先解锁；他自己写的、他改过的，系统本来就不该碰。
合成一句「不可编辑」，用户不知道该去解锁还是该收手。
`locked` 优先说——**解锁是可执行的一步，「你改过它」不是**。

### 2.2 受众**没有默认值**

后端原话（`flint/compose/audience.py`）：`audience is mandatory with no default`。
屏上初值是**没选**，提交键在选之前点不动。给一个默认值等于替用户做了这个决定，
而两条路产出的东西完全不同：五套人类模板是**给人读的散文**，
`vibe_pack` 是**喂给执行者的材料**。

`ai_executor` 时**不给选模板**，并说清「服务端锁死」——
而不是把五个选项灰掉：灰掉的五个仍然在屏上，用户会以为「再等等就能选」。
那条路**不带 `template_id`**（传 `null`）：前端替它填上去的话，
哪天后端换了名字，这里会开始发一个被拒的值。

五套模板的清单是**镜像**，判据两边各取字面量本身逐字比对（并钉住「五套」这个数）。

## 三、A 类脚手架被当场抓住（改对了）

首版把 `block_id`（`bf-01`）当正文渲染，`no_scaffold_on_screen` 判红
「内部 id 直接当正文」。**它是对的**：用户要判断「该不该重生成这一块」，
靠的是**它写了什么**，不是它叫什么。

改成显示这一块自己的文字（原样截断，**NEVER 改写**——改写过的摘要不是它本身），
id 留在 `data-block-id` 上供取证：取证认 id，人看内容。
没有文字的块（图表之类）不显示这一槽（逐槽隐藏）。

## 四、改既有文件（工单纪律 4）

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `web/app/globals.css` | 无这两屏样式 | +`chain-form__choices` 与干预行一段（卡壳与热点卡同源） | 结构与样式成对交付 |
| `web/messages/{zh,en}.json` | 无 | +14 键 ×2 | NEVER 在组件里写死中文 |
| `harness/fe_smoke.py`、`tests/v041/test_fe_smoke.py` | 20 屏 | **22 屏** | 那道绊线；干预页**进屏真取数**，所以用真交付物 id（占位串会让它恒 404） |
| `tests/v041/test_i18n_keys_defined.py` | 六处动态前缀 | +`proposal.audience.` | 那条判据自己写的规矩：多一个前缀就来这里确认候选值全都有定义 |

## 五、取证

```
harness/fe_smoke.py 全量：**22 屏** × 2 主题 × 2 视口
  horizontal_overflow 0 · 噪声面 {'/deliverables/[id]': 3, '/jobs/[id]': 1, '/topics/[id]': 1}（未变）
.ui-probe/chain_fork_screens.json
  interventions  受保护的行 >0，且**受保护的行里动作键 = 0**（S2-5 在真浏览器里也成立）；
                 受保护原因的判别位非空
  proposal       没选受众时提交点不动 → 选了受众 + 填了报告 id 之后能点；
                 选 ai_executor 时模板选择器消失且说清「服务端锁死」，切回给人读时它回来
  console_errors []
```

截图已看过：干预页第一块（`bf-01`，`locked: true`）只有一行虚线的
「这一块锁着：要改先解锁。」**没有任何动作键**；其余块三键齐全。

## 六、verify

```
pytest tests/v041/test_audience_and_intervention_screens.py -q → 19 passed
pytest tests/v041 -q                                           → 2434 passed / **1 failed**
                                                                 （只剩那条 SSE 403，已立单，非本批）
cd web && npm test -- --run                                    → 79 files / 802 tests passed（新增 8 条对照）
cd web && npx tsc --noEmit                                     → 0
ruff check . --no-cache                                        → All checks passed
node tools/check_design_constraints.mjs web                    → 11 条规则，0 处违规
node tools/no_scaffold_on_screen.mjs web                       → 产品面没有 A 类脚手架
node tools/i18n_scan.mjs web --fail-on-cjk                     → CJK 0
python tools/check_line_endings.py                             → 219 个文件全是 LF
```

返工三轮：模板镜像判据按固定字符数截了一段，把邻近的 `AI_TEMPLATE` 与 `Audience` 联合
也刮了进来（**那种「多了三个」的红说的是判据切歪了，不是清单不一致**，已改成只取字面量本身）；
A 类脚手架（见第三节）；i18n 动态前缀要登记。

## 七、self_review（worker.md §4.6）

① **测试覆盖 acceptance**：pytest 19 条 + vitest 8 条阴性对照。
`S2-5` 判了三层：源码层（屏里 NEVER 复刻三条件、NEVER 列第二份动作表）、
组件层（三种受保护各自 `availableBlockInterventions` 回空表）、
**真浏览器层**（受保护的行里动作键计数 = 0）。
② **无冻结件偏离**：`contracts/` 一字未动；受保护三条件与模板清单都**从真相源解析后比对**。
③ **无禁用词**：grep 零命中。
④ **复用断言在位**：屏复用 `BlockInterventionPanel` 与 `availableBlockInterventions`，
反向断言屏里没有第二份动作表；模板清单是镜像且判据钉着两边相等。
⑤ **装载未超预算**：≈14k tokens。

## 八、留给下游

- **蓝本 P1~P14 缺的六屏到此补齐**（P3 combo · P4 主题列表 · P5 主题详情 ·
  P6 发起分析 · P10 干预页 · P11 受众分叉）。`GAUGE-13` 的缺屏名单应当清空——
  那张卡的 acceptance② 逐字写着「CHAIN-03~05 做掉后名单清空」；
- `BlockInterventionPanel` 里有一处 `userId: "self"` 写死（`interventionClient` 的
  `ClientOpts`）。它今天没被脚手架尺子判红（那把尺子认的是 `X-User-Id` 字面量），
  但与 `PLAZA-04` 修掉的那处是同一类。**本卡没动它**——它在组件里、不在本卡触碰面，
  且改它会波及图谱工作台。留给下游或 owner。
