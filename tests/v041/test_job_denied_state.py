"""UIX-04：作业屏的第五态——「无权查看」。

## 改前：403 之后它停在加载骨架上，**永远**

`web/app/jobs/[id]/page.tsx` 只有四态（加载骨架 / 失败 / 空 / 就绪），
`useJobStream` 与 `jobClient` 里 grep `403|denied|forbidden` **零命中**。
SSE 被拒之后 `status` 恒为 `null`，屏上就是一张永远转下去的骨架。

**「在连」与「不让你连」在屏上长得一模一样**，而两者要用户做的事完全相反：
一个是继续等，一个是去要权限。

## `EventSource` 拿不到状态码，所以要探一次

原生 `EventSource` 的 `onerror` **不带 HTTP 状态**——它连 403 与断网都分不出来。
所以流出错时补一次 `fetch GET /jobs/{id}`（那条路能读到状态码），
据它把 `access` 定成 `denied` / `unauthenticated` / `unknown`。

**探一次，不是轮询**：轮询会在真断网时对着一个连不上的后端反复打，
而屏上那句话不会因为多打几次变得更准。

## 401 与 403 分开（`AUTH-03` 口径）

401 是「你是谁」（没登录 → 去登录），403 是「你能干什么」（登录了但这条不属于你
→ 去要权限）。**并成一句「无权访问」的话，用户不知道下一步该做什么。**

## NEVER 与断线态合并

`SseDisconnectNotice` 说的是「连不上」（可恢复，原生 `EventSource` 正在重连）；
「不让你连」是终局的——**重连一万次也还是 403**。
合并之后屏上会劝用户「稍后重试」，而重试永远不会成功。

## NEVER 把 403 加进控制台噪声白名单

那等于**把鉴权正确工作的证据当成噪声吞掉**（`DEC-037` 的原话）——
而下一次鉴权真的坏了时，这条判据不会响。
"""
from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CLIENT = REPO / "web" / "lib" / "jobClient.ts"
HOOK = REPO / "web" / "lib" / "useJobStream.ts"
PAGE = REPO / "web" / "app" / "jobs" / "[id]" / "page.tsx"
COMPONENT = REPO / "web" / "components" / "shell" / "JobDeniedNotice.tsx"
VITEST = REPO / "web" / "lib" / "jobDenied.test.tsx"
SWEEP = REPO / "tests" / "v041" / "test_mobile_sweep.py"
SHEET = REPO / "docs" / "blocked" / "JOB-SCREEN-HAS-NO-DENIED-STATE.md"

BACKEND = "http://localhost:8000"
NOT_MINE = "m1004-j"                 # initiated_by = u-sys，探针身份是 demo-user
MINE = "probe-owned-ingest"          # FIX-09 种的那条


def _status(path: str) -> int:
    request = urllib.request.Request(f"{BACKEND}{path}", method="GET")
    request.add_header("x-user-id", "demo-user")
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return int(response.status)
    except urllib.error.HTTPError as err:
        return int(err.code)
    except OSError as err:                      # 栈没起
        pytest.skip(f"本机后端没起：{err}")


def _code(source: str) -> str:
    """剥掉 `//` 注释。

    **不剥不行**：本卡在 `jobClient` 与那一屏里都写了改因注释，
    里面逐字提到「403」「denied」——判据要判的是**实现认不认**，
    不是**注释里提没提**。本仓这是第十一次撞见同一形状。
    """
    return "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("//"))


# ───────────────────────── 一、真栈：那两条作业的状态码就是分岔点


@pytest.mark.compose
def test_the_backend_really_denies_the_job_that_is_not_mine() -> None:
    """`/jobs/m1004-j` 回 403，`/jobs/probe-owned-ingest` 回 200。

    这一条是整张卡的**前提**：屏上要显示的那句话，来源是这个状态码。
    前提没了（比如鉴权被摘掉），下面所有判据都在测一件不再发生的事。
    """
    assert _status(f"/jobs/{NOT_MINE}") == 403, "那条不属于探针的作业不再回 403 了"
    assert _status(f"/jobs/{MINE}") == 200, "探针自己那条作业回不来了"


@pytest.mark.compose
def test_the_sse_endpoint_denies_it_too() -> None:
    """**SSE 那条路也 403**——所以 `EventSource` 会直接 `onerror`。

    如果只有快照端点鉴权、SSE 不鉴权，那屏上根本不会卡在骨架上
    （流会正常推事件）。这一条确认「卡住」的机械原因是真的。
    """
    assert _status(f"/jobs/{NOT_MINE}/events") == 403


