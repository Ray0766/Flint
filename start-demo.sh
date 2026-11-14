#!/usr/bin/env bash
# start-demo.sh — 燧石 Flint 本地 demo 一键启动（macOS / Linux；幂等，重复跑安全）
#
# start-demo.ps1 的 POSIX 对应物：进程、端口、环境变量名与它逐项相同
# （判据 tests/v041/test_start_demo_sh.py 逐项对）。两处有意不同：
#   ① 没有「新窗口」：后端 / 前端 / worker 各在后台跑，日志与 PID 落在 .run/；
#   ② NEVER 探测、NEVER 拉取本地模型（owner 2026-11-14 裁决：本地模型那条路先不做）。
#      模型端点只从环境透传——仓根有 .env 就整份导入，本脚本不解析其中任何一项。
#
# 做四步：① Docker + PG(55432) + redis(56379) + alembic 迁移；② 报告模型端点配没配；
#         ③ 起后端(:8000) + 前端(:3000) + worker；④ 打开浏览器 /demo。
# 本脚本 NEVER 写、NEVER 打印任何密钥。关闭用 stop-demo.sh。
#
# 兼容 macOS 自带的 bash 3.2：不用关联数组、mapfile、大小写展开。

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAY="2026-07-04"   # 演示日：harness.replay30 默认回放窗口（06-24 至 07-23）之内
PY="$ROOT/.venv/bin/python"
RUN="$ROOT/.run"

step() { printf '\n[%s] %s\n' "$1" "$2"; }
ok()   { printf '    OK  %s\n' "$1"; }
warn() { printf '    !!  %s\n' "$1"; }
fail() { printf '\n失败：%s\n' "$1" >&2; exit 1; }

