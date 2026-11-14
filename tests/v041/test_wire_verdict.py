"""WIRE-VERDICT：热点判定——后端通了，屏还在读旧那条路。

## 屏上那句话没变，**原因变了**

改前分析屏说「未判定」，因为 `cluster → job` 的对应关系**没有持久化真相**
（`docs/blocked/HOTSPOT-03.md` / `DEC-012`）。
`DEC-044` 之后 `cluster_verdicts` 就是那份真相，`PERSIST-04` 建了
`GET /clusters/{id}/verdict` 把它读出来——**而前端一处都没在调**
（对账器把它记在「已装配未调用」那 21 条里）。

于是屏上仍然说「未判定」。**对用户是同一句话，对改代码的人是两件事**：
从前该去建端点，现在该去接屏。

## 封版件一行没动

`AnalysisView` 是 v0.4 封版件，本批 rules 写着「无封版件例外」。
新端点回的 `job_id` **正好就是**那条缺失的对应关系，
所以分析屏只需把 `verdictJobId` 的来源从「只有 URL」扩成「URL 优先、其次问端点」——
封版件的入参一个字不用改。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import pytest

REPO = Path(__file__).resolve().parents[2]
CLUSTER_PAGE = REPO / "web" / "app" / "clusters" / "[id]" / "page.tsx"
PLAZA_PAGE = REPO / "web" / "app" / "plaza" / "page.tsx"
CLIENT = REPO / "web" / "lib" / "viewsClient.ts"
ANALYSIS_VIEW = REPO / "web" / "views" / "analysis" / "AnalysisView.tsx"
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")


def _code(path: Path) -> str:
    text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
    return "\n".join(
        ln for ln in text.splitlines() if not ln.strip().startswith("//"))


# ───────────────────────── 一、前端真的接上了那条读法


def test_the_new_read_path_exists_in_the_client() -> None:
    """客户端有「按热点问 job_id」这一条。"""
    code = _code(CLIENT)

    assert "fetchClusterVerdictJob" in code
    assert "/clusters/" in code and "/verdict" in code


def test_the_analysis_screen_asks_the_endpoint_when_the_url_has_no_job() -> None:
    """没带 `?verdictJob=` 时**去问端点**，而不是直接落「未判定」。"""
    code = _code(CLUSTER_PAGE)

    assert "fetchClusterVerdictJob" in code
    assert "verdictJob" in code


def test_the_caller_supplied_job_still_wins() -> None:
    """URL 带了就**用它**，NEVER 再去问一次把它覆盖掉。

    调用方手上那一个是「这一次作业判了什么」，比「这个热点最近判过什么」更具体。
    """
    code = _code(CLUSTER_PAGE)
    # 从 `useEffect(` 那一**调用**起切，NEVER 从 `useEffect` 这个词起——
    # 文件第一行的 import 里就有它，于是切出来的段落从 import 开始，
    # 而 `fetchClusterVerdictJob` 的 import 排在更前面，顺序判据当场误报。
    effect = code[code.index("useEffect("):]

    assert "if (fromUrl)" in effect, "没有「URL 优先」这一步"
    assert effect.index("setVerdictJob(fromUrl)") < effect.index(
        "fetchClusterVerdictJob"), "先去问了才看 URL——顺序反了"


def test_both_read_paths_are_documented_and_the_old_one_stays() -> None:
    """`/jobs/{id}/verdict` **留着**，且两条各自什么时候用写死在文件头。

    它与新那条服务的是两种问法——删掉的话，跑完一次分析拿着 job id 的那条路就断了。
    """
    client = CLIENT.read_text(encoding="utf-8")

    assert "fetchVerdict" in _code(CLIENT), "旧那条被删了"
    assert "/jobs/" in _code(CLIENT)
    # 文件头那张表：两种问法各一行。
    assert "这**一次作业**判了什么" in client
    assert "这**个热点**判过什么" in client


def test_the_sealed_component_was_not_touched() -> None:
    """封版件 `AnalysisView` **一行没动**（本批 rules：无封版件例外）。

    它的入参仍是 `verdictJobId`——本卡改的是那个 id 从哪儿来。
    """
    code = _code(ANALYSIS_VIEW)

    assert "fetchClusterVerdictJob" not in code, "封版件被改了取数路径"
    assert "verdictJobId" in code


# ───────────────────────── 二、那句变假的注释


def test_the_stale_comment_about_a_missing_endpoint_is_gone() -> None:
    """`plaza/page.tsx` 里那句「`GET /clusters/{id}/verdict` 不存在」**今天是假的**。

    留一句已经变假的注释比没有注释更贵：读注释的判据在本批踩过六次，
    而人读到它会以为这条路还不能走。
    """
    text = PLAZA_PAGE.read_text(encoding="utf-8")

    assert "`GET /clusters/{id}/verdict` 不存在" not in text
    # 而那条**禁令**（NEVER 猜一个 job）要留着——它没有过期。
    assert "猜" in text and "另一个热点的判定" in text


# ───────────────────────── 三、打真代码：塞一条真判定，端点读得出来


#: 本文件种下的行，收尾按外键顺序删干净。
#:
#: **种了不收的代价是别人的红**：`cluster_verdicts` 有外键指向 `clusters`，
#: 别的判据清 `clusters` 时会撞上它，报的是
#: 「`update or delete on table "clusters" violates ... cluster_verdicts_cluster_id_fkey`」
#: ——那条红出现在别人的文件里，而根因在这里。实测撞过一次：
#: 全量从 0 failed 变成 6 failed / 18 errors，全部是这一条。
_SEEDED: list[tuple[str, str]] = []


@pytest.fixture(autouse=True)
def _cleanup() -> object:
    yield
    if not _SEEDED:
        return
    import asyncio

    async def go() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            for cluster_id, job_id in _SEEDED:
                # 先子后父：外键方向决定删除顺序。
                await conn.execute(
                    "DELETE FROM cluster_verdicts WHERE cluster_id = $1", cluster_id)
                await conn.execute(
                    "DELETE FROM snapshots WHERE snapshot_id = $1",
                    f"snap-{job_id}-verdict")
                await conn.execute("DELETE FROM jobs WHERE job_id = $1", job_id)
                await conn.execute(
                    "DELETE FROM clusters WHERE cluster_id = $1", cluster_id)
        finally:
            await conn.close()

    asyncio.run(go())
    _SEEDED.clear()


def _seed(cluster_id: str, job_id: str) -> None:
    import asyncio

    _SEEDED.append((cluster_id, job_id))

    async def go() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            cat = await conn.fetchval("SELECT category_id FROM categories LIMIT 1")
            await conn.execute(
                "INSERT INTO clusters (cluster_id, canonical_name, category_id, "
                "centroid, status, first_seen, last_active) "
                "VALUES ($1,$2,$3,$4,'active',$5,$5) ON CONFLICT DO NOTHING",
                cluster_id, "判定用热点", cat,
                "[" + ",".join(["0"] * 1024) + "]", datetime.now(UTC).date())
            # cluster_verdicts.job_id 有外键指向 jobs——**先种作业**。
            # 少这一步时报的是 ForeignKeyViolation，而那与本卡要量的东西无关；
            # 更要紧的是：那条外键正是 DEC-044 关系表**不许挂空**的形态，
            # 判据自己 NEVER 绕开它去插一行孤儿。
            await conn.execute(
                "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, "
                "budget, cost_accum, cancel_requested, initiated_by, "
                "created_at, updated_at) VALUES "
                # state 走 ck_jobs_state 认的那八个词之一。'succeeded' 不在里面——
                # 那是我照别处的说法写的，而库里的终态叫 'done'。
                "($1,'gate1_analysis','{}','done',100,0,0,false,'seed',now(),now()) "
                "ON CONFLICT (job_id) DO NOTHING", job_id)
            # 列名照**库里实况**写（`snapshots` 三列、`cluster_verdicts` 三列）。
            # 第一版我照记忆写了 `kind` 与 `decided_at`，两个都不存在——
            # 种子写错时报的是 `UndefinedColumn`，而那与本卡要量的东西无关。
            await conn.execute(
                "INSERT INTO snapshots (snapshot_id, payload, created_at) "
                "VALUES ($1,$2,now()) ON CONFLICT (snapshot_id) DO NOTHING",
                f"snap-{job_id}-verdict",
                json.dumps({"decision": "A", "citations": ["fact-1"]}).encode())
            await conn.execute(
                "INSERT INTO cluster_verdicts (cluster_id, job_id, created_at) "
                "VALUES ($1,$2,now()) ON CONFLICT DO NOTHING",
                cluster_id, job_id)
        finally:
            await conn.close()

    asyncio.run(go())


@pytest.mark.compose
def test_a_seeded_verdict_comes_back_through_the_endpoint() -> None:
    """塞一条**真的** `cluster_verdicts` 行 → 端点回得出那条判定与它的 job。"""
    from fastapi.testclient import TestClient

    from flint.api.app import create_app

    cluster_id = f"c-wire-{uuid.uuid4().hex[:8]}"
    job_id = f"job-wire-{uuid.uuid4().hex[:8]}"
    _seed(cluster_id, job_id)

    client = TestClient(create_app(dsn=DSN), raise_server_exceptions=False)
    got = client.get(f"/clusters/{cluster_id}/verdict")

    assert got.status_code == 200, got.text
    body = got.json()
    assert body["job_id"] == job_id
    assert body["verdict"]["decision"] == "A"
    assert body["verdict"]["citations"] == ["fact-1"]


@pytest.mark.compose
def test_a_cluster_that_was_never_judged_says_so_instead_of_going_blank() -> None:
    """**没判过**时说「没判过」，NEVER 回一个空判定。

    回空的话前端分不出「没判过」与「判了但内容是空的」——
    而用户据此做的下一步完全不同（去发起一次分析 / 去查后端）。
    """
    from fastapi.testclient import TestClient

    from flint.api.app import create_app

    client = TestClient(create_app(dsn=DSN), raise_server_exceptions=False)
    got = client.get(f"/clusters/c-never-judged-{uuid.uuid4().hex[:6]}/verdict")

    assert got.status_code == 404
    assert got.json()["code"] == "NOT_FOUND"


# ───────────────────────── 四、对账器少一条


def test_the_endpoint_left_the_unused_list() -> None:
    """acceptance⑥：`backend_unused_by_frontend` 里**不再有这一条**。"""
    done = subprocess.run(
        [sys.executable, str(REPO / "tools" / "check_fe_be_parity.py"), "--json"],
        capture_output=True, text=True, encoding="utf-8", cwd=REPO, check=False)
    report = json.loads(done.stdout)
    unused = [f["subject"] for f in report["findings"]
              if f["kind"] == "backend_unused_by_frontend"]

    assert "/clusters/{}/verdict" not in unused, (
        f"接完了它还在「已装配未调用」里：{unused[:5]}")