# ───────────────────────── 二、客户端把 401 与 403 分开认出来


def test_the_client_exposes_an_access_state() -> None:
    """`JobStreamState` 上有 `access`，且它**不是** `connection` 的一个取值。

    塞进 `connection` 的话，「不让你连」就成了「连接的一种状态」——
    而它其实是**答案已经给了**：重连一万次也还是 403。
    """
    from_source = _code(CLIENT.read_text(encoding="utf-8"))

    assert "access" in from_source, "客户端还是不认这件事"
    assert re.search(r'"denied"', from_source), "没有 denied 这一态"
    assert re.search(r'"unauthenticated"', from_source), "401 那一态缺了"
    assert '"disconnected" | "denied"' not in from_source, (
        "denied 被塞进了 connection 的取值里")


def test_the_two_auth_failures_map_to_two_states() -> None:
    """401 → `unauthenticated`，403 → `denied`（`AUTH-03` 口径）。

    401 是「你是谁」（去登录），403 是「你能干什么」（去要权限）。
    并成一句的话，用户不知道下一步该做什么。
    """
    from_source = _code(CLIENT.read_text(encoding="utf-8"))

    assert "401" in from_source and "403" in from_source
    # 两个状态码 MUST 落到两个不同的分支上——写在同一个条件里就是并成一句。
    assert not re.search(r"(401\s*\|\|\s*[^)]*403|403\s*\|\|\s*[^)]*401)", from_source), (
        "401 与 403 被写进了同一个条件")


def test_an_unrelated_failure_is_not_reported_as_denied() -> None:
    """**阴性对照的源码半边**：500 / 断网 NEVER 被说成「无权」。

    说成无权的话，用户会去要一个他本来就有的权限，而真正的问题在后端。
    """
    from_source = _code(CLIENT.read_text(encoding="utf-8"))

    assert '"unknown"' in from_source, "没有「探不出来」这一态"


def test_the_probe_runs_once_not_in_a_loop() -> None:
    """探一次，**不是轮询**。

    轮询会在真断网时对着一个连不上的后端反复打，
    而屏上那句话不会因为多打几次变得更准。
    """
    from_source = _code(CLIENT.read_text(encoding="utf-8"))

    assert "setInterval" not in from_source, "引入了轮询"
    assert "while (" not in from_source


# ───────────────────────── 三、屏上真的显示（vitest 实跑）


def test_the_screen_has_a_denied_branch() -> None:
    """那一屏有第五态，且它带自己的取证属性。

    **取证属性判在组件里，不判在屏里**：屏只负责分支，
    `data-job-denied` 属于那个通用件——判错地方的话，
    一次把属性搬进通用件的正确重构会被判成「属性丢了」。
    """
    page = _code(PAGE.read_text(encoding="utf-8"))
    assert COMPONENT.exists(), "无权提示件不在"
    component = _code(COMPONENT.read_text(encoding="utf-8"))

    assert 's.access === "denied"' in page, "屏上没有无权那一条分支"
    assert "JobDeniedNotice" in page, "屏上没有挂那个件"
    assert "data-job-denied" in component, "无权件没有断言面"


def test_the_denied_state_is_not_the_disconnect_notice() -> None:
    """**NEVER 与断线态合并**。

    `SseDisconnectNotice` 说的是「连不上」（可恢复，正在重连）；
    「不让你连」是终局的。合并之后屏上会劝用户「稍后重试」，
    而重试永远不会成功。
    """
    page = _code(PAGE.read_text(encoding="utf-8"))
    # **剥注释再判**：无权件的注释里逐字写着「与 `SseDisconnectNotice` 刻意不共用」
    # 以及那句「劝一个无权的用户『稍后重试』」——两句都是**在解释为什么不那样做**。
    # 不剥的话，写清楚这条边界的人会被自己的判据罚（第十二次同一形状）。
    notice = _code(COMPONENT.read_text(encoding="utf-8"))

    assert "SseDisconnectNotice" in page, "断线那一态被删了"
    assert "JobDeniedNotice" in page
    assert "SseDisconnectNotice" not in notice, "无权件复用了断线件"
    # **禁的是「劝」，不是「提到」**：本件的文案与注释里都写着「重试不会有用」，
    # 那是在否掉重试这条路。第一版判据禁了「重试」二字，当场把这句实话判成违规
    # （本仓第十一次撞见「把说明问题的那句话当成问题本身」）。
    # 劝人重试的话术在**文案里**，所以这一条改判 messages，而不是判组件源码。
    messages = json.loads(
        (REPO / "web" / "messages" / "zh.json").read_text(encoding="utf-8"))
    for key in ("job.denied.hint", "job.unauthenticated.hint"):
        for advice in ("稍后重试", "请重试", "再试一次"):
            assert advice not in messages[key], (
                f"{key} 在劝人重试——而重试永远不会成功：{messages[key]}")
    assert "重试不会有用" in messages["job.denied.hint"], (
        "403 那一句没明说重试没用——什么都不说的话，用户自己会去刷新")


