"""FIX-09：`DEC-037` 落地——那条红改的是取证样例，不是产品。

## 那条红是什么

第 4 批接上鉴权之后，`GET /jobs/{id}` 判的是「发起人本人，或 owner-scope 成员」。
而 `harness/fe_smoke.py` 的样例 id `m1004-j` 是**鉴权之前**从库里查出来的：
它的 `initiated_by` 是 `u-sys`，而探针那个身份是 `demo-user`。

端点回 **403**——**那是正确行为**。红的是取证样例没跟着鉴权口径对齐。

## NEVER 把 403 加进控制台噪声白名单

加进去等于**把鉴权正确工作的证据当成噪声吞掉**：下一次鉴权真的坏了时，
那条判据不会响。本文件有一条判据专门守着这件事。

## 本卡没做完的那一半，写在这里

acceptance⑤ 要「另建一条判据专门守『无权时屏上显示无权查看』」。
**那一屏今天没有这个态**——`web/app/jobs/[id]/page.tsx` 只有
加载 / 失败 / 空 / 就绪四态，403 之后它停在**加载骨架**上，永远。
（第 5 批完成态报告里那句「屏上也正确地显示无权查看」是**写错了**。）

建那个态是 `web/` 的事，而本卡 outputs 是 `harness/` + 本文件——
按第 6 批工单纪律 5 停下，登记 `docs/blocked/JOB-SCREEN-HAS-NO-DENIED-STATE.md`。
本文件因此**先把这件事量出来**：断言那一屏至今没有拒绝态，
并断言单据开着——等它建好，这两条会红，那时才是写 acceptance⑤ 那条判据的时候。
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
SEED = REPO / "harness" / "demo_seed_probe_job.py"
SMOKE = REPO / "harness" / "fe_smoke.py"
JOB_SCREEN = REPO / "web" / "app" / "jobs" / "[id]" / "page.tsx"
SWEEP = REPO / "tests" / "v041" / "test_mobile_sweep.py"
OLD_SHEET = REPO / "docs" / "blocked" / "DEMO-JOB-NOT-OWNED-BY-THE-PROBE-USER.md"
NEW_SHEET = REPO / "docs" / "blocked" / "JOB-SCREEN-HAS-NO-DENIED-STATE.md"

# **测试库**，不是 demo 库。`tools`/`tests/harness/test_dsn_isolation.py` 判得对：
# 测试里的真 DSN 只能由 `FLINT_TEST_DSN` 注入——两库共用一个 PG 时，
# 一处写死就够把 demo 的数据清空一次（那条根因已经咬过六次）。
#
# 于是这里的分工是：**判据在测试库上验种子函数干得对不对**，
# 而往 demo 库种那一下是**运维动作**（`python -m harness.demo_seed_probe_job`），
# 不由判据代劳。
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _sample_ids() -> dict[str, str]:
    from harness.fe_smoke import SAMPLE_IDS

    return dict(SAMPLE_IDS)


# ───────────────────────── 一、样例换成了探针自己的那条


def test_the_job_sample_is_no_longer_the_one_it_cannot_see() -> None:
    from harness.demo_seed_probe_job import PROBE_JOB_ID

    assert _sample_ids()["/jobs/[id]"] == PROBE_JOB_ID, (
        "样例还是那条不属于探针的作业"
    )


def test_the_old_sample_is_kept_as_the_negative_one() -> None:
    """`m1004-j` **原样留着**，NEVER 删。

    它是「不属于我的作业」的**活样本**——屏上该显示「无权查看」这件事
    将来要靠它来量。删掉之后，那条正确行为就再也没有东西可以对着测了。

    **判的是源码面而不是库**：那条作业在 **demo 库**里，而本文件只许连测试库
    （见上面 `DSN` 那段）。「它还在不在」由单据点名 + 样例不再指向它两条钉住——
    真去查 demo 库，本文件就成了那条 DSN 纪律的一个例外。
    """
    from harness.demo_seed_probe_job import PROBE_JOB_ID

    assert _sample_ids()["/jobs/[id]"] != "m1004-j"
    assert _sample_ids()["/jobs/[id]"] == PROBE_JOB_ID
    assert "m1004-j" in NEW_SHEET.read_text(encoding="utf-8"), (
        "反向样本没有被任何单子点名——那它迟早会被当成垃圾清掉"
    )
    assert "m1004-j" in SMOKE.read_text(encoding="utf-8"), (
        "取证文件里连它为什么被换掉都没写"
    )


@pytest.fixture()
def probe_identity() -> Any:
    """测试库里放一行探针身份，跑完清掉。

    **身份由 fixture 建，NEVER 由种子脚本建**——那正是脚本里那道拒绝守的东西：
    脚本自己补一行 `users`，等于让取证自己给自己发身份，
    此后「鉴权通过」再也不说明任何问题。这里是判据在**布置前提**，两回事。
    """
    import asyncpg

    from harness.demo_seed_probe_job import PROBE_JOB_ID, PROBE_USER

    async def setup() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "INSERT INTO users (user_id, email, display_name, created_at) "
                "VALUES ($1, $2, $1, now()) ON CONFLICT DO NOTHING",
                PROBE_USER, f"{PROBE_USER}@example.invalid")
        finally:
            await conn.close()

    async def teardown() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "DELETE FROM job_events WHERE job_id = $1", PROBE_JOB_ID)
            await conn.execute("DELETE FROM jobs WHERE job_id = $1", PROBE_JOB_ID)
            await conn.execute("DELETE FROM users WHERE user_id = $1", PROBE_USER)
        finally:
            await conn.close()

    _run(setup())
    yield
    _run(teardown())


@pytest.mark.compose
def test_the_seed_refuses_when_the_identity_does_not_exist() -> None:
    """**阴性对照**：身份不在时脚本**拒绝**，NEVER 顺手补一行。

    没有这一条，上面那道 `RuntimeError` 可能只是没人触发过。
    """
    from harness.demo_seed_probe_job import seed

    with pytest.raises(RuntimeError, match="users"):
        _run(seed(DSN))


# ───────────────────────── 二、种子脚本自己的纪律


@pytest.mark.compose
def test_the_seed_makes_the_job_visible_to_the_probe(probe_identity: None) -> None:
    """种完之后，探针那个身份**看得见**它。

    判的是「发起人是探针」这件事本身——那正是 `may_view` 第一条判的东西。
    """
    from harness.demo_seed_probe_job import PROBE_JOB_ID, PROBE_USER, seed

    async def go() -> Any:
        import asyncpg

        conn = await asyncpg.connect(DSN)
        try:
            return await conn.fetchrow(
                "SELECT initiated_by, owner_scope, state FROM jobs WHERE job_id = $1",
                PROBE_JOB_ID)
        finally:
            await conn.close()

    try:
        _run(seed(DSN))
        row = _run(go())
    except OSError as exc:
        pytest.skip(f"demo 库连不上：{exc}")

    assert row is not None, "种子没落库"
    assert row["initiated_by"] == PROBE_USER
    assert json.loads(row["owner_scope"]) == {"kind": "user", "id": PROBE_USER}, (
        "owner_scope 不是指向探针自己——用 org 域的话，"
        "能不能看又押在 memberships 表上了"
    )
    assert row["state"] == "done", "样例作业不是终态，屏上只有一行状态"


@pytest.mark.compose
def test_running_the_seed_twice_changes_nothing(probe_identity: None) -> None:
    """幂等。取证脚本会被反复跑，第二次跑炸掉就等于取证不可重复。"""
    from harness.demo_seed_probe_job import PROBE_JOB_ID, seed

    async def count() -> Any:
        import asyncpg

        conn = await asyncpg.connect(DSN)
        try:
            return await conn.fetchval(
                "SELECT count(*) FROM jobs WHERE job_id = $1", PROBE_JOB_ID)
        finally:
            await conn.close()

    try:
        _run(seed(DSN))
        _run(seed(DSN))
        assert _run(count()) == 1
    except OSError as exc:
        pytest.skip(f"demo 库连不上：{exc}")


@pytest.mark.compose
def test_the_seed_also_plants_the_job_the_probe_must_not_see(probe_identity: None) -> None:
    """`MAC-05`：反向样本 `m1004-j` 也由种子脚本种，NEVER 指望它「本来就在库里」。

    它原先是 `tests/m1/test_m1_004.py` 早年直接打 demo 库时留下的一行残留，
    没有任何脚本负责造它。换一台机器、建一个新库，它就不在了——
    `test_job_denied_state` 那两条「不是我的作业回 403」于是量到 404，
    而 404 与 403 之间差的正是那两条判据要守的东西。

    判三件：种完它在；它**不属于**探针；重复种不多出一行。
    """
    from harness.demo_seed_probe_job import NOT_MINE_JOB_ID, PROBE_USER, seed

    async def wipe() -> None:
        import asyncpg

        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM job_events WHERE job_id = $1", NOT_MINE_JOB_ID)
            await conn.execute("DELETE FROM jobs WHERE job_id = $1", NOT_MINE_JOB_ID)
        finally:
            await conn.close()

    async def rows() -> Any:
        import asyncpg

        conn = await asyncpg.connect(DSN)
        try:
            return await conn.fetch(
                "SELECT initiated_by, owner_scope FROM jobs WHERE job_id = $1",
                NOT_MINE_JOB_ID)
        finally:
            await conn.close()

    try:
        _run(wipe())
        _run(seed(DSN))
        _run(seed(DSN))
        found = _run(rows())
        _run(wipe())
    except OSError as exc:
        pytest.skip(f"测试库连不上：{exc}")

    assert NOT_MINE_JOB_ID == "m1004-j", "改这个 id 之前先改 fe_smoke 与 test_job_denied_state"
    assert len(found) == 1, f"反向样本应当恰好一行，实得 {len(found)}"
    assert found[0]["initiated_by"] != PROBE_USER, "反向样本的发起人成了探针自己"
    scope = json.loads(found[0]["owner_scope"])
    assert scope != {"kind": "user", "id": PROBE_USER}, "反向样本的 owner_scope 指向了探针"
    assert scope["kind"] == "org", (
        "用 org 域：探针不在那个 org 的 memberships 里，所以看不见——"
        "这正是那条 403 要量的路径"
    )


def test_the_seed_never_invents_an_identity() -> None:
    """身份表是鉴权的根：脚本 NEVER 往 `users` 里插一行。

    补一行等于**让取证自己给自己发身份**——那之后「鉴权通过」这件事
    再也不说明任何问题。
    """
    source = SEED.read_text(encoding="utf-8")
    statements = re.findall(r'"[^"]*INSERT INTO[^"]*"', source)

    assert statements, "脚本里一条 INSERT 都没有？"
    for stmt in statements:
        assert "users" not in stmt, f"脚本往 users 里插了行：{stmt}"


def test_the_seed_is_opt_in_and_points_at_the_demo_dsn() -> None:
    """**NEVER 自动跑、NEVER 指向生产**（红线四类之一是数据面）。"""
    source = SEED.read_text(encoding="utf-8")

    assert "FLINT_DEMO_DSN" in source
    assert "55432" in source, "默认 DSN 不是本机那个"
    assert 'if __name__ == "__main__"' in source, "没有显式入口 = 可能被 import 时跑起来"


# ───────────────────────── 三、那条 403 NEVER 变成噪声


def _baseline_entries() -> str:
    """噪声基线的**条目**，注释剥掉。

    不剥的话，判据会把**解释这条纪律的那句注释**当成违规本身——
    基线里逐字写着「NEVER 把 403 加回来」。
    本仓栽过多次（`docs/blocked/SCANNERS-DO-NOT-STRIP-COMMENTS.md`），
    **本批这是第三次**：前两次在规格 `#2.4` 与 `flint/region/backfill.py` 上。
    """
    text = SWEEP.read_text(encoding="utf-8")
    block = text[text.index("CONSOLE_BASELINE"):]
    block = block[: block.index("\n}\n") + 2]
    return "\n".join(
        line for line in block.splitlines() if not line.lstrip().startswith("#"))


def test_the_403_is_not_whitelisted_as_console_noise() -> None:
    """**本卡最要紧的一条**：403 NEVER 进控制台噪声白名单。

    进了白名单，就等于把「鉴权正确工作」的证据当成噪声吞掉——
    而下一次鉴权真的坏了时，那条判据不会响。
    换的是样例，NEVER 是判据的容忍度。
    """
    entries = _baseline_entries()

    assert "403" not in entries, "403 被写进了噪声基线"
    assert "DEMO-JOB-NOT-OWNED-BY-THE-PROBE-USER" not in entries, (
        "作业屏那条额度还挂在旧单上——样例换掉之后它该零报错"
    )


def test_the_job_screen_has_no_baselined_console_error_any_more() -> None:
    """样例换成探针自己的之后，这一屏**该零报错**。

    留着额度的话，将来真出一条报错时没人会发现。
    """
    assert '"/jobs/[id]"' not in _baseline_entries(), "作业屏还占着一条噪声额度"


# ───────────────────────── 四、那一半后来做了（UIX-04 · 第 7 批）


def test_the_job_screen_now_has_a_denied_state() -> None:
    """**这一条被翻过来了**（`UIX-04`，v0.4.1 第 7 批）。

    改前它断言那一屏**还没有**拒绝态，并在 docstring 里写着
    「这一条哪天红了，是好事——那时该回到这里把它换成正向判据」。
    `UIX-04` 把态建好了，所以这里照那句话执行：**换成正向的**。

    `FIX-09` 当初没做这一半的理由仍然成立（它的 outputs 是 `harness/` + 本文件，
    建界面态是 `web/` 的事）——**留着一条描述旧世界的判据一直红着**，
    会让下一个人以为产品坏了。
    """
    code = JOB_SCREEN.read_text(encoding="utf-8")
    notice = (
        JOB_SCREEN.parents[3] / "components" / "shell" / "JobDeniedNotice.tsx"
    ).read_text(encoding="utf-8")

    # 与改前那条用**同一组词**（`denied|forbidden|无权|403`），只是方向反过来——
    # 换一组词的话，两条判据守的就不是同一件事了。
    assert re.search(r"denied|forbidden|无权|403", code, re.IGNORECASE), (
        "作业屏的拒绝态不见了")
    assert "JobDeniedNotice" in code, "屏上没有挂那个件"
    # 取证属性在**通用件**里（屏只负责分支）。判在屏里的话，
    # 一次把属性搬进通用件的正确重构会被判成「属性丢了」。
    assert "data-job-denied" in notice, "拒绝态没有取证属性"


def test_the_sheet_that_tracked_it_is_closed() -> None:
    """那张单已由 `UIX-04` 关掉，且靠哪条作业来量的记录**还在**。

    改前这条断言单据 `open`。关单之后它红了——**红的是自己描述的那个状态过去了**。
    `m1004-j` 那条记录必须留着：它是「不属于我的作业」的活样本，
    这个态将来还要靠它来量。
    """
    assert NEW_SHEET.exists(), "屏上缺拒绝态这件事的那张单不见了"
    text = NEW_SHEET.read_text(encoding="utf-8")
    state = next(ln for ln in text.splitlines()[:8] if ln.startswith("**状态**"))

    assert state.startswith("**状态** closed"), f"单据状态不对：{state!r}"
    assert "UIX-04" in text, "关单没写是被哪张卡关的"
    assert "m1004-j" in text, "单里没写靠哪条作业来量"
    assert "FIX-09" in text


def test_the_old_sheet_is_closed_because_the_sample_moved() -> None:
    """旧单关掉——它说的是「样例与鉴权口径没对齐」，那件事做完了。

    **NEVER 顺手把「屏上缺拒绝态」也算进它**：两件事的修法完全不同，
    一个是改取证样例，一个是建一个界面状态。
    """
    text = OLD_SHEET.read_text(encoding="utf-8")
    state = next(ln for ln in text.splitlines()[:8] if ln.startswith("**状态**"))

    assert state.startswith("**状态** closed"), f"旧单还开着：{state!r}"
    assert "FIX-09" in text
    assert "JOB-SCREEN-HAS-NO-DENIED-STATE" in text, (
        "旧单没把剩下那一半指给新单——那一半会就此丢掉"
    )


# ───────────────────────── 五、SSE 那条判据从「跳过」变成真绿


@pytest.mark.compose
def test_the_seeded_job_actually_has_events(probe_identity: None) -> None:
    """种子连事件一起种——否则 SSE 那条判据只会**跳过**。

    `GET /jobs/{id}/events` 对一条终态且没有事件的作业，冲刷之后直接关流，
    一个 `data:` 都不发。`test_sse_live` 于是走进「demo 栈没起」那个 skip 分支，
    **而那句话是假的**：栈起着，是这条作业没有话说。

    **跳过比红更坏**：红了有人会去看，跳过只是少了一行。
    """
    from harness.demo_seed_probe_job import PROBE_JOB_ID, seed

    async def rows() -> Any:
        import asyncpg

        conn = await asyncpg.connect(DSN)
        try:
            return await conn.fetch(
                "SELECT seq, payload FROM job_events WHERE job_id = $1 ORDER BY seq",
                PROBE_JOB_ID)
        finally:
            await conn.close()

    try:
        _run(seed(DSN))
        got = _run(rows())
    except OSError as exc:
        pytest.skip(f"demo 库连不上：{exc}")

    assert got, "种子没落事件——SSE 判据会跳过"
    assert [r["seq"] for r in got] == list(range(1, len(got) + 1)), "seq 不连续"
    for row in got:
        payload = json.loads(row["payload"])
        # 形状照 `flint/jobs/events.py` 的契约：每条带 `kind`，
        # 否则前端的归约器会在 `assertNever` 上炸。
        assert "kind" in payload, payload


@pytest.mark.compose
def test_seeding_events_twice_does_not_duplicate_them(probe_identity: None) -> None:
    from harness.demo_seed_probe_job import PROBE_JOB_ID, seed

    async def count() -> Any:
        import asyncpg

        conn = await asyncpg.connect(DSN)
        try:
            return await conn.fetchval(
                "SELECT count(*) FROM job_events WHERE job_id = $1", PROBE_JOB_ID)
        finally:
            await conn.close()

    try:
        _run(seed(DSN))
        first = _run(count())
        _run(seed(DSN))
        assert _run(count()) == first
    except OSError as exc:
        pytest.skip(f"demo 库连不上：{exc}")
