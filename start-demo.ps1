# start-demo.ps1 — 燧石 Flint 本地 demo 一键启动（幂等、重复点安全）
# 做四步：① Docker Desktop + PG(55432) + alembic 迁移；② 确认 Ollama qwen3.6:35b-a3b(11434)；
# ③ 起后端 uvicorn(:8000) + 前端 npm run dev(:3000)，各在独立窗口；④ 打开浏览器 /demo。
# 全程免费本地档、零 API key（key 只从你现有环境继承，本脚本 NEVER 写/读 key）。
# 关闭用 stop-demo.ps1（按端口精确关，不误杀无关进程）。

$ErrorActionPreference = "Stop"
$Root  = $PSScriptRoot
$Day   = "2026-07-04"                       # 最佳演示日：154 热点主榜 + 弱信号轨有货（solid-state battery 早期加速信号）
$Py    = Join-Path $Root ".venv\Scripts\python.exe"
$Model = "qwen3.6:35b-a3b"

function Step($n, $msg) { Write-Host "`n[$n] $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "    OK  $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "    !!  $msg" -ForegroundColor Yellow }

function Test-Port([int]$port) {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $c.Connect("127.0.0.1", $port); $c.Close(); return $true
    } catch { return $false }
}
function Wait-Port([int]$port, [int]$timeoutSec, [string]$label) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port $port) { return $true }
        Start-Sleep -Milliseconds 800
    }
    Warn "$label 端口 $port 在 $timeoutSec 秒内未就绪"; return $false
}

Write-Host "==== 燧石 Flint · demo 一键启动 ====" -ForegroundColor White
Write-Host "项目根：$Root"

if (-not (Test-Path $Py)) { throw "找不到 venv：$Py（先建好 .venv 并装依赖）" }

# ── ① Docker Desktop + PostgreSQL + 迁移 ─────────────────────────────
Step 1 "Docker Desktop / PostgreSQL(55432) / alembic 迁移"
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Warn "Docker 引擎未就绪，尝试启动 Docker Desktop ..."
    # FIX-07：**NEVER 写死安装路径。** 本机是用户级安装
    # （%LOCALAPPDATA%\Programs\DockerDesktop\），写死成 Program Files 那一条时
    # `Test-Path` 恒 false → 脚本掉进下面的 `Read-Host` 等人敲回车，
    # **无人值守时那就是挂住**（而挂住看起来与「Docker 起得慢」一模一样）。
    #
    # 三条路依次试，全都找不到就**明说找不到并给手动步骤**，NEVER 卡住：
    #   ① 候选安装路径（覆盖 Program Files 与 LOCALAPPDATA 两处）；
    #   ② 从 `docker` CLI 的实际位置反推（CLI 在 …
esourcesin\docker.exe，
    #      桌面端在它上两层）——**这一条最准**：CLI 能找到就说明装过；
    #   ③ 都不行 → 打印手动步骤。
    $ddCandidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe'),
        (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Docker\Docker\Docker Desktop.exe')
    )
    $cli = (Get-Command docker -ErrorAction SilentlyContinue).Source
    if ($cli) {
        # …
esourcesin\docker.exe → …\Docker Desktop.exe
        $guess = Join-Path (Split-Path (Split-Path (Split-Path $cli))) 'Docker Desktop.exe'
        $ddCandidates = @($guess) + $ddCandidates
    }
    $dd = $ddCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if ($dd) {
        Start-Process $dd | Out-Null
    } else {
        Warn "没找到 Docker Desktop 的可执行文件。手动启动它（开始菜单搜 Docker Desktop），"
        Warn "等鲸鱼图标稳定后重跑本脚本；或先跑 'docker info' 确认引擎已就绪。"
    }
    $deadline = (Get-Date).AddSeconds(180)
    while ((Get-Date) -lt $deadline) {
        docker info *> $null
        if ($LASTEXITCODE -eq 0) { break }
        Start-Sleep -Seconds 3
    }
    if ($LASTEXITCODE -ne 0) {
        # FIX-07：**NEVER 用 Read-Host 卡住**。无人值守时它会一直等在那里，
        # 而屏上看起来与「Docker 起得慢」一模一样——没人知道该去敲回车。
        # 改成明说找不到并给手动步骤，然后照实失败。
        Warn "  Docker 仍未就绪（等了 180 秒）。手动步骤："
        Warn "    1. 启动 Docker Desktop，等鲸鱼图标稳定；"
        Warn "    2. 跑 'docker info' 确认引擎就绪；"
        Warn "    3. 重跑本脚本。"
        throw "Docker 引擎不可用，无法起 PG。"
    }
}
Ok "Docker 引擎就绪"

Push-Location $Root
docker compose up -d | Out-Null
Ok "docker compose up -d（postgres:55432 / redis:56379）"

