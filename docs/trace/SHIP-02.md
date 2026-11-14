# SHIP-02 · 进程编排落地（文档 + 起停脚本带上 worker 与 cron）

**卡** `tasks-v041-b2.json#SHIP-02` · **开工** 机器 UTC 2026-08-04T04:04Z

## 1. 装载清单

卡面 SHIP-02 · `start-demo.ps1` / `stop-demo.ps1` 全文 ·
`flint/jobs/worker_main.py#build_worker` 与 `WorkerDeps` 字段 ·
`flint/jobs/cron.py#build_cron_jobs` 签名（四个注入点）·
`harness/demo_server.py` 的 `asyncio.create_task` 临时钩子 ·
`harness/e2e_smoke.py#_consume`（worker 在协程内构造的既有写法）。约 8k tokens。

## 2. 顺序（§4.2）

测试先落盘先跑红（**18 failed / 5 passed**）→ worker 入口 → 文档 → 两脚本 →
24 passed。连续第三十张。

## 3. 缺的是「有人调它们」

`build_worker` 与 `build_cron_jobs` 都在，但**没有任何进程调**——demo 走的是
`asyncio.create_task(_run())`：

- 作业在 **API 进程里**跑，队列形同虚设；
- 关掉 API 窗口，正在跑的作业就没了，而 `jobs` 表里它还写着 running；
- **cron 一次都没触发过**（时刻定义在 `sched.CRON_BATCHES` / `revalidation.SCAN_HOUR`，
  没有进程按它走）。

本卡建 `harness/run_worker.py` 把两件接起来，并让起停脚本带上它。
**那条临时钩子没有删**：demo_server 仍能单独跑——先有一条能跑的，再有一条对的。

## 4. cron 钩子要出声

本机面不接真实源（§7 事前必审），所以两个 cron 钩子是空的——但它们**打印一行**：

> 一条什么都不做又不出声的定时任务，与「定时任务没起来」在日志上长得一模一样。

## 5. 幂等：worker 没有端口可探

api 与前端都能探端口，worker 不能。按**命令行标记** `harness.run_worker` 查重：
查到就复用、NEVER 起第二份。停脚本按**同一个标记**认人——两边用不同标记就会
关不掉自己起的那个；**按标记停而不是按进程名停**，按 `python.exe` 停会连别人的
python 一起杀。

## 6. 真跑一次（不是只查源码）

`test_the_worker_can_actually_be_built_and_run_in_burst` 起真 worker（burst 口径）：
连上本机 redis、消费空队列后退出。

**这条当场救了一次**：首版直接 `asyncio.run` 一个在协程**外**构造的 Worker →
`RuntimeError: got Future attached to a different loop`（arq 的 Worker 在构造时
绑定事件循环）。只查源码里有 `build_worker` 三个字的话，这个错会一直留到有人
双击起停脚本的那一刻。改法照 `harness/e2e_smoke.py#_consume` 的既有写法：
**在协程内部构造**。

## 7. 变异考：七个里**先活了六个**——本卡最重要的一段

| 变异 | 首版 | 补判后 |
|---|---|---|
| ① 起脚本不查重就起第二份（`if ($false)`） | **24 passed** ✗ | **1 failed** ✓ |
| ② 起脚本不起 worker（`-m harness.nothing`） | **24 passed** ✗ | **1 failed** ✓ |
| ③ 停脚本的 `$marks` 认不出 worker | **24 passed** ✗ | **1 failed** ✓ |
| ④ 文档删掉「生产部署需 owner 人工确认」那句 | **24 passed** ✗ | **1 failed** ✓ |
| ⑤ 文档写进 `kubectl apply` | **1 failed** ✓ | ✓ |
| ⑥ 失败征兆表删掉 worker 两行 | **24 passed** | **惰性**（见下） |
| ⑦ 只接 worker 不接 cron | **24 passed** ✗ | **2 failed** ✓ |

**六个变异体活下来，病因只有一个**：判据查的是「文件里有没有这个词」，
而那个词在**别处**（包括我自己写的注释与变量名）也出现。逐条看：

- ①：查「文件里有『复用』两个字」——改掉 `if` 条件后那两个字还在；
- ②：查 `harness.run_worker` 在全文——`$workerMark = 'harness.run_worker'`
  这一行就把它喂饱了；
- ③：同上，**我自己加的那句注释**「按命令行标记 harness.run_worker 停」喂饱了断言
  （判据与留痕互相取消，本仓**第十二次**）；
- ④：查全文有「生产部署」——文档开头第一句就写着；
- ⑦：查 `build_cron_jobs` 在全文——import 那一行喂饱了断言。

