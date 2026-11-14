# WIRE-VERDICT · 热点判定：屏接上了后端那条读法

**结论**：分析屏没拿到 `?verdictJob=` 时**去问** `GET /clusters/{id}/verdict`；
`/jobs/{id}/verdict` 留着；**封版件一行没动**。
对账器 `backend_unused_by_frontend` **21 → 20**，`field_mismatch` 归零。
`verify_cmd` 9 条全绿。

装载：`docs/steward/tasks-v041-b10.json#WIRE-VERDICT` · `flint/api/views.py#cluster_verdict` ·
`web/app/clusters/[id]/page.tsx` · `web/lib/viewsClient.ts` · `web/app/plaza/page.tsx` ·
`docs/blocked/HOTSPOT-03.md`
（实测装载 ≈ 18k tokens，预算 40k）

---

## 1 屏上那句话没变，**原因变了**

改前分析屏说「未判定」，因为 `cluster → job` 的对应关系没有持久化真相。
`DEC-044` 之后 `cluster_verdicts` 就是那份真相，`PERSIST-04` 建了端点——
**而前端一处都没在调**。于是屏上仍然说「未判定」。

**对用户是同一句话，对改代码的人是两件事**：从前该去建端点，现在该去接屏。

## 2 封版件一行没动——**因为不需要动**

`AnalysisView` 是 v0.4 封版件，本批 rules 写着「无封版件例外」。
而新端点回的 `job_id` **正好就是**那条缺失的对应关系，
所以只需把 `verdictJobId` 的来源从「只有 URL」扩成「URL 优先、其次问端点」。

| 来源 | 什么时候 |
|---|---|
| URL 的 `?verdictJob=` | 调用方手上有 job id，**它更具体，NEVER 被端点回的覆盖** |
| `GET /clusters/{id}/verdict` | 只知道热点。404 = 这个热点没判过 |

**那条禁令一字未改**：「NEVER 拿 cluster_id 拼一个 job id 去试」。
改的是**去问**而不是去猜——猜错时用户看到的是另一个热点的判定，
问不到时端点回 404、屏上如实说「未判定」。

## 3 那句已经变假的注释

`plaza/page.tsx` 里写着「`GET /clusters/{id}/verdict` 不存在」——**今天是假的**。

第一版我把那句话**原样引进了新注释**（「改前写的是『…不存在』」），
于是判据照样红——**而它是对的**：一句变假的断言被原样引一遍，
下一个人扫过去读到的仍是那句假话。改成描述它、不复述它。

## 4 我自己写错的六处

1. 切片从 `useEffect` 这个**词**起切 → 切到了 import 行，顺序判据误报；
2. 封版件路径记成 `web/components/analysis-view/`，实际在 `web/views/analysis/`；
3. 新注释把那句假话原样引了一遍（§3）；
4. 种子照记忆写了 `snapshots.kind` 与 `cluster_verdicts.decided_at`——**两个列都不存在**；
5. `jobs.state` 写了 `'succeeded'`，而 `ck_jobs_state` 认的终态叫 `'done'`；
6. **种了不收**：`cluster_verdicts` 有外键指向 `clusters`，别的判据清 `clusters` 时撞上它——
   全量从 0 failed 变成 **6 failed / 18 errors**，全部是这一条，
   **而那些红出现在别人的文件里、根因在我这里**。补了 autouse teardown，按外键顺序删。

另一处在前端判据里：我断言「一个 `/jobs/…/verdict` 都不发」——**写反了**。
拿端点回的 id 去取判定内容正是「去问」，禁令禁的是「去猜」。
改成钉那个 id 的**来源**：必须是端点回的那一个，且 NEVER 含 cluster id。

## 5 顺带治好一处真漂移

接完之后对账器报 `/clusters/{}/verdict` 的 `field_mismatch`——**它是对的**：
端点回三个字段（`cluster_id` / `job_id` / `verdict`），
而前端复用的 `VerdictResponse` 只说了两个。补了 `ClusterVerdictResponse`。

客户端还加了一道：缺 `job_id` 读成**没判过**（`null`），
NEVER 让 `undefined` 漏出去——调用方用 `undefined` 表示「还没读」，
漏一个出去屏就永远停在加载态，**而那一屏什么都不会说**。

## 6 改前 / 改后 / 为什么非改不可

| 文件 | 改前 | 改后 | 为什么 |
|---|---|---|---|
| `web/lib/viewsClient.ts` | 只有按 job 那条 | +`fetchClusterVerdictJob` + 两条读法的表 | 卡面③ |
| `web/app/clusters/[id]/page.tsx` | 只读 URL | URL 优先、其次问端点 | §2 |
| `web/app/plaza/page.tsx` | 一句变假的注释 | 改成实况（禁令留着） | 卡面④ |
| `web/lib/types.ts` | 复用 `VerdictResponse` | +`ClusterVerdictResponse` | §5 |
| `web/__tests__/app/nav02.test.tsx` | 断言不发 verdict 请求 | 翻面 + 钉 id 来源 | 前提被推翻 |
| `tests/v041/test_ui_mainchain.py` | 断言全仓 NEVER 出现它 | 只许一处 | 同上 |
| `docs/端点分诊-v041.md` | B 类 17 条 | 16 条 | 接掉一条 |

## 7 自审（`self_review=true`）

**① 判据覆盖 acceptance**（六条）：①实况已钉；②原因变了写进 §1；
③两条读法各自何时用**在文件头写死**且旧那条留着（各一条判据）；
④变假的注释已删（且钉住禁令**没被一起删掉**）；
⑤打真代码——塞真行读得出四分类与引用，没判过时说「没判过」而不是空白；
⑥对账器少一条（判据实跑对账器）。
**先红后绿**：9 条里 4 条在改前红。

**② 无冻结件偏离**：四件未触碰；封版件 `AnalysisView` 有一条判据钉着它没被改取数路径。
**③ 无禁用词**：0 命中。**⑤ 装载未超预算**：≈18k / 40k。

## 8 门

```
pytest tests/v041/test_wire_verdict.py -q   9 passed
ruff check . --no-cache                     All checks passed!
mypy --strict flint                         320 source files
npx tsc --noEmit                            0
npm test -- --run                           858 passed
对账器：backend_unused_by_frontend 20（改前 21）· field_mismatch 0
```
