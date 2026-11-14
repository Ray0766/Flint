# v0.4.1 第 4 批 · 完成态报告

**产出者** worker / `SHIP-04` · **日期** 2026-08-06
**范围** `docs/steward/tasks-v041-b4.json` 全 20 张卡
**结论** **20/20 verified**，出口判据两个数**真达标**（各 0），全局门五条全绿。

---

## 一、全局门五条（逐字贴出，acceptance①）

```
$ ruff check . --no-cache
All checks passed!

$ mypy --strict flint
Success: no issues found in 301 source files

$ pytest -q
4088 passed, 12 warnings in 314.53s (0:05:14)

$ cd web && npm test -- --run
 Test Files  74 passed (74)
      Tests  754 passed (754)

$ npx tsc --noEmit
（无输出）
```

**第 3 批收卡时 pytest 是 3970**，本批 +118。前端 754（本批 +2）。

---

## 二、出口判据（acceptance②）

```
$ python tools/check_fe_be_parity.py --json
  frontend_missing_endpoint          0
  backend_not_assembled              0     ← 出口判据①
  frontend_untyped_response          0     ← 出口判据②
  dynamic_path_not_checked           0
  app_unbuildable                    0
  backend_unused_by_frontend        35     ← 不是判据，GAUGE-11 逐条分诊了
  field_drift                        0
```

**两个数都真达标，不是把一半写成达标。**

`backend_not_assembled` 从 `WIRE-01` 时的 10 条（四族）归零，
经 `WIRE-07`→`WIRE-10` 一族一族接通、`WIRE-11` 把判据收口。
`app_unbuildable == 0` 一并贴出：**它是 0 才说明上面那个 0 是量出来的**——
应用建不起来时对账器同样报不出未装配，两种 0 在报告上长得一模一样。

`backend_unused_by_frontend` 那 35 条**不是判据**，且 `GAUGE-11` 查明
**其中 12 条前端其实在调**（尺子的两个盲区）——详见 `docs/端点分诊-v041.md`。

---

## 三、20 张卡（Σ27 cycles）

| 卡 | cycles | 做了什么 |
|---|---|---|
| `AUTH-01` | 1 | `0020_identity` 迁移：users / orgs / memberships 三张表 |
| `AUTH-02` | 2 | 真 `role_resolver`（查 memberships），**NEVER `lambda: "owner"`** |
| `AUTH-03` | 1 | `X-User-Id` 身份入口；401/401/403 三种出口分开 |
| `AUTH-04` | 2 | 权限矩阵逐格判；viewer 读 jobs 的口径提 owner |
| `AUTH-05` | 1 | demo 三只假手退役，改注真身份 |
| `WIRE-07` | 1 | analysis 族接进 `create_app` |
| `WIRE-08` | 1 | compose 族接线 + **补上它压根没有的权限检查** |
| `WIRE-09` | 2 | interventions 族接线；aligner 恒回放 |
| `WIRE-10` | 2 | combo 族接线；模型地址进配置（不设=没配，NEVER 编默认） |
| `WIRE-11` | 1 | `UNWIRED_FAMILIES` 清空，判据回到真归零 + 阴性对照 |
| `WIRE-12` | 2 | 假空态：没有存储面的族回 `not_provided`，NEVER 空表 |
| `ROUTE-01` | 1 | `/render` 路由归属；三与门搬进赢家，NEVER 靠挂载顺序 |
| `CHAIN-01` | 2 | gate1 收尾落 claims 行（`analysis-{job}` 产物 id） |
| `CHAIN-02` | 1 | 端到端删掉人手种 claim——**主链路成一条** |
| `FIX-04` | 1 | 间歇红定位到根因（两拍竞态），40 次循环第 29 次复现 |
| `FIX-05` | 1 | 390px 横向溢出：`.app-shell__body` 少个 `border-box` |
| `FIX-06` | 2 | 移动视口进常规取证；16 屏 ×2 主题 ×2 视口 = 64 行 |
| `GAUGE-10` | 1 | 第二把尺子补剥注释（保住行号 + 引号状态机） |
| `GAUGE-11` | 2 | 35 条端点四类分诊，12 条查明是尺子盲区 |
| `SHIP-04` | 1 | 本报告 |

---

## 四、本批关掉的单（8 张）

| 单 | 关它的卡 | 一句话 |
|---|---|---|
| `WIRE-01-FOUR-FAMILIES-NEED-AUTH-AND-PROVIDER` | `WIRE-11` | 四族十条路由全接通 |
| `WIRE-03-EMPTY-FROM-A-STORE-THAT-HAS-NO-DATABASE` | `WIRE-12` | 假空态改成 `not_provided` 姿态 |
| `RENDER-ROUTE-CLAIMED-BY-TWO-MODULES` | `ROUTE-01` | 冲突真解掉，登记面清空 |
| `GATE1-VERDICT-IS-NOT-A-COMPOSE-SOURCE` | `CHAIN-01`+`CHAIN-02` | 那一跳接上了 |
| `UI07-LOCALE-TEST-IS-FLAKY` | `FIX-04` | 根因不是单子猜的 stubGlobal |
| `LOCALE-FORM-OVERFLOWS-ON-MOBILE` | `FIX-05` | 根因不是单子猜的表单行 |
| `SCANNERS-DO-NOT-STRIP-COMMENTS` | `GAUGE-10` | 扫描器不在单子猜的那个文件里 |
| （另有 `AUTH` 段关掉的） | — | 见各卡 trace |

