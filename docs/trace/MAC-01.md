# MAC-01 · macOS 起停脚本 + 安装文档 + README（@2026-11-14）

owner 2026-11-14 在会话里直接驱动，不在 `tasks.json` 的 DAG 里。背景三条：

1. 开发机从 Windows 换到 macOS；
2. 项目转开源：`github.com/Ray0766/Flint`，AGPL-3.0；
3. 本地模型那条路先不做，开发阶段调闭源模型的 API。

## 一、实际装载清单

| 装了什么 | 为什么 |
|---|---|
| `start-demo.ps1`、`stop-demo.ps1` 全文 | 要逐项对的原件 |
| `docs/进程编排-v041.md` 全文 | 进程、端口、起停顺序、查重标记的出处 |
| `tests/v041/test_start_demo_paths.py` 全文 | 同类静态判据的先例（FIX-07） |
| `harness/local_model.py` 全文 | 演示栈的模型接入只有这一处定义 |
| `flint/llm/production.py:225-410` | 云端三档的配置加载长什么样 |
| `compose.yaml`、`pyproject.toml`、`requirements.lock`、`.env.example`、`Makefile` | 端口、依赖、门禁命令 |
| `harness/replay30.py:1-45,155-164`、`scripts/provision_test_db.py:1-60` | 空库怎么灌回数据 |
| `docs/progress-v041.jsonl` 末 5 行、`docs/progress.jsonl` 末 20 行 | S8 |

## 二、交付

| 文件 | 内容 |
|---|---|
| `start-demo.sh` | `start-demo.ps1` 的 POSIX 对应物；后台进程 + `.run/` 下的日志与 PID |
| `stop-demo.sh` | `stop-demo.ps1` 的 POSIX 对应物；只发 TERM，容器只 stop |
| `docs/macOS-安装.md` | 前置、装依赖、模型端点现状、起栈、灌数据、门禁、排障 |
| `README.md` | 仓库首页 |
| `tests/v041/test_start_demo_sh.py` | 26 条静态判据 |
| `.gitignore` | 增 `.run/` |

verify_cmd：`pytest tests/v041/test_start_demo_sh.py -q`

## 三、断点与决策

**判据先行**：判据写完先跑，26 条全红（文件都不存在）；实现后 26 条全绿，无 skip。
相邻静态守门（`test_start_demo_paths` / `test_orchestration_doc` / `test_doc_gates` /
`test_encoding_guard` / 两本台账的配对守门）59 过；1 条红
`test_the_worker_can_actually_be_built_and_run_in_burst` 要连 redis `:56379`，
本机 Docker 起不来（见 `docs/trace/REPORT-SRC-01.md` §三），与本卡的改动无关。

**与 ps1 有意不同的三处**（都写进了脚本头注释）：

1. 没有独立窗口。macOS 上「开一个新终端窗口并留住它」要靠 AppleScript 驱动 Terminal，
   换一个终端应用就不成立。改成后台进程，日志落 `.run/*.log`；
2. 不探测、不拉取本地模型。ps1 第 ② 步的两处 `Read-Host` 问的都是 Ollama 的事，
   owner 裁决那条路先不做，于是这一段整段不搬。判据第四节守着：脚本里出现 `11434` 即红；
3. 仓根有 `.env` 就整份导入。ps1 靠的是 Windows 的机器级环境变量，macOS 上没有对应物。

**停脚本多做的一件事**：`.run/*.pid` 里的 PID 先用 `ps` 核对命令行再停。
PID 会被系统复用，只凭一个数字发信号，杀到的可以是任何人的进程。

## 四、本卡没有做、也 NEVER 该读成做了的

1. **macOS 实机一次都没跑过。** 26 条判据全是静态的。`start-demo.sh` 里的每一条命令
   （`open -ga Docker`、`lsof -ti tcp:… -sTCP:LISTEN`、`pgrep -f`、`nc -z`）都是照文档写的，
   没有一条在 Mac 上执行过；
