# DESIGN-05 trace — G15 两处修复 + 资产扫描器@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-05`；
- context_refs：`WORKORDER-v04.md#2-J6`（两处已知问题登记）、`docs/handoff_gap_v04.md`（全文）；
- 前置产物：`web/public/_ds/…`（DESIGN-04 挂进来的副本）、其 `_ds_bundle.js` 与 `tokens/base.css`。
- 实测装载 ≈ 11k tokens，未超 40k。

## 2 先说清楚「修的是哪一份」——这是本卡最要紧的一句

登记的 456 处 inline mono / 14 处 tabular-nums / 23 处 ⚠ 出自
**`design_handoff_flint_web/`（20 屏两轨的页面包）**，而该包**至今不在本仓库**
（`docs/handoff_gap_v04.md` 开头已核实并标 `[待核实]`）。

DESIGN-04 挂进来的是**设计系统本体 `_ds`**（tokens / styles / bundle），
与页面包的交集只有组件层。所以本卡的实测值 **NEVER 用来「验证」或「推翻」登记数字**——
把本体的体检报告拿去给页面包签字，是两份材料混为一谈。gap 文档里我把这句写在了
实测表的正上方，并保留页面包那两行的 `[待核实]` 标记。

## 3 实测与处置（`node tools/scan_ds_assets.mjs web/public/_ds`，11 个文件）

| 项 | 实测 | 处置 |
|---|---|---|
| mono 样式点总数 | 27 | — |
| 缺 `tabular-nums` 的**数字容器** | **2**（`_ds_bundle.js:201` Input 数值标签、`:556` DataTable 数值列表头） | 各补一行 `fontVariantNumeric: "tabular-nums"`，其它样式一个字未动 |
| mono 作**标签**用途 | 17 | **不改** |
| `.num` 类 | 存在且带 `tabular-nums` | 不改 |
| 代码里的 ⚠ 等图标字符 | **0** | — |
| 文档里的 ⚠ | **1**（`readme.md:43`） | 改为「斜纹方 = 争议」 |

**为什么 17 处标签不改**：mono 在这套系统里也是标签字体（表头文字、按钮、说明）。
给标签加等宽数字没有意义，而把它们算作违规会让这把尺子每次报一堆无关项——
然后没人再看它。判据因此只针对**数字容器**：用了 mono，且上下文出现数值语义的名字。

**readme 那处 ⚠ 是描述陈旧，不是图标滥用**：代码里 `StatusMark` 的争议态画的是
**斜纹方块**（`Mark kind="warn"`：9×9 描边方 + `--tex-hatch`），几何印记由组件内联渲染，
一个 emoji 都没有。readme 却把它写成 ⚠——改的是那句描述，让文档与代码对上。
（若反过来把代码改成 ⚠ 才是真的违规。）

## 4 扫描器的判据（`tools/scan_ds_assets.mjs`）

- `--tabular-nums`：数字容器缺 `tabular-nums` 即失败；另断 `.num` 类存在且带该属性
  （类缺失时页面里所有靠它的数字都会失去等宽，而那一处改动不会报错）。
- `--no-warn-emoji`：⚠ ⚡ ❗ ✅ ❌ 🔺 ⛔ ℹ 八个字符。**代码文件即违规**；
  文档里的单独列出——文档描述这套记号是正当的，但描述必须与代码一致，所以照样报出来给人看。
- 不给 flag 时只报告不失败（跟 `i18n_scan` 同款口径，便于先看清现状再决定）。

## 5 自审报告（§4.6，本卡 self_review=true）

**①** acceptance「数字容器 .num/tabular-nums 覆盖；⚠ 字符零残留」↔ 出口命令：
`node tools/scan_ds_assets.mjs web/public/_ds --tabular-nums --no-warn-emoji` → **exit 0**，
输出四行计数（数字容器 0 / `.num` 在 / 代码图标 0 / 文档图标 0）。修复前同一命令 exit 1
且逐条列出三处命中——**先红后绿有据可查**（本 trace §3 表即修复前实测）。
**②** 无冻结件偏离：本卡只动 `web/public/_ds` 副本与文档，零触碰 `contracts/`。
**③** 无禁用词：扫描器源码 `BANNED_HITS= 0`。
**④** 复用断言在位：扫描器的目录遍历/报告口径照 `tools/i18n_scan.mjs` 写法，
未引入任何新依赖（纯 node 内置模块）。
**⑤** 装载 ≈11k tokens，未超 40k。

## 6 verify

```
$ node tools/scan_ds_assets.mjs web/public/_ds --tabular-nums --no-warn-emoji
扫描 11 个文件（web/public/_ds）
  数字容器缺 tabular-nums：0 处
  .num 类带 tabular-nums：在
  代码里的图标字符：0 处
  文档里的图标字符：0 处
EXIT=0
```

回归：`npm test -- --run design/ds-mount` 11 passed（DESIGN-04 的挂载断言在补丁后仍成立）；
前端全套 324 passed / 43 files；`python tools/check_impact_doc.py docs/handoff_gap_v04.md
--require-sections screens,i18n-hardcode,known-issues` 通过。

## 7 产出

- `tools/scan_ds_assets.mjs`
- `web/public/_ds/…/_ds_bundle.js`（2 处补 tabular-nums）、`readme.md`（1 处描述改正）
- `docs/handoff_gap_v04.md`（实测节 + 「登记数字与实测对象不是同一个东西」的说明）
