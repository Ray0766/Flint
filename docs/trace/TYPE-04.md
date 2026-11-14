# TYPE-04 · 那条扫不动的动态派发路径 + 尺子的两处旧病

**卡** `docs/steward/tasks-v041-b3.json#TYPE-04` · **cycles 1** ·
**self_review = true** → §5 · **owner_review = false**
**依赖** `TYPE-03`（verified）

## 1. 装载清单

卡面 TYPE-04 · `tools/check_fe_be_parity.py` 的 `frontend_calls` /
`_frontend_field_names` / `_field_findings` 三段 ·
`web/lib/jobClient.ts` 的 `submitJob` 与 `JobKind` · `TYPE-01`/`TYPE-02` 登记的两张单 ·
四条真缺口的后端 `response_keys`。约 13k tokens，预算 40k 以内。

## 2. 本卡拥有那把尺子，所以三件事一起做

| 来源 | 病 |
|---|---|
| 卡面 | `/projects/${id}/${kind}` 扫不动 |
| `TYPE-01` 登记 | **平集比对**：一个同名字段就能把「没建类型」误判成「漂移」 |
| `TYPE-02` 登记 | **只读 `types.ts`**：类型在 client 里就被报成「根本没建」 |

三处是同一段代码上的三处病。分开修，第二次还要再读一遍那段逻辑。

## 3. 那条路不是判不动，是没人去展开它

`kind` 的类型是 `JobKind = "analysis" | "report" | "proposal"`，
后端也正好有这三条 POST 路由。加了 `_union_members` + `_expand_enum_segments`：

- 收 `type X = "a" | "b";` 与形参注解 `kind: X`，把变量名接到成员上；
- **只认全部成员都是字符串字面量的联合**——混进一个 `string` 就整条放弃；
- **展不开就原样返回一条**，照旧落进 `dynamic_path_not_checked`。
  **NEVER 展不开还硬猜**：猜错了就是把「没核对」写成「核对过了」。

## 4. 字段面：按接口分组，覆盖面按「层」算

`_frontend_field_names`（读一个文件、返回平集）→ `_frontend_interfaces`
（扫 `web/lib/**` 非测试文件，键是 `"文件名#接口名"`）+ `_best_interface`：

1. **至少两个字段重合**才算「这个接口是为它建的」——一个同名字段的巧合不算；
2. 覆盖面按**层**算：**整个接口都落在这条响应里**，它才是这条响应的一层。
   后端 `response_keys` 是摊平的（`/plaza/hot` 那 21 键分布在信封/簇行/分量/弱信号
   四层上），要求单个接口覆盖半数以上，会把**分层建得好好的**响应判成「没建类型」；
3. **单字段信封**（`TopicResponse { topic }`）只在这条端点已确认有类型落点时才算一层——
   一律排除会把 `/topics/{}` 判成缺口，一律接受又太容易碰巧成立；
4. 报「漂移」时**指名是哪个接口**（`前端在 types.ts#ComboSubmitEcho 里…`）。

三次改判据的过程都在测试里留了对照——**每一步收敛都是被一次实测误判逼出来的**。

## 5. 结果：三类**真归零**，并新看见四条缺口

```
dynamic_path_not_checked   1 → 0
field_mismatch             6 → 0
frontend_untyped_response  0 → 0（TYPE-02 那次的零是误分类得来的）
对账表                     43 条（TYPE-03 收卡时 47）
```

**尺子改准之后新看得见四条真缺口**，本卡一并补齐类型：
`/projects/combo` 的 `hypothesis` · `/projects/{}/report` · `/projects/{}/proposal` ·
`/projects/{}/disputes`。后两条此前**藏在那条「扫不动」里**——展开枚举才露出来。

`DisputeSubmitEcho` 的注释记了一处口径：`current_version`（争议记录自己的乐观锁）
与 `ledger_version`（所依据的证据台账版本）**各是各的**，
合成一个会让「有人同时改了争议」与「台账更新了」分不开。

## 6. 又撞上一处：注释里的路径被当成真调用

给 `types.ts` 写了一句说明「这条路径此前藏在 …… 里」，
**两把尺子都把它读成了一次真调用**：

| 尺子 | 报了什么 |
|---|---|
| `check_fe_be_parity.py` | `dynamic_path_not_checked: /projects/{}/{}` |
| `tests/v041/test_fe_api_contract.py` | `types.ts:158 GET /projects/{}/proposal —— 方法不允许` |

根因：扫描器在**字符串字面量**里找路径，而 `//` 注释里的反引号
**本身就长得像模板串**。`check_fe_be_parity` 的模块注释一直写着
「只在字符串里找，是为了把注释排除在外」——**那句话对反引号引的路径不成立**。