2. **闭源 API 没有接进演示栈。** `harness/local_model.py:53` 造的是不带 `api_key` 的
   `LocalProvider`，后端与 worker 都从这里拿 provider。接闭源 API 要改这一处工厂，
   并由 owner 定厂商、模型、单价（S2-10 人审触点）。本卡只在文档里把这件事写明；
3. **`CLAUDE.md` S3 没有动。** 它仍写 Python 3.11，而实际 venv 是 3.13.3；
   `docs/macOS-安装.md` 取 3.13 并写明这是未决项；
4. **演示数据没有搬。** Windows 机的 PG 卷导不出（Docker 起不来）。文档给的是
   `harness.replay30` 重灌，回放结果与原演示库是否逐项相同没有核过。

## 五、首次在 Mac 上跑时要回填的

- `docs/macOS-安装.md` 顶部那段「实机一次都没跑过」换成实跑日期与机型；
- 哪一步走不通，记在本文件下面，再改脚本或文档；
- `requirements.lock` 里若有哪个钉死版本没有 macOS 轮子，开问题单，NEVER 手改锁文件。

## 六、后续：`CLAUDE.md` S8 改指现行台账（owner 2026-11-14 直接指令）

`CLAUDE.md` 属 owner 变更通道（`DEC-019`：本体零修改）。本次改动由 owner 在会话里逐字下达：
「把 CLAUDE.md 的 S8 改成指向新台账，然后推送」。

改前 S8 让新会话读 `docs/progress.jsonl` 末 20 行，而那本台账停在 2026-08-01；
现行的是 `docs/progress-v041.jsonl`。照旧文走，Mac 上的新会话会从三个月前的状态接手。

改了四处，其余一字未动：

- S8 第一条：现行台账写成 `docs/progress-v041.jsonl`；
- S8 新增一条：点名两本历史台账及各自末行日期；
- S8 启动规则：读 `docs/progress-v041.jsonl` 末 20 行；
- 附页 Human Digest「怎么看进度」同步改指（它与 S8 说的是同一件事，留着旧指向即两处矛盾）。

**有意没改的**：

- S9 审核检查单第 ④ 项「trace 与 progress.jsonl 完整」——`tests/m4/test_m4_006.py:66`
  逐字比对检查单条目，改它判据会红；
- `AGENTS.md`——它是 `CLAUDE.md` 的同文副本（仅标题行不同），owner 的第一条指令只点了 `CLAUDE.md`，
  当时没动。**随后 owner 同日指令「同步 AGENTS.md」，已同步**：同样四处改动，
  `diff CLAUDE.md AGENTS.md` 只剩标题行一处不同。

## 七、首次实机运行（2026-11-14）

owner 指令：按 `docs/macOS-安装.md` 把环境起起来，跑通即止；红的用例只列不修；
不接模型 API；不开 `REPORT-SRC-01`。

**机器**：MacBook Air 15 英寸（型号标识 `Mac15,13`），Apple M3，16 GB，arm64，
macOS 27.2.1（26B131）。Docker Desktop 29.7.2（开工时引擎已在跑）、Node v24.21.0（mise 装的）、
pango 1.57.0_2（Homebrew，开工前已装）。

### 7.1 逐步现象

