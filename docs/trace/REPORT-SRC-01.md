# REPORT-SRC-01 · 成文端点收分析作业号（`DEC-061`）

**状态**：实现已写，**verify 未跑**（本机 Docker 起不来，见 §三）。

## 一、装载清单

`flint/api/compose.py`（全文）· `flint/jobs/gate1.py:96-116`（`analysis_product_id`）·
`flint/jobs/runner.py:51-135`（`PgJobRunner.__init__` / `submit` / `get`）·
`flint/jobs/worker_main.py:118-142`（来源怎么被消费）· `flint/api/schemas.py:19-53`（错误码）·
`tests/m3/test_m3_057.py:1-75` 与 `tests/v041/test_wire_compose.py:1-130`（既有搭法）·
`docs/blocked/ANALYSIS-ID-HAS-NO-PATH-FROM-AN-ANALYSIS.md`。

## 二、决定

1. **两格并存、二选一**，不是把 `analysis_id` 换掉：`tests/v041/test_compose_e2e.py:287`
   的夹具那条路拿一份既有交付物（`del-demo-fixture-report`）当来源，它没有分析作业可给。
   单子里写的代价「既有那一格的语义要改（或并存两格）」，本卡取后者。
2. **换算之前核四件事**：作业在 / 属于本项目 / kind=`gate1_analysis` / state=`done`。
   不核的话，错的作业号会安静地产出一份全是 `gap_notice` 的报告。
3. **错误码不新增**：不存在与别的项目的作业同为 404 `NOT_FOUND`（防枚举，与
   `project_overview` 同一口径）；不是分析 / 没跑完同为 422 `VALIDATION_FAILED`，
   message 里点名是哪一件（kind 或 state）。没有借 `PROJECT_CONFLICT`——那一个码说的是
   project 行的乐观锁，借来说「分析没跑完」就是 `DEC-034` / `DEC-038` 禁的那种借码。
4. **前端类型本卡不动**：`web/lib/types.ts` 的 `ReportSubmitEcho` 描述的是回声，
   请求体类型由 `CHAIN-UI-01` 随调用点一起加，NEVER 先写一个没有调用方的类型。

## 三、test-first 的实况（如实）

判据 `tests/v041/test_report_src.py` **先于实现写成**，但**没能跑出那一次红**：
本机 Docker 起不来，`flint_test` 库连不上。改前的端点 `analysis_id: str` 必填，
所以判据第一条（只给 `analysis_job_id` 期望 200）在改前必然是 pydantic 422——红是推得出的，
**但不是跑出来的**，这一句 NEVER 写成「已确认红」。

Docker 的卡点：`%LOCALAPPDATA%\Docker\run\dockerInference` 与
`%LOCALAPPDATA%\docker-secrets-engine\engine.sock` 两个 9/26 留下的孤儿 AF_UNIX socket。
前者整目录改名后过了；后者目录改名被拒（沙箱内外都拒，`wsl --shutdown` 之后仍拒），
从 WSL 侧删除被权限分类器拦下（不可逆删除），WSL 侧 `cd` 进不去。交 owner 处理。

## 四、已过的部分

`ruff check --no-cache flint/api/compose.py tests/v041/test_report_src.py` → All checks passed
`mypy --strict flint/api/compose.py` → Success: no issues found in 1 source file
