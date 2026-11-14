# 取证用的 demo 作业不属于探针那个用户 —— 四条既有判据因此红

**状态** closed @2026-08-08 · `FIX-09`（`DEC-037`）

> 发现者：worker，v0.4.1 第 5 批（DS-02 与 DS-03 之间跑全局门时）。
> **不是本批任何一张卡改出来的**：本批到此只动过 `web/` 的四个文件、`tools/` 的一条规则与两个测试文件，
> 一个字都没碰鉴权、种子数据与 `harness/`。

## 现象（命令原样输出）

```
$ curl -s -o /dev/null -w "%{http_code}" -H "X-User-Id: self" http://localhost:8000/jobs/m1004-j
403
$ curl -s -H "X-User-Id: self" http://localhost:8000/jobs/m1004-j
{"code":"PERMISSION_DENIED","message":"job snapshot requires initiator or owner-scope membership"}
```

SSE 那一条同因：

```
{"code":"PERMISSION_DENIED","message":"SSE subscription requires initiator or owner-scope membership"}
```

连带四条判据红（`pytest -q` 全量 4098 passed / 7 failed 里的 4 条；另 3 条是本批当场改掉的）：

```
tests/v041/test_mobile_sweep.py::test_console_errors_match_a_baseline_that_names_its_ticket
tests/v041/test_screens_live_probe.py::test_the_remaining_noise_is_exactly_the_registered_tickets
tests/v041/test_ui_restyle.py::test_the_remaining_console_errors_are_only_the_registered_unseeded_refs
tests/v041/test_sse_live.py::test_the_channel_really_connects_and_delivers_at_least_one_event
```

三条控制台判据报的话是同一句：「实测 `{'/deliverables/[id]': 3, '/jobs/[id]': 1}`，
登记 `{'/deliverables/[id]': 3}`」——多出来的那一条就是这个 403。

## 怀疑根因

第 4 批把**鉴权**接上了（`AUTH-03` 一族：403 与 404 分开呈现）。
`harness/fe_smoke.py:81` 用的样例 id `m1004-j` 是**更早**从 demo 库里查出来的
（`docs/trace/EYE-03.md` 记着当时是怎么查的），那时还没有鉴权。
现在这条作业的 `initiator` 不是探针用的 `self`，于是：

- 屏上：`/jobs/[id]` 正确地显示「无权查看」——**这是对的行为**；
- 判据上：控制台多一条 403，四条既有判据把它读成「新出现的噪声」。

**所以红的不是产品，是取证样例**：样例 id 与新鉴权口径没对齐。

## 已试三条

1. 重跑 `harness/fe_smoke.py`（`C:\pwenv` 解释器，真栈 web :3000 / api :8000）——
   产物刷新到 2026-08-08，四条依旧红，实测面与旧产物一致 → 不是产物过期；
2. 直接打端点（上面两条 curl）→ 403 来自后端本身，不是前端取数写法；
3. 查 `m1004-j` 在既有问题单里的出处（`docs/blocked/SSE-DISCONNECT-IS-SILENT.md`）→
   那张单说的是「断线静默」，与本条不是一回事，不能顺手并进去。

## 需要 owner 的什么

三选一，**都不该由 worker 自己挑**：

1. **换样例 id**：在 demo 库里挑一条 `initiator == self` 的作业，改 `harness/fe_smoke.py:81`。
   最省事，但要确认那条作业同样能跑出 SSE 事件（`test_sse_live` 要的是「至少一个事件」）。
2. **给种子数据补一条属于 `self` 的作业**：动 `harness/demo_seed_report.py` 一族。
   动的是**种子数据**，属 owner 面。
3. **把这条 403 登记进基线**：三条控制台判据各加一行「`/jobs/[id]` 有 1 条 403，
   原因是样例作业不属于探针用户」。**最不推荐**——那会把一条「取证没对齐」写成常态，
   下次真出 403 时没人分得出来。

## 绕行现状

本批 18 张卡与这条无关（表现层，不碰鉴权与种子数据），**照常继续**。
第 5 批完成态报告（`SHIP-05`）会把这四条逐条列名，NEVER 用一句「其余无异常」收口。

---

## 结案（`FIX-09` · v0.4.1 第 6 批）

owner 2026-08-08 裁 `DEC-037`：**改取证样例，不改产品**。

`harness/demo_seed_probe_job.py` 种了一条属于探针自己的作业
（`probe-owned-ingest`，`initiated_by = demo-user`，owner_scope 指向探针本人），
`harness/fe_smoke.py` 的 `SAMPLE_IDS["/jobs/[id]"]` 改指它。
`tests/v041/test_mobile_sweep.py` 里那一条噪声额度**删掉**——这一屏现在零报错。

**403 NEVER 进控制台噪声白名单**（判据 `test_the_403_is_not_whitelisted_as_console_noise`
守着）：进了白名单等于把鉴权正确工作的证据当成噪声吞掉，
下一次鉴权真的坏了时那条判据不会响。

### 剩下的那一半另立了单

本单说的是「样例与鉴权口径没对齐」，那件事做完了。
**但第 5 批报告里那句「屏上也正确地显示无权查看」是写错的**——
那一屏根本没有拒绝态，403 之后它停在加载骨架上。
两件事修法完全不同（一个改取证样例，一个建界面状态），所以
**NEVER 把它算进本单**：见 `docs/blocked/JOB-SCREEN-HAS-NO-DENIED-STATE.md`。
