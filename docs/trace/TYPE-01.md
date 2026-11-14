# TYPE-01 · `/deliverables/{}` 的类型漂移

**卡** `docs/steward/tasks-v041-b3.json#TYPE-01` · **cycles 1（oneshot）** ·
**self_review = true** → §4 · **owner_review = false**
**依赖** `WIRE-01`（verified）

## 1. 装载清单

卡面 TYPE-01 · `docs/前后端对账表-v041.md` 第 71 行那条 ·
`web/lib/types.ts` 的 `Block` / `BlocksResponse` 段 ·
`tools/check_fe_be_parity.py::_field_findings` · 后端真 payload（实打）。
约 6k tokens，预算 40k 以内。

## 2. 对账表说的「漂移」，实测**不是漂移**

表里写：「前端已为这条端点建了类型，但后端这几个字段没被声明（真漂移）；
前端已声明 `deliverable_id`, `type`」。

**前端从没为它建过类型。** 那两个名字来自 `Block` 接口——
对账器把 `types.ts` 的字段名当成**一个平集**比，两个同名字段撞上了。

两者要人做的事不同：**漂移去对齐，没建类型去新建**。
本卡做的是后者：新建 `DeliverableMeta`，五个字段逐条对齐后端。

三个字段各是什么，写进了类型的注释里——`version` 是交付物自身的版本，
`ledger_version` 是它所依据的**证据台账**版本，**两者会各走各的**
（台账更新了而交付物没重生成，正是 Revalidator 要处理的情形）；
`reproducible` 是 S2-2 那条铁律的可读形态。

## 3. 这一改把误报从**一条变成了两条**——已登记

新建的 `DeliverableMeta` 带 `ledger_version`，于是
`/projects/{}/disputes` 与 `/projects/{}/evidence` **立刻被判成「漂移」**，
理由是「前端已声明 `ledger_version`」——而那个字段属交付物元信息，
与争议、证据毫无关系。

**不是改坏了什么**：这把尺子的判别方式本来就会随 `types.ts` 变大
而越来越容易误判。修法要动 `_field_findings`（按接口分组而非全文件平集），
超出本卡 outputs → 停下登记：
`docs/blocked/PARITY-FIELD-NAMES-COMPARED-AS-ONE-FLAT-SET.md`，
**天然归属 `TYPE-04`**（它拥有 `tools/check_fe_be_parity.py`）。

单子里另记了一条给 `TYPE-02` 的提醒：**它要判
`frontend_untyped_response` 归零，而在本缺陷修好之前那个计数会因误判而偏低**
（被错分到 `field_mismatch` 去了）。收卡时 MUST 核对。

## 4. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_type_drift_deliverable.py -q → 7 passed（0 skipped）
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3729 passed（WIRE-06 收卡时 3722，本卡 +7）
            cd web && npm test -- --run → 74 files / 750 passed（未动前端测试）
            cd web && npx tsc --noEmit  → 只剩 2 条既有错，本卡零新增
            python tools/check_fe_be_parity.py → 53 条（WIRE-06 时 54，本卡 -1）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 补齐 `ledger_version` · `reproducible` · `version` | `test_the_frontend_type_declares_every_field_the_backend_returns`（判包含）、`test_the_three_drifted_fields_are_there_by_name`（点名那三个）、`test_the_type_declares_nothing_the_backend_never_sends`（反向：多声明也不行） |
| ② 判据取自后端真实 payload，NEVER 手抄 | `_backend_keys()` 从 **AST** 抽；`test_the_ast_keys_match_the_real_payload` 拿 **真请求**互相校验（实测对上，未 skip）；`test_the_field_names_were_not_hand_copied_into_this_file` 判**本文件自己**不许出现手抄清单 |
| ③ 对账表里这条 `field_mismatch` 消失 | `test_the_parity_table_no_longer_reports_this_path_as_drift` + `test_the_ruler_still_reports_drift_elsewhere`（阴性对照：尺子没瞎） |

**两个源互相校验**是这张卡最值钱的一处：AST 抽漏了、或后端改了响应而
处理函数里的字面量 dict 没跟着变，两边就对不上。单靠任何一个源都发现不了。

**② 改既有文件一处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `web/lib/types.ts` | 新增 `DeliverableMeta`（5 字段 + 说明那三个字段各是什么的注释） | **卡上 outputs**，本卡主体 |

另**重生成** `docs/前后端对账表-v041.md`（54 → 53 条）——表是跑出来的。

**③ 变异考 3 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 少声明一个字段 | 红 |
| ② 多声明一个后端不给的字段 | 红 |
| ③ 整个接口删掉（退回没建类型） | 红 |
| ④ 假变异对照：只改一句注释 | 全绿 |

**④** 装载约 6k tokens；**⑤** 禁用词六词 0 命中。

## 5. 登记未做

1. **分类精度**（§3）→ `TYPE-04`，单子已落盘。
2. **`DeliverableMeta` 还没有人用**：`deliverableClient.ts` 明确只打
   `/blocks`（「`/deliverables/{id}` 那只回元信息」）。类型建好了但没有调用点——
   **这是有意的**：本卡只对齐契约，接线不在卡面。
   哪天有屏要显示「这份报告依据的台账版本」，直接用它即可。
