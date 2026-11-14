# WIRE-11 · UNWIRED_FAMILIES 清空，出口判据回到真归零

**卡** `docs/steward/tasks-v041-b4.json#WIRE-11` · **cycles 1（oneshot）** ·
**self_review = true** → §4 · **owner_review = false** ·
**依赖** `WIRE-07` / `WIRE-08` / `WIRE-09` / `WIRE-10`

## 1. 装载清单

卡面 WIRE-11 · `flint/api/app.py` 的 `UNWIRED_FAMILIES` ·
`tools/check_fe_be_parity.py#parity` 与 `mounted_paths` ·
`tests/v041/test_fe_be_parity.py` 全文 ·
`docs/blocked/WIRE-01-FOUR-FAMILIES-NEED-AUTH-AND-PROVIDER.md`。
约 10k tokens，预算 40k 以内。

## 2. 出口判据实跑（acceptance②）

```
$ python tools/check_fe_be_parity.py --json
scanned:  backend 62 · frontend 16 · expected 16
  backend_not_assembled          0      ← DEC-031 的出口判据，归零
  frontend_untyped_response      0
  app_unbuildable                0
  backend_unused_by_frontend     35     ← 不是判据（GAUGE-11 逐条分诊）
  field_drift                    0
```

`UNWIRED_FAMILIES` 已由 `WIRE-10` 清空（本卡确认并把判据收口）。
判据从「已挂 52 + 已登记 10」改回 **`backend_not_assembled == 0`**。

## 3. 「0」的意义由一条阴性对照担保（acceptance③）

归零有两种读法：**「量到了、确实全挂上了」** 与 **「尺子塌了，什么都量不到」**——
两者在报告上长得一模一样。所以本卡加了
`test_a_module_that_is_not_mounted_still_turns_the_zero_red`：
造一个真的临时 api 目录，里面一个模块声明 `/never-mounted`，
另有一份 `app.py` 不挂它，断言那条被算进「未挂载」的差集。

`WIRE-05` 建的三条对照（`include_router` 无路径字面量 / 空 router 不算挂 /
前缀与隐藏路由照样算挂）**一条都没拆**，本卡在它们旁边加了第四条。

## 4. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_fe_be_parity.py -q → 43 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 301 source files
            pytest -q               → 4005 passed（WIRE-10 收卡时 4004，本卡 +1）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 清空 + 判据回到归零 | `test_an_unmounted_route_is_reported_as_idle_capacity`（断言空集）、`test_each_unwired_family_says_what_is_missing_and_holds_a_ticket`（`UNWIRED_FAMILIES == ()`） |
| ② 实跑输出贴进 trace | §2 |
| ③ 阴性对照仍在位 | `test_a_module_that_is_not_mounted_still_turns_the_zero_red` + `WIRE-05` 那三条原样保留 |
| ④ 关闭 `WIRE-01` 那张单 | 单子顶部 `**状态** closed · 2026-08-06 · WIRE-11`，正文写明 owner 裁决走第 1 条与兑现它的九张卡；`test_blocked_sheets_state.py` 7 passed |

**② 改既有文件两处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `tests/v041/test_fe_be_parity.py` | 加归零的阴性对照；**顺手修复一处被我自己改坏的常量** | **卡上 outputs**。修复那处见 §5 |
| `docs/blocked/WIRE-01-…md` | `open` → `closed`，附兑现清单与实跑输出 | 卡上 acceptance④ |

`flint/api/app.py` 本卡**一字未改**（`WIRE-10` 已清空登记）。
`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；未新增依赖。

**③ 变异考 3 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 退回缺陷态：不挂 analysis | 红 |
| ② 不挂 compose | 红 |
| ③ 应用建不起来（装配期抛） | 红（6 条，且报的是 `app_unbuildable` 而不是「全都没装配」） |
| ④ 假变异对照：末尾加一行注释 | 全绿 |

③ 值得单说：应用建不起来时，对账器报的是**「装配面没量到」**，
而不是印一份与「62 条全没挂」逐字相同的报告——两者该让人做的事完全相反。

## 5. 一处我自己改坏又修好的地方

用脚本插判据时，替换区间吃掉了 `_APP_WITH_ROUTER` 那个常量的**开头**
（`_APP_WITH_ROUTER = '''` 与前三行），留下一段游离的源码文本，整个文件语法坏掉。

**修法是从判据反推原值**：`test_a_router_mounted_without_a_path_literal_is_seen`
断言 `mounted_paths(...) == {"/alpha", "/beta/{}"}`，据此把
`@router.get("/alpha")` 那几行补回去，再跑一次那条判据确认。

**教训**：拿「找起点、找下一个 `def`」当替换区间是不可靠的——
两个常量之间没有 `def`。这一类批量改动 MUST 先验语法（`ast.parse`）再跑测试。

## 6. 登记未做

1. **`backend_unused_by_frontend` 35 条不是判据**，`GAUGE-11` 逐条分诊。
   本卡只把它照实印出来。
2. **`SHIP-03` 的 blocked 前提消失了，但那张卡属第 3 批**。
   本批 `SHIP-04` 收尾时会重跑那五条出口命令；第 3 批那张卡要不要改状态，
   是 steward 的事，本卡不动别人批次的台账。
