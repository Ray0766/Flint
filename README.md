# 燧石 Flint

热点分析与项目计划书引擎：把每天的热点变成有出处的证据卡，再一路推到带引用的判定、深度报告与计划书。

*Flint turns daily trending topics into cited evidence cards, then into a sourced go/no-go verdict, a research report, and a project plan. Documentation is in Chinese.*

> **状态：开发中，不是生产就绪的软件。** 最新进度以 [`docs/progress-v041.jsonl`](docs/progress-v041.jsonl) 尾部为准；
> 各里程碑的出口结论见 `docs/M1-出口报告.md` 至 `docs/M4-出口报告.md`。

## 它做什么

```
四个热点源日更 → 证据卡 / 工作台 / 关联假设 → 主题生成
  → Gate① 四分类判定（全引用） → 深度报告 → 计划书
```

- **热点源**：微博热搜、Google 趋势、GitHub Trending、arXiv，每源一个模块（`flint/sources/`）。
- **计划书按受众分叉**：给人看的五套模板，或给 AI 执行的 `vibe_pack` 执行包。
- **三条铁律**：结论必有引用；数字必有出处，且三个出处通道互不混用；产物可复现。

V1 范围之外的东西（实时热点、付费数据源、英文界面、团队空间、B 端 API）见 [`CLAUDE.md`](CLAUDE.md) S1。

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python · FastAPI · SQLAlchemy 2 + alembic + asyncpg · arq |
| 存储 | PostgreSQL 16 + pgvector（1024 维，HNSW）· Redis 7 |
| 检索与聚类 | sentence-transformers（bge-m3）· scikit-learn 凝聚聚类 |
| 文书 | markdown-it-py · weasyprint · python-docx |
| 前端 | Next.js 16 · React 19 · next-intl |
| 质量门 | ruff · mypy --strict · pytest · vitest |

版本全部钉死在 [`requirements.lock`](requirements.lock) 与 `web/package-lock.json`；逐项选型理由见 [`技术方案-v1.1.md`](技术方案-v1.1.md) E1。

## 目录

```
flint/           后端：sources / norm / cluster / lineage / retrieval / gate / ledger / compose / jobs / api
web/             前端（Next.js App Router）
contracts/       冻结件：全部实体与接口签名，只读
harness/         演示服务、worker、离线回放、口径测量
eval/            出口断言与台账守门
migrations/      alembic 迁移
fixtures/        外部调用的录制回放（测试永不联网）
tests/           pytest 判据，按里程碑分目录
docs/            进度台账、每张任务卡的 trace、阻塞单、出口报告
```

## 跑起来

需要 Docker、Python 3.13、Node.js 24。

**macOS / Linux** —— 完整步骤见 [`docs/macOS-安装.md`](docs/macOS-安装.md)：

```bash
./start-demo.sh
```

**Windows**：

```powershell
.\start-demo.ps1
```

两个脚本起的是同一组进程：postgres `:55432`、redis `:56379`、后端 `:8000`、前端 `:3000`、worker。
职责与起停顺序见 [`docs/进程编排-v041.md`](docs/进程编排-v041.md)。

两点先说清：

- `start-demo.sh` 写于 Windows 主机，2026-11-14 在一台 Apple M3 的 MacBook Air 上实跑过一次，
  一次走完、exit 0（记录在 [`docs/trace/MAC-01.md`](docs/trace/MAC-01.md) 第七节）；
- **模型接入**：选哪一家由环境变量 `FLINT_DEMO_PROVIDER` 决定，唯一定义处是
  `harness/demo_model.py`。不设就是本地 OpenAI 兼容端点（不要密钥，`start-demo.ps1` 默认指向本机 Ollama）；
  设成 `anthropic` / `deepseek` / `openai` 就走那一家，key、模型名、单价都从 `.env` 读。
  详见安装文档的「模型端点」一节。

## 跑门禁

```bash
ruff check . && mypy --strict flint eval harness && PYTHONIOENCODING=utf-8 pytest -q
```

需要 postgres 与 redis 在线。测试中的一切外部调用都走 `fixtures/` 录制回放。

## 这个仓库是怎么写出来的

本仓的代码由 AI 执行者按一份「执行包」逐卡完成，人负责裁决与验收：

- [`CLAUDE.md`](CLAUDE.md)（[`AGENTS.md`](AGENTS.md) 是给其他执行者的版本）—— 章程、不变量、契约、升级规则；
- `tasks.json` / `tasks-v04.json` —— 机器可读的任务 DAG，每张卡带验收与 `verify_cmd`；
- `contracts/` —— 冻结的类型与接口，实现 MUST 与它逐字一致；
- `docs/progress*.jsonl` —— 只追加的进度台账；`docs/trace/` —— 每张卡的装载清单与决策日志；
- `docs/blocked/` —— 执行中撞到、留给 owner 裁决的问题单。

想改代码，先读 `CLAUDE.md` 的 S2（不变量）与 S7（先写失败的判据，再实现）。

## 许可证

[AGPL-3.0](LICENSE)。

`fixtures/` 下是四个热点源与其他第三方接口的录制响应，只为离线回放测试而收录；
其内容的权利归各自来源所有，不在本仓许可证的授权范围之内。
