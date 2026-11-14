# DESIGN-13 trace — 后台检查三态（unreported ≠ passed）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-13`；
- context_refs：`WORKORDER-v04.md#5-G`（G19 一行）、`WORKORDER-v04.md#4`（事件增量：design_check）；
- 前置产物：`web/components/hotspot-card/HotspotCard.tsx`（「缺失逐槽隐藏 NEVER 占位」）、
  `web/design/comments/CommentLayer.tsx`（DESIGN-12 的「失锚仍可见」）、`web/test-utils/source.ts`。
- 实测装载 ≈ 5k tokens，未超 40k。

## 2 为什么这条值得一张卡

`unreported` 是「这项检查没跑或没回话」，它与「跑了、过了」是**两件相反的事**：
一个是不知道，一个是知道没问题。把不知道画成绿色，用户会拿着一份「全绿」的界面
去做决定，而那些绿里有几格其实什么都没检查过。

这与 HOTSPOT-01 的「缺失逐槽隐藏 NEVER 占位」、DESIGN-12 的「失锚仍可见」同源：
**不确定的状态 NEVER 伪装成确定的**。本卡是这条纪律在「检查结果」上的落点。

## 3 关键设计判断

**三处都分得开**：class（看得见）、`aria-label`（读得出）、`data-state`（机器读）。
只靠颜色区分的话，色觉障碍用户与读屏用户拿到的就是两态。测试用集合计数断言
三者各不相同，而不是逐个字符串比对——这样换文案不会误伤，换成两态一定红。

**未知状态抛错**：多一个状态进来时，宁可在开发期炸掉，也不要在界面上多一格
看起来没问题的绿。

**汇总的 `all_passed` 只有全 passed 才为真**：有 unreported 不算全过（那是不知道），
**空清单也不算全过**——一项都没有时说「通过」没有任何依据。

**源码级堵住两种折算写法**：`unreported…passed` 同现于一行、以及
`state !== "failed"`（「不是失败就算过」）——后者是这类 bug 最常见的形态。

## 4 自审报告（§4.6，本卡 self_review=true）

**①** acceptance「三态视觉可区分（aria+class）；unreported 渲染 NEVER 等同 passed」↔ 测试：

| 测试名 | 覆盖点 |
|---|---|
| `三态就是这三个` | 状态集逐字 |
| `三态的 class 与 aria 各不相同` | class/aria-label 各 3 个不重复 + `data-state` 逐项 |
| `unreported 的每一处呈现都不等于 passed` | class / aria-label / 文本三处逐一比对 |
| `unreported 不靠颜色说话` | aria-label 非空且取到词条 |
| `未知状态不当成 passed` | 抛错 |
| `检查名如实带出` | 用户要知道是哪一项没跑 |
| `汇总把三态分开计数` | 三个计数属性 |
| `有 unreported 时整体不算「全过」` | `all-passed=false` |
| `全 passed 才是全过` | 阴性对照 |
| `空清单不是全过` | 零项时不显示通过 |
| `源码里没有把 unreported 折算成 passed 的写法` | 两种折算写法 |

**②** 无冻结件偏离：纯前端。
**③** 无禁用词：两份产出 0 命中。
**④** 复用断言在位：文案经 `t()`；源码扫描走共享 `codeOnly`；三态语义与
`contracts_v04` 的 `design_check` 事件成员对齐（本卡未新增类型）。
**⑤** 装载 ≈5k tokens，未超 40k。

## 5 verify

```
$ cd web && npm test -- --run design/check-tristate  → 12 passed
$ npm test -- --run                                    → 407 passed / 50 files
$ npm run typecheck                                    → 干净
$ node tools/i18n_scan.mjs web/design --fail-on-cjk    → exit 0
```

产出均为 LF；禁用词 0。

## 6 产出

- `web/design/check-tristate/CheckStatus.tsx`、`CheckStatus.test.tsx`（12 条）
- `web/messages/{zh,en}.json`：各 +3 key（80 键，键集一致）
