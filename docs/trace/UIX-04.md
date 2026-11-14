# UIX-04 · trace

**卡**：作业屏——403 之后它停在加载骨架上，永远
**verify_cmd**：`pytest tests/v041/test_job_denied_state.py -q` → **13 passed**
**cycles**：1（卡面估 2）
**owner_review**：true —— 按 `DEC-000` 事后补审

---

## 装载清单（实际）

`docs/blocked/JOB-SCREEN-HAS-NO-DENIED-STATE.md` 全文 ·
`web/app/jobs/[id]/page.tsx` 全文 · `web/lib/{useJobStream,jobClient}.ts` 全文 ·
`web/components/shell/SseDisconnectNotice.tsx` 全文 ·
`tests/v041/test_probe_job_owned.py` §四 · `tests/v041/test_mobile_sweep.py` 的基线段 ·
`web/__tests__/app/screens.test.tsx` 的桩。约 21k tokens。

---

## 断点与决策日志

### 一、`EventSource` 拿不到状态码——这是整件事的机械根因

原生 `EventSource` 的 `onerror` **不带 HTTP 状态**，它连 403 与断网都分不出来。
所以补一次 `fetch GET /jobs/{id}`：那条路读得到状态码，而且**与 SSE 受同一条鉴权**
（实测两条都回 403，判据 `test_the_sse_endpoint_denies_it_too` 钉住这个前提）。

**探一次，不轮询**：轮询会在真断网时对着一个连不上的后端反复打，
而屏上那句话不会因为多打几次变得更准。
探不出来（500 / 真断网）就是 `unknown`，**NEVER 猜成 denied**——
猜错会让用户去要一个他本来就有的权限，而真正的问题在后端。

### 二、`access` 刻意**不塞进** `connection`

塞进去，「不让你连」就成了「连接的一种状态」——而它其实是**答案已经给了**：
重连一万次也还是 403。判据 `test_the_client_exposes_an_access_state` 反向守住
（`"disconnected" | "denied"` 这种写法直接红）。

同理，无权件与 `SseDisconnectNotice` **刻意不共用**：
后者说「正在重连，下面的内容可能不是最新的」（可恢复），前者是终局的。

### 三、「不劝重试」还不够，要**明说重试没用**

只是不劝的话，用户自己会去刷新，而刷新永远不会成功。
所以 403 那句文案逐字写着「重试不会有用」。

**判据第一版把这句实话判成了违规**（禁「重试」二字）——第十一次同一形状。
修法是分开「劝」与「提到」：禁的是 `稍后重试 / 请重试 / 再试一次 / retry later`
这些**劝进**的话术，并**正面断言**「重试不会有用」在位。

### 四、屏上那条分支的条件：正向枚举，不是 `!== "unknown"`

第一版写的是 `if (s.access !== "unknown")`。**它当场打红两条既有判据**：
`web/__tests__/app/screens.test.tsx` 的桩里没有 `access`，
于是 `undefined !== "unknown"` 成立 → 那一屏走进拒绝分支 →
**五个取证属性整片消失**。

那正是 `probeJobAccess` 自己拒绝去做的事（探不出来就是 `unknown`，NEVER 猜成 denied），
而我在呈现层把它做了一遍。改成 `s.access === "denied" || s.access === "unauthenticated"`，
并给桩补上 `access: "unknown"`（如实：那几条判据测的是「能看的时候屏上有什么」）。
另加一条 vitest 判据钉住这个条件的写法。

### 五、分支**排在骨架之前**

骨架那条的条件是 `status === null`，而无权时它同样成立——排在后面永远命中不到。
判据比的是**两条分支条件的位置**，不是「denied 这个词第一次出现在哪」
（后者会被 import 行左右）。

### 六、第 6 批那条反向判据翻过来了

`test_the_job_screen_still_has_no_denied_state` 的 docstring 里写着
「这一条哪天红了，是好事——那时该回到这里把它换成正向判据」。
照那句话执行：换成 `test_the_job_screen_now_has_a_denied_state`，
**并且用同一组词**（`denied|forbidden|无权|403`），只是方向反过来——
换一组词的话，两条判据守的就不是同一件事了。

**留着一条描述旧世界的判据一直红着，会让下一个人以为产品坏了。**

---

## 视觉取证（真栈）

```json
"not_mine (/jobs/m1004-j)": {
  "denied": [{"v": "denied",
              "t": "无权查看这条作业它不是你发起的。要看的话，找发起人给你开权限——重试不会有用。"}],
  "skeleton_nodes": 0,
  "job_status": [],
  "console_errors": ["… 403 (Forbidden)", "… 403 (Forbidden)"]
}
"mine (/jobs/probe-owned-ingest)": {
  "denied": [], "skeleton_nodes": 0, "job_status": ["done"], "console_errors": []
}
```

