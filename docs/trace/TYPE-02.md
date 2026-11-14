# TYPE-02 · 九条端点的前端类型建齐

**卡** `docs/steward/tasks-v041-b3.json#TYPE-02` · **cycles 1** ·
**self_review = true** → §5 · **owner_review = false**
**依赖** `TYPE-01`（verified）

## 1. 装载清单

卡面 TYPE-02 · 对账表的 `frontend_untyped_response` / `field_mismatch` 两节 ·
`web/lib/` 七个 client 的接口声明面（正则抽取，未全文装载）·
`/plaza/hot` · `/topics/{}` · `/projects/{}/topics` 三条的**真 payload**（实打）·
`tools/check_fe_be_parity.py::_frontend_field_names`。约 12k tokens，预算 40k 以内。

## 2. 卡面前提与盘上事实不符

卡面说这九条「前端根本没建类型」。那是**对账器只读 `web/lib/types.ts`** 的结论，
而本仓的类型**跟着各自的 client 放**：`viewsClient.ts` 有 `PlazaCluster` /
`EvidenceCard` / `Verdict`，`topicClient.ts` 有 `Topic` / `ProjectTopics` /
`ComboResult`，`interventionClient.ts` 有 `DisputeInput` / `EvidenceResult`。
**这种组织没有问题**——类型放在用它的地方比全塞进一个大文件更好读。

按「全 `web/lib`」重新量一遍：

| 端点 | 只看 `types.ts` | 全 `web/lib` 实际仍缺 |
|---|---|---|
| `/projects/{}/topics` | 「没建类型」 | **0** |
| `/topics/{}` · `/jobs/{}/verdict` · `/clusters/{}/evidence-cards` | 「没建类型」 | 各 1（信封键） |
| `/projects/{}/disputes` · `/projects/{}/evidence` | 「漂移」 | 各 1（`current_version`） |
| `/projects/combo` · `/projects/{}/analysis` | 「没建类型」 | 各 2 |
| `/plaza/hot` | 「没建类型」 | **15** ← 真缺口 |

**九条里只有一条真的缺一大片。** 照卡面做会把正在被使用的类型再抄一遍，
两份定义从抄完那一刻起各走各的——而 TypeScript 不会告诉你它们已经不一样了。

登记：`docs/blocked/PARITY-ONLY-SCANS-TYPES-TS.md`（归 `TYPE-04`）。

## 3. 补了什么

只补真缺的，字段与类型逐条取自**真 payload**（`GET /plaza/hot?day=2026-07-04` 实打）：

- `HotnessComponents`（6）· `WeakSignalRow`（9）· `PlazaClusterRow`（8）·
  `PlazaHotResponse`（3）——`/plaza/hot` 那 15 个真缺口；
- 三个**信封类型**（`TopicResponse<T>` / `VerdictResponse<T>` /
  `EvidenceCardsResponse<T>`）——泛型化，元素形状仍用 client 里那份，**不重抄**；
- `CurrentVersioned`（乐观锁那个字段）· `AnalysisSubmitEcho` · `ComboSubmitEcho`。

两处口径写进了类型注释：`day` 是 `string` 而非 `Date`（换成 `Date` 会诱使前端
按本地时区解析，跨时区差一天，而屏上说的是「这一天的热点」）；
`HotnessComponents` 判**等值**六个字段，**NEVER 造一个综合分**
（后端已经给了 `hotness`，前端再合成一个，两个数会各走各的）。

## 4. acceptance③ 是个陷阱：那个零**归得不对**

补完之后实测：

```
frontend_untyped_response  →  0 条      ← 卡面要的「归零」
field_mismatch             →  6 条
```

**不是类型建齐了**——是每条端点都碰上了至少一个同名字段，于是全被归进「漂移」。
`test_a_drift_and_an_untyped_response_are_two_different_findings` 当场变红
（它原先要求真仓库两类都有）。

规律很难看：**`types.ts` 越大，「没建类型」这一类越报不出来**——
这把尺子会随着项目变好而变瞎。
**拿这个零当验收通过，就是把一次误分类当成一次完工。**

所以判据判的是**两类之和 == 6**，并单独断言 `untyped` 为空**且原因已登记**。
这条决定性证据已补进
`docs/blocked/PARITY-FIELD-NAMES-COMPARED-AS-ONE-FLAT-SET.md`。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_types_complete.py -q → 8 passed（0 skipped）
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3737 passed（TYPE-01 收卡时 3729，本卡 +8）
            cd web && npm test -- --run → 74 files / 750 passed
            cd web && npx tsc --noEmit  → 只剩 2 条既有错，本卡零新增
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 九条建齐 | `test_every_field_the_nine_endpoints_return_has_a_typed_home`（**主判据**：九条的每个字段在 `web/lib` 里都有落点——比「`types.ts` 里有没有」严格，又不逼人重复定义）、`test_the_nine_are_exactly_the_ones_the_card_named` |
| ② 字段以真 payload 为准 | `test_the_plaza_types_match_the_real_payload`（真 `curl`，逐层校验信封/簇行/分量/弱信号）、`test_the_hotness_components_are_numbers_not_a_synthesized_score`、`test_the_day_is_the_one_the_backend_gave` |
| ③ `frontend_untyped_response` 归零并接成硬判据 | **归零了，但原因不对**（§4）。`test_the_untyped_count_is_pinned_until_the_ruler_is_fixed` 判两类之和 == 6 且 untyped 为空；`test_the_ticket_shows_the_measurement_that_contradicts_the_card` |
| （自加） | `test_no_type_was_copied_from_a_client_into_types_ts`——**NEVER 重抄**：`types.ts` 里不许出现 client 已有的接口名 |

**② 改既有文件两处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `web/lib/types.ts` | 新增 9 个接口（见 §3） | **卡上 outputs**，本卡主体 |
| `tests/v041/test_fe_be_parity.py` | `test_a_drift_and_an_untyped_response_are_two_different_findings` 从「真仓库两类都有」→「`field_mismatch` 有、`frontend_untyped_response` 恒为零且原因已登记」 | 本卡的正当改动让那一类整个消失，旧判据**恒红**。改判等值后，尺子修好那天它会红并指回两张单 |

另**重生成** `docs/前后端对账表-v041.md`。

**③ 变异考 4 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 少补一个热度分量 | 红 |
| ② 在分量里造一个综合分 | 红 |
| ③ `day` 改成 `Date` | 红 |
| ④ 重抄一份 client 已有的接口 | 红 |
| ⑤ 假变异对照：只改一句注释 | 全绿 |

**另一处判据自己写坏过**：`test_the_hotness_components_...` 第一版用字符窗口
切源码判「本接口里没有 score」，扫到了下一个接口的 `weak_score` 当场假红。
改成在**接口内**判字段名。窗口开大一点就假红的东西不是判据，是巧合。

**④** 装载约 12k tokens；**⑤** 禁用词六词 0 命中。

## 6. 登记未做

1. **两张尺子单**（只读一个文件 / 平集比对）归 `TYPE-04`，**建议一并修**——
   它们是同一段代码的两处病，分开修第二次还要再读一遍那段逻辑。
2. **新建的九个接口还没有调用点**：`types.ts` 里的类型要被 client 用起来
   （比如 `viewsClient.fetchPlazaHot` 的返回值换成 `PlazaHotResponse`），
   那要改 client 文件——**不在本卡 outputs**。属接线，不属对齐。
3. **`/plaza/hot` 的 `by_source: Record<string, number>`**：键是源名，
   后端可能新增源。这是**有意留成开放映射**的，不是漏了枚举——
   写死枚举会在加源那天让前端整块解析失败。
