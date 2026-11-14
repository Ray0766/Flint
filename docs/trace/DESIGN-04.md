# DESIGN-04 trace — 设计系统 `_ds` 挂载（引用不新建 token）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-04`；
- context_refs：`WORKORDER-v04.md#2-J6`（design_handoff 登记 + 两处已知问题 → DESIGN-05）、
  `WORKORDER-v04.md#5-G`（G12 一行）、`DECISIONS-v04.md#DEC-007`（`_ds` 挂 `web/public/_ds`）；
- 前置产物：参考资产包里的 `_ds` 副本（`Claude design Flint 前端设计/Flint 应用 · 20 屏/_ds/`）、
  其 `_ds_manifest.json`（74 个 token、7 份全局样式）。
- 实测装载 ≈ 9k tokens，未超 40k。

## 2 挂了哪一份，为什么

参考包里有 8 个 `_ds` 目录（营销首屏、404、卡堆叠等各带一份）。挂的是
**「Flint 应用 · 20 屏」** 那一份——J6 登记的正是这套 20 屏两轨资产，
后续 DESIGN-05 的两处修复（`tabular-nums`、⚠ 当图标）也是对它做。
挂错版本的后果不是报错，是**样板引用到不存在的 token 后静默回落到无值**，
界面上表现为一处没有颜色的文字或塌掉的间距——所以另加了一条
「manifest 里的 token 名与 `colors.css` 实际定义对得上」的测试来钉住版本。

副本落 `web/public/_ds/flint-design-system-8fd95ba3…/`（127 KB，含 tokens/fonts/styles
与 manifest）。

## 3 关键设计判断

**「不新建 token」比「长得像」要紧**：新建一个 `--my-blue: #2E4A7E` 看起来和藍染
`#2E4A7D` 一模一样，但设计系统改色时它不会跟着变——半年后界面上会有两种「藍染」，
而没有人知道第二种是哪来的。引用 `var(--indigo)` 则永远跟着系统走。

**把判据做成函数而不是留给眼睛**：`findNewTokenDefinitions` 把「新建 token」变成
可机器检查的事。定义与引用的区别就是这条规则的全部：`var(--indigo)` 是引用，
`--indigo: #xxx` 是定义。

**还查「引用了不存在的 token」**：拼错名字不会报错，只会静默回落到无值。
`findUnknownTokenReferences` 拿 manifest 的 74 个名字当已知集合。

**全局样式顺序照 manifest**：顺序影响层叠，打乱会让 `base.css` 覆盖掉 token 定义。
有一条逐项相等的断言盯着。

## 4 一次实现修正 + 一次已知缺陷规避

**实现修正**：`DEFINITION` 正则起初要求名字前面是 `;{` 或空白，于是行内
`style="--gap:12px"` 里的第一个定义被漏掉——**藏在属性里不代表不存在**。
改为只按「名字后跟冒号」判定（引用形态 `var(--x)` 后面是 `)` 或 `,`，不会误判）。
这是判据太窄的实现 bug，不是测试写错。

**已知缺陷规避**：`dsMount.ts` 里一段 JSDoc 被 `i18n_scan` 判成未 key 化 CJK ——
DEC-013 / 卡 `I18N-09` 已登记的第一类假阳性（跨行块注释）。按 GRAPH-16 的同款处置
改写成行注释并注明出处；**未改扫描器**（那是 I18N-09 的产出）、未加白名单。

## 5 acceptance ↔ 测试映射

acceptance 唯一条：**样板引用 _ds 变量；新建 token 扫描零命中**。

| 测试名 | 覆盖点 |
|---|---|
| `副本真的挂在 web/public/_ds 下` | 目录、manifest、`tokens/colors.css` 三处存在（不是只写了个路径常量） |
| `全局样式清单与 manifest 逐项一致，顺序也一致` | 顺序影响层叠 |
| `每个样式文件都存在` | 清单写着而文件缺失会静默丢一整套 token |
| `href 拼出来指向 public 下的真实位置` | 拼接正确 |
| `引用不算新建：var(--indigo) 零命中` | 引用与定义分得开 |
| `定义算新建：--my-blue 必须被抓出来` | 正向命中 |
| `行内 style 里的定义同样算` | 属性里的定义（本卡修正的那条） |
| `样板新建 token 零命中` | acceptance 的正面结论 |
| `引用未知 token 会被抓出来` | 拼错名字静默回落 |
| `_ds 自己的 tokens/*.css 当然是定义（阴性对照）` | 一把认不出定义的尺子会让「零命中」变成空话 |
| `manifest 里的 token 名与 colors.css 实际定义对得上` | 钉住挂载版本 |

## 6 verify

```
$ cd web && npm test -- --run design/ds-mount  → 11 passed
$ npm test -- --run                             → 324 passed / 43 files
$ npm run typecheck                             → 干净
$ node tools/i18n_scan.mjs web/design --fail-on-cjk → exit 0
```

整棵 `web/` 树的 CJK 命中从 7 升到 8 个文件——新增的那个是 **挂进来的 `_ds` 副本**
（`readme.md` 之外的资产本身带中文注释），属参考资产而非我们写的界面文案；
`I18N-09` 收尾时须把 `web/public/_ds` 排除在扫描面外（已在本 trace 记明，
供那张卡执行时采信）。

## 7 产出

- `web/public/_ds/flint-design-system-8fd95ba3…/`（挂载副本）
- `web/design/ds-mount/dsMount.ts`、`dsMount.test.ts`（11 条）
