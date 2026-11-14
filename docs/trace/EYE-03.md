# EYE-03 · 前端 e2e 冒烟：起真栈、逐屏取证、把数字留下

**卡** `tasks-v041-b2.json#EYE-03` · **批次** v0.4.1 第 2 批 · **开工** 机器 UTC 2026-08-03T22:53Z

## 0. 台账时间戳更正（诚实条款 §8）

本会话此前各行的 `ts` 是我按经过时间推算的，**比机器 UTC 快约 43 分钟**
（开工时 `date -u` = 21:42:15Z，而 EYE-02 收卡行写的是 23:39:10Z，当时真实时间约 22:51）。
历史行 append-only **NEVER 回改**；本卡起全部用 `date -u` 实读。
事实顺序与 `cycles_used` 不受影响，受影响的只是各行的绝对时刻。

## 1. 装载清单

卡面 EYE-03 · `start-demo.ps1`（③ 段起栈命令）· `harness/demo_server.py` 头部 ·
`scripts/ui_probe.py`（EYE-01 的观测口径与三种红）· `web/app/**/page.tsx`（3 个）·
`web/app/deliverables/[id]/page.tsx` 全文（诊断 500 用）。约 14k tokens。

## 2. 顺序（§4.2）

**测试先落盘先跑红**（collection ERROR，`harness/fe_smoke` 不存在）→ 实现 → 12 passed + 1 skipped
（skip 的是「实跑产物有则必验」那条，当时还没跑真栈）→ 真跑之后 14 passed。连续第三张顺序正确。

## 3. 起真栈与逐屏取证（acceptance①③）

**栈**：`postgres:55432` 与 `ollama:11434` 本已在跑，Docker 就绪；本卡起了
后端 `harness.demo_server`（:8000）与前端 `npm run dev`（:3000）。

**屏清点从磁盘来**：`web/app/**/page.tsx` 三个 → `/demo`、`/deliverables/[id]`、`/jobs/[id]`。
动态段用**显式声明**的样例 id（`SAMPLE_IDS`）填，且两个 id 都是从 demo 库里**查出来**的
（`select deliverable_id from deliverables` → `del-demo-fixture-report`；
`select job_id from jobs` → `m1004-j`）。

**首版我自己踩了这个坑**：给 `/jobs/[id]` 编了个 `job-demo-fixture`，实跑当场现形——
页面 200 但控制台一条 404。**探针给错地址会被读成「这屏坏了」**，正是本模块 docstring
警告的那种假红。改成真 id 后该屏控制台归零。

### 本次取证全部数字（3 屏 × 2 主题 = 6 行）

**A. 按 `start-demo.ps1` 的文档路径起前端**（只设 `NEXT_PUBLIC_FLINT_API`）：

| 主题 | 屏 | HTTP | 控制台 error | 页高 | 横向溢出 | 截图 |
|---|---|---|---|---|---|---|
| dark | `/deliverables/[id]` | **500** | **2** | 900px | 无 | deliverables-id-dark.png |
| dark | `/demo` | 200 | 0 | 152px | 无 | demo-dark.png |
| dark | `/jobs/[id]` | 200 | 0 | 58px | 无 | jobs-id-dark.png |
| light | 三屏 | 同上逐行一致 | | | | |

→ `EXIT=1`，控制台原文 `pageerror: Failed to parse URL from /deliverables/…/blocks`。

**B. 前端补 `FLINT_API_BASE=http://localhost:8000` 重起**（唯一变量）：

| 主题 | 屏 | HTTP | 控制台 error | 页高 | 横向溢出 |
|---|---|---|---|---|---|
| dark | `/deliverables/[id]` | 200 | 0 | 422px | 无 |
| dark | `/demo` | 200 | 0 | 152px | 无 |
| dark | `/jobs/[id]` | 200 | 0 | 58px | 无 |
| light | 三屏 | 同上逐行一致 | | | |