def test_the_denied_state_replaces_the_skeleton_not_stacks_on_it() -> None:
    """无权时**不再显示加载骨架**。

    骨架的意思是「还在连」。两个一起出现，用户读到的还是「等一等」——
    而这一屏正是因为那张永远转下去的骨架才立单的。
    """
    page = _code(PAGE.read_text(encoding="utf-8"))
    # 比的是**两条分支的条件**，不是「denied 这个词第一次出现在哪」——
    # 后者会被 import 行左右，而 import 的顺序与命中顺序无关。
    denied_branch = page.index('s.access === "denied"')
    skeleton_branch = page.index("s.status === null")

    assert denied_branch < skeleton_branch, "无权分支排在骨架之后——骨架会先命中"
    # 无权那一支里 NEVER 出现骨架：两个一起出现，用户读到的还是「等一等」。
    denied_body = page[denied_branch:skeleton_branch]
    assert "LoadingSkeleton" not in denied_body, "无权时还画着加载骨架"


def test_the_rendering_is_asserted_by_a_real_component_test() -> None:
    """**跑一次 vitest**：断言那句话真的出现在渲染树上。

    源码里有 `data-job-denied` 与「渲染出来了」是两件事——
    分支写错了条件时源码判据照样绿。
    """
    assert VITEST.exists(), "没有组件级判据"
    done = subprocess.run(
        ["npx", "vitest", "run", "lib/jobDenied"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=REPO / "web", timeout=600, check=False, shell=True)

    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]
    assert "passed" in done.stdout


# ───────────────────────── 四、403 NEVER 进噪声白名单


def test_the_forbidden_status_is_not_whitelisted_as_console_noise() -> None:
    """`CONSOLE_BASELINE` 里 NEVER 出现为 403 开的额度（`DEC-037` 的原话）。

    那等于**把鉴权正确工作的证据当成噪声吞掉**，
    而下一次鉴权真的坏了时，这条判据不会响。

    判的是**基线表本身**，不是整份文件：文件里那段改因注释逐字写着
    「NEVER 把 403 加回来」——把说明禁令的那句话判成违规是第十一次同一形状。
    """
    code = SWEEP.read_text(encoding="utf-8")
    table = code[code.index("CONSOLE_BASELINE"):code.index("def _report")]
    entries = [line for line in table.splitlines()
               if line.lstrip().startswith('"/') and ":" in line]

    for line in entries:
        assert "jobs" not in line, f"给作业屏开了额度：{line}"
    assert not any("403" in line for line in entries), "有一条额度是为 403 开的"


# ───────────────────────── 五、第 6 批那条反向判据要跟着翻过来


def test_the_batch_six_placeholder_judgement_was_turned_around() -> None:
    """`FIX-09` 留的那条 `test_the_job_screen_still_has_no_denied_state`
    断言的是这一屏**还没有**这个态——本卡建好之后它必须被翻成正向。

    单子里写着「它哪天红了是好事」。**红了就该回去改它**，
    而不是让一条描述旧世界的判据一直红着——那会让下一个人以为产品坏了。
    """
    probe = (REPO / "tests" / "v041" / "test_probe_job_owned.py").read_text(
        encoding="utf-8")

    assert "still_has_no_denied_state" not in probe, "那条反向判据还在"
    assert "UIX-04" in probe, "翻过来时没写是被哪张卡翻的"


# ───────────────────────── 六、单据关掉


def test_the_sheet_is_closed() -> None:
    text = SHEET.read_text(encoding="utf-8")
    head = "\n".join(text.splitlines()[:8])

    assert "**状态** closed" in head, f"单据还开着：{head!r}"
    assert "UIX-04" in text
    for must in ("401", "403", "断线"):
        assert must in text, f"关单没写清 {must}"


def test_the_fifth_state_is_recorded_in_the_screen_docstring() -> None:
    """那一屏的注释里数得清**五**态。

    注释写着四态而代码有五个分支时，下一个人会以为多出来那个是遗留代码。
    """
    page = PAGE.read_text(encoding="utf-8")

    assert "五态" in page or "第五态" in page, "屏头注释没把新态数进去"
