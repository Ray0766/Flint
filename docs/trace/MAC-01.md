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