**修法一律是把判据钉在结构上**：
起脚本只判 worker 那一段（`③b` 到 `# ── ④` 之间）、判**分支先后**
（`if ($existing)` < `复用` < `Start-Process`）、判**启动命令**（`-m harness.run_worker`）；
停脚本只判 `$marks = …` 那一行；文档只判 `## 生产部署` 那一节与失败征兆**那张表**；
入口判**调用**（带括号）而不是词。

**变异⑥ 是惰性变异不是洞**：删掉两行之后，表里仍有一行
「提交按钮点了报错 → redis 没起 / **worker** 没起」——「每个进程都有失败征兆」
这条性质**依然成立**，所以断言不该红。

七次变异后各文件的 sha256 与变异前逐位相同（脚本按字节比对，BOM 一并核）。

## 8. verify 与 self_review

```
verify_cmd: pytest tests/v041/test_orchestration_doc.py -q → 24 passed
PowerShell 语法解析（两脚本 ParseFile）→ 均 OK
worker burst 真跑 → 连 redis、消费空队列后退出
ruff check . --no-cache → All checks passed!
mypy --strict flint → 281 files, no issues
```

**① acceptance 映射**

| acceptance | 测试 |
|---|---|
| ① 起停脚本带上 arq worker 与 cron | `test_the_start_script_launches_the_worker`、`test_the_stop_script_stops_the_worker`、`test_the_worker_entry_exists_and_builds_both_pieces`、`test_the_worker_can_actually_be_built_and_run_in_burst`（真跑） |
| ② 文档写清四进程的职责/端口/起停顺序/失败征兆 | `test_the_doc_covers_every_process`（4 例）、`test_the_doc_names_the_ports`（4 例）、`test_the_doc_states_the_start_order_and_why`、`test_the_doc_lists_a_failure_symptom_for_each_process`、`test_the_doc_records_what_the_demo_hook_used_to_be` |
| ③ NEVER 触碰生产部署，文档明写需 owner 确认 | `test_the_doc_says_production_deployment_needs_the_owner`、`test_the_doc_never_gives_production_deployment_steps`（禁 kubectl/helm/systemctl/docker stack） |
| ④ UTF-8+BOM；起停幂等 | `test_the_scripts_keep_the_utf8_bom`（2 例，字节级）、`test_the_start_script_checks_before_starting_a_second_worker`（判分支先后）、`test_the_stop_script_kills_by_marker_not_by_name` |

**② 无冻结件偏离**：`contracts/`、`flint/domain/` 未触碰；零新增依赖
（arq / redis / httpx 早在 lock 里）；改既有文件两处，见 §9。

**③ 禁用词**：三个产物文件六词 0 命中、本 trace 收尾「等」0 命中。

**④ 复用**：worker 在协程内构造的写法照 `harness/e2e_smoke.py#_consume`；
「按唯一命令行标记认人」是 `stop-demo.ps1` 既有办法的延用；
provider 注入与 `harness/demo_server.py` 同一免费档。

**⑤ 装载预算**：约 8k tokens。

## 9. 改既有文件（§4.1，逐处记账）

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `start-demo.ps1` | 四步（docker/ollama/api+前端/浏览器），无 worker | 在 ③ 与 ④ 之间插 ③b 段：按命令行标记查重 → 复用或起独立窗口；末行提示改成「后端/前端/worker」 | 卡面 outputs 就是这个文件。既有四步**一行未动**，BOM 按字节重写保住 |
| `stop-demo.ps1` | `$marks` 只认 demo_server 与前端 | `$marks` 加 `harness\.run_worker`；②b 位置加一行说明 | 不加的话，起脚本起的 worker 窗口关不掉——而它没有端口，按端口停的那两段够不着它 |

**新增**：`harness/run_worker.py`（worker+cron 进程入口）。卡面 outputs 没列它，
但「起停脚本带上 worker」除了这里没有别的落点——脚本要 `-m` 一个模块，
而仓里此前没有可以 `-m` 的 worker 入口。

## 10. 登记未做

1. **cron 的两个钩子在本机面是空的**：日更采集要真实源（NET-03 红线，需 owner 在场）、
   复核扫描要到期项目清单（`PgJobRunner` + 清单查询，属部署面接线）。
   两者到点都会打印一行说明自己没做事。
2. **demo_server 的临时钩子仍在**：不删是有意的（§3）。哪天要删，得先确认
   起停脚本一定会起 worker——否则 demo 会变成「点了没反应」。
3. **worker 只起一份**：多份并行属部署面（生产才需要），本机 demo 不需要。
4. **没有健康检查端点**：worker 没有监听端口，「它还活着吗」目前只能看窗口。
   要做得给它一个心跳落库，属另一张卡。