Write-Host "    等待 PostgreSQL 就绪 ..." -NoNewline
$pgReady = $false
$deadline = (Get-Date).AddSeconds(120)
while ((Get-Date) -lt $deadline) {
    docker compose exec -T postgres pg_isready -U flint -d flint *> $null
    if ($LASTEXITCODE -eq 0) { $pgReady = $true; break }
    Write-Host "." -NoNewline; Start-Sleep -Seconds 2
}
Write-Host ""
if (-not $pgReady) { Pop-Location; throw "PostgreSQL 120 秒内未就绪。" }
Ok "PostgreSQL 就绪"

$env:DATABASE_URL = "postgresql+asyncpg://flint:flint@localhost:55432/flint"
& $Py -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "alembic upgrade head 失败。" }
Ok "数据库迁移到 head"

# 测试库 flint_test：建库 + 迁移 + 大类种子（三步都幂等，重复点安全）。
# 演示库与测试库分家之后，跑 pytest 不再动 demo 数据——这一步就是分家的落地前提。
# 注意 Postgres 的 CREATE DATABASE 没有 IF NOT EXISTS，脚本里是先查 pg_database 再建；
# compose 的 initdb 脚本只在数据卷首次创建时跑，对既有 pgdata 卷是空操作，故走运行时这条路。
& $Py scripts\provision_test_db.py
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "测试库 flint_test 备置失败（建库/迁移/种子）。" }
Ok "测试库 flint_test 就绪（pytest 不再碰 demo 数据）"

# 报告屏夹具：演示库与测试库是同一个 PG，跑测试会把 deliverables 清掉，
# 于是报告屏变 404。这里每次启动都幂等重灌一次，让它自愈。
# 它只写 deliverables/blocks 两张表，不跑生成、不联网、不花钱；
# 正文是脚本写死的夹具（del-demo-fixture- 前缀即标记），NEVER 冒充模型产出。
& $Py -m harness.demo_seed_report
if ($LASTEXITCODE -ne 0) { Warn "报告夹具灌入失败；报告屏会显 404（其余流程不受影响）。" }
else { Ok "报告夹具就绪（del-demo-fixture-report）" }
Pop-Location

# ── ② Ollama + 免费本地模型 ──────────────────────────────────────────
Step 2 "确认 Ollama($Model) 在 11434"
while ($true) {
    $tags = $null
    try { $tags = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 8 } catch { $tags = $null }
    if ($null -eq $tags) {
        Read-Host "  Ollama(11434) 不可达。请启动 Ollama（命令行 'ollama serve' 或桌面应用），然后按回车重试"
        continue
    }
    $names = @($tags.models | ForEach-Object { $_.name })
    if ($names -contains $Model) { Ok "本地模型就绪：$Model"; break }
    Warn "未发现模型 $Model。当前已装：$($names -join ', ')"
    $ans = Read-Host "  运行 'ollama pull $Model' 拉取？(y=现在拉 / 回车=我自己拉后重试 / n=中止)"
    if ($ans -eq "n") { throw "缺少免费本地模型 $Model，已中止。" }
    if ($ans -eq "y") { ollama pull $Model }
}

# ── ③ 后端 uvicorn(:8000) + 前端 npm run dev(:3000) ──────────────────
Step 3 "起后端(:8000) + 前端(:3000)"

# 后端：幂等——已在跑就复用
$backendUp = $false
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/plaza/hot?day=$Day" -UseBasicParsing -TimeoutSec 5
    if ($r.StatusCode -eq 200) { $backendUp = $true }
} catch { $backendUp = $false }
if ($backendUp) {
    Ok "后端已在 :8000 运行，复用"
} else {
    $backendCmd = @"
`$Host.UI.RawUI.WindowTitle = 'Flint Backend :8000'
`$env:FLINT_DEMO_DSN = 'postgresql://flint:flint@localhost:55432/flint'
`$env:FLINT_LOCAL_BASE_URL = 'http://localhost:11434/v1'
`$env:FLINT_FREE_TIER_MODEL = '$Model'
Set-Location '$Root'
& '$Py' -m harness.demo_server
"@
    Start-Process powershell -ArgumentList '-NoExit','-Command',$backendCmd -WindowStyle Normal | Out-Null
    Write-Host "    等待后端 :8000 ..." -NoNewline
    $ready = $false; $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/plaza/hot?day=$Day" -UseBasicParsing -TimeoutSec 4
            if ($r.StatusCode -eq 200) { $ready = $true; break }
        } catch {}
        Write-Host "." -NoNewline; Start-Sleep -Seconds 2
    }
    Write-Host ""
    if (-not $ready) { throw "后端 :8000 未在 90 秒内就绪，请看新弹出的『Flint Backend』窗口日志。" }
    Ok "后端就绪（合并 views+combo+analysis，combo/Gate 走免费本地 $Model）"
}

