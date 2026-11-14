# FIX-09 · `DEC-037` 落地：那条红改取证样例，不改产品

> v0.4.1 第 6 批第九张。**全量 `pytest -q` 自此零 failed**（4445 passed）。

## 装载清单

`tasks-v041-b6.json#FIX-09` · `DECISIONS-v04.md#DEC-037` ·
`harness/fe_smoke.py`（`SAMPLE_IDS`）· `harness/demo_seed_report.py`（种子脚本形状）·
`flint/api/analysis.py#may_view` · `tests/v041/test_{mobile_sweep,screens_live_probe,sse_live}.py` ·
`tests/harness/test_dsn_isolation.py`（DSN 纪律）· 本机 demo 库实查。
约 13k tokens，**未超 40k**。

## 一、改了什么

| 处 | 改前 | 改后 |
|---|---|---|
| `harness/demo_seed_probe_job.py` | 不存在 | 种一条 `initiated_by = demo-user`、`owner_scope = {user, demo-user}` 的终态作业 + 三条事件 |
| `harness/fe_smoke.py` | `"/jobs/[id]": "m1004-j"` | `"probe-owned-ingest"`，并写明换的理由 |
| `tests/v041/test_mobile_sweep.py` | 作业屏占 1 条噪声额度 | **整行删掉**（这一屏现在零报错） |
| `tests/v041/test_screens_live_probe.py` | 同上 + `/topics/[id]` 挂在已关的单上 | 作业屏那行删掉；主题屏改指新单 |

`m1004-j` **原样留着**：它是「不属于我的作业」的活样本。

## 二、`owner_scope` 为什么用 user 域

用 org 域的话，能不能看取决于 `memberships` 表里有没有那一行——
那就把「样例属于探针」这件事又押在**另一张表**上。
user 域直接指向探针本人，`may_view` 第一条就通过。

## 三、事件也要种，否则那条判据只会**跳过**

第一版只种了作业。`test_sse_live` 于是从「红」变成「skip」，
理由写着「demo 栈没起」——**而那句话是假的**：栈起着，是这条作业没有话说
（终态 + 零事件 ⇒ 端点冲刷后直接关流，一个 `data:` 都不发）。

**跳过比红更坏**：红了有人会去看，跳过只是少了一行。
所以连事件一起种，形状照 `flint/jobs/events.py` 的契约（每条带 `kind`），
用库里既有 `drill-*` 一族验证过的 `step` 形状。改完那条判据是**真绿**。

## 四、身份由 fixture 建，NEVER 由种子脚本建

脚本里有一道拒绝：`users` 里没有探针那个身份就**报错退出**，
NEVER 顺手补一行——补一行等于**让取证自己给自己发身份**，
此后「鉴权通过」再也不说明任何问题。判据里有一条阴性对照专门触发它。

测试库里那一行由 fixture 建、跑完清掉：那是**判据在布置前提**，与脚本自己发身份是两回事。

## 五、一次真返工：DSN 纪律

第一版判据默认连 `FLINT_DEMO_DSN`。`tests/harness/test_dsn_isolation.py` 当场判红——
**它判得对**：两库共用一个 PG 时，一处写死就够把 demo 的数据清空一次
（那条根因它自己记着「已咬六次」）。

改法不是给尺子开口子，是**分清两件事**：
判据在**测试库**上验种子函数干得对不对；往 demo 库种那一下是**运维动作**
（`python -m harness.demo_seed_probe_job`），不由判据代劳。

「`m1004-j` 还在不在」也跟着改成判**源码面**（单据点名 + 样例不再指向它）——
真去查 demo 库，本文件就成了那条纪律的一个例外。

## 六、本卡**没做**的那一半（acceptance⑤）

卡面要「另建一条判据专门守『无权时屏上显示无权查看』」。
**那一屏今天没有这个态**：`web/app/jobs/[id]/page.tsx` 只有加载 / 失败 / 空 / 就绪四态，
`useJobStream` 与 `jobClient` 里 grep `403|denied|forbidden` **零命中**——
403 之后 `status` 恒为 `null`，屏上是一张**永远转下去的骨架**。

**「在连」与「不让你连」在屏上长得一模一样**，而两者要用户做的事完全相反。

**第 5 批完成态报告里那句「屏上也正确地显示无权查看」是写错了**，本卡把它纠正过来
（那两处注释也一并改了）。建那个态是 `web/` 的事，本卡 outputs 是 `harness/` + 判据——
按纪律 5 停下，立单 `docs/blocked/JOB-SCREEN-HAS-NO-DENIED-STATE.md`（含三步修法）。

本文件因此**先把这件事量出来**：断言那一屏至今没有拒绝态。
**它哪天红了是好事**——那意味着有人建好了，而那时该回来把它换成 acceptance⑤ 那条正向判据。

## 七、verify

```
pytest tests/v041/test_probe_job_owned.py -q                     → 20 passed
pytest tests/v041/test_{mobile_sweep,screens_live_probe,
       ui_restyle,sse_live}.py -q                                → 59 passed（四条既有判据全回绿）
pytest -q（全量）                                                 → **4445 passed / 0 failed**
ruff / mypy --strict flint / check_line_endings                  → 全绿 / 304 files / 219 LF
C:\pwenv\…\python.exe harness/fe_smoke.py                        → 作业屏 console_errors 0，横向溢出 0
```

## 八、self_review

① 判据覆盖 acceptance 六条中的五条（⑤ 据实停下并量出缺口），
含三条阴性对照（身份不在时脚本要拒 / 403 NEVER 进白名单 / 屏上还没有拒绝态）；
② 零冻结件改动；③ 无禁用词；
④ 改动面：`harness/` 两个文件 + 本判据（卡上 outputs）+ 三份既有判据的基线登记面
（逐处记因，都是「样例换了所以额度该删」）；⑤ 装载 ≈13k tokens。

## 九、留给下游

- `JOB-SCREEN-HAS-NO-DENIED-STATE`：一张小卡，outputs 应为 `web/` + 判据；
- 噪声面现在只剩两处：`/deliverables/[id]`（3，无存储面）与 `/topics/[id]`（1，库里没主题），
  各挂各的活单。
