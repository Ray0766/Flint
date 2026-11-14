# AUDIT-02 · 交付包技术约束清单可执行化

**卡** `docs/steward/tasks-v041-b2.json#AUDIT-02` · **cycles 2**（`oneshot=false`）·
**self_review = true** → §6 · **owner_review = false**
**依赖** EYE-02（verified）

## 1. 装载清单

卡面 AUDIT-02 · `04_技术约束清单.md` 全文 · `tools/_scan_lib.mjs`（剥注释口径）·
`tools/lint_no_confidence_viz.mjs`（避免重叠）· `web/app/**/page.tsx` 六个页面 ·
`web/components/shell/`（S1 通用件实况）· 交付包 README 的 S1 通用件契约。
约 11k tokens，预算 40k 以内。

## 2. 卡面写「19 条」，文件里是 32 条

`04_技术约束清单.md` 实际编号到 **32**（A1~7 / B8~12 / C13~19 / D20~28 / E29~32）。
卡面标题写的是「19 条」——**照文件办，不停**（与 BE-07 那处
「orthogonality_check 名字对不上」同一处置：说的那件事在，只是数字/名字不符）。

本卡做成机器断言的是 **11 条**，覆盖卡面点名的重点六条 + 与后端字段相关的三条：

| 规则 | 清单条目 |
|---|---|
| A1 | 1 把布尔/枚举画成连续量（星级 / 雷达 / 合成百分比） |
| A3 | 3 未建接口留位必须写「接口未提供」 |
| A4 | 4 状态标记有非颜色载体 |
| A5 | 5 `--rust` 只留给阻塞标 / 409 / 503 |
| A6 | 6 每屏三态齐全、空态 ≠ 错误态 |
| B8 | 8 `/plaza/hot` 无前端重排 |
| B9 | 9 `by_source` 不合成 |
| C17a | 17 verdict 直取，前端不判 |
| C17b | 17 `constraints_checked` 按对象不按 boolean |
| C19 | 19 `unknown` 与 `weak` 不同形 |
| D23 | 23 `quantity` 不乘算 |

**没做成断言的那些不是漏了**，是它们量不动（见 §7 登记）：
「mock 键名与文档示例逐字一致」要有那份示例 JSON、「保护块不渲染控件」要跑起来看 DOM。
静态扫不动的东西，**硬扫出来的结果比不扫更糟**。

## 3. 不与既有尺子重叠

清单第 1 条的「置信度可视化」那一半归 `tools/lint_no_confidence_viz.mjs`（DESIGN-23）。
本器**不重复实现**——两把尺子量同一件事的那天，它们会在某个边界上给出不同答案，
而两边各有一半的道理。本器只补它没覆盖的那一半：星级 / 雷达 / 合成百分比。

## 4. 尺子自己会瞎：三处实测到的

### 4.1 A6 的 `appliesTo` 写错，一个文件都没落到（**静静地全绿**）

第一版写 `/[\\/]app[\\/].*page\.tsx$/`，而相对路径是 `app/plaza/page.tsx`——
**开头就是 `app/`，前面没有分隔符**。于是这条规则匹配 0 个文件，
而扫描器照样打印「0 处违规」。

这促成了本器的一条结构性设计：**每条规则报「落到过几个文件」**。
一条规则一个文件都没落到 = 它是瞎的，退出码算不通过。
判据 `test_no_rule_is_blind_on_the_real_tree` 钉住它。

### 4.2 「对象还不存在」与「规则写错了」要分开

A4 的对象是 `StatusMark` 组件，而**本仓根本还没有这个组件**（属 v2 屏 UI 卡）。
把它算成「瞎的」会让门恒红；算成「通过」又会被读成「状态标记查过了、干净」。
所以第三种态：`noSubject`，**列出来但不算失败**，且必须写明为什么没有对象。

这是本轮反复出现的那条（`not_checked` vs `checked-empty`）在扫描器上的形态。

### 4.3 `--json` 里丢了 `applied`

统计挂在返回的**数组**上（`findings.applied = applied`），而
`JSON.stringify` 只序列化数组的元素——那个属性在 `--json` 里悄悄消失了。
改成返回对象。**报告里没有的东西，读的人无从知道它存在过。**

## 5. 规则太窄与太宽各一次

| 方向 | 事 | 修法 |
|---|---|---|
| 太宽 | A6 只看 page 自己的文本 → 六个页面全被报「缺三态」，而三态写在 `<Screen>`/`<PlazaView>` 里 | 跟着**本地 import 走一层** |
| 太窄 | C17a 只认 `verdict === "A"`，抓不到 `score > 3 ? "A" : "B"`——**后者才是最常见的那种**，而它长得完全不像在判 verdict | 加「三元出一个 A/B/C/D」 |
| 太窄 | C19 只认两个字面量紧挨着，抓不到 `s === 'unknown' \|\| s === 'weak'` | 允许中间隔一个比较式 |

两处「太窄」都是**阴性对照逼出来的**：我先写了违规样例，再发现规则抓不到它。
没有阴性对照的话，这两条规则会以「一直是绿的」的形态活很久。