# 前端：幂等——已在跑就复用
if (Test-Port 3000) {
    Ok "前端已在 :3000 运行，复用"
} else {
    if (-not (Test-Path (Join-Path $Root "web\node_modules"))) {
        Warn "web\node_modules 缺失，先 npm install（首次较慢）..."
        Push-Location (Join-Path $Root "web"); npm install; Pop-Location
    }
    $frontCmd = @"
`$Host.UI.RawUI.WindowTitle = 'Flint Frontend :3000'
`$env:NEXT_PUBLIC_FLINT_API = 'http://localhost:8000'
# 服务器组件读的是**没有 NEXT_PUBLIC_ 前缀的那一份**（web/app/deliverables/[id]/page.tsx）。
# 少了它，基址为空 → Node 侧 fetch("/deliverables/…/blocks") 是相对 URL →
# Failed to parse URL → 该路由恒 500。两份都要设：一份给服务端，一份给客户端。
`$env:FLINT_API_BASE = 'http://localhost:8000'
# PLAZA-04：写数据的端点（收藏/分享）要一个身份头。本仓还没有真的登录态，
# 在那之前它由部署配置给——**没配就不发那个头**，服务端会照实拒绝，
# 屏上显示服务端自己的说明，而不是我们假装有一个用户。
# FIX-16：这里原本是 'self'，而 demo 库里**没有任何东西属于 self**——
# 项目、作业、事实全部挂在 `demo-user` 名下（探针用的也是它）。
# 于是配了身份反而比匿名看到的更少：`GET /facts/{id}` 对 self 回 404
# （404 而不是 403：状态码本身不泄露存在性），报告屏整片丢内容。
# 身份要指向**真正持有这批 demo 数据的那个人**，否则「配了身份」等于没配。
`$env:NEXT_PUBLIC_FLINT_USER_ID = 'demo-user'
Set-Location '$Root\web'
npm run dev
"@
    Start-Process powershell -ArgumentList '-NoExit','-Command',$frontCmd -WindowStyle Normal | Out-Null
    Write-Host "    等待前端 :3000 ..." -NoNewline
    if (Wait-Port 3000 150 "前端") { Write-Host ""; Ok "前端就绪（Next dev，API 指向 :8000）" }
    else { Write-Host ""; throw "前端 :3000 未就绪，请看『Flint Frontend』窗口日志。" }
}

# ── ③b worker + cron（消费作业与定时批）────────────────────────────
# 改之前：作业在 API 进程里用 asyncio.create_task 跑，队列形同虚设，关掉 API 窗口
# 正在跑的作业就没了（而 jobs 表里它还写着 running），cron 一次都没触发过。
# 现在把 build_worker + build_cron_jobs 接成独立进程，晚起只是晚跑、不会丢。
Step "3b" "起 worker + cron（无监听端口，按命令行标记查重）"
$workerMark = 'harness.run_worker'
$existing = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and ($_.CommandLine -match [regex]::Escape($workerMark)) }
if ($existing) {
    Ok "worker 已在运行，复用（PID $($existing.ProcessId -join ', ')）"
} else {
    $workerCmd = @"
`$Host.UI.RawUI.WindowTitle = 'Flint Worker + Cron'
`$env:FLINT_DEMO_DSN = 'postgresql://flint:flint@localhost:55432/flint'
`$env:FLINT_REDIS_URL = 'redis://localhost:56379/0'
`$env:FLINT_LOCAL_BASE_URL = 'http://localhost:11434/v1'
`$env:FLINT_FREE_TIER_MODEL = '$Model'
Set-Location '$Root'
& '$Py' -m harness.run_worker
"@
    Start-Process powershell -ArgumentList '-NoExit','-Command',$workerCmd -WindowStyle Normal | Out-Null
    Start-Sleep -Seconds 2
    Ok "worker 已起（消费队列 + 日更/复核 cron；进程编排见 docs/进程编排-v041.md）"
}

# ── ④ 打开浏览器 ────────────────────────────────────────────────────
Step 4 "打开浏览器"
$url = "http://localhost:3000/demo?day=$Day"
Start-Process $url | Out-Null
Ok $url

Write-Host "`n==== 启动完成 ====" -ForegroundColor Green
Write-Host "演示路径：广场(热度主榜+弱信号轨) → 点簇 → 工作台证据卡 → combo 生成主题[免费 $Model]" -ForegroundColor White
Write-Host "         → 选主题 → Gate 分析[live 真实 github/arxiv + 本地 qwen] → 报告进度页" -ForegroundColor White
Write-Host "后端/前端/worker 各在独立窗口运行（关掉窗口或跑 stop-demo 即可停）。" -ForegroundColor White
Write-Host "停止：双击 stop-demo.bat（或 powershell -File stop-demo.ps1）" -ForegroundColor White