**三张单猜错了根因**（`UI07` / `LOCALE-FORM` / `SCANNERS`），三处都在关闭段里
**写下了「猜错在哪」**——只写「已修复」的话，下一个人还会照那句猜想去改别处。

---

## 五、未解决的，逐条列名（acceptance④）

**NEVER 用一句「其余无异常」收口。** 盘上现存 8 张 open 单：

| 单 | 归属 | 卡在谁那里 |
|---|---|---|
| `PARITY-BLIND-TO-PAGES-AND-UNLISTED-PREFIXES` | **本批新开**（`GAUGE-11`） | 对账器两个盲区（首段白名单 / 只扫 `web/lib/`）。改工具超出该卡 outputs |
| `UI-DESIGN-SCREEN-NEEDS-A-FOURTH-STATE` | **本批新开**（`WIRE-12`） | 设计屏要显示的「没有存储面」是第四态，组件只有三态。加它要改组件契约 |
| `ONE-UNNAMED-FRONTEND-RED-NOT-CAPTURED` | **本批新开**（`FIX-05`） | 观测到一次前端红、**名字没抓到**（我的操作失误）。之后连跑 16 次全绿 |
| `DEMO-REFS-NO-STORAGE-FACE` | 第 3 批 | chart / 质量卡 / gap hints 全库没有存储面。**当前 404 是正确行为**，建不建面由 owner 定 |
| `E2E-REALSOURCE` | 早批 | 真实源端到端，属红线（首次授权）范畴 |
| `K1-02-SOURCE-CONTRACTS-MISSING` | 早批 | 源契约 |
| `K2-COMPLIANCE-BEFORE-LAUNCH` | 早批 | 上线前合规 |
| `LINEAGE-GOLD-REPLAY-MISSING` | 早批 | 血缘金标回放 |

### owner 要裁的三件（各卡 trace 里已写清三选一）

1. **队列路径不钉引用**（`CHAIN-01` §6）：`pin_verdict_citations` 只在
   `gate1.main()` 跑，队列 worker 不跑 → 那批 claim 全是 `speculative`，
   账本里 **0 条 Fact**。已被 `test_the_chain_carries_conclusions_but_not_yet_citations`
   钉成等值判据，接上那天它会红。
2. **`viewer` 读不了 jobs**（`AUTH-04`）。
3. **`fmt=pack_markdown` 要不要加**（`ROUTE-01` §6）：单文件 CLAUDE.md 预览
   随路由归属一起没了，内容仍可读（`/pack` 逐章），但那条路不过导出门。

### 另外两处小的

- `FLINT_EMBED_MODEL` 目前没人读（`WIRE-10` §6）；
- `PackApiDeps.dsn` 现在没人读（`ROUTE-01` §6）。

---

## 六、这一批反复撞到的三件事

**一 · 说明问题的那句话被当成犯下问题（7 次）**
`AUTH-02` / `AUTH-05` / `WIRE-09` / `WIRE-10` / `WIRE-12` / `FIX-05` / `GAUGE-11`。
docstring 里引用一个反例、CSS 注释里写一条算式、Markdown 里写一句 `json.loads(...)`——
都被扫描器判成违规。**修法一律是走 `ast` 或整块剥注释，NEVER 按行 split。**
`GAUGE-10` 把这件事本身做成了一张卡。

**二 · 「变异没造成功」与「判据不咬」在返回码上一模一样（3 次）**
`WIRE-12` / `ROUTE-01` / `GAUGE-10`。改成**先比对文本是否真的变了**、
再核对红的**理由**，才分得出这两类。`GAUGE-10` 里还有两条变异是真活下来的——
那是判据的洞，补完才咬住。

**三 · 判据读到别人留下的状态（2 次）**
`AUTH-05`（上一轮的 membership 行）、`CHAIN-01`（变异器插的假交付物没清）。
**变异器留下的写操作要与判据的清理面对齐。**

---

## 七、主链路现在是一条

```
提交分析 → 队列 → gate1 → 判定落 snapshots + claims（analysis-{job}）
                                          ↓
提交报告（analysis_id = 那次判定的产物 id）→ 队列 → 组稿 → 渲染 → 导出门
```

端到端 `tests/v041/test_e2e_full_stack.py` 9 条全绿，**零真实出网**
（`respx` 护栏 `went_out == []`），且**没有任何人手种的 claim**。
