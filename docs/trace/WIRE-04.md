# WIRE-04 · 逐屏真栈取证（16 屏 × 明暗两主题）

**卡** `docs/steward/tasks-v041-b3.json#WIRE-04` · **cycles 2** ·
**self_review = true** → §4 · **owner_review = false**
**依赖** `WIRE-03`（verified）

## 1. 装载清单

卡面 WIRE-04 · `harness/fe_smoke.py`（全文，230 行）· `.ui-probe/fe_smoke.json` ·
`docs/trace/EYE-02.md` / `EYE-03.md` 的取证口径段 ·
`web/components/project-overview/ProjectOverview.tsx` 的入参与 `Section`。
约 11k tokens，预算 40k 以内。

## 2. 首跑抓到两处，**都只有真数据才看得见**

`WIRE-03` 接线之前，四张屏收 `null` 就直接返回「接口未提供」，
**下面那条渲染路径一行都不走**。所以这两处不是「样式没对齐」那一类，
是接线之后才存在的缺陷，单测拿假数据喂组件永远碰不到。

### 2.1 跑着的后端是**旧进程**

首跑：`/account` `/billing` `/settings/locale` `/projects/[id]` 各带 1 条控制台 404。
直连 `create_app` 是 200，而 `curl localhost:8000/account` 是 **404**。

`Get-NetTCPConnection -LocalPort 8000` → PID 80004，**启动于 2026-08-04 22:55**，
早于 `WIRE-01`/`02` 的全部改动。跑着的是装配前那份只有七族的 app。

**取证是忠实的**——它照实反映了那个进程。重启后端（`python -m harness.demo_server`）
后四屏转绿。

### 2.2 `/projects/[id]` 一条 React key 警告 → 我在 `WIRE-03` 少写了一个适配层

```
Each child in a list should have a unique "key" prop.
Check the render method of `Section`.
```

根因：`WIRE-03` 给 account / billing 写了适配层，却把项目总览的后端 JSON
**直接喂给了组件**。后端给的是领域对象（`topic_id` + `one_liner` + `why_now` …），
组件要的是三列 `{id, label, state}`——于是 `key={row.id}` 全是 `undefined`。

已补 `toProjectOverviewView`。取证复跑：`/projects/[id]` 两主题**零报错**。

**这正是本卡存在的理由**：`WIRE-03` 的 12 条判据、vitest 750 条、tsc 全绿，
没有一条能看见它。

## 3. 收在哪儿

```
16 屏 × 2 主题 = 32 行，全部 HTTP 200 · 无横向溢出
截图 52 张（.ui-probe/*.png，文件名带屏名与主题）
仍带控制台报错的：/deliverables/[id] 10 条 · /gate/[id] 1 条
```

后两者**各自挂着单**（`DEMO-REPORT-REFS-NOT-SEEDED`，由 `FIX-02` 处置）。
判据判**等值**：判零会把别人的活算成本卡失败，不判会让新增的报错混进来。
数字一变（修好了 / 又多了）都要有人回到判据这里确认。

## 4. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_screens_live_probe.py -q → 10 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3712 passed（WIRE-03 收卡时 3702，本卡 +10）
            cd web && npm test -- --run → 74 files / 750 passed（未动前端测试）
            cd web && npx tsc --noEmit  → 只剩 2 条既有错，本卡零新增
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 逐屏 200 / 零报错 / 无溢出 / 两主题截图 | `test_every_screen_on_disk_was_probed_in_both_themes`（判**屏数×主题数**，不是「取到的都通过」）、`test_every_screen_answers_200_without_horizontal_overflow`、`test_the_screens_wired_by_wire_03_are_console_clean`、`test_the_remaining_noise_is_exactly_the_registered_tickets`（判等值）、`test_the_probe_names_the_screenshot_for_every_row` |
| ② 复用 `DARK-02` 前置判据，NEVER 关掉 | `test_the_two_themes_are_not_the_same_screenshot`（两主题截图逐字节相同即红）、`test_the_theme_switch_gate_is_still_wired_in` |
| ③ 阴性对照 | `test_the_probe_would_go_red_if_a_screen_lost_its_styles`；另有变异考 7 条（§③） |
| ④ 截图落 `.ui-probe/`、带屏名与主题、不覆盖上一批 | `test_the_probe_names_the_screenshot_for_every_row`（断言文件名含主题且非空） |

**② 改既有文件两处 + 一处 `WIRE-03` 的补漏**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `harness/fe_smoke.py` | ① `/projects/[id]` 的样例 id `p-placeholder` → **从库里查出来的** `proj-demo14bf9d94b0`；② URL 替换 `route.replace("[id]", sample)` → `_PARAM_SEGMENT.sub(...)` 通配任意参数名 | ①`WIRE-03` 接了这一屏，占位 id 会让它恒 404——正是本文件 docstring 自己警告的「探针给错地址」那种假红。②`[token]` 用 `[id]` 替换替不掉，URL 里原样留着 `[token]`，于是 `SAMPLE_IDS["/share/[token]"]` 是**死配置**，改它没有任何效果而报告看起来一切正常 |
| `web/lib/screenAdapters.ts` | 新增 `toProjectOverviewView` | `WIRE-03` 的补漏，见 §2.2。**属 `WIRE-03` 的 outputs（`web/lib/`），未越界** |
| `web/app/projects/[id]/page.tsx` | 直接喂 → 走适配层 | 同上 |

**未改**：`scripts/ui_probe.py` · `tools/visual_assert.py`（本卡未用到它们的改动面）。
`.ui-probe/` 里上一批的截图**没有被覆盖**——文件名带屏名与主题，本轮新屏是新文件名。

**③ 变异考 7 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 少取一屏 | 红 |
| ② 只取一个主题 | 红 |
| ③ 接线后的屏出现控制台报错 | 红 |
| ④ 一屏横向溢出 | 红 |
| ⑤ 既有噪声「消失」 | 红（等值判据提醒来改登记） |
| ⑥ 已接线的动态路由退回占位 id | 红 |
| ⑦ 参数替换退回只认 `[id]` | 红 |
| ⑧ 假变异对照：只改一句注释 | 全绿 |

**④** 装载约 11k tokens；**⑤** 禁用词六词 0 命中。

## 5. 登记未做

1. **重启了本机 demo 后端**（PID 80004 → 新进程）。这是取证的必要步骤，
   属本机 dev 服务，非红线四类。但**下一个 worker 要知道**：
   改了 `flint/api/` 或 `harness/demo_server.py` 之后，
   **跑取证前 MUST 重启 `:8000`**，否则量到的是旧代码。
   建议 `WIRE-05` 把「取证前检查后端进程启动时间晚于最后一次源码改动」做成判据——
   本卡没做，那超出本卡 outputs。
2. **`/share/[token]` 与 `/workbenches/[id]` 仍用占位串**：它们没接线（`WIRE-03` 的
   登记面），占位串此刻是对的。**接线那天 MUST 换成真值**，
   `test_no_dynamic_route_is_probed_with_a_stale_placeholder` 的
   `wired_dynamic` 集合要同步加进去。
3. **`/deliverables/[id]` 的 10 条与 `/gate/[id]` 的 1 条**由 `FIX-02` 处置。