port_open() {
    if command -v nc >/dev/null 2>&1; then
        nc -z 127.0.0.1 "$1" >/dev/null 2>&1
    else
        (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
    fi
}

http_ok() {
    [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time "$2" "$1" 2>/dev/null)" = "200" ]
}

# poll <次数> <间隔秒> <命令...>：命令成功即返回 0，次数用尽返回 1。
poll() {
    _tries="$1"; _gap="$2"; shift 2
    _i=0
    while [ "$_i" -lt "$_tries" ]; do
        if "$@"; then return 0; fi
        sleep "$_gap"
        _i=$((_i + 1))
    done
    return 1
}

docker_ready() { docker info >/dev/null 2>&1; }
pg_ready() { docker compose exec -T postgres pg_isready -U flint -d flint >/dev/null 2>&1; }
backend_ready() { http_ok "http://127.0.0.1:8000/plaza/hot?day=$DAY" 4; }
frontend_ready() { port_open 3000; }

printf '==== 燧石 Flint · demo 一键启动 ====\n项目根：%s\n' "$ROOT"

[ -x "$PY" ] || fail "找不到 venv 解释器 .venv/bin/python（先按 docs/macOS-安装.md 建 venv 并装依赖）"
command -v docker >/dev/null 2>&1 || fail "找不到 docker 命令（先装 Docker Desktop 或 OrbStack，见 docs/macOS-安装.md）"
command -v curl >/dev/null 2>&1 || fail "找不到 curl 命令"
cd "$ROOT" || fail "进不了项目根：$ROOT"

if [ -f "$ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$ROOT/.env"
    set +a
fi

# ── ① Docker + PostgreSQL + 迁移 ─────────────────────────────────────
step 1 "Docker / PostgreSQL(55432) / redis(56379) / alembic 迁移"
if ! docker_ready; then
    warn "Docker 引擎未就绪，尝试启动 ..."
    if [ "$(uname -s)" = "Darwin" ]; then
        open -ga Docker >/dev/null 2>&1 \
            || open -ga OrbStack >/dev/null 2>&1 \
            || warn "没找到 Docker Desktop 或 OrbStack 应用，本脚本起不了引擎。"
    else
        warn "非 macOS：本脚本不代为启动 Docker 守护进程。"
    fi
    if ! poll 60 3 docker_ready; then
        warn "Docker 仍未就绪（已轮询 180 秒）。手动步骤："
        warn "  1. 启动 Docker Desktop（或 OrbStack / colima start），直到引擎稳定；"
        warn "  2. 跑 'docker info' 确认引擎就绪；"
        warn "  3. 重跑本脚本。"
        fail "Docker 引擎不可用，无法起 PG。"
    fi
fi
ok "Docker 引擎就绪"

docker compose up -d >/dev/null || fail "docker compose up -d 失败。"
ok "docker compose up -d（postgres:55432 / redis:56379）"

poll 60 2 pg_ready || fail "PostgreSQL 120 秒内未就绪。"
ok "PostgreSQL 就绪"

export DATABASE_URL="postgresql+asyncpg://flint:flint@localhost:55432/flint"
"$PY" -m alembic upgrade head || fail "alembic upgrade head 失败。"
ok "数据库迁移到 head"

# 测试库 flint_test：建库 + 迁移 + 大类种子（三步都幂等）。演示库与测试库分家，
# 跑 pytest 不动 demo 数据。
"$PY" scripts/provision_test_db.py || fail "测试库 flint_test 备置失败（建库/迁移/种子）。"
ok "测试库 flint_test 就绪"

# 报告屏夹具：只写 deliverables/blocks 两张表，不跑生成、不联网。
if "$PY" -m harness.demo_seed_report; then
    ok "报告夹具就绪（del-demo-fixture-report）"
else
    warn "报告夹具灌入失败；报告屏会显 404（其余流程不受影响）。"
fi

# ── ② 模型端点：只报告配没配，不探测 ─────────────────────────────────
step 2 "模型端点（只透传，不探测）"
if [ -n "${FLINT_LOCAL_BASE_URL:-}" ] && [ -n "${FLINT_FREE_TIER_MODEL:-}" ]; then
    ok "已配置模型：$FLINT_FREE_TIER_MODEL（端点取自 FLINT_LOCAL_BASE_URL）"
else
    warn "FLINT_LOCAL_BASE_URL / FLINT_FREE_TIER_MODEL 没配齐。"
    warn "生成类功能（combo 主题、Gate 分析）调用模型时会失败；见 docs/macOS-安装.md 的「模型端点」一节。"
fi

# ── ③ 后端(:8000) + 前端(:3000) + worker ─────────────────────────────
step 3 "起后端(:8000) + 前端(:3000) + worker"
mkdir -p "$RUN" || fail "建不了运行目录 .run/"

# 后端：幂等——已在跑就复用
if backend_ready; then
    ok "后端已在 :8000 运行，复用"
else
    FLINT_DEMO_DSN="postgresql://flint:flint@localhost:55432/flint" \
    FLINT_REDIS_URL="redis://localhost:56379/0" \
        nohup "$PY" -m harness.demo_server >"$RUN/backend.log" 2>&1 &
    echo "$!" >"$RUN/backend.pid"
    poll 45 2 backend_ready || fail "后端 :8000 未在 90 秒内就绪，日志：.run/backend.log"
    ok "后端就绪（日志 .run/backend.log）"
fi

# 前端：幂等——已在跑就复用
if frontend_ready; then
    ok "前端已在 :3000 运行，复用"
else
    if [ ! -d "$ROOT/web/node_modules" ]; then
        warn "web/node_modules 缺失，先 npm ci（按 package-lock.json 装，首次较慢）..."
        (cd "$ROOT/web" && npm ci) || fail "npm ci 失败。"
    fi
    # 两份 API 基址都要设：NEXT_PUBLIC_ 那份给浏览器，没有前缀那份给服务器组件
    # （少了后者，报告路由在 Node 侧 fetch 相对 URL，恒 500）。
    # 身份指向持有 demo 数据的那个用户：库里的项目、作业、事实都挂在 demo-user 名下。
    (
        cd "$ROOT/web" || exit 1
        NEXT_PUBLIC_FLINT_API="http://localhost:8000" \
        FLINT_API_BASE="http://localhost:8000" \
        NEXT_PUBLIC_FLINT_USER_ID="demo-user" \
            nohup npm run dev >"$RUN/frontend.log" 2>&1 &
        echo "$!" >"$RUN/frontend.pid"
    )
    poll 75 2 frontend_ready || fail "前端 :3000 未在 150 秒内就绪，日志：.run/frontend.log"
    ok "前端就绪（Next dev，API 指向 :8000，日志 .run/frontend.log）"
fi

# worker + cron：没有监听端口，按命令行标记查重（停脚本按同一个标记认人）。
if pgrep -f "harness.run_worker" >/dev/null 2>&1; then
    ok "worker 已在运行，复用"
else
    FLINT_DEMO_DSN="postgresql://flint:flint@localhost:55432/flint" \
    FLINT_REDIS_URL="redis://localhost:56379/0" \
        nohup "$PY" -m harness.run_worker >"$RUN/worker.log" 2>&1 &
    echo "$!" >"$RUN/worker.pid"
    sleep 2
    if kill -0 "$(cat "$RUN/worker.pid")" 2>/dev/null; then
        ok "worker 已起（消费队列 + 日更/复核 cron，日志 .run/worker.log）"
    else
        fail "worker 起后即退，日志：.run/worker.log"
    fi
fi

# ── ④ 打开浏览器 ─────────────────────────────────────────────────────
step 4 "打开浏览器"
URL="http://localhost:3000/demo?day=$DAY"
if [ "$(uname -s)" = "Darwin" ]; then
    open "$URL" >/dev/null 2>&1 || warn "open 没成功，手动打开上面的地址。"
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 || warn "xdg-open 没成功，手动打开上面的地址。"
fi
ok "$URL"

printf '\n==== 启动完成 ====\n'
printf '后端 / 前端 / worker 在后台运行，日志在 .run/ 下。\n'
printf '停止：./stop-demo.sh（容器只 stop，数据卷保留）\n'
