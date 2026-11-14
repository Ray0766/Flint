# 连跑-overnight.ps1 — 外层重启循环（worker.md §7 那个「外层重启循环」的实体）
#
# 与 /loop 的区别：/loop 往**同一个会话**再发一遍，上下文用尽时循环跟着死；
# 本脚本每轮拉起一个**全新的 claude 会话**，上下文用尽是正常翻页而不是故障。
#
# 用法（在项目根目录）：
#   powershell -File docs\steward\连跑-overnight.ps1
#   powershell -File docs\steward\连跑-overnight.ps1 -MaxIterations 30 -DryRun
#
# 三道自停闸，任一触发即退出：
#   ① DONE 标记出现（正常收工）
#   ② 迭代数达上限（防跑飞）
#   ③ 台账连续 N 轮不涨（全卡 blocked 在等 owner，再跑也是空转）
#
# 停不下来时：Ctrl+C，或删掉 .overnight-stop 那一步——见 -StopFile。

param(
  [string] $WorkOrder     = "docs\steward\常备连跑工单-v041-第10批.md",
  [string] $DoneMarker    = "docs\FLINT-V041-B10-DONE",
  [string] $Ledger        = "docs\progress-v041.jsonl",
  [int]    $MaxIterations = 20,
  [int]    $StagnantLimit = 3,
  [string] $LogDir        = "docs\steward\overnight-logs",
  [string] $StopFile      = ".overnight-stop",
  [switch] $DryRun
)

$ErrorActionPreference = "Stop"
$Root = (Get-Location).Path

function Say($msg, $color = "White") {
  Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg) -ForegroundColor $color
}

# ── 前置检查：缺一个就别开跑，NEVER 让它在半夜里静静地空转 ──────────────
if (-not (Test-Path $WorkOrder))  { throw "找不到工单：$WorkOrder" }
if (-not (Test-Path $Ledger))     { throw "找不到台账：$Ledger" }
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { throw "claude CLI 不在 PATH 上" }
if (Test-Path $DoneMarker) { Say "DONE 标记已存在（$DoneMarker）——这一批已经收工了，无事可做。" Yellow; exit 0 }
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force $LogDir | Out-Null }

# ── 活人检测：已经有 worker 在跑就别开第二个 ─────────────────────────────
# **NEVER 只看锁的 mtime**：worker.md 只要求收卡时刷新锁，而一张卡要跑 20~90 分钟——
# 活着的 worker 在卡中间看起来和死了一样。所以再看一眼「盘上有没有人在写文件」。
function Test-WorkerAlive([int] $QuietMinutes = 10) {
  $cut  = (Get-Date).AddMinutes(-$QuietMinutes)
  $dirs = @("docs\trace", "tests", "flint", "web\app", "web\components", "web\lib") |
          Where-Object { Test-Path $_ }
  $hot = @()
  if (Test-Path "docs\WORKER.lock") {
    if ((Get-Item "docs\WORKER.lock").LastWriteTime -gt $cut) { $hot += "docs\WORKER.lock" }
  }
  $hot += Get-ChildItem $dirs -Recurse -File -ErrorAction SilentlyContinue |
          Where-Object { $_.FullName -notmatch 'node_modules|\.venv|\.next|__pycache__' -and
                         $_.LastWriteTime -gt $cut } |
          Select-Object -First 3 -ExpandProperty FullName
  if ((Get-Item $Ledger).LastWriteTime -gt $cut) { $hot += $Ledger }
  return $hot
}

$alive = Test-WorkerAlive
if ($alive.Count -gt 0) {
  Say "盘上最近 10 分钟有人在写——**已经有 worker 在跑**，不开第二个。" Red
  $alive | Select-Object -First 4 | ForEach-Object { Say "    $_" Red }
  Say "等它收工（或先停掉它）再跑本脚本。两个 worker 会互相清空测试库。" Red
  exit 1
}