→ `EXIT=0`。落盘的 `.ui-probe/fe_smoke.json` 是 **B**，因为它同时是这把尺子的**正向对照**：
证明它报得出绿，不是只会报红。A 组数字进了问题单（§4）。

## 4. 首跑就挖出的三件事

### 4.1 配置缺陷（**新**，已立问题单 `docs/blocked/FE-DEMO-ENV-FLINT-API-BASE.md`）

`web/app/deliverables/[id]/page.tsx:15` 是服务器组件，取基址用
`process.env.FLINT_API_BASE ?? ""`；而 `start-demo.ps1` **全文零命中** `FLINT_API_BASE`，
只设了客户端那一份 `NEXT_PUBLIC_FLINT_API`。于是**按文档一键起栈，报告屏恒 500**。
后端无辜：`curl .../blocks` 直接 200。三点实证 + 三案排除写在问题单里。

改 `start-demo.ps1` 不在本卡 outputs 内 → 按工单 §2 走问题单，NEVER 自行改。
配一条**自己退休**的断言：脚本一天没补那行，问题单就一天不许消失；补上之后本条自动放行
（`test_the_demo_start_script_gap_stays_registered_until_it_is_fixed`）——
一条永远要求问题单存在的断言，会逼着修好之后还留一份过期文档。

### 4.2 主题开关是空的（**已碑在 FB-01**，本卡只补硬证据）

三屏的 dark 与 light 截图**逐字节相同**：

```
deliverables-id  dark=6a8f9fd8837d light=6a8f9fd8837d  逐字节相同
demo             dark=e7908c0ac2e9 light=e7908c0ac2e9  逐字节相同
jobs-id          dark=2bbd4f8dc48b light=2bbd4f8dc48b  逐字节相同
grep -c "import.*css|_ds" web/app/layout.tsx → 0
```

`layout.tsx` **零 CSS import** → 设计系统从未被应用加载 → 明暗两套值不存在，
`color_scheme` 与 `localStorage.theme` 全都不起作用。这正是终检 F-09 的根因，
工单把它列为 FB-01（「设计系统接进应用——F-09 的根因」）。
**本卡不修**（不在 outputs 内），只把它从「读代码推断」变成**可复看的字节级证据**：
FB-01 做完之后，这六张图必须不再逐字节相同——那就是它的验收。

### 4.3 六类 id 原样显给用户（**已碑在 FB-04~FB-10**）

报告屏截图（`.ui-probe/deliverables-id-dark.png`，我用 Read 直接看了）里，用户看到的是
`fact-demo-vecdb-cost`、`cit-demo-arxiv-2506-06962`、`chart-demo-cost-trend`、
`qc-demo-fixture-01`、`sec-04-gap-hints` —— **数据库 id 而不是内容**。
与工单 C 组「FB-04~08 是后端六个解引用端点」逐条对上。同样只记录不修。

## 5. 只读边界（acceptance④）

冒烟全程只 `goto` + `screenshot` + `evaluate` 读量测，**不点、不填、不提交、不写库**。
`test_the_harness_never_touches_the_page` 扫源码里的 `.click(` / `.fill(` / `.press(` /
`.select_option(` / `.set_input_files(` / `.check(` 六种交互调用，恒零命中。
理由写在模块 docstring：一旦开始点，冒烟就会改数据；改了数据的冒烟下一次跑出来的东西不一样，
那时候没人分得清是回归还是上一次自己留下的痕迹。

## 6. 「NEVER 只报一句通过」落在哪（acceptance②）

- `validate_row`：每屏必须带 12 个字段（HTTP 状态、控制台报错数与原文、页高、
  横向溢出、scrollWidth、视口宽、截图名…），缺任一即判无效，`counts.invalid_rows` 计数；
- `build_report.ok` 要求四项同时为零（非 200 / 控制台 error / 溢出 / 无效行）**且行数非零**——
  空报告 NEVER 算过；
