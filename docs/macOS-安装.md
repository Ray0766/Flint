# macOS 安装与起栈（MAC-01 @2026-11-14）

> **实机跑过一次：2026-11-14，MacBook Air 15 英寸（`Mac15,13`，Apple M3，16 GB），macOS 27.2.1。**
> Python 3.13.18（Homebrew）、Node v24.21.0、Docker Desktop 29.7.2、pango 1.57.0_2。
> 第二节装依赖、第四节 `./start-demo.sh` 四步、第五节回放都一次走完，脚本一个字没改。
> 脚本的静态面仍由 `tests/v041/test_start_demo_sh.py` 守着（脚本文本逐项对 `start-demo.ps1`
> + `bash -n` 语法检查）。
> **第六节的门禁在这台机器上是红的**：ruff 1 条、mypy 3 条、pytest 79 failed + 3 errors，
> 逐条原因见 `docs/trace/MAC-01.md` §七。
> 没走到的：Docker 冷启动那段轮询、`.env` 导入、重复起栈、`stop-demo.sh`、任何调模型的功能
> ——这几样仍是「没在 Mac 上跑过」。本文其余写着「没有核过」的句子原样保留。

## 一、前置

| 要装的 | 版本 | 出处 |
|---|---|---|
| Python | **3.13** | Windows 开发机的 venv 是 3.13.3，全部门禁都是在它上面跑绿的 |
| Node.js | **24** | Windows 开发机是 v24.18.0 |
| 容器引擎 | Docker Desktop 或 OrbStack | `compose.yaml` 起 postgres（pgvector/pg16）与 redis 7 |
| pango | Homebrew 最新 | weasyprint 69 出 PDF 要它 |

```bash
brew install python@3.13 node@24 pango
```

**Python 版本有一处未决**：`CLAUDE.md` S3 与 `.github/workflows/ci.yaml` 写的是 3.11，
而实际开发环境是 3.13。`requirements.lock` 是在 3.13 下冻结的，其中的 `numpy==2.5.1`
能不能装进 3.11 **没有核过**。本文按「先复现已知跑绿的环境」取 3.13；改回 3.11 属 owner 决策。

## 二、取代码、装依赖

```bash
git clone https://github.com/Ray0766/Flint.git
```

```bash
cd Flint && python3.13 -m venv .venv && .venv/bin/pip install -r requirements.lock
```

- `requirements.lock` 是 Windows 上 `pip freeze` 的结果。里面的 `torch==2.13.0` 在 macOS 上
  解析到 arm64 轮子；`colorama` 是 Windows 才用得上的包，装上无害。
  **哪个钉死的版本没有 macOS 轮子，pip 会点名报出来**——照实记下，NEVER 手改锁文件
  （`.claude/settings.json` 对它设了写保护，新增或换版要先过 RegistryValidator，S2-6）。
- 前端依赖由 `start-demo.sh` 在首次起栈时用 `npm ci` 装。`web/package-lock.json` 里
  已有 `@next/swc-darwin-arm64`、`@rolldown/binding-darwin-arm64` 这些 macOS 原生包的条目。
- 换行符：仓里 CRLF 与 LF 混用，`.gitattributes` 用 `* -text` 关掉了转换。
  NEVER 在本仓设 `core.autocrlf=true`——`contracts/` 的副本是逐字节比对的。

## 三、模型端点

**先说清现状：演示栈今天只能接「不要密钥的 OpenAI 兼容端点」。**

- 后端与 worker 的模型接入只有一处定义：`harness/local_model.py:53` 的
  `LocalProvider(base_url=..., model=...)`，**不传 `api_key`**；
- 地址与模型名从两个环境变量读：`FLINT_LOCAL_BASE_URL`、`FLINT_FREE_TIER_MODEL`
  （都不设时落到本机 `localhost:11434`）；
- 云端三档的配置加载已经有了——`flint/llm/production.py` 的 `load_anthropic_tier`（:284）、
  `load_deepseek_tier`（:384）、`load_openai_tier`（:390）——但**演示栈没有接它们**，
  用到它们的是 `harness/topic_caliber.py`、`harness/prod_caliber.py` 这类口径测量脚本。

owner 2026-11-14 裁决：本地模型那条路先不做，开发阶段调闭源模型的 API。
这条裁决**还没有落到代码上**：要让演示栈走闭源 API，得改 `harness/local_model.py`
那一处工厂，并定下用哪一家、哪个模型、单价填多少（单价是 cost 记账的出处，NEVER 内置价表）。
付费接口开通是 S2-10 的人审触点，那三样都属 owner 决策。

在那之前：

```bash
cp .env.example .env
```

- `start-demo.sh` 会把仓根 `.env` 整份导入环境（`.env` 已被 `.gitignore` 排除）；
- 两个变量没配齐时脚本照常起栈，只在第 ② 步警告：生成类功能（combo 主题、Gate 分析）
  调用模型时会失败。读库的屏幕（广场、工作台、报告查看）是否全部不受影响，**没有在 Mac 上核过**；
- `.env.example` 里的 `model-a` / `model-b` 是占位值，原样拷过去不会有模型可用。

## 四、起栈

```bash
./start-demo.sh
```

脚本做四步，重复跑安全：

