"""SHIP-02：进程编排落地（文档 + 起停脚本带上 worker 与 cron）。

## 接线前的实况

`flint/jobs/worker_main.py#build_worker` 与 `flint/jobs/cron.py#build_cron_jobs`
都在，但**没有任何进程调它们**——demo 走的是 `harness/demo_server.py` 里
`asyncio.create_task(_run())` 的临时钩子：

- 作业在 **API 进程里**跑，队列形同虚设；
- 关掉 API 窗口，正在跑的作业就没了，而 jobs 表里它还是 running；
- cron 一次都没触发过（日更批与复核扫描的时刻定义在，没有进程按它走）。

## 本卡只管本机编排

**NEVER 触碰生产部署**（S2-10 红线）。文档里明写「生产部署需 owner 人工确认」，
这一条有测试守着——写文档最容易滑向「顺便把生产怎么部署也写了」，
而那份文档一旦存在，就会有人照着做。

## 脚本的两条硬约束

- **UTF-8 + BOM**：PowerShell 5.1 读无 BOM 的 UTF-8 会把中文变成乱码（既有踩坑）；
- **起停幂等**：重复起 NEVER 产生第二份 worker——按命令行标记判定，
  与 `stop-demo.ps1` 既有的「按唯一命令行标记收尾窗口」同一套办法。
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
START = REPO_ROOT / "start-demo.ps1"
STOP = REPO_ROOT / "stop-demo.ps1"
DOC = REPO_ROOT / "docs" / "进程编排-v041.md"
WORKER_ENTRY = REPO_ROOT / "harness" / "run_worker.py"

# worker 进程的唯一命令行标记（起停两侧都按它认人）
WORKER_MARK = "harness.run_worker"
# 四个进程：文档必须逐个交代职责/端口/起停顺序/失败征兆
PROCESSES = ("postgres", "redis", "api", "worker")


# ───────────────────────── 一、脚本真的带上了 worker


def _worker_block(text: str) -> str:
    """起脚本里 worker 那一段（从 3b 标题到下一个 `# ── ` 分节）。

    判据必须落在**这一段里**：查全文的话，`$workerMark = 'harness.run_worker'`
    那一行就能把所有断言喂饱——变异考实测七个变异体活了六个，全是这个病。
    """
    start = text.index("③b")
    tail = text[start:]
    end = tail.index("# ── ④")
    return tail[:end]


def test_the_start_script_launches_the_worker() -> None:
    """acceptance①：起脚本里有 worker 的**启动命令**，不是只有一个同名变量。"""
    block = _worker_block(START.read_text(encoding="utf-8-sig"))

    assert f"-m {WORKER_MARK}" in block, "起脚本没有真的起 worker"


def test_the_stop_script_stops_the_worker() -> None:
    """停脚本按**同一个标记**认人——两边用不同标记，就会关不掉自己起的那个。

    判的是 `$marks = '…'` 那一行本身，不是「全文有没有这个词」：
    我自己写的那句注释里就有这个词（判据与留痕互相取消，本仓第十二次）。
    """
    text = STOP.read_text(encoding="utf-8-sig")
    marks_line = next(
        ln for ln in text.splitlines() if ln.strip().startswith("$marks")
    )

    assert "run_worker" in marks_line, f"停脚本的标记行认不出 worker：{marks_line}"


def test_the_worker_entry_exists_and_builds_both_pieces() -> None:
    """入口把 `build_worker` 与 `build_cron_jobs` **两件**都接上。

    只接 worker 的话，日更批与复核扫描仍然一次都不会触发。
    """
    source = WORKER_ENTRY.read_text(encoding="utf-8")

    # 判**调用**（带括号），不判「文件里有这个词」——import 那一行会把断言喂饱。
    assert "build_worker(" in source
    assert "build_cron_jobs(" in source


def test_the_worker_entry_never_reads_an_api_key() -> None:
    """免费档，零 key：付费开通是 owner 人审节点（S2-10）。"""
    source = WORKER_ENTRY.read_text(encoding="utf-8")

    for forbidden in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "api_key="):
        assert forbidden not in source, f"worker 入口读了 key：{forbidden}"


def test_the_cron_hooks_say_something_when_they_fire() -> None:
    """本机面没接真实源的 cron 钩子**要出声**。

    一条什么都不做又不出声的定时任务，与「定时任务没起来」在日志上长得一模一样。
    """
    source = WORKER_ENTRY.read_text(encoding="utf-8")

    assert source.count("print(") >= 3


# ───────────────────────── 二、幂等（acceptance④）


def test_the_start_script_checks_before_starting_a_second_worker() -> None:
    """重复起 NEVER 产生第二份 worker：起之前先按标记查一遍。"""
    block = _worker_block(START.read_text(encoding="utf-8-sig"))

    assert "CommandLine" in block, "起脚本没有按命令行标记查重"
    # 判**分支结构**：查到了要走复用那一支，没查到才起。
    # 只查「文件里有『复用』两个字」的话，把 `if ($existing)` 改成 `if ($false)`
    # 照样绿——变异考实测过。
    guard = block.index("if ($existing)")
    reuse = block.index("复用")
    launch = block.index("Start-Process")

    assert guard < reuse < launch, "查重、复用、启动三者的先后不对"


def test_the_stop_script_kills_by_marker_not_by_name() -> None:
    """按标记停，不按进程名停——按 `python.exe` 停会连别人的 python 一起杀。"""
    text = STOP.read_text(encoding="utf-8-sig")

    assert WORKER_MARK in text
    assert "Name='python.exe'" not in text


@pytest.mark.parametrize("script", [START, STOP])
def test_the_scripts_keep_the_utf8_bom(script: Path) -> None:
    """acceptance④：UTF-8 **带 BOM**。

    PowerShell 5.1 读无 BOM 的 UTF-8 会把中文变成乱码——脚本里的中文提示
    全是给人看的，乱码等于没有。
    """
    assert script.read_bytes()[:3] == b"\xef\xbb\xbf", f"{script.name} 掉了 BOM"


def test_the_worker_can_actually_be_built_and_run_in_burst() -> None:
    """入口真的能起来：连上 redis、消费空队列后退出（burst 口径）。

    只查源码里有 `build_worker` 三个字是不够的——**装配面缺一个注入件就起不来**，
    而那种失败只在真跑时才出现（本卡实测撞过一次：Worker 在构造时绑定事件循环，
    必须在协程**内部**构造）。
    """
    import asyncio

    from flint.jobs.cron import build_cron_jobs, today_utc
    from flint.jobs.worker_main import build_worker
    from harness import run_worker

    async def go() -> None:
        worker = build_worker(
            run_worker.build_deps(), burst=True,
            cron_jobs=build_cron_jobs(
                redis_url=run_worker.REDIS_URL, day_of=today_utc,
                ingest=run_worker._not_wired_ingest, scan=run_worker._not_wired_scan,
            ),
        )
        await worker.async_run()
        await worker.close()

    asyncio.run(go())


# ───────────────────────── 三、文档四进程（acceptance②）


def test_the_doc_exists() -> None:
    assert DOC.exists(), "进程编排文档不在盘上"


@pytest.mark.parametrize("process", PROCESSES)
def test_the_doc_covers_every_process(process: str) -> None:
    """四个进程一个不少。"""
    assert process in DOC.read_text(encoding="utf-8").lower()


@pytest.mark.parametrize("port", ["55432", "56379", "8000", "3000"])
def test_the_doc_names_the_ports(port: str) -> None:
    """端口写出来——不写的话，「起不来」这件事没法自查。"""
    assert port in DOC.read_text(encoding="utf-8")


def test_the_doc_states_the_start_order_and_why() -> None:
    """起停顺序**带理由**：只写顺序不写为什么，下一个人会以为可以随便换。"""
    text = DOC.read_text(encoding="utf-8")

    assert "起停顺序" in text
    assert "为什么" in text or "理由" in text


def test_the_doc_lists_a_failure_symptom_for_each_process() -> None:
    """每个进程一条**失败征兆**——「症状 → 是谁没起来」这张对照表才是文档的用处。"""
    text = DOC.read_text(encoding="utf-8")

    assert "失败征兆" in text
    # 只取**那张表**（到下一个 `## ` 为止）：切到文末的话，后面「幂等」一节
    # 提到的 worker 会把断言喂饱——变异考实测删掉表里的 worker 两行照样绿。
    table = text[text.index("## 失败征兆"):]
    table = table[: table.index("\n## ")]

    for process in PROCESSES:
        assert process in table.lower(), f"失败征兆表里没有 {process}"


def test_the_doc_says_production_deployment_needs_the_owner() -> None:
    """acceptance③：**生产部署需 owner 人工确认**（S2-10 红线），文档里明写。"""
    text = DOC.read_text(encoding="utf-8")
    section = text[text.index("## 生产部署"):]

    # 判据落在**那一节里**：全文任意处都有「生产部署」四个字（开头就写了一句），
    # 查全文等于永远绿。
    assert "owner" in section
    assert "人工确认" in section or "人审" in section
    assert "S2-10" in section


def test_the_doc_never_gives_production_deployment_steps() -> None:
    """文档里 NEVER 出现可照做的生产部署步骤。

    写文档最容易滑向「顺便把生产怎么部署也写了」——而那份文档一旦存在，
    就会有人照着做，那一刻红线已经被越过了。
    """
    text = DOC.read_text(encoding="utf-8")

    for forbidden in ("kubectl", "helm", "systemctl enable", "docker stack deploy"):
        assert forbidden not in text, f"文档里出现了生产部署步骤：{forbidden}"


def test_the_doc_records_what_the_demo_hook_used_to_be() -> None:
    """写清**改之前是什么**：`asyncio.create_task` 的临时钩子。

    不写的话，下一个人看到 demo_server 里还留着的那条路会以为它才是正路。
    """
    text = DOC.read_text(encoding="utf-8")

    assert "create_task" in text