| 步 | 命令 | 现象 |
|---|---|---|
| 前置 | `brew install python@3.13` | 本机原先只有 3.14.3，没有 `python3.13`。装完得 3.13.18。文档那条命令里的 `node@24`、`pango` 本机已有，没有重装 |
| 建 venv | `python3.13 -m venv .venv` | 通过，pip 26.2.2 |
| 装依赖 | `.venv/bin/pip install -r requirements.lock` | exit 0。锁文件里 81 个钉死版本全部装上，**没有一个缺 macOS arm64 轮子**；`torch==2.13.0`、`numpy==2.5.1`、`scipy==1.18.0`、`selectolax==0.4.11`、`asyncpg==0.31.0` 都解析到了 arm64 或 universal2 轮子。锁文件首行带 BOM，pip 认 |
| 起栈 ① | `./start-demo.sh` | `docker compose up -d` → PG 就绪 → alembic 0001 至 0028 → `flint_test` 新建并迁移、大类种子 12 条 → 报告夹具 9 blocks |
| 起栈 ② | 同上 | 仓根没有 `.env`，照设计警告「没配齐」，继续 |
| 起栈 ③ | 同上 | 后端 `:8000` 就绪；`npm ci` 装 151 个包（6 秒）；前端 `:3000` 就绪（Next.js 16.2.12，Turbopack）；worker 起后存活 |
| 起栈 ④ | 同上 | `open` 打开 `/demo?day=2026-07-04`。**整个脚本一次走完，exit 0，一个字没改** |
| 回放 | `.venv/bin/python -m harness.replay30 --days 30` | `replay30: 30/30 days green; all_green=True`，36 秒。225 条 `cluster_naming_failed … offline replay: LLM disabled` 警告，是离线回放的本意 |

起栈之后核过的：

- `lsof` 看到 `:8000`（Python）、`:3000`（node）、`:55432` / `:56379`（Docker）四个监听；
  `pgrep -fl harness.run_worker` 有一个进程；
- `curl`：`/plaza/hot?day=2026-07-04` 200，`/demo?day=2026-07-04` 200，
  `/deliverables/del-demo-fixture-report` 200；
- 回放之前 `/plaza/hot` 回 `clusters: []`，回放之后回 154 个簇 + 1 条弱信号；
- **真浏览器里看过**（应用内浏览器，视口 800×600）：`/demo?day=2026-07-04` 进去先显
  「该区当日无数据」，点「加载当日热点广场」之后才发 `GET /plaza/hot`，随后「今日精选」与
  「全部热点」出卡（热搜话题02 / 01 / 00 …），console 无报错。
  1920×1080 与 390×844 两档视口**没有看**。

### 7.2 没走到的分支（NEVER 读成验过）

1. `start-demo.sh` 的「Docker 引擎未就绪 → `open -ga Docker` → 轮询 180 秒」：引擎本来就在跑，这一段没执行；
2. 仓根 `.env` 整份导入：本机没有 `.env`，这一段没执行；
3. 「重复跑安全」：脚本只跑了一遍，三处「已在运行，复用」都没走到；
4. `stop-demo.sh`：一次都没跑。栈现在还开着；
5. 生成类功能（combo 主题、Gate 分析）：没接模型，没有点；
6. 回放出来的内容与 Windows 机那份演示库是否逐项相同：仍然没有核。

### 7.3 门禁实测

三条命令分开跑（连成一条 `&&` 的话 ruff 一红后两条就不跑了，看不到全貌）。

**ruff**：exit 1，1 条。
`EXE001 Shebang is present but file is not executable`，`tools/validate_dag_v04.py:1`。
该文件在索引里是 `100644` 而首行是 `#!/usr/bin/env python3`。ruff 在 Windows 上不判这条规则
（那边没有可执行位），到 macOS 才第一次被判。

**mypy --strict flint eval harness**：exit 1，3 条（371 个文件）。

| 位置 | 报错 | 原因 |
|---|---|---|
| `harness/fe_smoke.py:281` | `Cannot find implementation or library stub for module named "playwright.sync_api"` | playwright 按纪律不进 `.venv`，`pyproject.toml` 的 mypy overrides 里没有它 |
| `eval/gate1.py:135` | `Argument "gaps" to "decide" has incompatible type "list[DerivedGap]"; expected "list[GapHint]"` | `derive_gaps` 回 `list[DerivedGap]`（`flint/gate/rule_d.py:55`），`decide` 收 `list[GapHint]`（`flint/gate/engine.py:32`） |
| `harness/e2e_stack.py:81` | `Unused "type: ignore" comment` | 那一行的 `# type: ignore[arg-type]` 已经没有东西可压 |

三条都不带平台特征。另外单跑了 `mypy --strict flint`（S7 与 `ci.yaml:31` 的写法）：
`Success: no issues found in 323 source files`。台账 `SHIP-15` 记的「mypy 323 文件」与这个数逐字相同，
所以那一次量的是 `flint` 一个包；`eval` 与 `harness` 在 Windows 上最后一次是哪天过的 strict，
本机查不到。

