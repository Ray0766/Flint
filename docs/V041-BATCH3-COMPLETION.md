# v0.4.1 第 3 批 · 完成态报告

**收在** 2026-08-05 · **进度** 24 / 25 verified，1 张 `blocked`（`SHIP-03` 自己）
**机读真相** `docs/progress-v041.jsonl`（三批共用一本）· `docs/steward/tasks-v041-b3.json`

> **一句话**：25 张卡里 24 张收了；最后一张（本报告）**记 blocked**，
> 因为 `DEC-031` 定的出口判据「`backend_not_assembled` 归零」要么等鉴权，
> 要么用一句 `lambda: "owner"` 换绿——**后者是安全洞，NEVER 走**。详见 §3。

---

## 1. 收在哪儿：25 张逐张

| 卡 | 事 | 状态 |
|---|---|---|
| `WIRE-01` | `flint/api/app.py` 从 22 行变成全族装配器；逐条探活，不认「include_router 存在」 | verified |
| `WIRE-02` | demo 栈改用装配后的 app；修掉报告屏恒 500（`FLINT_API_BASE` 没设） | verified |
| `WIRE-03` | 前端五态 `Fetched<T>`：loading / ready / not_provided / not_configured / failed | verified |
| `WIRE-04` | 九屏接真取数；补 `toProjectOverviewView` | verified |
| `WIRE-05` | 主链路四屏接线 | verified |
| `WIRE-06` | SSE 断线态与重连 | verified |
| `TYPE-01` / `TYPE-03` / `TYPE-04` | 前端响应类型化；`constraints_checked` 三态；对账器按**层**比字段 | verified |
| `UIX-01` / `UIX-02` / `UIX-03` | S1 通用件三件；SSE 断线提示；状态标记 | verified |
| `GAUGE-07` | 地区口径尺加宽到九区 | verified |
| `GAUGE-08` | 行尾尺（CRLF 让 JS 剥刀失效） | verified |
| `GAUGE-09` | 第 2 批 89 卡 / 363 条 acceptance 专项清点 | verified |
| `FIX-01` | `"" in "%％"` 恒真——正文末尾每个数字都被误判 | verified |
| `FIX-02` | demo 报告正文引用的九个实体补种六个，三个没有存储面 | verified |
| `FIX-03` | `?raw` 导入补类型声明；`tsc --noEmit` 接进 pytest | verified |
| `LOC-01` | 九区字面量副本退役，清单改从 `/settings/locale` 下发 | verified |
| `HYG-01` | 关三张陈旧单 + 34 张单据状态机读化 | verified |
| `HYG-02` | 38 张 `owner_review` 压成一页摘要 | verified |
| `QUEUE-01` | 经作业队列跑通 gate1（回放，非红线） | verified |
| `E2E-01` | 装配后的真栈 + 真队列跑完主链路 | verified |
| `NET-03` | 真实源冒烟 | `skipped_by_owner`（`DEC-033①`，第 2 批处置） |
| `SHIP-03` | 本报告 + 出口全局门 | **blocked**（§3） |

## 2. 出口全局门：五条命令的实跑输出

```
$ ruff check . --no-cache
All checks passed!

$ mypy --strict flint
Success: no issues found in 299 source files

$ python -m pytest -q
3905 passed, 12 warnings in 253.98s

$ cd web && npm test -- --run
 Test Files  74 passed (74)
      Tests  752 passed (752)

$ cd web && npx tsc --noEmit
（无输出，exit 0）
```

**五条全绿。** 本批 pytest 从第 2 批收卡时的 3830 增到 3905（+75）。

### 对账器与设计约束尺

```
$ python tools/check_fe_be_parity.py --json
backend_not_assembled:      10      ← **未达标**（判据要 0），见 §3
frontend_untyped_response:  0       ← 达标
backend_unused_by_frontend: 33      （不是判据，见 §5-2）

$ node tools/check_design_constraints.mjs
技术约束清单：11 条规则跑过 web，0 处违规。   exit 0
```

## 3. 出口判据没达标的那一条，卡在哪里

`DEC-031` 逐字：「`tools/check_fe_be_parity.py` 的 **`backend_not_assembled`
计数归零是出口判据**」。实测 **10 条**，逐条列名：

```
interventions.py  /interventions/lock · /projects/{}/evidence ·
                  /projects/{}/disputes · /deliverables/{}/sections/{}/regenerate
analysis.py       /projects/{}/analysis · /jobs/{} · /jobs/{}/events
compose.py        /projects/{}/report · /projects/{}/proposal
combo.py          /projects/combo
```

这 10 条**正是 `WIRE-01` 当时拒绝挂上的那四族**：它们全都要
`role_resolver`，而本仓**还没有 `users` / `memberships` 两张表**，
做不出一个诚实的角色解析。

归零只有两条路，**两条都不在第 3 批任何一张卡的 outputs 内**：

1. **补鉴权**：两张表 + 一个真 `role_resolver`，然后四族进 `create_app`。这是一批卡的量；
2. **`lambda _u, _o: "owner"` 挂上去**：计数当场归零，
   而**每一条写操作从此对任何调用者开放**。

`WIRE-01` 拒了第 2 条并开了单
（`docs/blocked/WIRE-01-FOUR-FAMILIES-NEED-AUTH-AND-PROVIDER.md`，本报告已在其中追记）。
**本批维持那次拒绝**：一个绿色的计数换不来一个没有鉴权的写接口。

