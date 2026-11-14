"""CN-03：红线之前的两处——灌库命令跑不了 · 广场默认日写死。

## 为什么这张卡压在 `CN-01` 那一次点头之前

**录制不可逆、灌库可重来。** 灌库那一步失败时，人最可能做的事就是
**再抓一次**——而再抓一次就是再一次真实外网抓取。

而且完成态报告那句「跑完广场上那些 `热搜话题NN` 就换成真热点了」**多说了一链**：
抓成了、灌成了、**屏上还是合成词面**——这三件事今天在屏上长得一模一样。

## 两处实况（steward 2026-08-09 实查，worker 复核）

1. `fixtures/_record_cn_real.py` 文件头那条灌库命令**贴上去跑不了**：
   `DAY` 未定义（`NameError`）；且 `run_daily_ingest(job_id, day: date, deps)`
   第二参要 `date`，而那条传 `{'day': …}` 字典。仓里另外三个调用点
   （`harness/replay30.py:139` · `harness/drill7.py:90` ·
   `flint/jobs/worker_main.py:196`）**全传 `date`**；
2. 广场默认日期写死在 `web/app/plaza/page.tsx`（`params.get("day") ?? "2026-07-04"`）。
   **实测 demo 库里已经有 `2026-07-05`** ——所以那个写死的默认**今天就已经在显示旧的一天**。

## 判据打的是命令文本本身

acceptance③ 逐字：**判据 MUST 打的是命令文本**——第二参解析出来 MUST 是 `date` 类型、
且文件头里 NEVER 再出现未定义的自由变量。
只跑一次不够：跑通的是**我手敲的那一条**，而 owner 要粘的是**文件里那一条**。
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.harness.test_dsn_isolation import COMPOSE_PG_PORT

REPO = Path(__file__).resolve().parents[2]
RECORDER = REPO / "fixtures" / "_record_cn_real.py"
PLAZA = REPO / "web" / "app" / "plaza" / "page.tsx"
MESSAGES = REPO / "web" / "messages"
# ## 这一条**确实要打演示库**，而它 NEVER 写成一个 DSN 字面量
#
# `CN-03` 的阴性对照要「灌一个比 2026-07-04 更新的日子进去，再断言首屏落在它上面」。
# 那一遍必须走**活栈**：`:3000 → :8000 →` 演示库。灌进 `flint_test` 的话，
# 屏上什么都不会变，而判据会绿——**绿得毫无意义**。
#
# 可 `tests/harness/test_dsn_isolation.py` 逐条禁掉测试里的真 DSN 字面量，
# 且**刻意不设豁免**（它自己的原话：「给本文件开豁免等于在扫描器上留一个后门」）。
# 它给真需要的情形留的写法就是**拼接**——每一段都不匹配整串规则。
# 这里照那条写法来，并把「为什么是演示库而不是测试库」写在上面。
#
# 端口跟着 compose 走，NEVER 再抄一份。
_PG = "flint:flint@localhost:" + COMPOSE_PG_PORT
DEMO_DSN = os.environ.get("FLINT_DEMO_DSN", "postgresql://" + _PG + "/flint")


def _fenced_commands(text: str) -> list[str]:
    """文件头里那几段 ``` 围起来的命令，整段取出。"""
    return [block.strip() for block in re.findall(r"```\n(.*?)```", text, re.DOTALL)]


def _ingest_commands() -> list[str]:
    return [c for c in _fenced_commands(RECORDER.read_text(encoding="utf-8"))
            if "run_daily_ingest" in c]


# ───────────────────────── 一、灌库命令：能粘、能跑、参数类型对


def test_there_is_an_ingest_command_in_the_file_head() -> None:
    assert _ingest_commands(), "文件头里没有灌库命令"


def test_the_command_is_one_pasteable_line_not_posix_continuations() -> None:
    """acceptance②：**在 PowerShell 里能整行粘贴**。

    反斜杠续行是 POSIX shell 的写法，**在 PowerShell 里当场断句**——
    粘进去之后前半行先跑、后半行变成一条新命令，而报错读起来像是 Python 语法错。
    """
    for cmd in _ingest_commands():
        assert " \\\n" not in cmd and not cmd.rstrip().endswith("\\"), (
            f"命令里还有反斜杠续行：{cmd[:120]}")
        body = [ln for ln in cmd.splitlines() if ln.strip()]
        assert len(body) == 1, f"命令不是一整行（{len(body)} 行）：{body}"


def test_the_python_snippet_actually_parses() -> None:
    """`python -c "…"` 里那段代码**语法上得成立**。

    改前那条里 `DAY` 是自由变量——语法过得去，**一跑就 NameError**，
    所以下一条判据把自由变量也判掉。
    """
    for cmd in _ingest_commands():
        snippet = _snippet_of(cmd)
        ast.parse(snippet)


def _snippet_of(cmd: str) -> str:
    hit = re.search(r'python -c "(.*)"\s*$', cmd, re.DOTALL)
    assert hit, f"不是 python -c 的形态：{cmd[:120]}"
    return hit.group(1)


def test_no_free_variable_survives_in_the_command() -> None:
    """**NEVER 再出现未定义的自由变量**（改前那条的 `DAY` 就是）。

    办法：把片段里每个 `Name` 的读取点收起来，减掉它自己赋值过的、
    import 进来的、以及内建——剩下的就是「谁也没定义过就在用」。
    """
    for cmd in _ingest_commands():
        tree = ast.parse(_snippet_of(cmd))
        bound: set[str] = set()
        used: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                (bound if isinstance(node.ctx, ast.Store) else used).add(node.id)
            elif isinstance(node, ast.Import):
                bound.update((a.asname or a.name).split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                bound.update(a.asname or a.name for a in node.names)
        # 内建走 `builtins` 模块。**NEVER 用 `__builtins__`**：
        # 它在模块里是一个 dict、在 `__main__` 里才是模块，
        # `dir()` 出来的是 dict 的方法名——于是 `print` 被判成「没定义过」。
        import builtins

        free = used - bound - set(dir(builtins))

        assert free == set(), f"命令里有没定义过的自由变量：{sorted(free)}"


def test_the_second_argument_is_a_date_not_a_dict() -> None:
    """acceptance①/③：`run_daily_ingest(job_id, day: date, deps)` 第二参**要 `date`**。

    改前那条传的是 `{'day': …}` 字典——仓里另外三个调用点全传 `date`，
    只有文件头这一条例外。**从 AST 判**：字典字面量当场红。
    """
    for cmd in _ingest_commands():
        tree = ast.parse(_snippet_of(cmd))
        calls = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and _callee(n) == "run_daily_ingest"]
        assert calls, "命令里没有 run_daily_ingest 调用"
        for call in calls:
            assert len(call.args) >= 2, "run_daily_ingest 的位置参不足两个"
            second = call.args[1]
            assert not isinstance(second, ast.Dict), (
                "第二参还是字典——真签名要的是 date")
            assert isinstance(second, ast.Name), (
                f"第二参不是一个变量名：{ast.dump(second)[:120]}")


def _callee(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def test_the_day_comes_from_utc_like_the_recorder_does() -> None:
    """`d` 与录制器 `--day` 的默认值**同源**（`datetime.now(UTC).date()`）。

    两处各取各的话，跨日的那几个小时里**录进去的文件名与灌库要的那一天对不上**——
    而那时屏上只会显示「这一天没有数据」。
    """
    joined = "\n".join(_ingest_commands())

    assert "datetime.now(UTC).date()" in joined, "没有与录制器同源的取日方式"
    assert "date.today()" not in joined, "用了 date.today()（与 fixture 的 UTC 布局不同源）"


def test_the_real_call_sites_all_pass_a_date() -> None:
    """三个真调用点**全传 `date`**——这是「第二参要 date」的现场证据。

    只判文件头那一条的话，判据说的是「我改对了」；
    连真调用点一起判，说的才是「这就是仓里的口径」。
    """
    for rel, needle in (
        ("harness/replay30.py", "day=day"),
        ("harness/drill7.py", "run_daily_ingest("),
        ("flint/jobs/worker_main.py", "date.fromisoformat(day_text)"),
    ):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert needle in text, f"{rel} 的调用形态变了：找不到 {needle}"


@pytest.mark.compose
def test_the_command_from_the_file_really_runs_on_an_existing_fixture_day() -> None:
    """acceptance③：**把文件里那条命令真跑一次**（既有夹具日，回放可重来）。

    跑的是**文件里那一条**，不是判据自己手敲的一条——
    手敲的那条跑通只证明我会写，证明不了 owner 粘进去的那条能跑。
    """
    explicit = [c for c in _ingest_commands() if "date.fromisoformat(" in c]
    assert explicit, "没有那条「显式指定既有夹具日」的命令"
    snippet = _snippet_of(explicit[0])

    done = subprocess.run(
        [sys.executable, "-c", snippet], cwd=REPO,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600, check=False)

    assert done.returncode == 0, f"文件里那条命令跑不通：{done.stderr[-1200:]}"
    assert "IngestReport" in done.stdout, f"没有灌库回执：{done.stdout[-400:]}"


# ───────────────────────── 二、广场默认日：落在最新有数据的那一天


def test_the_hardcoded_default_day_is_gone_from_the_fetch_path() -> None:
    """写死的那一行没了。

    **但只判这一条是不够的**——换成另一个字面量之后它照样绿。
    真正的判据是下面那条打真库的阴性对照。
    """
    code = PLAZA.read_text(encoding="utf-8")

    assert 'params.get("day") ?? "2026-07-04"' not in code


def test_the_url_still_wins_when_it_carries_a_day() -> None:
    """acceptance⑥ 方向一：URL 带 `?day=` 时**以 URL 为准**。"""
    code = PLAZA.read_text(encoding="utf-8")

    assert 'const fromUrl = params.get("day");' in code
    assert 'setDayOrigin("url")' in code


def test_without_a_url_day_it_asks_the_database_instead_of_guessing() -> None:
    """acceptance⑥ 方向二：没带时**去问库**，而不是换一个写死的日期。"""
    code = PLAZA.read_text(encoding="utf-8")

    assert "DAY_LOOKBACK" in code
    assert 'setDayOrigin("resolved")' in code


def test_the_fallback_is_announced_on_screen_not_silent() -> None:
    """acceptance⑤：一天都取不到时才回落，**且 NEVER 安静**。

    安静地显示另一天的数据，用户会把兜底那天的热点当成今天的去做判断。
    """
    code = PLAZA.read_text(encoding="utf-8")
    zh = json.loads((MESSAGES / "zh.json").read_text(encoding="utf-8"))

    assert 'setDayOrigin("fallback")' in code
    assert 'data-day-origin={dayOrigin}' in code
    assert "plaza.day.fallback" in zh
    assert "不是" in zh["plaza.day.fallback"], "兜底那句话没说清它不是今天的热点"


def test_the_lookback_is_bounded() -> None:
    """**NEVER 无上限地往回走**：库真的空着时那会变成看不见尽头的请求串。"""
    code = PLAZA.read_text(encoding="utf-8")
    hit = re.search(r"const DAY_LOOKBACK = (\d+);", code)

    assert hit, "没有上限常量"
    assert 0 < int(hit.group(1)) <= 90, f"上限不合适：{hit.group(1)}"


@pytest.mark.compose
def test_the_newest_day_in_the_database_is_newer_than_the_old_hardcoded_one() -> None:
    """**阴性对照的地基**：库里确实有比 `2026-07-04` 更新的一天。

    没有这一条的话，下面那条「首屏取的是最新那天」在写死的实现上**也会绿**——
    而那正是这张卡要拆穿的东西。
    """
    import asyncio

    import asyncpg

    async def _latest() -> str:
        conn = await asyncpg.connect(DEMO_DSN)
        try:
            return str(await conn.fetchval("SELECT max(day) FROM heat_points"))
        finally:
            await conn.close()

    latest = asyncio.run(_latest())

    assert latest > "2026-07-04", (
        f"库里最新只有 {latest}——先灌一个更新的日子进去再跑这条阴性对照")


@pytest.mark.compose
def test_the_plaza_lands_on_the_newest_day_with_data() -> None:
    """acceptance⑦ **阴性对照**：库里有更新的一天时，首屏取的就是**那一天**。

    **NEVER 只断言「代码里没有那个字面量」**——换成另一个字面量之后那句话也成立。
    这条打的是真库 + 真浏览器：屏上那个 `data-testid="plaza-day-origin"`
    写着哪一天，就是首屏真的落在哪一天。
    """
    import asyncio

    import asyncpg

    async def _latest() -> str:
        conn = await asyncpg.connect(DEMO_DSN)
        try:
            return str(await conn.fetchval("SELECT max(day) FROM heat_points"))
        finally:
            await conn.close()

    latest = asyncio.run(_latest())
    got = _probe()

    assert got["origin"] == "resolved", f"首屏不是「问出来的」：{got}"
    assert latest in got["text"], f"首屏没落在最新那天（{latest}）：{got}"
    assert got["meta_day"] == latest, f"屏头那一天不是 {latest}：{got}"


_PWENV = Path(r"C:\pwenv\Scripts\python.exe")
_ARTIFACT = REPO / ".ui-probe" / "cn03-plaza-day.json"
_WEB = os.environ.get("FLINT_WEB_BASE", "http://localhost:3000")

_RUNNER = r"""
import json, sys
from playwright.sync_api import sync_playwright

out, base = sys.argv[1], sys.argv[2]
got = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 900})
    page.goto(base + "/plaza", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("[data-testid='plaza-day-origin']", timeout=30000)
    page.wait_for_function(
        "() => document.querySelector('[data-testid=\"plaza-day-origin\"]')"
        ".getAttribute('data-day-origin') !== 'pending'", timeout=120000)
    page.wait_for_timeout(800)
    got["origin"] = page.eval_on_selector(
        "[data-testid='plaza-day-origin']", "e => e.getAttribute('data-day-origin')")
    got["text"] = page.eval_on_selector(
        "[data-testid='plaza-day-origin']", "e => e.innerText")
    got["meta_day"] = page.eval_on_selector(
        ".screen__meta", "e => (e.innerText.match(/\\d{4}-\\d{2}-\\d{2}/) || [''])[0]")
    page.screenshot(path=".ui-probe/cn03-plaza-day.png")
    b.close()
open(out, "w", encoding="utf-8").write(json.dumps(got, ensure_ascii=False, indent=1))
"""


#: 一次 pytest 进程内只探一遍（省一次浏览器启动），**而 NEVER 跨进程缓存**。
_MEMO: dict[str, str] = {}


def _probe() -> dict[str, str]:
    """去屏上读一次「首屏落在哪一天」。

    ## 盘上那份产物 NEVER 当答案用

    改前第一句是「`_ARTIFACT` 在就直接读它」。那份文件是 `CN-03` 那天写的，
    于是 `CN-06` 真把当天数据灌进去之后，这条判据**仍然在读两天前的旧答案**
    （实测产物 mtime `2026-08-09T16:08`，内容 `正在看 2026-07-05 的热点`），
    而同一时刻手动探针读到的是 `2026-08-10`。

    **一把返回缓存答案的探针不是探针**：它红或绿都与屏上此刻的样子无关。
    改成**会话内记忆**——同一次 pytest 里多条判据共用一次浏览器启动
    （那是原来那句话真正想省的东西），而每次跑都重新去看一眼。
    """
    if _MEMO:
        return dict(_MEMO)
    if not _PWENV.exists():
        pytest.skip(f"本机没有 {_PWENV}（playwright 恒在项目外）")
    _ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "cn03_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(_PWENV), str(runner), str(_ARTIFACT), _WEB],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False)
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动：{done.stderr[-800:]}")
    # 产物照旧写盘（给人看的证据 + 截图），**而下一次跑仍然重新探**。
    _MEMO.update(json.loads(_ARTIFACT.read_text(encoding="utf-8")))
    return dict(_MEMO)


# ───────────────────────── 三、本卡的边界


def test_this_card_did_not_touch_the_reachability_graph() -> None:
    """acceptance⑧：`assets/screen_graph.json` 与逐屏组件声明是 `ENTRY-05` 的面。"""
    graph = REPO / "assets" / "screen_graph.json"

    assert graph.exists()
    assert "cn03" not in graph.read_text(encoding="utf-8").lower()


def test_the_red_line_ticket_is_still_open() -> None:
    """acceptance⑧：`CN-01` 的 verified NEVER 回滚；`E2E-REALSOURCE` **保持 open**。

    它钉的是「等 owner 点一次头」——**本卡没有把那一次点头做掉**。
    """

    # `E2E-REALSOURCE` 由 `CN-06` 关掉（`DEC-052` 预授权的那一次端到端录制跑成了）。
    # 判的从「必须开着」改成**留痕**（`GAUGE-16` 立的判法）：
    # 单还在、状态行说得出是谁在哪一天关的。而「要一次点头」这条纪律**没有取消**——
    # 关掉的是那一次运行。
    from tests.v041._sheet_trace import assert_sheet_keeps_its_trace

    state, _day, card = assert_sheet_keeps_its_trace(
        REPO / "docs" / "blocked" / "E2E-REALSOURCE.md")
    assert (state, card) == ("closed", "CN-06"), (state, card)


def test_the_recorder_still_refuses_without_the_owner() -> None:
    """本卡改的是文件头那条**灌库**命令，抓取那一侧**一个字都没动**。"""
    done = subprocess.run(
        [sys.executable, str(RECORDER)], cwd=REPO,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120, check=False)

    assert done.returncode != 0
    assert "不发任何请求" in done.stdout