`.ui-probe/uix04-not_mine.png` **已用 Read 看过**：屏上是那两句话，
**骨架不见了**。`uix04-mine.png` 那一屏照常显示 `done`。

那两条 403 控制台报错**没有进白名单**（`DEC-037`：把鉴权正确工作的证据当成噪声吞掉）。
`fe_smoke` 的样例是 `probe-owned-ingest`（0 报错），所以全量取证仍然绿；
`test_the_forbidden_status_is_not_whitelisted_as_console_noise` 钉住这一条。

---

## 改既有文件

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `web/lib/jobClient.ts` | `JobStreamState` 无 `access`；`onerror` 只标断线 | 加 `access` 三态 + `probeJobAccess()`；`onerror` 后探一次 | 卡面 outputs。没有它，403 与断网在屏上长得一样 |
| `web/app/jobs/[id]/page.tsx` | 四态，无权落进加载骨架 | 第五态，排在骨架之前；屏头注释改成五态表 | 同上 |
| `web/messages/{zh,en}.json` | — | 各 +4 key（denied / unauthenticated 各标题+提示） | 两种失败**两句话**（`AUTH-03` 口径） |
| `web/__tests__/app/screens.test.tsx` | 桩无 `access` | 补 `access: "unknown"` | 见断点四。**outputs 外，供复核** |
| `tests/v041/test_probe_job_owned.py` | 反向判据 + 单据 open 断言 | 两条都翻成正向 | 第 6 批那条 docstring 写明「红了就回来改」。**outputs 外，供复核** |

`docs/blocked/JOB-SCREEN-HAS-NO-DENIED-STATE.md` 关单，立单原文一字未改。

---

## self_review

**① 覆盖 acceptance**

| acceptance | 判据 |
|---|---|
| ① 现状（四态、grep 零命中、骨架转不停） | 单据原文 + `test_the_backend_really_denies_the_job_that_is_not_mine` / `test_the_sse_endpoint_denies_it_too` 钉住机械前提 |
| ② 第五态，「在连」与「不让你连」NEVER 一样 | `test_the_screen_has_a_denied_branch` · `test_the_denied_state_is_not_the_disconnect_notice` · `test_the_denied_state_replaces_the_skeleton_not_stacks_on_it` · vitest 12 条 |
| ③ 401 与 403 分开 | `test_the_two_auth_failures_map_to_two_states`（禁写进同一条件）+ vitest 两例两句话 |
| ④ 补上 `FIX-09` 没做成的那条正向判据，打真栈 | 真栈 403/200 + playwright 取证 + `test_the_batch_six_placeholder_judgement_was_turned_around` |
| ⑤ 403 NEVER 进噪声白名单 | `test_the_forbidden_status_is_not_whitelisted_as_console_noise`（判**基线表本身**，不判整份文件——文件里那段注释逐字写着这条禁令） |
| ⑥ 关单 | `test_the_sheet_is_closed` |

test-first：判据先跑 **10 failed / 4 passed**，实现后 13 passed。

**② 无冻结件偏离**：未触碰 `contracts/` 与 `flint/domain/`；后端一行未改。
**③ 无禁用词**：新增/改动文件扫过，无命中。
**④ 复用断言**：`JobDeniedNotice` 沿用 `state state--*` + `data-screen-state` 的既有通用件形状；
NEVER 复用断线件（判据反向守住）。
**⑤ 装载**：约 21k / 40k。

**其它门**：`ruff check . --no-cache` All passed（一处自动修）；
`npx tsc --noEmit` exit 0；`npx vitest run` **81 文件 825 通过**（全量）；
`pytest tests/v041/test_job_denied_state.py tests/v041/test_probe_job_owned.py -q` 28 passed。

---

## 产出文件清单

- `web/components/shell/JobDeniedNotice.tsx`（新）
- `web/lib/jobClient.ts` · `web/app/jobs/[id]/page.tsx`
- `web/lib/jobDenied.test.tsx`（新，12 条）
- `web/messages/zh.json` · `web/messages/en.json`（各 +4 key）
- `web/__tests__/app/screens.test.tsx`（桩补 `access`，**outputs 外**）
- `tests/v041/test_job_denied_state.py`（新，13 条）
- `tests/v041/test_probe_job_owned.py`（两条判据翻正向，**outputs 外**）
- `docs/blocked/JOB-SCREEN-HAS-NO-DENIED-STATE.md`（closed）
- `.ui-probe/uix04-{not_mine,mine}.png`
- `docs/trace/UIX-04.md`（本文件）
