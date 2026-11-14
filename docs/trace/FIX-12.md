# FIX-12 · 后端 NEVER 把枚举原值拼进给人看的句子

> v0.4.1 第 6 批第十三张。全量 `pytest -q` **4488 passed / 0 failed**。

## 装载清单

`tasks-v041-b6.json#FIX-12` · `docs/blocked/BACKEND-PROSE-EMBEDS-RAW-ENUM.md` ·
`flint/gate/rule_d.py` · `flint/jobs/gate1.py`（序列化那一段）·
`contracts/models.py#GapHint`（冻结件字段面）·
`flint/competitor/coverage.py#CoverageReason` · `web/lib/i18n/enumLabel.ts`（DS-03 标签表）·
`tests/m2/test_m2_037.py`（既有判据）。约 12k tokens，**未超 40k**。

## 一、屏上那句话与它的机械根因

```
竞品扫描覆盖未达标（not_saturated）（search）
```

`not_saturated` 是 `CoverageReason` 的机器值，拼这句话的是**后端**
（`flint/gate/rule_d.py:44` 的 `missing_what` f-string）。两处坏：

1. **前端换不掉**。`DS-03` 的标签表里 `coverage` 一族五个值全在，却派不上用场；
2. **两边话术各自漂移**。后端改一个词，标签表不会跟着改，
   而屏上同一个概念会出现两种说法。

## 二、`GapHint` 是冻结件，所以结构化那一半加在序列化层

冻结件字段面是 `missing_what / cause / suggested_sources / action /
target_count / required_scope`——**加字段是 `S2-1` 禁止的**。

改法：`rule_d.derive_gaps` 回 `DerivedGap`（冻结件那一份原样装在 `hint` 里，
`reason_code` 与 `params` 并排放），而 `flint/jobs/gate1.py` 拼的那个 dict
**不是冻结件**，两半在那里一起发出去。

```
missing_what = "竞品扫描覆盖未达标"          ← 人话，零机器值
reason_code  = "not_saturated"               ← 前端按 DS-03 标签表说人话
params       = {"pending_queries": [...]}
```

**原因码没被丢掉，它换了个位置。** 只把括号里那截删掉的话，屏上确实干净了，
而「为什么没达标」这个信息没了——**那比印一个机器值更坏**：
用户从此不知道该去补什么。判据里有一条专门盯这件事。

**没有原因码的缺口 `reason_code` 恒 `None`，NEVER 编一个**：
编出来的码不在标签表里，前端只能原样印出来，绕一圈回到改前的样子。
`unknown_competitor_gap`（别的模块回的冻结件）就是这么处理的。

## 三、判定语义一字不动（acceptance④）

`decide()` 吃的仍是 `[d.hint for d in gaps]`。判据逐条比对派生出的
`(cause, action)` 序列——**那才是判定语义**，改前改后必须逐字相同。

## 四、同一个毛病的第二处：`card_gap_annotations`

它的 docstring 逐字写着「E6 row 1 **user-facing copy**」，
而它拼的是 `f"今日缺 {源} 数据（{n.reason}）"`——
`rate_limited` / `parse_drift` / `fetch_failed` 会原样上屏。

**本卡一并修**：acceptance③ 要「新增拼接会被拦住」，
而**拦得住新的却留着旧的，那条判据从第一天起就是绿的谎**。

## 五、留下来的那把尺子，以及它开工后收窄的一次

`test_no_module_interpolates_an_enum_into_chinese_prose` 扫全 `flint/`：
中文句子里 NEVER 插一个枚举字段。

第一版扫出第三处：`flint/design/graph_stale.py:60`
「未知图谱变更类型 {kind!r}：NEVER 当成…」。**那一条报得不对**——
它是 `raise` 的消息，**异常是给我们自己看的**，把出问题的那个值印出来
正是它该做的事，否则收到报错的人不知道是哪一个值出的问题。

所以口径收窄了一格：**「中文」不足以分开「给人看的」与「给我们自己看的」，
「是不是 `raise` 的实参」才是**。收窄写进了那个 helper 的 docstring，
并加了第三条阴性对照（异常消息必须不报）。

**窄不是放水**：它换来的是零误报，而一把会误报的尺子迟早被人加白名单绕过。

## 六、动了两份既有判据（取值路径变了，期望值没变）

`tests/m2/test_m2_037.py`（9 条）与 `tests/m2/test_m2_050.py`：
`g.cause` → `g.hint.cause` 之类。**判据的意图与期望值一个都没改**，
变的只是取冻结件那一份的路径。改因写在文件头。

## 七、verify

```
pytest tests/v041/test_no_raw_enum_in_prose.py -q → 10 passed
pytest tests/m2 -q                                 → 308 passed
pytest -q（全量）                                   → **4488 passed / 0 failed**
ruff / mypy --strict flint                          → 全绿 / 306 files
python tools/check_line_endings.py                  → 220 个文件全是 LF
```

## 八、self_review

① 判据覆盖 acceptance 五条，含**三条阴性对照**（原因码没被丢掉 /
注入一条拼接必须抓到 / 异常消息与干净写法必须不报）与一条「判定语义未动」；
② 零冻结件改动——本卡反而是**因为**冻结件不能动才把结构化那半放到序列化层；
③ 无禁用词；④ 改动面：`flint/gate/rule_d.py` · `flint/jobs/gate1.py` ·
`flint/sources/degradation.py` + 判据 + 两份既有判据的取值路径，
**全在卡上 outputs**（`flint/` · 测试）；⑤ 装载 ≈12k tokens。

## 九、留给下游

- 前端接 `reason_code` 是**另一张卡**（本卡 outputs 没有 `web/`）：
  `GateView` 现在显示的是干净人话，接上标签表之后会显示得更具体
  （「还有待跑的检索」而不是「未达标」）；
- 那把尺子从此拦着新的拼接。**要加一个枚举字段名**（比如某天出现 `severity`），
  在 `enum_fields` 里加一行即可。
