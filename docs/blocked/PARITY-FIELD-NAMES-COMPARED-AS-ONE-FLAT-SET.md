# PARITY-FIELD-NAMES-COMPARED-AS-ONE-FLAT-SET · 一个同名字段就能把「没建类型」误判成「漂移」

**状态** closed · 2026-08-05 · `TYPE-04`

> **已关闭 · 2026-08-05 · `TYPE-04`**（本卡拥有 `tools/check_fe_be_parity.py`，
> 两张单一并修——它们是同一段代码上的两处病）。
>
> **改法**：`_frontend_field_names`（只读 `types.ts`、返回平集）→
> `_frontend_interfaces`（扫 `web/lib/**` 的非测试文件，**按接口分组**，
> 键是 `"文件名#接口名"`）；`_field_findings` 改用 `_best_interface` 判：
>
> 1. **至少两个字段重合**才算「这个接口是为它建的」——一个同名字段的巧合不算；
> 2. 覆盖面按**层**算：**整个接口都落在这条响应里**，它才是这条响应的一层
>    （后端 `response_keys` 是摊平的，`/plaza/hot` 那 21 键分布在四层上）；
> 3. 报「漂移」时**指名是哪个接口**（`前端在 types.ts#ComboSubmitEcho 里…`）。
>
> **结果**：`field_mismatch` 6 → **0**，`frontend_untyped_response` **真归零**
> （`TYPE-02` 那次的零是误分类得来的）。修好之后新看得见四条真缺口，已补齐类型：
> `/projects/combo` 的 `hypothesis`、`/projects/{}/report`、`/projects/{}/proposal`、
> `/projects/{}/disputes`。
>
> 阴性对照见 `tests/v041/test_parity_dynamic_path.py`——
> 每一条「现在归零了」旁边都有一条「这样必须重新报出来」。
>
> 以下为关闭前的原文，一字未改。

---

**发现者** worker / `TYPE-01` 执行中 · **发现时间** 2026-08-05
**危害** 中 —— 报告把**两类要人做不同事的问题**混成一类
**为什么停下**：修它要改 `tools/check_fe_be_parity.py::_field_findings`，
而 `TYPE-01` 的 outputs 是 `web/lib/` 与一个测试文件。按工单 §五.1 登记。
**天然归属**：`TYPE-04`（它拥有 `tools/check_fe_be_parity.py`）。

## 缺陷

`_field_findings` 这样取前端字段面：

```python
declared = _frontend_field_names(repo / "web" / "lib" / "types.ts")
```

——**整个文件的字段名合成一个平集**。然后对每条端点：

```python
overlap = declared & keys
if not overlap:  →  frontend_untyped_response（没建类型，要去新建）
else:            →  field_mismatch（漂移了，要去对齐）
```

于是**只要 `types.ts` 里任何一个接口碰巧有一个同名字段**，
这条端点就被判成「建了类型」。

## 实测：本卡两次撞上

**撞上一（本卡开工时）**：`/deliverables/{}` 被判成「漂移，前端已声明
`deliverable_id`, `type`」。真相是**前端从没为它建过类型**——那两个名字来自
`Block` 接口（`block_id` / `deliverable_id` / `section_id` / `type` / …）。

**撞上二（本卡改完之后）**：新建的 `DeliverableMeta` 带 `ledger_version`，
于是 `/projects/{}/disputes` 与 `/projects/{}/evidence` **立刻变成「漂移」**，
理由是「前端已声明 `ledger_version`」——而那个字段属于交付物元信息，
与争议、证据毫无关系。

**这一改把误报从一条变成了两条。** 不是我改坏了什么，
是这把尺子的判别方式本来就会随 `types.ts` 变大而越来越容易误判。

## 决定性证据：`TYPE-02` 之后这一类**整个消失了**

`TYPE-02` 往 `types.ts` 补了几组**正当的**类型（`/plaza/hot` 的 15 个字段等）。
补完之后：

```
frontend_untyped_response  →  0 条
field_mismatch             →  6 条
```

**不是类型建齐了**——是每条端点都碰上了至少一个同名字段，于是全被归进「漂移」。
`tests/v041/test_fe_be_parity.py::test_a_drift_and_an_untyped_response_are_two_different_findings`
当场变红（它原先要求真仓库两类都有）。

这条规律很难看：**`types.ts` 越大，「没建类型」这一类越报不出来**。
也就是说这把尺子会随着项目变好而变瞎。

`TYPE-02` 的 acceptance③ 写的是「`frontend_untyped_response` 计数归零」——
**它今天确实是零，但归零的原因完全不对**。
拿这个零当验收通过，就是把一次误分类当成一次完工。

## 为什么这两类不能混

| 分类 | 要人做什么 |
|---|---|
| `frontend_untyped_response` | **新建**一个接口 |
| `field_mismatch` | 在**已有**接口里补字段 |

读表的人按「漂移」去找那个接口，会发现根本不存在——
然后开始怀疑是尺子坏了。**误伤会让人不再看这把尺子**
（`BL-09` 那把尺的原话）。

## 修法

`_field_findings` 按**接口**分组，而不是全文件平集：

1. 把 `types.ts` 解析成 `{接口名: {字段名}}`；
2. 对一条端点，先找**哪个接口最像它**（字段重合度最高，且重合数 ≥2 或
   ≥ 后端键数的一半）——找不到就是 `frontend_untyped_response`；
3. 找到了才比字段差集，报 `field_mismatch` **并指出是哪个接口**
   （现在的报告连接口名都不给，定位活全退回给人）。

第 3 步那句「指出是哪个接口」本身就值一条判据。

## 现状与影响

- **`TYPE-01` 的 acceptance③ 已达成**：`/deliverables/{}` 不再出现在
  `field_mismatch` 或 `frontend_untyped_response` 里（实测）；
- **`TYPE-02` 会顺带解掉这两条的内容**：它要为包括
  `/projects/{}/disputes` · `/projects/{}/evidence` 在内的九条建真类型，
  建完之后差集自然消失。**但分类精度这个缺陷仍在**——
  下一个同名字段还会再触发一次；
- **`TYPE-02` 的 acceptance③ 要判 `frontend_untyped_response` 归零**。
  注意：**在本缺陷修好之前，那个计数会因为误判而偏低**
  （被错分到 `field_mismatch` 去了）。`TYPE-02` 收卡时 MUST 核对这一点。