所以 `SHIP-03` 记 `blocked` 而不是 `verified`——
**把出口判据的一半写成达标，才是这份报告最坏的写法。**

## 4. 本批发现（按「不修就会咬人」排）

1. **主链路在中间断成两段**（`E2E-01`）。gate1 的判定落 `snapshots`，
   组稿读 `claims WHERE deliverable_id=<analysis_id>`，而 gate1 **从不写 claims 行**。
   两段各自都是绿的，**中间那一跳没有任何判据横跨过**——今天只能人手种一条 claim。
   单：`docs/blocked/GATE1-VERDICT-IS-NOT-A-COMPOSE-SOURCE.md`；
2. **`"" in "%％"` 恒为真**（`FIX-01`）。正文以数字结尾时，年份被当成数量、
   非百分数多了一条 `value/100` 的「找得到」通路。**两条都是少查**，
   而少查在报告上与「查过了没问题」长得一模一样；
3. **demo 报告屏九条引用一条也解不开**（`FIX-02`）。补种六条；
   chart / 质量卡 / gap hints **没有存储面**——质量卡那条是唯一「塞一行就能变 200」的，
   **没塞**：`card_ref` 按冻结件指向 `QualityCard`（现算不落库），而端点服务的是
   `EvidenceCard`，塞了就是用一个看起来对的答案盖住一个类型不符；
4. **九区清单在前端还有一份字面量副本**（`LOC-01`）。退役之后，
   「九区完整、无 EU」那句断言从**抄件**搬到了**正本**（真栈上判冻结件）；
5. **`K1-02` 的「已关闭」说的是 reddit 的自助注册**（`HYG-01`）。
   按字符串搜「已关闭」数单子，会把它数成已解决——34 张单从此有一行机读状态；
6. **CRLF 让 JS 注释剥刀整个失效**（`GAUGE-08` 建尺、`LOC-01` 当场被抓）。
   我自己用 python 写盘时把三个 `web/` 文件的行尾翻成了 CRLF，
   **上一张卡刚建的尺子这一轮就抓到第一条真鱼**；
7. **`arq` 按 job id 去重**（`QUEUE-01`）。同一作业第二次提交**静默地什么都不做**，
   而那个「什么都没发生」与「链路断了」长得一模一样。

## 5. 未解决清单：逐条列名，卡在谁那里

| # | 事 | 卡在谁 | 单 |
|---|---|---|---|
| 1 | 四族没挂（10 条路由）＝ 出口判据的一半 | **owner**：补鉴权还是认这条挂着 | `WIRE-01-FOUR-FAMILIES-NEED-AUTH-AND-PROVIDER.md` |
| 2 | 33 条端点前端没调用 | **下一批**：不是缺陷（多为 deref/design/favorites 等未上屏的族），但没人核过哪些该上屏 | 无单，本报告登记 |
| 3 | 主链路中间那一跳 | **owner**：gate1 落 claims，还是组稿多认一种来源 | `GATE1-VERDICT-IS-NOT-A-COMPOSE-SOURCE.md` |
| 4 | chart / 质量卡 / gap hints 没有存储面 | **owner**：要不要建面；质量卡那条**先定口径再谈补种** | `DEMO-REFS-NO-STORAGE-FACE.md` |
| 5 | `/deliverables/{}/render` 被两个模块声明 | **owner**：哪个赢（现按 `deliverables.py` 登记） | `RENDER-ROUTE-CLAIMED-BY-TWO-MODULES.md` |
| 6 | 前端空态来自没有数据库的内存件 | **owner**：那个「空」是不是假话 | `WIRE-03-EMPTY-FROM-A-STORE-THAT-HAS-NO-DATABASE.md` |
| 7 | 55 条 vitest acceptance 在全局门之外 | **owner**：`npm test` 进不进门（`FIX-03` 已把 `tsc` 接进去了） | 无单，`GAUGE-09` §6 登记 |
| 8 | `ui07` 曾偶发一次红 | **下一批**：疑似跨文件 `vi.stubGlobal` 污染，**未证实** | `UI07-LOCALE-TEST-IS-FLAKY.md` |
| 9 | `/settings/locale` 在 390px 横向溢出 48px | **下一批**：一行样式；已实测排除非 `LOC-01` 所致 | `LOCALE-FORM-OVERFLOWS-ON-MOBILE.md` |
| 10 | 本机 worker 进程仍跑不了 gate1 作业 | **owner**：demo 面走不走真实源 | `QUEUE-01` trace §8-1 |
| 11 | 第 2 批 38 张 `owner_review` 里 28 张仍待看 | **owner** | `docs/owner复核摘要-v041.md` |

**其余无异常** 这句话本报告一次都没有用。上表 11 条就是全部未解决项。

## 6. 给下一批的建议

1. **先解 #1**（鉴权）。它一条卡着出口判据、10 条路由、四族的全部写操作，
   还卡着 `E2E-01` 那句「端到端判据证的是鉴权之外的链路」；
2. **#3 跟着做**：主链路断在中间，比任何一屏的样式都要紧。两条路的代价单子里都写了；
3. **把 `npm test` 的归属定下来**（#7）。第 3 批把 `tsc --noEmit` 接进 pytest 之后，
   门外只剩 vitest 那 55 条——**这是纪律，不是机制**；
4. **清 33 条未被调用的端点**（#2）：逐条判「该上屏 / 内部用 / 该删」，
   现在它们混在一起，看不出哪条是真漏。
