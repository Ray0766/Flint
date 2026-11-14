# FIX-06 · 移动视口从来没有全量量过——逐屏补一遍

**卡** `docs/steward/tasks-v041-b4.json#FIX-06` · **cycles 2（oneshot=false）** ·
**self_review = true** → §5 · **owner_review = false** · **依赖** `FIX-05`

## 1. 装载清单

卡面 FIX-06 · `harness/fe_smoke.py` 全文 · `scripts/ui_probe.py` 的视口处理 ·
`docs/blocked/LOCALE-FORM-OVERFLOWS-ON-MOBILE.md` 与 `DEMO-REFS-NO-STORAGE-FACE.md` ·
`docs/trace/WIRE-04.md` · `tests/v041/test_fe_smoke.py` / `test_screens_live_probe.py` /
`test_demo_stack_wired.py` 里所有读取证的判据。约 15k tokens。

## 2. 「新被看见的」不是「新坏的」（acceptance②）

`LOCALE-FORM-OVERFLOWS-ON-MOBILE` 那条 48px 溢出，是有人**手工单独**跑了一次
`ui_probe` 才看见的：常规冒烟只跑 1440。**靠偶然发现的东西，下一次就会靠偶然错过。**

本卡把 390×844 接进 `harness/fe_smoke.py` 的 `VIEWPORTS`，
此后每一次冒烟都自带这一半，且报告里 `mobile_rows` / `mobile_overflow` 单独计数——
混在总数里的话，「十六屏全绿」与「十六屏桌面全绿、移动一屏没跑」长得一模一样。

## 3. 实测：屏是十六张，不是卡面写的十三张

`discover_screens` 从磁盘数（`web/app/**/page.tsx`）：**16 张**。
判据按磁盘数，**NEVER 按卡面那个数**——写死 13 的话，新增一屏永远不会被量到，
而报告看起来是全绿的。

```
counts: {"screens": 64, "mobile_rows": 32, "mobile_overflow": 0,
         "bad_status": 0, "console_errors": 12, "overflow": 0, "invalid_rows": 0}
```

16 屏 × 2 主题 × 2 视口 = **64 行**，截图 64 张全部存档在 `.ui-probe/`。

## 4. 移动端横向溢出：**0**（acceptance①③）

一条都没有。这既是本卡的结论，也反过来印证 `FIX-05` 找的那个根因是对的：
`.app-shell__body` 是所有屏共用的容器，修它等于一次修掉十六屏。
**若溢出源不止那一处，这里会剩下几条。**

所以 acceptance③「查出来的每一条溢出：能修的修，改动面超出的逐条开单」
在本卡是**空集**——没有可修可开的，因为一条都没查出来。

## 5. 顺带查出来的四条控制台报错，逐条落实

| 屏 | 报错 | 处置 |
|---|---|---|
| `/deliverables/[id]` | 3 × 404（`/charts/…`、`/hints/…`、`/cards/…`） | **不动**：`DEMO-REFS-NO-STORAGE-FACE` 登记的**正确行为**（三类实体全库没有存储面，端点如实回 404）。判等值并点名单号 |
| `/gate/[id]` | 1 × 404（`/jobs/m1004-j/verdict`） | **修了**：样例 id 指向一个**没有 verdict 快照**的 job。换成 `job-gate1-live-qwen`（demo 库里唯一有判定的 job） |

第二条正是 `fe_smoke.py` 自己开篇写的那句：「现编一个 id 更糟：那一屏会恒 404，
而 404 会被读成『这屏坏了』，真相是**探针给错了地址**」。改前那一屏取证拍回来的是
一张空态截图，而报告上它叫「判定屏」。

## 6. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_mobile_sweep.py -q → 11 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 301 source files
            pytest -q               → 4066 passed（FIX-05 收卡时 4055，本卡 +11）
取证:       C:\pwenv\Scripts\python.exe harness/fe_smoke.py → 64 行，mobile_overflow=0
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 十六屏 390px 逐屏取证：无溢出 · 200 · 零控制台报错 · 截图存档 | `test_no_screen_overflows_horizontally_on_a_390px_viewport`、`test_every_mobile_row_answered_two_hundred`、`test_console_errors_match_a_baseline_that_names_its_ticket`、`test_every_mobile_row_has_a_screenshot_on_disk`（**报告里有名字、磁盘上没有 = 没取证**） |
| ② mobile 进常规取证 | `test_the_regular_smoke_run_now_includes_a_mobile_viewport`、`test_screenshot_names_carry_the_viewport`、`test_every_screen_on_disk_was_measured_on_mobile_in_both_themes`（**按磁盘数**） |
| ③ 查出来的每条都落实 | 溢出是空集（§4）；控制台那四条见 §5，`test_the_gate_screen_probe_points_at_a_job_that_has_a_verdict` + `test_every_baselined_route_still_points_at_a_live_ticket`（**基线挂的单必须仍 open**——单子关了而基线还留着数，就是拿过期单为新缺陷背书） |
| ④ 明暗两主题各一遍 | 所有判据都跨 `THEMES` 两值；`test_screens_live_probe.py::test_the_two_themes_are_not_the_same_screenshot` 仍在（截图逐字节相同即红） |