# 工单正文 = 提示词。取 ``` 围栏之间那一段；没有围栏就取全文。
$raw = Get-Content $WorkOrder -Raw -Encoding UTF8
$fenced = [regex]::Match($raw, '(?s)```\s*(.+?)```')
$Prompt = if ($fenced.Success) { $fenced.Groups[1].Value.Trim() } else { $raw.Trim() }
if ($Prompt.Length -lt 200) { throw "提示词只有 $($Prompt.Length) 字符，像是取错了段落——先检查 $WorkOrder" }

Say "外层重启循环启动" Cyan
Say "  工单     $WorkOrder（提示词 $($Prompt.Length) 字符）"
Say "  DONE     $DoneMarker"
Say "  上限     $MaxIterations 轮 · 台账连续 $StagnantLimit 轮不涨即停"
Say "  日志     $LogDir\iter-NN.log"
Say "  急停     在项目根建一个名叫 $StopFile 的文件"
if ($DryRun) { Say "（DryRun：只打印，不真的起会话）" Yellow }

$lastCount = (Get-Content $Ledger | Where-Object { $_.Trim() }).Count
$stagnant  = 0
Say "台账起点：$lastCount 行"

for ($i = 1; $i -le $MaxIterations; $i++) {

  if (Test-Path $DoneMarker) { Say "DONE 标记出现 → 收工。" Green; break }
  if (Test-Path $StopFile)   { Say "发现急停文件 $StopFile → 停。" Yellow; break }

  $log = Join-Path $LogDir ("iter-{0:D2}.log" -f $i)
  Say "── 第 $i 轮开跑（新会话）→ $log" Cyan

  if ($DryRun) {
    Say "  DryRun：跳过实跑" Yellow
  } else {
    # 每轮都是全新会话：NEVER 用 --continue / --resume，那会把上一轮用尽的上下文一起拖进来。
    # 权限：见脚本末尾那段说明——这一条是 owner 的选择，不是脚本替他做的决定。
    $env:PYTHONIOENCODING = "utf-8"
    try {
      $Prompt | & claude -p --dangerously-skip-permissions --add-dir $Root *>&1 |
        Tee-Object -FilePath $log
    } catch {
      Say "  这一轮异常退出：$_" Red
      $_ | Out-File -Append -Encoding utf8 $log
    }
  }

  # 进展判定只认台账——**NEVER 拿「会话跑完了」当成「有进展」**：
  # 上下文用尽而一张卡都没收，会话照样正常退出。
  $now = (Get-Content $Ledger | Where-Object { $_.Trim() }).Count
  if ($now -gt $lastCount) {
    Say "  台账 $lastCount → $now（+$($now - $lastCount)）" Green
    $lastCount = $now; $stagnant = 0
  } else {
    $stagnant++
    Say "  台账没涨（连续 $stagnant / $StagnantLimit 轮）" Yellow
    if ($stagnant -ge $StagnantLimit) {
      Say "连续 $StagnantLimit 轮零进展 → 停。多半是所有卡都 blocked 在等 owner，去读台账末尾与 docs/blocked/。" Yellow
      break
    }
  }
}

Say "── 循环结束 ──" Cyan
if (Test-Path $DoneMarker) {
  Say "结果：这一批收工了（$DoneMarker 在盘上）。下一步 = 让 steward 做收工复核。" Green
} else {
  Say "结果：**没有**收工。台账现在 $lastCount 行；读末 20 行与 docs/blocked/ 看卡在哪。" Yellow
}

# ── 关于 --dangerously-skip-permissions（owner 要知道的三件事）────────────
# 1. 它绕过**全部**权限确认。整夜无人值守时，护栏只剩提示词里的纪律
#    （worker.md §7 事前必审四类、DEC-052 的域名与额度边界）——那是文字，不是闸门。
# 2. `.claude/settings.json` 里的 deny 规则**能不能挡住它，steward 没有实测过**。
#    要靠 deny 兜底的话，先自己验一次，NEVER 假设它生效。
# 3. 想要更紧的话，把上面那行换成白名单式：
#      & claude -p --permission-mode acceptEdits --allowedTools "Bash(pytest*) Bash(git*) Edit Write Read Glob Grep" ...
#    代价是遇到没列进白名单的命令会停下等人——整夜跑就断在那儿。
#    紧与不断，只能挑一个。