本卡修了自己那把（`_without_comments`：先剥块注释再按行剥行注释），
另一把在 `test_fe_api_contract.py` 里、超出本卡 outputs →
登记 `docs/blocked/SCANNERS-DO-NOT-STRIP-COMMENTS.md`，
并把 `types.ts` 那句注释改成不带反引号的写法（**绕行，不是修好**）。

## 7. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_parity_dynamic_path.py -q → 16 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3764 passed（TYPE-03 收卡时 3748，本卡 +16）
            cd web && npm test -- --run → 74 files / 750 passed
            cd web && npx tsc --noEmit  → 只剩 2 条既有错，本卡零新增
            python tools/check_fe_be_parity.py → 43 条
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 收敛成有限枚举 / 让扫描器识别 | `test_the_job_kind_dispatch_expands_into_three_real_paths`、`test_the_three_expanded_paths_show_up_as_frontend_calls` |
| ② `dynamic_path_not_checked` 归零；确实判不动的 MUST 继续留在这一类 | `test_the_dynamic_class_is_empty_now_and_the_mechanism_still_works`、`test_a_path_that_really_cannot_be_resolved_stays_in_the_class`、`test_a_union_with_a_non_literal_member_is_not_expanded` |
| ③ 阴性对照：构造一条真判不动的，断言它仍被列进那一类 | 同上第二、三条（两种判不动的形态各一条） |
| （登记单一）平集比对 | `test_one_coincidental_field_name_is_not_evidence_of_a_type`、`test_a_layered_response_is_covered_by_its_layers`、`test_an_interface_with_a_stray_field_is_not_counted_as_a_layer` |
| （登记单二）只读一个文件 | `test_the_field_scan_covers_every_file_in_web_lib` |
| （本卡新撞）注释被当调用 | `test_a_comment_that_mentions_a_path_is_not_read_as_a_call` + 阴性对照 `test_a_real_call_is_still_seen_after_comment_stripping` |

**② 改既有文件七处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `tools/check_fe_be_parity.py` | 三处修复（见 §3/§4/§6）+ docstring 那句已不成立的话 | **卡上 outputs**，本卡主体。docstring 不改的话，下一个人会照文档去查然后查错地方 |
| `web/lib/types.ts` | 新增四个 Echo 接口（尺子改准后新看见的真缺口） | 不补的话，尺子会一直报这四条——修尺子的卡留下四条新红是没做完 |
| `tests/v041/test_fe_be_parity.py` | 三条判据（漂移必列两边 / 两类都要有 / 扫不动那条）改判「机制还在」 | 它们的失败信息**自己写着**「修好了就来改这里」——那正是本卡触发的机制 |
| `tests/v041/test_type_drift_deliverable.py` | 阴性对照从「尺子仍在报别的路径」→「扫描面没塌 + 合成对照在」 | 两类真归零后，原写法等于**逼人留一个缺陷不修** |
| `tests/v041/test_types_complete.py` | 计数从「== 6 且 untyped 为空」→ 断言空集 | 同上，且它的失败信息也写着这句 |

**未改**：`tests/v041/test_fe_api_contract.py`（另一把扫描器，超出 outputs，已登记）。
另**重生成**对账表。

**③ 变异考 6 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 不展开末段枚举 | 红 |
| ② 展不开也硬猜 | 红 |
| ③ 退回平集比对 | 红 |
| ④ 覆盖面放宽成「有交集就算一层」 | 红 |
| ⑤ 字段面退回只读 `types.ts` | 红 |
| ⑥ 不剥注释 | 红 |
| ⑦ 假变异对照：只改一句注释 | 全绿 |

**④** 装载约 13k tokens；**⑤** 禁用词六词 0 命中。

## 8. 登记未做

1. **`tests/v041/test_fe_api_contract.py` 的扫描器不剥注释** →
   `docs/blocked/SCANNERS-DO-NOT-STRIP-COMMENTS.md`。
   与既有的 `CRLF-BREAKS-COMMENT-STRIPPING`（JS 侧按 `\n` 剥、遇 CRLF 失效）
   **是同一件事的两面**，建议一并处置。
2. **四个 Echo 接口还没有调用点**：类型建好了，client 的返回值类型没换——
   那要改 client 文件，属接线不属对齐。
3. **`backend_unused_by_frontend` 仍有 33 条**：那是「挂上了但前端没调」，
   本卡没碰。其中多数是 `BE-01~11` 建的端点，等前端接线。