**② 改既有文件五处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `harness/fe_smoke.py` | 加 `VIEWPORTS`（含 mobile 390）；行加 `viewport` 字段并进 `REQUIRED_FIELDS`；截图名带视口；`counts` 加 `mobile_rows` / `mobile_overflow`；`/gate/[id]` 样例 id 换成有判定的 job | **卡上 outputs**，§2 §5 |
| `tests/v041/test_fe_smoke.py` | `_row()` 夹具补 `viewport`；形状判据加那个键；缺字段判据改成「在清单里」而不是「排第一」；截图名判据带视口 | 行的形状变了；**排第一那条本来就脆**——顺序取决于 `REQUIRED_FIELDS`，那不是它要钉的东西 |
| `tests/v041/test_screens_live_probe.py` | 行数按 `屏 × 主题 × 视口`（视口数**从报告里数**，NEVER 写死 2）；`KNOWN_NOISY` 更新；截图配对改成替换主题段 | 见 §7 |
| `tests/v041/test_demo_stack_wired.py` | 报告屏控制台报错 10 → 3，并改挂 `DEMO-REFS-NO-STORAGE-FACE` | 它自己写着「若是 FIX-02 修好了，把本条改成 0；若是新增的，停下登记」——实测是 3，两句都不适用，所以照实改并写清剩下三条为什么是对的 |
| `.ui-probe/` | 64 张截图 + `fe_smoke.json` | 卡上 outputs |

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；`flint/` 一行未改；未新增依赖（playwright 恒在 `C:\pwenv`）。

**③ 变异考 6 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 把 mobile 从 `VIEWPORTS` 拿掉（退回缺陷态） | 红 |
| ② 截图名不带视口（mobile 覆盖 desktop） | 红 |
| ③ 取证里悄悄少一屏 | 红 2 条，点名是哪一屏 |
| ④ 某屏真溢出 | 红，报出 438/390 |
| ⑤ 新增一条没登记的控制台报错 | 红 |
| ⑥ 样例 id 退回没有判定的那个 | 红 |
| ⑦ 假变异对照：文件末尾加一行注释 | 全绿 11 passed |

**④** 装载约 15k tokens；**⑤** 禁用词六词 0 命中。

## 7. 我自己把一条判据改红了，红在一个没有错的地方

截图名加了视口段之后，`test_the_two_themes_are_not_the_same_screenshot` 当场红：
它用 `.replace("-dark.png", "-light.png")` 配对两主题的截图，
而新名字是 `account-dark-desktop.png`——**那个子串一个字符都匹配不上**，
于是 light 指向了与 dark 同一个文件，字节当然相同。

判据报的是「主题切换没生效」，而真相是「配对逻辑坏了」。
改成替换**主题那一段**（`-dark-` → `-light-`），并加一条
`assert light != dark`——**配对逻辑坏掉时要报配对坏了，NEVER 报成主题坏了**。

这与本批一路在治的是同一件事：**两种不同的失败 NEVER 共用一个说法**。

## 8. 登记未做

1. **只加了一档移动视口**（390×844）。平板（768）没量。
   加一档的成本是 `VIEWPORTS` 里一行 + 一次重跑，但要不要把它列进常规取证，
   属取证口径，值得单独定。
2. **`DEMO-REFS-NO-STORAGE-FACE` 那三条仍 open**：本卡确认它们是正确行为并挂进基线，
   建不建存储面是 owner 的事（那张单自己写着「待办归属 owner」）。
3. **没有把移动取证接进 CI**：CI 不联网也没有浏览器（S2-7），
   这份取证恒是本机跑。要让它长期可见，得有一条定期作业——`SHIP` 面的事。
4. **`.ui-probe/` 里旧命名的截图没清**：上一次跑留下的 `*-dark.png`（不带视口）
   还在盘上。它们不会被任何判据读到（报告里的名字都带视口了），
   但留着会让人以为是这次的产物。清理属整洁范畴，本卡没做。