- `skip_reason` 只在**栈没起**时给理由（退出码 3），**跑了没过 NEVER 给理由**（退出码 1）。
  两者修法不同（起服务 vs 改代码），与 EYE-01 的三种红同源。

## 7. 变异考

| 变异 | 抽掉什么 | 结果 |
|---|---|---|
| ① 动态路由没样例 id 就 `continue` | 「报出来而不是跳过」 | **1 failed** ✓ |
| ② `validate_row` 恒返回空 | 「缺数字即无效」 | **1 failed** ✓ |
| ③ `ok` 不再看 `stack_down` | 栈没起也报绿 | **3 failed** ✓ |

三次均从备份还原，`harness/fe_smoke.py` sha256 前缀 `7dd31089882fdd6e`。

## 8. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_fe_smoke.py -q → 14 passed
ruff check . --no-cache → All checks passed!
真跑：C:\pwenv\Scripts\python.exe harness/fe_smoke.py → EXIT=0（B 配置）/ EXIT=1（A 配置）
```

**① acceptance 映射**

| acceptance | 测试 / 证据 |
|---|---|
| ① 起真栈、全部页面逐屏取证 | `test_every_page_file_in_the_app_router_becomes_a_screen`（磁盘几个 `page.tsx` 就得几张屏）、`test_the_three_known_routes_are_all_there`、`test_a_dynamic_route_uses_a_declared_sample_id` + §3 六行真实数字 |
| ② 未起时 skip 并说明、起了必须给真实数字 | `test_a_down_stack_is_never_reported_as_pass`、`test_a_live_stack_has_no_skip_reason`、`test_a_row_missing_a_number_is_invalid`、`test_a_non_200_screen_is_red`、`test_console_errors_and_overflow_are_counted_not_summarised` |
| ③ 截图带屏名与主题、trace 列全部屏与数字 | `test_the_screenshot_name_carries_screen_and_theme` + 本 trace §3 两张表 |
| ④ 全程只读 | `test_the_harness_never_touches_the_page` |

另有 `test_a_dynamic_route_without_a_sample_id_is_reported_not_dropped`（构造用例：
悄悄跳过的那一屏在报告里根本不存在，而报告看起来是全绿的）。

**② 无冻结件偏离**：零新增依赖（stdlib `socket`/`json`/`argparse`/`dataclasses`）；
`contracts/`、`flint/domain/`、`requirements.lock`、`pyproject.toml`、`web/package.json` 一字未动。
**未改任何既有文件**——两处缺陷都走了登记（问题单 / 指向 FB-01 与 FB-04~10）。

**③ 禁用词**：两个产物文件六词 0 命中、收尾「等」0 命中。

**④ 复用**：观测口径与截图落点复用 `scripts/ui_probe.py`（EYE-01）——`console`/`pageerror`
监听、`scrollHeight/scrollWidth/innerWidth` 溢出判、`.ui-probe/` 产物目录、三种红的分层。
NEVER 另写一套量测。

**⑤ 装载预算**：约 14k tokens。

## 9. 登记未做

1. **`start-demo.ps1` 不改**（§4.1，问题单已立，自退休断言盯着）；
2. **FB-01 / FB-04~10 不做**（§4.2、§4.3 是它们的面，本卡只留可复看的证据）；
3. **只跑桌面视口 1440×900**：移动视口下的横向溢出没量（`scripts/ui_probe.py` 有 `--mobile-only`，
   本卡的冒烟没接这个维度——接它要在报告里再开一维，属扩面，留给用它的那张卡）；
4. **`/jobs/[id]` 只取了一个静态时刻**：SSE 进度流的中间态没取证（要点击/等待才能驱动，
   与 acceptance④ 的只读边界冲突，需另设口径）；
5. **停栈**：本卡起的后端 :8000 与前端 :3000 仍在跑（供后续 UI 卡复用）；
   关闭用 `stop-demo.ps1`。NEVER 在这里删数据或动生产。
