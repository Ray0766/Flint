# DEMO-REPORT-REFS-NOT-SEEDED · demo 报告的正文引用了七个从未入库的实体

**状态** closed · 2026-08-05 · `FIX-02`

**发现者** worker / FB-09 接线后的真页面取证 · **发现时间** 2026-08-04
**危害** 中 —— demo 报告屏是给人看的第一屏，现在整屏的引用都显示「接口未提供」
**改动面** 要么补种数据、要么改 demo fixture 的 block 内容；两者都在本卡 outputs 之外

## 现象

FB-09 把六类 id 接上解引用端点之后，真页面（`/deliverables/del-demo-fixture-report`）
**每一处引用都显示「接口未提供 + 原 id」**：

```
向量库托管  接口未提供 fact-demo-vecdb-cost   接口未提供 pe-demo-vecdb-2026
推理算力    接口未提供 fact-demo-infer-cost   接口未提供 pe-demo-gpu-2026
            接口未提供 chart-demo-cost-trend
接口未提供 qc-demo-fixture-01
1. 接口未提供 cit-demo-arxiv-2506-06962
2. 接口未提供 cit-demo-gh-lightrag
接口未提供 sec-04-gap-hints
```

**这是正确行为**（FB-09 acceptance②：端点不可用时如实标注并显示原 id，
NEVER 空白、NEVER 编造），但它暴露的是数据侧的问题。

## 根因（逐条查库）

`demo` 库里：

| 引用 | 实况 |
|---|---|
| `fact-demo-vecdb-cost` / `fact-demo-infer-cost` | **`facts` 表是空的** |
| `cit-demo-arxiv-2506-06962` / `cit-demo-gh-lightrag` | `citations` 里只有 `cit-gate1-…` 这类**别的 id** |
| `pe-demo-vecdb-2026` / `pe-demo-gpu-2026` | `pricebook` 里查不到 |
| `chart-demo-cost-trend` | 全仓**没有任何 ChartSpec**（FB-07 §3 已登记） |
| `qc-demo-fixture-01` | `QualityCard` **全仓无存储面**（FB-08 §8-1 已登记） |
| `sec-04-gap-hints` | `gap_hints` / `section_states` **两张表都不存在**（FB-08 已登记） |

**demo 报告的 Block 树是单独种下的，而它引用的实体没有跟着种。**
在 FB-09 之前这件事看不出来——那时屏上直接显示 id 本身，看起来「有东西」。

## 端点本身是好的（已排除）

- 挂载生效：`GET /facts/x` 回 `{"code":"NOT_FOUND","message":"no such fact"}`，
  而未注册的路由回 FastAPI 默认的 `{"detail":"Not Found"}`——两者可区分，确认路由在；
- 六条路由与前端拼的六条路径逐条对上（`test_every_mounted_path_matches_what_the_client_asks_for`）；
- 端点在 `flint_test` 库里用真数据跑通（FB-04~08 各自的 compose 测试共 63 条全绿）。

## 需要 owner / 下一张卡做什么

三选一（我倾向第 1 条）：

1. **给 demo 补种被引用的实体**——facts / citations / pricebook 三张表按 block 内容补齐；
   chart 与 quality_card 要先有存储面（FB-07/FB-08 已各自登记），可先只补前三类；
2. **改 demo fixture 的 block 内容**，只引用真存在的 id（改的是演示数据，不是产品）；
3. 维持现状——**但那意味着 demo 报告屏整屏「接口未提供」**，第一次看它的人会以为产品坏了。

## 绕行现状

- 前端行为正确且有测试守着（`web/components/deref/DerefValue.test.tsx` 的三条：
  不空白、不编造、原 id 可见）；
- `harness/fe_smoke.py` 会把这一屏的 8 条控制台 error 报出来（那是浏览器在报 404），
  所以这件事**不会悄悄消失**：数据补齐之前，冒烟对这一屏恒非零。

## 关闭（FIX-02 · 2026-08-05）

`harness/demo_seed_report.py` 现在连正文引用的实体一起种，走生产 store：
`PgProjectStore` / `PgLedgerStore.derive` / `PgDocStore` / `seed_pricebook_on`。
**九条里六条**在装配后的真栈上逐条解得开（判据 `tests/v041/test_demo_refs_seeded.py`
全程走 `create_app(dsn)` + HTTP，NEVER 断言脚本里有那几行 INSERT）：

| 引用 | 现况 |
|---|---|
| `fact-demo-vecdb-cost` / `fact-demo-infer-cost` | 200 · 记账口径 + 数值 + 单位 + 出处（`origin="injected"`，NEVER 冒充 promoted） |
| `pe-demo-vecdb-2026` / `pe-demo-gpu-2026` | 200 · `source` 自报「夹具数据…NEVER 当作真实报价」 |
| `cit-demo-arxiv-2506-06962` | 200 · 公开文献 + 钉住段落 |
| `cit-demo-gh-lightrag` | 200 · **失锚态**照实标记（不编一句 README 原文来填满） |
| `chart-demo-cost-trend` · `qc-demo-fixture-01` · `sec-04-gap-hints` | 照旧 404 —— **没有存储面**，转 `docs/blocked/DEMO-REFS-NO-STORAGE-FACE.md` |

上面「三选一」里选的是第 1 条。第 3 条（维持现状）不再成立：
剩下那三条 404 不是「整屏接口未提供」，而是 FB-09 诚实态在这一屏上的**活样本**——
六条换成人话、三条如实标注并显示原 id，这一屏现在同时展示了两种状态。
