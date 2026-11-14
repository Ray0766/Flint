# 可点击 demo · 本地启动（TS-012）

端到端 demo 路由 `/demo`：**广场 → 点簇 → 工作台 → combo（选卡+写假设）→ 候选主题 → 选主题 → 发起 Gate 分析 → 进度/报告页**。

## 前置
- 本地 PostgreSQL（compose 端口映射 55432）+ 已灌种子数据（clusters / heat_points / evidence_cards）。
- 本地 qwen3.6 端点（Ollama，11434）——combo 生成走免费本地档（`FLINT_LOCAL_*`）。
- Node 环境（见 `web/`）。

## 环境变量（照 `.env.example`，NEVER 提交真实值/key）
```
DATABASE_URL=postgresql+asyncpg://flint:flint@localhost:55432/flint
FLINT_LOCAL_BASE_URL=http://localhost:11434/v1
FLINT_LOCAL_MODELS=qwen3.6:27b
FLINT_FREE_TIER_MODEL=qwen3.6:27b
# 付费档（可选，启用 Claude 对比时才设；key 绝不进仓/日志/会话）
# FLINT_ANTHROPIC_API_KEY / FLINT_PAID_TIER_MODEL /
# FLINT_ANTHROPIC_USD_PER_MTOK_INPUT / _OUTPUT
```

## 启动步骤
1. **DB**：`docker compose up -d`（或已运行的本地 PG）；迁移到最新：
   `./.venv/Scripts/python.exe -m alembic upgrade head`（含主题子系统 0017）。
2. **后端 API**：装配三个应用并挂载（同 FastAPI 进程，示例）——
   - `flint.api.views:create_views_app`（广场/工作台/Gate 只读 + 主题只读端点，TS-007）
   - `flint.api.combo:create_combo_app`（`POST /projects/combo`，注入 `LocalProvider`(qwen3.6) + `EmbeddingService`，TS-010）
   - `flint.api.analysis:create_analysis_app`（`topic_keywords_for=make_topic_keywords_resolver(dsn)`，TS-006/010）
   用 `uvicorn` 起在 web 可达的 base（前端 `ViewOpts.baseUrl` 指向它）。
3. **前端**：`cd web && npm run dev`，打开 `http://localhost:3000/demo?day=2026-07-20`。

## 点开跑
- 点「加载当日热点广场」→ 列出当日热点簇；
- 点一个簇 → 工作台列该簇证据卡 + combo 入口；
- combo 入口复选 2~5 张卡（**允许跨簇**）+ 写一句话关联假设 → 点「生成候选主题」；
- 候选主题列出（two-tag / why-now speculative 灰标 / keywords）→ 选一个主题；
- 发起 Gate 分析 → 路由到 `/jobs/{id}` 进度页（L1 渐进交付 → L0/L2 报告 + 指令重生成）。

## 说明
- combo 的「生成候选主题」真机走 qwen3.6:27b（免费本地）；质量口径见
  `docs/主题生成-模型口径报告.md`。**Claude 对比档需 owner 设 `FLINT_ANTHROPIC_*` 后**
  才可用（未设即免费本地档跑，NEVER 贴 key）。
- 前端 `/demo` 与各视图均纯呈现 + 客户端接线（`ViewOpts.baseUrl`/`fetchImpl` 注入），
  离线 vitest 全绿。
