# UIX-03 · `StatusMark`：A4 规则终于有可量对象

**卡** `docs/steward/tasks-v041-b3.json#UIX-03` · **cycles 1（oneshot）** ·
**self_review = true** → §4 · **owner_review = false** · **依赖** `UIX-01`（verified）

## 1. 装载清单

卡面 UIX-03 · `tools/check_design_constraints.mjs` 的 A4 规则与
`optionalSubject` / `noSubject` 机制 · `docs/trace/AUDIT-02.md` 的口径段 ·
`web/components/project-overview/ProjectOverview.tsx` 的 `data-row-state` 用法 ·
`tests/v041/test_design_constraints.py` 的 no-subject 判据。约 7k tokens，预算 40k 以内。

## 2. 为什么「只靠颜色」是缺陷，不是无障碍加分项

四种很常见的情况下它**完全失效**：

1. **灰度打印**——报告打出来交给评审，红绿两点变成一样的灰点；
2. **色觉差异**——红绿型最常见，而「成功/失败」偏偏最爱用红绿；
3. **强制暗色 / 高对比模式**——系统会覆写颜色；
4. **截图转黑白**——本仓 `.ui-probe` 的取证里就有。

所以每个状态**必带非颜色载体**：形状（`glyph`）+ 文字。颜色是第三条线索。

**判据不止判「每个状态都有形状」**——六个状态全用同一个圆点、只换颜色，
那和只靠颜色没有区别。所以还判**形状本身分得开**（种类 ≥3，
且**形状的种类不少于色调的种类**：色调比形状多，说明有一组状态只靠颜色分）。

## 3. 三条口径写进了组件

- **前端零判定**：`state` 由后端给，形状是**查表**来的。
  判据断言组件里没有 `state ===` / `state !==` / `if (`——
  出现分支就是前端在自己判状态了。
- **认不出的状态照样显示**并给中性形状 `◇`。
  不画的话，屏上看起来像「这一行没有状态」，而真相是
  「有状态，但我们没见过这个值」——两者要人做的事不同。
- **形状标 `aria-hidden`，文字不标**。形状字符对读屏软件是噪音；
  文字是它**唯一**能念的那条线索。两条都藏起来，
  用不了眼睛的人就完全不知道这一行是什么状态。

## 4. 撤掉豁免语，比「让名单空掉」更要紧

A4 此前挂着 `optionalSubject`（大意：那个组件还没建）。`AUDIT-02` 当时写着：
「没有对象不是『跑过了、干净』——它进 `no_subject` 名单单独列出来，
免得这条规则的绿被读成『状态标记已经查过了』。」

建出对象后，`noSubject` 名单**自动空了**（它按「没落到文件」算）。
但**豁免语必须撤掉**：留着它，哪天 `StatusMark` 被删掉或改名，
这条规则会**悄悄退回豁免**——报告上写「无可量对象」，
而真相是「本来有，被弄没了」。**两者在报告里长得一模一样。**

变异⑤（把豁免语塞回去）实测判据咬得住。

**另有一处判据抓到了我自己**：第一版注释里引了那句豁免语的原文，
`test_a4_is_no_longer_excused`（判「源码里不许再有那句话」）当场红。
改成转述，不引原文。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_status_mark.py -q → 11 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3802 passed（UIX-02 收卡时 3791，本卡 +11）
            cd web && npm test -- --run → 74 files / 750 passed
            cd web && npx tsc --noEmit  → 只剩 2 条既有错，本卡零新增
            node tools/check_design_constraints.mjs web → 11 条规则 0 违规，**noSubject 空**
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 建 `StatusMark`，状态 MUST 有非颜色载体 | `test_the_component_exists_and_exports_its_name`、`test_every_known_state_carries_a_shape_not_just_a_tone`（判形状分得开）、`test_the_label_is_rendered_as_text_not_only_as_a_glyph`、`test_an_unknown_state_is_still_shown_never_silently_dropped`、`test_the_front_end_never_decides_the_state_itself` |
| ② A4 从 `noSubject` 移出，名单少一条据此变红 | `test_a4_now_has_a_subject_and_reports_clean`、`test_a4_is_no_longer_excused`（含「豁免语不许留在源码里」）、`test_no_other_rule_quietly_joined_the_excused_list`（判**整张名单**为空） |
| ③ 阴性对照：只靠颜色 → A4 报红 | `test_a_colour_only_status_mark_is_reported`、`test_a_status_mark_with_a_shape_passes`（正例）、`test_the_real_component_would_fail_if_its_shapes_were_removed`（**拿真组件抽掉形状再量**——证明它是靠形状通过的，不是碰巧命中了规则认得的某个词） |

**② 改既有文件两处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `tools/check_design_constraints.mjs` | A4 的 `optionalSubject` 豁免语删除，替以「为什么撤掉」的说明 | 卡上 acceptance②。**不撤的话它会在组件被删时悄悄退回豁免** |
| `tests/v041/test_design_constraints.py` | `test_a_rule_with_no_subject_is_declared_not_silently_green` 从「A4 必须在名单里」→「名单为空 + `blind` 也为空 + 每条豁免都要有理由」 | 原判据是组件还没建时的实况，再要求 A4 留在名单里，**就是逼人把一个已经能量的规则挂回豁免**。改后两张名单一起判——只判一张，另一张就成了盲区 |

**③ 变异考 5 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 所有状态换成同一个形状 | 红 |
| ② 文字也标 `aria-hidden` | 红 |
| ③ 认不出的状态悄悄不画 | 红 |
| ④ 组件里自己判状态 | 红 |
| ⑤ 豁免语被塞回去 | 红 |
| ⑥ 假变异对照：只改一句注释 | 全绿 |

**④** 装载约 7k tokens；**⑤** 禁用词六词 0 命中。

## 6. 登记未做

1. **`StatusMark` 还没有调用点**。最自然的两处是
   `ProjectOverview` 的 `data-row-state` 与 `jobs/[id]` 的 `data-job-status`——
   但换它们要动那两个组件的断言面（`UIX-01` 刚被同一类问题拦下过一次），
   **不在本卡 outputs**。属接线，不属建件。
2. **`StatusMark` 的样式没写**（`status-mark--*` 那几个类名在 `globals.css` 里还没有）。
   A4 判的是**非颜色载体存在**，与样式无关；但屏上真要好看，
   得有人补那几条 CSS。属 v2 屏那批卡。
3. **A4 只扫文件名含 `StatusMark|status-mark` 的文件**。
   哪天有人在别处手写一个只靠颜色的状态点，这条规则**看不见**——
   规则的 `appliesTo` 窄成这样是 `AUDIT-02` 的原设计（避免误伤），
   但它的代价要有人知道。