**pytest -q**（单跑，319 秒）：`79 failed, 5363 passed, 355 skipped, 12 warnings, 3 errors`。
第二遍（带 `-rs` 收 skip 原因，303 秒）：`79 failed, 5364 passed, 354 skipped, 3 errors`，
红的条数相同。文档、台账、本节写完之后在最终树上又单跑一遍（289 秒）：
`79 failed, 5364 passed, 354 skipped, 3 errors`，红的 82 条与第一遍逐条相同
（两份 `FAILED` / `ERROR` 清单排序后 `diff` 无输出）。82 条红分四类：

**甲、`.ui-probe/` 取证产物不在本机——68 条。** 该目录没有进仓。
`test_combo_wire` 7 · `test_eye04` 6 · `test_eye05` 11 · `test_fav_card` 6 ·
`test_palette_onscreen` 2 · `test_palette_v4` 1 · `test_tail_01` 3 ·
`test_theme_really_switches` 3 · `test_ui_mainchain` 6 · `test_ui_restyle` 7 ·
`test_wb_annotate` 2 · `test_wb_cards` 2 · `test_wb_generate` 2 · `test_wb_layout` 6 ·
`test_wb_preview` 2 · `test_wb_sections` 2。
报的都是「缺这一张」「没有 .ui-probe/fe_smoke.json」「缺搬家前那份取证」或对
`.ui-probe/…json` 的 `FileNotFoundError`。

**乙、判据里写死了 Windows 的写法——6 条。**

| 用例 | 现象 | 原因 |
|---|---|---|
| `test_theme_toggle::test_the_dark_palette_ruler_still_stands` | `FileNotFoundError: 'python'` | 子进程直接叫 `python`，本机 PATH 上只有 `python3` |
| `test_workbench_persist::test_the_two_workbench_responses_are_typed_now` | `FileNotFoundError: …/.venv/Scripts/python.exe` | Windows venv 的目录布局 |
| `test_job_denied_state::test_the_rendering_is_asserted_by_a_real_component_test` | returncode 0 而 stdout 为空 | `subprocess.run([...列表], shell=True)`：POSIX 上只有 `npx` 一个词被执行，后面的参数没传进去 |
| `test_screen_data_refetch::test_the_refetch_really_refires_the_request` | 同上 | 同上（`tests/v041/test_screen_data_refetch.py:136-139`） |
| `test_translator::test_the_call_site_is_the_only_one` | 把 `flint/i18n/translate.py:189`、`:191` 判成多出来的构造点 | 白名单前缀写的是反斜杠 `flint\\i18n\\translate.py`（`tests/v041/test_translator.py:129`） |
| `test_gauge_map::test_disk_copies_are_current` | 落盘 json 过期 | 169 条里差 1 条，差的只是 `files` 两项的先后：`sorted(Path)` 在 Windows 上不分大小写、在 POSIX 上分，`SourceColumns.test.tsx` 与 `attribution.test.tsx` 换了位置 |

**丙、新机器的状态与判据钉的不一样——7 条。**

| 用例 | 现象 | 原因 |
|---|---|---|
| `test_job_denied_state::test_the_backend_really_denies_the_job_that_is_not_mine` | 期望 403，实得 404 | 判据打真栈 `:8000`，要演示库里有 `m1004-j` 这条作业；新库里没有 |
| `test_job_denied_state::test_the_sse_endpoint_denies_it_too` | 同上 | 同上 |
| `test_sse_live::test_the_channel_really_connects_and_delivers_at_least_one_event` | `unknown job: probe-owned-ingest` | 同上，缺的是 `FIX-09` 种的那条 |
| `test_m3_035` 三条（setup error） | `Unable to find image 'flint-pdf:69' locally` | 本机没构建过这张镜像（`docker/pdf`） |
| `test_m3_058::test_read_and_three_formats` | 期望 503，实得 200 | 判据钉着「PDF 引擎不可用（Q-003）→ 503」。本机有 pango，weasyprint 直接出得了 PDF |

