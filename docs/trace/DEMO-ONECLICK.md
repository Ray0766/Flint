# DEMO-ONECLICK trace — 一键 demo 开关脚本（owner @2026-07-31，已实测交付）

## 装载清单
- `docs/demo-本地启动.md`（启动步骤参考）、`compose.yaml`（postgres:55432/redis:56379/api·worker=sleep 占位）、
  `migrations/env.py`（DATABASE_URL 默认已是 host 形 localhost:55432）、
  `flint/api/{views,combo,analysis}.py`（三 app factory + ComboCreateRequest/AnalysisSubmitRequest schema）、
  `flint/jobs/{runner,gate1}.py`（PgJobRunner enqueue 钩子 + build_live_deps/run_gate1）、
  `flint/llm/local.py`（LocalProvider 免费本地档）、`flint/evidence/{search,enrich}.py`（GithubArxivSearcher/pin_verdict_citations）、
  `web/lib/{viewsClient,topicClient,jobClient,useJobStream}.ts`（各 client baseUrl 缝）、`web/app/{demo,jobs/[id]}/page.tsx`。

## 交付物
- **合并后端** `harness/demo_server.py`：views+combo+analysis 挂同一 FastAPI/uvicorn(:8000)。
- **前端接线** `web/lib/apiBase.ts`（`API_BASE=NEXT_PUBLIC_FLINT_API ?? ""`）+ `demo/page.tsx`（`opts.baseUrl`）+ `jobs/[id]/page.tsx`（`useJobStream(id,{baseUrl})`）。
- **脚本** `start-demo.ps1`+`start-demo.bat`、`stop-demo.ps1`+`stop-demo.bat`（项目根，双击即用）。

## 决策日志
- **合并入口=纯 ASGI 中间件注 x-user-id**：前端各 client 不发 `X-User-Id`；用 `_InjectUserMiddleware`（scope 级追加 header，
  NEVER 碰 body/receive 流）注 `demo-user`。**踩坑**：起初怀疑 `@app.middleware("http")`（BaseHTTPMiddleware）吞 body；
  换纯 ASGI 后仍报 `error parsing the body` → **真因是 Git Bash `curl -d` 把中文 UTF-8 字节 mangle 成非法 JSON**（测试假象，非中间件/schema）；
  ASCII body 即通。真实前端发合法 UTF-8，无此问题。
- **id_factory 用 uuid（非 count(1)）**：count 每次重启从 demo1 起 → combo 第二次撞 `pk_origins` 唯一键（origin-demo1 已存在）。
  改 `f"demo{uuid.uuid4().hex[:10]}"` → 重复点安全（每次 combo 建新 project）。
- **Gate① 无 arq worker → enqueue 钩子后台跑**：`_gate1_enqueue` 对 `gate1_analysis` 建 LocalProvider+GithubArxivSearcher(resilient)+build_live_deps，
  `asyncio.create_task(run_gate1 → pin_verdict_citations)`；submit 即返 job_id，`/jobs/{id}/events` SSE 报进度。
- **demo 日 07-20→07-04**：owner 给的 `?day=2026-07-20` **无 heat_points 数据**（heat_points 仅 06-29~07-05 七天）。
  06-29 是首个 heat 日→各簇无前日历史→velocity=0→弱信号轨空。逐日扫描：**07-04 = 154 热点主榜 + 弱信号轨有货**
  （solid-state battery，velocity/weak_score=20，早期加速信号，叙事好）→ 定为默认演示日（script $Day + page 默认双改）。
- **PS 5.1 读 ps1 用 GBK → 中文 mojibake**（Windows quirk）：两 .ps1 存 **UTF-8+BOM**（Write 工具默认无 BOM，Python 补 BOM）；否则解析报 "string missing terminator"。
- **stop 精确关**：按监听端口定位 owner 进程(+子进程) Stop-Process；再按唯一命令行标记（`harness.demo_server|NEXT_PUBLIC_FLINT_API`）收尾两个启动器 powershell 窗口；`docker compose stop`（非 down -v，保留种子卷 pgdata）。本 stop 脚本自身命令行=stop-demo.ps1，不匹配标记，NEVER 自杀/误伤。
- **零 key**：脚本只 SET 非密钥 demo 变量（DSN/BASE_URL/MODEL/NEXT_PUBLIC_FLINT_API）；付费 key 由子进程继承 owner 现有 env，本脚本 NEVER 读/写 key（不设即免费本地）。

## 实测（script-started stack，2026-07-04）
- **start-demo happy 路径全过**：Docker 引擎就绪 → compose up -d → PG pg_isready → alembic head → ollama 确认 qwen3.6:35b-a3b → :8000 就绪 → :3000 就绪 → 开浏览器 `/demo?day=2026-07-04`。
- **读端点**：`:8000/plaza/hot?day=2026-07-04` HTTP 200（clusters=154 主榜 top 热搜话题02 hotness 87.75；weak_signals=1 solid-state battery）；`/clusters/c-20260704-000/evidence-cards` 1 卡；`:3000/demo` HTTP 200；CORS `access-control-allow-origin: *`（Origin :3000）。
- **combo（免费 qwen）**：POST /projects/combo（07-04 两簇卡）→ 6 主题，`degraded=false`。
- **Gate①（live）**：POST analysis → job；轮询 `retrieving→judging→done`；`/jobs/{id}/verdict` = `D_insufficient`，3 个 **live arxiv 竞品（真实 arxiv.org/abs URL）**。
  注：该 verdict `key_citation_ids/rationale_fact_ids=0` 是**语义正确**——D_insufficient=证据不足不提升/不引用；早前 06-29 另组 keywords 命中更多则非零。竞品匹配质量受薄种子卡限（=待办 D2「补厚证据」），**管线本身**（live 搜→判→裁）已验证通。
- **幂等**：第二次跑 start-demo → 「后端已在 :8000 运行，复用」「前端已在 :3000 运行，复用」，不双起。
- **stop-demo**：关前端 :3000(node PID)+后端 :8000(python PID)+2 启动器窗口 + docker compose stop；端口 **3000/8000/55432/56379 全释放**（复核绿）。

## 落盘 / 门
- 新增 `harness/demo_server.py`、`web/lib/apiBase.ts`、`start-demo.ps1`、`start-demo.bat`、`stop-demo.ps1`、`stop-demo.bat`；
  改 `web/app/demo/page.tsx`、`web/app/jobs/[id]/page.tsx`（baseUrl 接线 + 默认日 07-04）。
- verify：`ruff check harness/demo_server.py` 净 · `mypy --strict harness/demo_server.py` 净 · web `tsc --noEmit` 净 · `npm test` 63/63 绿 · 台账 append_entry malformed=[]。
- **冻结件不动**（contracts/ 未碰，仅在既有 factory/接口上装配）；**零付费**（免费本地 qwen + 免费公网 github/arxiv）；**脚本零 key**；未改依赖锁（新增仅 stdlib uuid + 既有 httpx/uvicorn/fastapi）。

## 返工记录
- combo 400「error parsing the body」误判为中间件/schema → 隔离出真因是 Git Bash curl 中文 body mangle（测试环境假象）；同因未连续 2 次盲试，定位后即修 id_factory 真 bug。
- ps1 首跑 PS5.1 GBK mojibake 解析失败 → UTF-8+BOM 重存后通过。
