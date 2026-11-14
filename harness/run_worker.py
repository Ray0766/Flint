"""SHIP-02：本机 worker 进程入口（arq worker + cron 一起起）。

用法：python -m harness.run_worker

## 为什么需要这个文件

`flint/jobs/worker_main.py#build_worker` 与 `flint/jobs/cron.py#build_cron_jobs`
都在，但**没有任何进程调它们**——demo 走的是 `harness/demo_server.py` 里
`asyncio.create_task(_run())` 的临时钩子：作业在 API 进程里跑，队列形同虚设，
关掉 API 窗口正在跑的作业就没了。

本模块把那两件真件接起来，成为一个可以独立起停的进程。

## 免费档，零 key

provider 用 `LocalProvider`（本机 Ollama，与 `harness/demo_server.py` 同一档），
**NEVER 读任何 API key**：付费开通是 owner 人审节点（S2-10）。

## 起一个就够

同一队列起两个 worker 不会出错（arq 自己会分配），但 demo 面不需要——
起停脚本按命令行标记 `harness.run_worker` 判定「已经有一个了」，重复起不产生第二份。
"""
from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import httpx

from flint.domain.models import Principal, UserProfile
from flint.evidence.search import GithubArxivSearcher
from flint.jobs.cron import build_cron_jobs, today_utc
from flint.jobs.design_generate import DesignGenerateDeps
from flint.jobs.events import PgJobEventStream
from flint.jobs.gate1 import build_live_deps
from flint.jobs.worker_main import WorkerDeps, build_worker
from harness.local_model import build_local_provider

DSN = os.environ.get("FLINT_DEMO_DSN", "postgresql://flint:flint@localhost:55432/flint")
REDIS_URL = os.environ.get("FLINT_REDIS_URL", "redis://localhost:56379/0")


def _profile(now: datetime) -> UserProfile:
    """demo 无真实档案 → 全空（NEVER 编造涉我信息，同 demo_server 口径）。"""
    return UserProfile(
        profile_id="demo-profile", owner=Principal(kind="user", id="demo-user"),
        identity={}, research={}, team=[], assets={}, constraints={},
        track_record=[], locale="zh-CN", sensitivity_overrides={}, updated_at=now,
    )


def build_deps() -> WorkerDeps:
    """装配面。真实 provider 从这里注入——模块层 NEVER 造 http 客户端去读 key。"""
    now = datetime.now(UTC)
    # `COMBO-WIRE-01`：地址、模型名、超时三样都在 `harness/local_model.py`——
    # combo 那一族（API 进程）拿的是**同一处定义**造出来的 provider。
    provider = build_local_provider()
    return WorkerDeps(
        dsn=DSN,
        redis_url=REDIS_URL,
        repo_root=REPO_ROOT,
        profile=_profile(now),
        now=now,
        compose_provider=provider,
        # `VERDICT-01`：**gate1 这一缝此前是空的**，于是本机 worker 上
        # 每一条 `gate1_analysis` 都以 `HandlerDepsMissing` 收场——
        # 而 `⑥热点分析` 那一屏因此永远说「还没有判定」。
        #
        # 注进去之后 `_gate1_handler` 会把 payload 里的 `topic_id` 一路传给
        # `run_gate1`，判定结束时那句 `if topic_id is not None:` 才走得到，
        # `cluster_verdicts` 也才落得下行（今天全库 0 行的直接原因见
        # `docs/trace/VERDICT-01.md`）。
        #
        # searcher 打的是**真实 github / arxiv**：这是 demo 面按下「发起分析」
        # 时本来就会做的事（`build_live_deps` 的既有口径），
        # 与 CI 无关——CI 走 `build_offline_deps`，S2-7 恒不联网。
        # `SMOKE-01`：设计工作台那一步此前也是 `HandlerDepsMissing`——
        # 与 gate1 同一类缺缝，第一次真跑才看得见（屏上只说「设计产物接口未提供」）。
        # 这一族**全本地**：provider 是同一个 `LocalProvider`，事件流是库，
        # 一发外部请求都不发。
        design_generate_deps=DesignGenerateDeps(
            provider=provider, events=PgJobEventStream(dsn=DSN),
            now=lambda: datetime.now(UTC),
            # `DESIGN-STATE`：收尾要把 `jobs.state` 也推到 `done`，那要库连接。
            # 不给的话事件流说 `done` 而作业表停在 `queued`——
            # 用户侧就是「点了生成转圈不停，而内容其实已经出来了」。
            dsn=DSN),
        gate1_deps=build_live_deps(
            DSN, REPO_ROOT, provider,
            GithubArxivSearcher(
                httpx.Client(timeout=30.0, follow_redirects=True), now,
                per_source=3, resilient=True),
            now),
    )


async def _not_wired_ingest() -> None:
    """日更采集在本机 demo 面**不真跑**：它要真实源（§7 事前必审）。

    cron 到点时打一行日志就走——**NEVER 静默**：一条什么都不做又不出声的定时任务，
    与「定时任务没起来」在日志上长得一模一样。
    """
    print("[flint cron] 日更批到点：本机 demo 面不触真实源（NET-03 需 owner 在场）")


async def _not_wired_scan() -> None:
    """复核扫描同理：它要 `PgJobRunner` 与到期项目清单，属部署面接线。"""
    print("[flint cron] 复核扫描到点：本机 demo 面未接到期清单（BL-07 的消费者已在）")


def main() -> int:
    """起 worker（带 cron）。Ctrl+C / 关窗口即停——本进程不写任何持久状态。"""
    deps = build_deps()
    worker = build_worker(deps, cron_jobs=build_cron_jobs(
        redis_url=REDIS_URL,
        day_of=today_utc,
        ingest=_not_wired_ingest,
        scan=_not_wired_scan,
    ))
    print(f"[flint worker] queue 已连 {REDIS_URL}；DSN={DSN}")
    print("[flint worker] cron：日更 ×2 + revalidation 扫描（时刻取自 sched / revalidation）")
    worker.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