## 6. 验证：阴性对照就是扫描器的变异考

对一把扫描器来说，**变的是被量的东西，不是尺子**。所以本卡没有单独的变异脚本，
verification 由三组对照构成：

- **12 条阴性对照**（每条规则至少一条真违规样例 → 必须报红）；
- **7 条正向对照**（干净写法 → 必须闭嘴，不误伤）；
- **3 条尺子自检**（没有瞎规则 / 无对象要声明 / 统计要报出来）。

外加两条边界：测试文件不被扫（里面故意写着违规样例）、真干净的树 exit 0。

## 7. 本仓实况：四处真缺口，逐条列名

```
node tools/check_design_constraints.mjs web
A6 app/deliverables/[id]/export/page.tsx:1 — 缺加载态
A6 app/deliverables/[id]/page.tsx:1       — 缺加载态
A6 app/demo/page.tsx:1                    — 缺加载态、错误态
A6 app/jobs/[id]/page.tsx:1               — 缺加载态、错误态
```

这四条是**真的**：这些页面在源码里连「加载中」这个意思都找不到（中英文都没有），
而 README 的 S1 通用件契约点名的 `LoadingSkeleton` / `EmptyState` / `ErrorState`
**一件都没建**（`web/components/shell/` 只有 AppShell / Screen / NotProvided）。

修法是建三个通用件 + 改四个页面——**属 UI 卡的活**，改动面远大于本卡 outputs
（§六.1）。所以：

1. 登记 `docs/blocked/S1-COMMON-STATES-MISSING.md`（含四个文件名与建议去向）；
2. 判据 `test_the_real_tree_has_exactly_the_known_gaps` 把这四条**逐条写死**——
   **多一条或少一条都红**：多一条 = 新引入了违规；少一条 = 有人修好了，去更新单子。

这不是「放过」：放过是让门变绿；这里门里钉着一张会因为任何变动而红的单子。

## 8. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_design_constraints.py -q → 29 passed
            （基线：collection error，收集期就红）
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: no issues found in 299 source files
            pytest -q               → 3526 passed（AUDIT-01 收卡时 3497，本卡 +29）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 重点六条做成机器断言 | `test_a_real_violation_is_reported[A1/A3/A4/A5/A6/B8/B9/D23-*]`、`test_a_clean_sample_is_not_reported[*]` |
| ② 与后端字段相关的三条 | `test_a_real_violation_is_reported[C17a-*]`（verdict 直取）、`[C17b-*]`（constraints_checked 按对象）、`[C19-*]`（unknown ≠ weak）+ 各自的正向对照 |
| ③ 每条配阴性对照 | 上面 12 条 parametrize 就是；外加 `test_no_rule_is_blind_on_the_real_tree`、`test_a_rule_with_no_subject_is_declared_not_silently_green`、`test_the_scanner_counts_every_rule_it_applied` |
| ④ 接进全局门 | `test_this_test_file_is_the_gate_wiring`、`test_the_scanner_runs_from_the_command_line`、`test_a_tree_with_no_violations_exits_zero`、`test_node_is_available` |

**② 无冻结件偏离**：新增两个文件 + 一个登记文档；`web/` **一个字没改**；
`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
未触碰；零新增依赖（node 标准库 + 既有 `_scan_lib.mjs`）。
**playwright 与 `C:\pwenv` 未触碰**（本卡是静态扫描，不需要浏览器）。

**③ 禁用词**：六词在三个产物里 0 命中；「等」全是「等于」「等价」。

**④ 复用**：剥注释走既有 `tools/_scan_lib.mjs`（CRLF 与 `https://` 两个坑已在那里踩过）；
置信度可视化那半条留给 `lint_no_confidence_viz.mjs`；
`--json` 出机读版的约定与 PAY-03 / AUDIT-01 一致。

**⑤ 装载预算**：约 11k tokens，未超 40k。

**⑥ cycles**：卡面 2，实际 1 个连跑回合内完成。

## 9. 登记未做

1. **21 条没做成断言**（32 − 11）。不是漏，是**静态扫不动**：
   - 「mock 键名与文档示例 JSON 逐字一致」（第 2 条）：要那份示例 JSON 当基准，
     而它在交付包的 `.dc.html` 里，得先抽出来——属另一张卡；
   - 「保护块是不存在还是置灰」（第 20 条）：要跑起来看 DOM，
     属 `scripts/ui_probe.py` 那条视觉取证线；
   - 「SSE 接线对吗」（第 16 条）、「乐观锁走确认流」（第 26 条）：
     要跑一次真实交互才看得出来。
   **硬扫出来的结果比不扫更糟**——它会给出一个「查过了」的假象。
2. **A4 当前无可量对象**（`StatusMark` 组件未建），已在 `noSubject` 里声明。
3. **四处真缺口未修**，见 §7 与 `docs/blocked/S1-COMMON-STATES-MISSING.md`。
4. **规则表按「条目号」编，不按屏**。同一条约束在不同屏上的形态可能不同
   （例如 A6 的三态在列表屏与详情屏要求不一样），本器**只判有没有**，不判形态。
