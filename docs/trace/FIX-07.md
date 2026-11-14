# FIX-07 · 缺陷⑦：一键启动脚本的 Docker 路径写死，本机走不通

> v0.4.1 第 5 批第十六张。`depends_on: []`。oneshot。

## 装载清单

`tasks-v041-b5.json#FIX-07` · `start-demo.ps1` 的 Docker 一段 ·
`docs/blocked/SCANNERS-DO-NOT-STRIP-COMMENTS.md`（判据剥注释的既有教训）。
约 4k tokens，**未超 40k**。

## 一、改前/改后

**改前**（`start-demo.ps1:42`）：

```powershell
$dd = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (Test-Path $dd) { Start-Process $dd } else { Warn "未找到 …，请手动启动" }
```

本机是**用户级安装**（`%LOCALAPPDATA%\Programs\DockerDesktop\`），
`Test-Path` 恒 false → 脚本掉进下面的 `Read-Host` 等人敲回车。
**无人值守时那就是挂住**，而挂住在屏上与「Docker 起得慢」长得一模一样
——没人知道该去敲那个回车。

**改后**：三条路依次试，全都找不到就明说并给手动步骤。

1. **从 `docker` CLI 反推**（`…\resources\bin\docker.exe` → 上两层）
   ——这一条最准：CLI 能找到就说明装过；
2. 候选安装路径：`$env:LOCALAPPDATA\Programs\DockerDesktop\` 与
   `$env:ProgramFiles\Docker\Docker\`（还带上 x86 那处）；
3. 都不行 → 打印手动步骤，**NEVER `Read-Host`**。

等待分支同样改掉：等不到引擎就打印三步手动步骤然后 `throw`——
**不卡住 ≠ 装作成功**。

## 二、为什么判据是静态检查

起一次 Docker 要几分钟，而它在 CI 里根本不在（`S2-7`）。
所以判的是**脚本文本**：不含写死的绝对安装路径、候选覆盖两处、
CLI 反推在、等待分支不再挂人、找不到时给得出可执行的手动步骤、
以及**照实失败**（`throw` 还在）。

判据**先剥注释再扫**——本文件与脚本的注释里都逐字写着那条被修掉的写死路径
（说明为什么不能那样写）。不剥的话，判据会把**解释问题的那句话**当成问题本身。
这一形状本仓栽过多次（`SCANNERS-DO-NOT-STRIP-COMMENTS.md`）。

## 三、剩下的 `Read-Host` 说清楚

脚本里还有三处 `Read-Host`，**都在 Ollama 那一段**，本卡不动：
它们问的是「要不要现在拉模型」——**那是真的需要人回答的问题**，
与 Docker 那条「等它起来」不同（后者的答案只有一个：等）。

判据 `test_the_remaining_read_hosts_are_the_ollama_ones` 逐条验它们确实都在 Ollama 段里
——**「改完了」与「只改了一半」NEVER 长得一样**。要不要一起改，留给 owner。

## 四、verify

```
pytest tests/v041/test_start_demo_paths.py -q → 8 passed
```

返工一轮：脚本语法检查那条命令自己写错了（`[ref]$errors` 要求变量先存在，
PowerShell 报 `NonExistingVariableReference`）——**那句话说的是检查命令有病，
不是脚本有语法错**，混起来会让人去改一个没病的脚本。已先声明再传引用。

## 五、self_review（worker.md §4.6）

① **测试覆盖 acceptance**：8 条对三条 acceptance。
「候选覆盖两处」是逐个环境变量点名验的，不是数个数；
另有一条钉住脚本改完之后**仍然解析得过**——语法错的脚本与「Docker 没装」
在屏上也长得一样。
② **无冻结件偏离**：本卡只动 `start-demo.ps1` 与新增判据。
③ **无禁用词**：grep 零命中。
④ **复用断言在位**：剥注释的写法与本仓既有尺子一致。
⑤ **装载未超预算**：≈4k tokens。

## 六、留给下游

Ollama 那三处 `Read-Host` 在无人值守下同样会挂住。它们**问的是真问题**，
所以本卡没动——但若要做完全无人值守，需要给它们一个「非交互默认」
（例如环境变量 `FLINT_ASSUME_YES`）。留给 owner 定。
