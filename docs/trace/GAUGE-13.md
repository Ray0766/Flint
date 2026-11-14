# GAUGE-13 · 尺子⑦：蓝本 P 编号 ↔ 实仓路由双向对账

> v0.4.1 第 5 批第十五张。依赖 `CHAIN-05`（verified）。

## 装载清单

`tasks-v041-b5.json#GAUGE-13` · 蓝本 `design_handoff_flint_web/README.md` 的路由表 ·
`docs/前端功能说明-v2.md` 的 18 条屏总表 · `web/app/**/page.tsx` ·
`harness/fe_smoke.py` 的路由发现口径。约 8k tokens，**未超 40k**。

## 一、为什么要**双向**

- 只查「蓝本有而实仓没有」→ 实仓多出来的屏没人管，蓝本会慢慢过期；
- 只查「实仓有而蓝本没有」→ **缺屏永远发现不了**。

而本批开工时就缺六屏（P3/P4/P5/P6/P10/P11）——**用户当时从广场走不到报告**。

## 二、蓝本与实仓的路径本来就不一样

蓝本写 `/combo/new`、`/plaza/hot`、`/deliverables/[id]/edit`；
实仓是 `/combo`、`/plaza`、`/deliverables/[id]/interventions`。
**这不是错，是两套命名习惯**——蓝本 README 自己就写着
「仓库路由习惯亦可用 `/gate/[jobId]`」。

所以对账用一张**显式映射**（`ALIASES`），逐条带理由。
判据反向盯着源码里 NEVER 出现 `startswith` / `difflib` / `SequenceMatcher`：
模糊匹配会在某天把两个不同的屏认成同一个，**而那时缺屏会静静地消失在报告里**。

## 三、四份名单，各自带理由

| 名单 | 管什么 |
|---|---|
| `ALIASES` | 蓝本路径 → 实仓路由 |
| `V2_SCREENS` | 蓝本没登记、由 `docs/前端功能说明-v2.md` 的 18 条认领的九屏 |
| `DELIBERATELY_ABSENT` | 蓝本列了而**有意不做**的（P2 工作台 → 实仓做成了图谱工作台） |
| `KNOWN_ENDPOINT_GAPS` | 蓝本写了端点而实仓那屏还没接的（`/plaza` 的 `/categories` 大类筛选条） |

判据 `test_every_exemption_carries_its_reason` 逐条要求理由 >10 字——
**没有理由的豁免与「忘了做」长得一模一样**。

## 四、两处实现细节（都是被自己的红逼出来的）

**① 端点对照要跟两层 import。** 取数常常是 page → `useXxx` 钩子 → `xxxClient`。
只跟一层会把 `/jobs/[id]` 报成「没提到 `/jobs`」——而它当然提到了，
只是那句话在第二层里。**三层就开始把无关文件也拖进来**，那时「提到了」不再说明这屏在用它。

**② 蓝本表解析要钉住条数。** 那张表哪天换了格式，解析会静静地回空表——
**而空表下缺屏恒为 0**。所以判据钉住「解析得到 14 条」。

## 五、当前实况（本卡的出口判据）

```
python tools/check_screen_coverage.py
→ 屏对照：蓝本 14 条 / 实仓 22 屏；缺屏 0 · 蓝本未登记 1 · 端点对不上 0

两边都没登记的那 1 条是 /demo（演示串屏，不是产品屏——它不进两份表是对的）
```

**开工时缺的六屏名单已清空**，且判据**逐条点名**验（不是只看总数为 0：
只看总数的话，将来有人删掉一屏又加一屏，总数不变而那六屏里少了一个）。

`docs/屏对照表-v041.md` 是给人看的那一份，判据钉着它与脚本 NEVER 说两样话。

## 六、阴性对照三条

1. 蓝本多一条没有屏的 → 报 `missing`（acceptance③ 的「新增蓝本条目而没有屏则判红」）；
2. 实仓少一屏（拿掉 `/combo`）→ 报 `missing`（**acceptance② 的「NEVER 回潮」那一半**）；
3. 实仓多一屏而两份表都没登记 → 报 `extra`。

## 七、verify

```
pytest tests/v041/test_screen_coverage.py -q → 14 passed
pytest tests/v041 -q                         → 2458 passed / **1 failed**
                                               （只剩那条 SSE 403，已立单，非本批）
ruff check . --no-cache                      → All checks passed
python tools/check_line_endings.py           → 219 个文件全是 LF
```

返工两轮：`extra` 首版把九屏 v2 新屏全报成「蓝本没登记」（**报得对但没用**——
它们在 v2 那份表里，只是那份表不写路径），补 `V2_SCREENS` 映射；
端点对照跟一层不够（见 4.①）。

## 八、self_review（worker.md §4.6）

① **测试覆盖 acceptance**：14 条对四条 acceptance；三条阴性对照证明尺子认得出
新缺口、屏被删、屏没人登记——**没有它们，「缺屏 0」说明不了任何事**；
另有一条钉住蓝本表的解析条数（空表下缺屏恒为 0 是最坏的绿）。
② **无冻结件偏离**：`contracts/` 一字未动。
③ **无禁用词**：grep 零命中。
④ **复用断言在位**：路由发现口径与 `harness/fe_smoke.py` 一致；
四份名单逐条带理由（与本仓既有的噪声基线是同一套办法）。
⑤ **装载未超预算**：≈8k tokens。

## 九、留给下游

- 新屏进来时有**两道绊线**：`harness/fe_smoke.py` 的 `SAMPLE_IDS`（取证）与
  这把尺子的两份表（登记）。两道都不过，屏就进不来；
- `/plaza` 的大类筛选条（`GET /categories`）已登记为端点缺口，
  它跟着地区筛选一起来（`PLAZA-02` 那张单）。
