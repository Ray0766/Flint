#!/usr/bin/env bash
# stop-demo.sh — 燧石 Flint 本地 demo 一键关闭（macOS / Linux）
#
# stop-demo.ps1 的 POSIX 对应物。停的顺序是起的逆序（docs/进程编排-v041.md）：
#   前端 :3000 → 后端 :8000 → worker → docker compose stop（postgres / redis）。
# 只停本 demo 起的进程：端口按监听者定位；worker 没有端口，按命令行标记认人；
# .run/ 里的 PID 先核对命令行再停（PID 会被系统复用，NEVER 只凭一个数字杀进程）。
# 容器用 stop：端口释放，数据卷 pgdata 完整保留。全程只发 TERM。

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN="$ROOT/.run"

warn() { printf '    !!  %s\n' "$1"; }

stop_port() {
    _port="$1"; _label="$2"
    if ! command -v lsof >/dev/null 2>&1; then
        warn "找不到 lsof，无法按端口定位 $_label :$_port"
        return
    fi
    _pids="$(lsof -ti "tcp:$_port" -sTCP:LISTEN 2>/dev/null)"
    if [ -z "$_pids" ]; then
        printf '    %s :%s 未在监听（已关或未起）\n' "$_label" "$_port"
        return
    fi
    for _pid in $_pids; do
        # 先收子进程（如 npm → node），再收本体
        pkill -TERM -P "$_pid" 2>/dev/null
        if kill -TERM "$_pid" 2>/dev/null; then
            printf '    已停 %s :%s（PID %s）\n' "$_label" "$_port" "$_pid"
        else
            warn "停 $_label PID $_pid 失败"
        fi
    done
}

# 停 .run/<名字>.pid 记下的那个进程——命令行对得上才停。
stop_recorded() {
    _file="$RUN/$1.pid"; _marker="$2"
    [ -f "$_file" ] || return 0
    _pid="$(cat "$_file" 2>/dev/null)"
    rm -f "$_file"
    [ -n "$_pid" ] || return 0
    _cmd="$(ps -p "$_pid" -o command= 2>/dev/null)"
    case "$_cmd" in
        *"$_marker"*)
            pkill -TERM -P "$_pid" 2>/dev/null
            kill -TERM "$_pid" 2>/dev/null && printf '    已停 %s（PID %s）\n' "$1" "$_pid"
            ;;
    esac
}

printf '==== 燧石 Flint · demo 一键关闭 ====\n'

# ① 前端 :3000 、② 后端 :8000
stop_port 3000 "前端"
stop_recorded frontend "npm run dev"
stop_port 8000 "后端"
stop_recorded backend "harness.demo_server"

# ②b worker + cron：按命令行标记停（与 start-demo.sh 查重用的是同一个标记）
_workers="$(pgrep -f 'harness\.run_worker' 2>/dev/null)"
if [ -n "$_workers" ]; then
    for _pid in $_workers; do
        kill -TERM "$_pid" 2>/dev/null && printf '    已停 worker（PID %s）\n' "$_pid"
    done
else
    printf '    worker 未在运行（已关或未起）\n'
fi
rm -f "$RUN/worker.pid"

# ③ docker compose stop（保留数据卷 pgdata）
if [ -f "$ROOT/compose.yaml" ]; then
    if docker info >/dev/null 2>&1; then
        if (cd "$ROOT" && docker compose stop >/dev/null 2>&1); then
            printf '    已 docker compose stop（postgres / redis 停止，数据保留）\n'
        else
            warn "docker compose stop 返回非零，手动检查 'docker compose ps'"
        fi
    else
        warn "Docker 引擎未就绪，跳过容器停止（若在跑，手动 docker compose stop）"
    fi
fi

printf '\n==== 已关闭 ====\n重开：./start-demo.sh。数据未删除。\n'
