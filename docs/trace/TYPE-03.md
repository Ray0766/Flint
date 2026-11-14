# TYPE-03 · `Verdict.constraints_checked` 前端标成 boolean，后端是对象

**卡** `docs/steward/tasks-v041-b3.json#TYPE-03` · **cycles 1（oneshot）** ·
**self_review = true** → §4 · **owner_review = false**
**依赖** `TYPE-02`（verified）

## 1. 装载清单

卡面 TYPE-03 · `docs/blocked/VERDICT-CONSTRAINTS-CHECKED-TYPE.md` 全文 ·
`web/lib/viewsClient.ts#Verdict` · **`flint/gate/engine.py:55-75`**
（`constraints_checked` 的构造处——期望值从这里抽，不手抄）·
`web/components/views/GateView.tsx` 的渲染面。约 6k tokens，预算 40k 以内。

## 2. 后端真形状比卡面列的更深

卡面列了六个字段。实测 `engine.py` 的构造：顶层确实六个，
但**三条规则各自还有子字段**：

| 顶层键 | 内容 |
|---|---|
| `order` | 判定顺序 A>B>C>D，**后端给什么就是什么**（前端 NEVER 自己排） |
| `demoted_by_alignment` | 被两段式对齐降级掉的那些 |
| `rule_a` | `satisfied` · `used_user_evidence_only` · `blocked_pending_optin` |
| `rule_b` | `satisfied` · `by_count` · `by_strength` · `reachable_count` · `strong_names` |
| `rule_c` | `satisfied` · `failed_conditions` · `blocking_competitors` |
| `gap_count` | 缺口条数（判 D 时必然 > 0，`engine.py` 有断言） |

摊平成一个 `satisfied` 就丢了复盘依据——`engine.py` 的 docstring 原话是
「摊平三规则的评估痕迹，**供 VerdictShift 重跑复盘**」。已按真形状建齐。

## 3. 改类型的那一刻当场抓到一处

`web/components/views/views.test.tsx` 的夹具写着 `constraints_checked: true`。

**夹具照着错类型写，于是两边一起错**——所以此前谁都看不出来。
`tsc` 在我改完类型的那一秒就把它拦下来了。已按真形状改。

这也是这张卡最值得记的一点：**错类型不会自己暴露，它会把配套的夹具一起带偏**。

## 4. 危险点写成了会跑的判据

卡面 acceptance② 要求「构造这种误用并判红」。
**只断言「类型已经改成对象」是不够的**——那只说明字面量变了。
要证明的是**那种误用现在写不出来**。

所以判据跑**真 `tsc`**：

| 片段 | 期望 |
|---|---|
| `const flag: boolean = v.constraints_checked;` | **编译不过** |
| `return v.constraints_checked.gap_count;` | **编译通过** |

两条都跑，才分得清「拦住了」和「见谁都拦」。
临时探针 `web/_type03_probe.ts` 用完即删（`finally`），并有一条判据确认它没留下。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_verdict_constraints_type.py -q → 11 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3748 passed（TYPE-02 收卡时 3737，本卡 +11）
            cd web && npm test -- --run → 74 files / 750 passed
            cd web && npx tsc --noEmit  → 只剩 2 条既有错，本卡零新增
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 改成对象、字段逐字对齐 | `test_the_field_is_no_longer_a_boolean`、`test_the_object_declares_exactly_what_the_backend_puts_in`（判**等值**，期望值从 `engine.py` 抽）、`test_the_three_rules_keep_their_own_sub_fields`、`test_the_counts_are_numbers_not_ratios`、`test_the_backend_shape_is_read_from_the_engine_not_hand_copied` |
| ② 危险点写成判据、构造误用并判红 | `test_tsc_rejects_the_boolean_misuse_and_accepts_the_right_one`（**真 `tsc`**，两个方向各一条）、`test_the_probe_file_is_not_left_in_the_tree` |
| ③ 关闭问题单 | `test_the_ticket_is_closed_with_a_banner_and_a_date`、`test_the_existing_fixture_was_fixed_too` |
| （自加） | `test_the_gate_view_still_does_not_render_it`——盯着「哪天有人开始渲染」，见 §6 |

**② 改既有文件三处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `web/lib/viewsClient.ts` | `constraints_checked: boolean` → `ConstraintsChecked`（新建接口，含三规则子字段与说明） | **卡上 outputs**，本卡主体 |
| `web/components/views/views.test.tsx` | 夹具 `constraints_checked: true` → 真形状对象 | 改类型后 `tsc` 当场拦下它。**不改则整个前端类型检查恒红** |
| `docs/blocked/VERDICT-CONSTRAINTS-CHECKED-TYPE.md` | 顶部加关闭横幅（日期 + 卡号 + 修法 + 夹具那处发现），原文一字未改以 `---` 隔开 | **卡上 acceptance③** |

**③ 变异考 6 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 退回 boolean | 红 |
| ② 摊平三规则（只留 `satisfied`） | 红 |
| ③ 少声明一个顶层字段 | 红 |
| ④ 计数改成比率 | 红 |
| ⑤ 夹具退回 `true` | 红 |
| ⑥ 有人开始渲染判定依据了 | 红 |
| ⑦ 假变异对照：只改一句注释 | 全绿 |

**④** 装载约 6k tokens；**⑤** 禁用词六词 0 命中。

## 6. 登记未做

1. **`GateView` 仍然不渲染这个字段**——本卡只改类型，不做渲染。
   `test_the_gate_view_still_does_not_render_it` 盯着它：
   **哪天有人开始渲染，那条会红**，而那正是该确认「面板是按六项依据画的、
   不是 `{v.constraints_checked ? …}`」的时刻。
2. **判定依据面板本身**没有卡。蓝本 P8 说「已按对象渲染成可展开判定依据」，
   而本仓的 `GateView` 没做——**这是一处蓝本与实况的差**，
   若 owner 要那个面板，需要单开一张卡。