1. 起 Docker 引擎（没起就 `open -ga Docker`，轮询 180 秒，起不来就失败并给手动步骤）
   → `docker compose up -d` → `alembic upgrade head` → 备置测试库 `flint_test` → 灌报告屏夹具；
2. 报告模型端点配没配（只透传，不探测）；
3. 后端 `:8000`、前端 `:3000`、worker 各在后台起，日志与 PID 落在 `.run/`；
4. 打开 `http://localhost:3000/demo?day=2026-07-04`。

与 `start-demo.ps1` 的两处不同：没有独立窗口（看日志用 `tail -f .run/backend.log`）；
不探测也不拉取本地模型。四个进程的职责、起停顺序、失败征兆对照表见 `docs/进程编排-v041.md`
——那张表里「任务管理器里找窗口」一类的说法换成 `pgrep -fl harness.run_worker`。

```bash
./stop-demo.sh
```

容器只 `stop`，数据卷 `pgdata` 保留。

## 五、演示数据

**新机器上的库是空的。** Windows 开发机的数据在它本机的 Docker 卷里，没有搬过来
（那台机器的 Docker 自 2026-10-27 起不来，导不出）。

起栈之后跑一次 30 天离线回放，把广场数据灌回来：

```bash
.venv/bin/python -m harness.replay30 --days 30
```

- 全程 fixtures 回放，零联网（S2-7）；默认窗口 2026-06-24 至 2026-07-23，演示日 07-04 在其中；
- 向量用 `DeterministicHashBackend`（`flint/jobs/ingest.py:146`），**不会**下载 bge-m3；
- 回放出来的内容与 Windows 机上那份演示库是否逐项相同，**没有核过**。
  那边的项目与主题是真调模型生成的（`docs/progress.jsonl` 的 `UI-BATCH2-TOPIC-JOB` 一行），
  回放不会重建它们——那要模型端点接通后重新生成。

## 六、跑门禁

```bash
PYTHONIOENCODING=utf-8 .venv/bin/ruff check . && .venv/bin/mypy --strict flint eval harness && PYTHONIOENCODING=utf-8 .venv/bin/pytest -q
```

- 需要 postgres 与 redis 在线（先 `./start-demo.sh`，或只 `docker compose up -d`
  再跑 `.venv/bin/python scripts/provision_test_db.py`）；
- **演示栈起着的时候**，有三条判据直接打 `:8000`，要演示库里有两条取证作业。新库里没有，
  种一次（幂等，只写 `jobs` 两行与它们的事件；栈没起时这三条会 skip）：

  ```bash
  .venv/bin/python -m harness.demo_seed_probe_job
  ```

- `tests/m3/test_m3_035.py` 在容器里出 PDF，要本机有 `flint-pdf:69` 这张镜像。构建一次
  （要联网拉 `python:3.11-slim`、apt 与 pip 包；2026-11-14 实测镜像 548MB）：

  ```bash
  docker build -t flint-pdf:69 docker/pdf
  ```

- `PYTHONIOENCODING=utf-8` 是为 Windows 的 GBK 管道加的固定前提（`Makefile` 里有说明），
  macOS 上不带它也该成立，带着无害；
- `.ui-probe/` 没有进仓（79MB 截图，本机运行产物）。读它的那批判据在新机器上 skip，
  并写明缺哪一份、怎么补（口径在 `tools/probe_evidence.py`；2026-11-14 首跑时其中 68 条是红的，
  `MAC-06` 统一成了 skip）。跑过取证而缺某一张图，仍然判红。
  重跑各自的取证脚本之后恢复，这一步还没在 Mac 上做过；其中 6 条读的是开工前拍的历史对照，
  只在原来那台 Windows 机的 `.ui-probe/` 里，重跑造不出来；
- playwright 不是本项目依赖，NEVER 装进 `.venv`。探针脚本的报错文案里写的
  `C:\pwenv` 是 Windows 上那个隔离环境的位置；macOS 上另建一个 venv 装它即可，位置自定。

**接手点**：最后一张在途的卡是 `REPORT-SRC-01`（`docs/progress-v041.jsonl` 末段，状态 blocked）。
`flint/api/compose.py` 已改、判据 `tests/v041/test_report_src.py` 已写，**一次都没跑过**——
卡住的原因正是 Windows 机上起不了库。Mac 上门禁跑通之后，先收这一张。

## 七、排障

| 症状 | 多半是 | 怎么办 |
|---|---|---|
| `./start-demo.sh: Permission denied` | 可执行位没带过来 | `chmod +x start-demo.sh stop-demo.sh`，或 `bash start-demo.sh` |
| `bad interpreter: /usr/bin/env bash^M` | 脚本被转成了 CRLF | 查 `git config core.autocrlf`，应为 `false` 或未设；重新检出该文件 |
| weasyprint 报 `cannot load library 'libgobject-2.0'` | Apple 芯片上找不到 Homebrew 的动态库 | 起栈前 `export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix)/lib"` |
| 后端 90 秒内未就绪 | 看 `.run/backend.log` | 连不上 55432 → `docker compose ps` |
| 作业永远停在 `queued` | worker 没起 | `pgrep -fl harness.run_worker`；看 `.run/worker.log` |
| 广场是空的 | 库里没有数据 | 跑第五节的回放 |
| `/demo` 显「该区当日无数据」 | 这一屏不自动取数 | 点「加载当日热点广场」；点了仍空才是库里没有数据 |
