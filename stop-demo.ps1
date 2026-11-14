# stop-demo.ps1 — 燧石 Flint 本地 demo 一键关闭（按端口精确关，NEVER 误杀无关进程）
# 关三样：① 前端 :3000（Next dev）② 后端 :8000（uvicorn）③ docker compose stop（PG/redis）。
# 只停「本 demo 起的」进程：先按监听端口定位 owner 进程，再按唯一命令行标记收尾启动器窗口。
# docker 用 stop（非 down -v）：容器停下、端口释放，种子数据卷 pgdata 完整保留，下次 start 秒起。

$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot

function Warn($msg) { Write-Host "    !!  $msg" -ForegroundColor Yellow }

function Stop-ByPort([int]$port, [string]$label) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { Write-Host "    $label :$port 未在监听（已关或未起）" -ForegroundColor DarkGray; return }
    $procIds = $conns.OwningProcess | Sort-Object -Unique
    foreach ($procId in $procIds) {
        if (-not $procId -or $procId -eq 0) { continue }
        try {
            $name = (Get-Process -Id $procId -ErrorAction SilentlyContinue).ProcessName
            # 先收子进程（如 npm→node），再收本体
            Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue |
                ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            Write-Host "    已停 $label :$port（PID $procId $name）" -ForegroundColor Green
        } catch { Warn "停 $label PID $procId 失败：$_" }
    }
}

Write-Host "==== 燧石 Flint · demo 一键关闭 ====" -ForegroundColor White

# ① 前端 :3000 、② 后端 :8000（按端口精确关）
Stop-ByPort 3000 "前端"
Stop-ByPort 8000 "后端"

# ②b worker + cron：无端口，按命令行标记 harness.run_worker 停（见下方 $marks）

# 收尾：仅关掉「本 demo 启动器」留下的 powershell 窗口（按唯一命令行标记，绝不误伤）
# worker 没有监听端口，只能按**命令行标记**认人（按进程名停会连别人的 python 一起杀）。
$marks = 'harness\.demo_server|harness\.run_worker|NEXT_PUBLIC_FLINT_API'
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and ($_.CommandLine -match $marks) } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "    已关启动器窗口（PID $($_.ProcessId)）" -ForegroundColor Green
    }

# ③ docker compose stop（保留数据卷 pgdata）
if (Test-Path (Join-Path $Root "compose.yaml")) {
    Push-Location $Root
    docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        docker compose stop *> $null
        if ($LASTEXITCODE -eq 0) { Write-Host "    已 docker compose stop（postgres/redis 停止，种子数据保留）" -ForegroundColor Green }
        else { Warn "docker compose stop 返回非零，请手动检查 'docker compose ps'" }
    } else {
        Warn "Docker 引擎未就绪，跳过容器停止（若在跑，请手动 docker compose stop）"
    }
    Pop-Location
}

Write-Host "`n==== 已关闭 ====" -ForegroundColor Green
Write-Host "重开：双击 start-demo.bat。数据未删除，下次秒起。" -ForegroundColor White