这三条打真栈的判据在栈没起时会 skip；现在红是因为栈起着而库是新的。

**丁、与平台无关——1 条。**
`test_decisions_landed::test_the_numbers_continue_the_existing_watermark`：
`最高编号是 DEC-064，不是 DEC-060`。第 17 批往 `DECISIONS-v04.md` 落了 061 至 064，
判据的水位还钉在 60。在 Windows 上跑也是红的。

**skip 354 条的去向**（第二遍 `-rs`）：230 条的原因里点名 playwright 或 `C:\pwenv`
（那个隔离环境本机没有），其余 124 条里绝大多数是「还没取证」「缺 `.ui-probe/…`」。
`SHIP-15` 在 Windows 上的数是 2 skipped。

### 7.4 文档与实况对不上的两处（已改文档）

1. `docs/macOS-安装.md` 第六节原话：读 `.ui-probe/` 的那批判据「在新机器上会 skip」。
   实况是一部分 skip、68 条红（甲类）。已改成实测的数；
2. 排障表「广场是空的 → 跑回放」：`/demo` 这一屏在点「加载当日热点广场」之前恒显
   「该区当日无数据」，库里有数据也一样。已在那一行补上。

顶部「实机一次都没跑过」那段已换成实跑日期与机型。`start-demo.sh`、`stop-demo.sh` 未改。

### 7.5 只登记、没有动的

1. **回放与 pytest 会改写 70 个已入库的文件。** 跑完 `git status` 里
   `docs/trace/replay30/` 30 个、`docs/trace/goldcases/` 20 个、`docs/trace/golddocs-doc/` 12 个、
   `assets/trial_specs/` 7 个、`docs/trace/drill7.md` 1 个全是 `M`。
   `git diff --ignore-cr-at-eol` 之后只剩 4 个：三个 `pack.zip`（字节不同）与 `drill7.md`
   （一行墙钟耗时 `7.695` → `6.006`）。其余 66 个的差别只有换行符：仓里是 CRLF，
   macOS 上重新生成出来是 LF。本次用 `git restore` 全部还原，没有进提交。
   **以后在 Mac 上每跑一次回放或全量 pytest 都会这样**；
2. `requirements.lock` 没有钉全：weasyprint 与 python-docx 的 13 个传递依赖
   （`cffi 2.1.1`、`fonttools 4.68.0`、`brotli 1.2.1`、`lxml 6.1.3`、`pillow 13.0.0`、
   `pydyf 0.13.0`、`Pyphen 0.18.1`、`tinycss2 1.5.1`、`tinyhtml5 2.1.0`、`webencodings 0.6.1`、
   `zopfli 0.4.3`、`cssselect2 0.10.1`、`pycparser 3.12`）是 pip 现场解析的，
   不在锁文件里。S2-6 要求版本锁死；锁文件没有动；
3. `CLAUDE.md` S3 列了 `pytest-asyncio`，锁文件里没有它，`.venv` 里也没有装上；
4. `harness.demo_seed_report` 打印的地址是 `http://localhost:3001/deliverables/…`，前端实际在 `:3000`；
5. `.run/frontend.pid` 记的是 `npm run dev` 那层的 PID，监听 `:3000` 的是它的子进程 node。
   `stop-demo.sh` 先按端口找人，设计上盖得住；没有实跑验证（见 7.2 第 4 条）；
6. `npm ci` 报 9 个 vulnerabilities（2 moderate / 6 high / 1 critical），另有 4 个包的安装脚本
   未被 `allowScripts` 覆盖（`@parcel/watcher`、`fsevents`、`@swc/core`、`sharp`）。前端照常起来了；
7. `compose.yaml` 里的 `api` / `worker` 两个占位容器（`python:3.11-slim` + `sleep infinity`）也被一并拉起；
8. Python 3.11 与 3.13 那条未决项原样留着。本次只在 3.13.18 上跑过。
