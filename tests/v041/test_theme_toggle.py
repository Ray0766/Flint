"""SHELL-02 / `DEC-047` / `DEC-050`：白天/夜间切换——板早就建好，缺的一直是控件。

## 实况

`DARK-01` 建了暗色板与**双通道**（`prefers-color-scheme` 与 `[data-theme]`，
后者写在 media 块之后所以压得过系统偏好），**而 `web/` 下零切换控件**——
今天用户只能跟着系统偏好走，手动切不了。

## 三态，而「跟随系统」是**显式**的那一个

`跟随系统 / 白天 / 夜间`。两态会把「**我没选过**」和「我选了白天」混成一个——
前者在系统切暗时该跟着变暗，后者 NEVER 变。合并之后这两种人只能有一种被满足，
而**屏上看不出自己是哪一种**。

落地上有一处容易做错：「跟随系统」**MUST 是移除 `data-theme` 属性**，
NEVER 写 `data-theme="system"`——那两条 CSS 规则一条都不匹配，
看起来像亮色，**而系统切暗时它不会变**。

## 存得住：第三根正交轴（`DEC-050`）

`prefs` 加一列，`Prefs` 加一个字段，`GET/PUT /settings/locale` 认第三根轴。
**不按设备存**的理由 `DEC-050` 写死了，本判据只钉住落地形态。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

REPO = Path(__file__).resolve().parents[2]
SHELL = REPO / "web" / "components" / "shell"
CONTROL = SHELL / "ThemeControl.tsx"
FIRST_PAINT = SHELL / "themeFirstPaint.ts"
APP_SHELL = SHELL / "AppShell.tsx"
MESSAGES = REPO / "web" / "messages"
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
PWENV = Path(r"C:\pwenv\Scripts\python.exe")
ARTIFACT = REPO / ".ui-probe" / "shell02-theme.json"
WEB = os.environ.get("FLINT_WEB_BASE", "http://localhost:3000")


# ───────────────────────── 一、第三根轴：库 · 域 · 端点


def test_the_migration_adds_the_theme_column_without_a_gap() -> None:
    """迁移接盘上当时最高的那一号，**不留号也不跳号**（`DEC-050` 逐字）。"""
    versions = sorted(
        (REPO / "migrations" / "versions").glob("[0-9][0-9][0-9][0-9]_*.py"))
    numbers = [int(p.name[:4]) for p in versions]
    mine = [p for p in versions if "prefs_theme" in p.name]

    assert len(mine) == 1, "主题那张迁移不在盘上，或者有两张"
    assert numbers == list(range(1, len(numbers) + 1)), f"号有洞或重号：{numbers}"
    text = mine[0].read_text(encoding="utf-8")
    assert re.search(r'down_revision\s*[:=]\s*"00\d\d"', text)


@pytest.mark.compose
def test_the_column_is_really_there_and_defaults_to_system() -> None:
    """实查库：非空 + 默认 `system`。

    可空的话，读的人分不出「没选过」与「选了跟随系统」——
    而这两件事在本卡里恰恰是同一件，更没有理由留一个第三态出来。
    """
    import asyncio

    import asyncpg

    async def _col() -> tuple[str, str]:
        conn = await asyncpg.connect(DSN)
        try:
            row = await conn.fetchrow(
                "SELECT is_nullable, column_default FROM information_schema.columns "
                "WHERE table_name = 'prefs' AND column_name = 'theme'")
        finally:
            await conn.close()
        assert row is not None, "prefs 上没有 theme 列"
        return row["is_nullable"], str(row["column_default"])

    nullable, default = asyncio.run(_col())

    assert nullable == "NO"
    assert "system" in default


def test_the_three_states_have_one_source_of_truth() -> None:
    """可选值**只有一份**：`flint/profile/prefs.py#_THEMES`。

    端点从那里取，NEVER 再抄一份——抄一份就是第二个真相，
    而它会在加第四态那天悄悄少一项。
    """
    from flint.profile.prefs import DEFAULT_THEME, theme_options

    assert theme_options() == ["dark", "light", "system"]
    assert DEFAULT_THEME == "system"

    settings = (REPO / "flint" / "api" / "settings.py").read_text(encoding="utf-8")
    assert "theme_options()" in settings, "端点没从那一份真相取"
    assert '"light"' not in settings, "端点里抄了一份主题清单"


def test_an_out_of_range_theme_is_refused_not_silently_dropped() -> None:
    """越界值**当场拒**，与另外两根轴同一条口径。

    NEVER 因为它是「显示偏好」就少一道校验：存进去之后每个读它的人
    都要再判一次，而总有人会忘。
    """
    from flint.profile.prefs import Prefs, PrefsStore, set_prefs

    store = PrefsStore()

    with pytest.raises(ValueError, match="theme"):
        set_prefs(store, user_id="u", theme="neon")
    assert store.get("u") == Prefs(), "被拒的那次写竟然改了库里那份"


def test_setting_the_theme_leaves_the_other_two_axes_alone() -> None:
    """三根轴**互不牵动**（`PRINCIPLES#A3` 的推广）。"""
    from flint.profile.prefs import Prefs, PrefsStore, set_prefs

    store = PrefsStore()
    store.put("u", Prefs(lang="en", region="JP", theme="system"))

    set_prefs(store, user_id="u", theme="dark")

    assert store.get("u") == Prefs(lang="en", region="JP", theme="dark")


@pytest.mark.compose
def test_the_endpoint_carries_the_third_axis_both_ways() -> None:
    """`GET` 回得出、`PUT` 收得下，且 `extra="forbid"` 照旧——**只是多认一个合法键**。"""
    from fastapi.testclient import TestClient

    from flint.api.app import create_app

    client = TestClient(create_app(dsn=DSN), raise_server_exceptions=False)
    # **每次跑换一个身份**：上一次跑把这个人的主题写成了 dark，
    # 于是下一次跑第一句就红——红的是判据自己没把前提清干净。
    head = {"x-user-id": f"shell02-{uuid4().hex[:8]}"}

    got = client.get("/settings/locale", headers=head).json()
    assert got["theme"] == "system", "新身份的默认不是跟随系统"
    assert sorted(got["options"]["theme"]) == ["dark", "light", "system"]

    put = client.put("/settings/locale", json={"theme": "dark"}, headers=head)
    assert put.status_code == 200, put.text
    assert put.json()["theme"] == "dark"

    bad = client.put("/settings/locale", json={"theme": "neon"}, headers=head)
    assert bad.status_code == 422, bad.text

    junk = client.put("/settings/locale", json={"nope": "x"}, headers=head)
    assert junk.status_code == 422, "extra=forbid 被放宽了"


@pytest.mark.compose
def test_the_theme_survives_a_new_store_object() -> None:
    """acceptance④：**存得住**（`prefs` 表）。"""
    from flint.profile.pgprefs import PgPrefsStore
    from flint.profile.prefs import set_prefs

    set_prefs(PgPrefsStore(dsn=DSN), user_id="shell02-persist", theme="light")

    assert PgPrefsStore(dsn=DSN).get("shell02-persist").theme == "light"


def test_the_preference_is_not_kept_in_the_browser() -> None:
    """真相在服务端（`DEC-050`）——控件 NEVER 拿浏览器存储当偏好。

    首帧那个 cookie 是**提示**不是真相，判据在下面单独量它的性质。
    """
    code = CONTROL.read_text(encoding="utf-8")

    assert "localStorage" not in code and "sessionStorage" not in code
    assert 'putLocaleAxis("theme"' in code, "没有写回服务端"


# ───────────────────────── 二、三态与「跟随系统」


def test_follow_system_is_an_explicit_option() -> None:
    """acceptance②：**「跟随系统」MUST 是一个显式选项**。"""
    code = CONTROL.read_text(encoding="utf-8")
    zh = json.loads((MESSAGES / "zh.json").read_text(encoding="utf-8"))

    # **只看 `THEMES` 那一行**：文件头那张表里也写着 `light`，
    # 按整份文件比位置的话，比的是注释而不是代码——本轮第五次撞上这个形状。
    line = next(ln for ln in code.splitlines() if ln.startswith("export const THEMES"))

    assert 'THEMES = ["system", "light", "dark"] as const' in line
    assert line.index('"system"') < line.index('"light"'), "「跟随系统」不是第一项"
    for key in ("theme.system", "theme.light", "theme.dark", "theme.label"):
        assert key in zh, f"缺词条 {key}"
    assert "跟随系统" in zh["theme.system"]


def test_follow_system_removes_the_attribute_instead_of_writing_it() -> None:
    """**最容易做错的那一处**：「跟随系统」= 移除 `data-theme`。

    写 `data-theme="system"` 的话那两条 CSS 规则一条都不匹配——
    看起来像亮色，**而系统切暗时它不会变**。
    """
    code = FIRST_PAINT.read_text(encoding="utf-8")

    assert "removeAttribute" in code
    body = code.split("export function applyTheme")[1]
    assert 'setAttribute("data-theme", choice)' in body
    assert '"data-theme", "system"' not in body


def test_an_explicit_choice_beats_the_system_preference_both_ways() -> None:
    """acceptance③：**两个方向各断言一次**（`DARK-01` 已实现的优先级）。

    这一条判的是 CSS 那一侧的既有事实：`[data-theme]` 写在 media 块**之后**，
    所以显式选择压得过系统偏好；而两条显式规则**都在**，
    所以从暗切回亮、从亮切到暗都成立。
    """
    css = next((REPO / "web" / "public" / "_ds").rglob("tokens/colors.css"))
    # **先剥注释再比位置**（`TAIL-01` 现场撞到的）：这一条靠 `index()` 比先后，
    # 而文件里的注释在解释「哪条规则管暗色」时也会写出 `[data-theme="dark"]`——
    # 于是尺子量到的是**注释的位置**，判出「显式暗色写在 media 之前」这种假红。
    # 本仓这一类（尺子读了注释）此前栽过六次。
    text = re.sub(r"/\*.*?\*/", "",
                  css.read_text(encoding="utf-8"), flags=re.DOTALL)

    media = text.index("prefers-color-scheme")
    dark = text.index('[data-theme="dark"]')
    light = text.index('[data-theme="light"]')

    assert dark > media, "显式暗色写在 media 之前——那样它压不过系统偏好"
    assert light > media, "显式亮色写在 media 之前"


def test_the_dark_palette_ruler_still_stands() -> None:
    """acceptance⑤：`DARK-02` 的 `theme-switches` 判据不倒。

    本卡只加控件与一列，**NEVER 动调色板**——两主题量到同一组颜色仍判红。
    """
    from subprocess import run as _run

    done = _run(
        [sys.executable, "-m", "pytest", "tests/v041/test_dark_palette.py",
         "tests/v041/test_theme_really_switches.py", "-q"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8",
        errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False)

    assert done.returncode == 0, done.stdout[-1500:]


# ───────────────────────── 三、首帧不闪


def test_the_first_paint_snippet_is_rendered_before_the_bar() -> None:
    """acceptance⑥：那一段**同步脚本**排在外壳最前面。

    排在后面的话它就不是「首帧之前」了——而这条 acceptance 要的正是那一刻。
    """
    code = APP_SHELL.read_text(encoding="utf-8")

    assert "THEME_FIRST_PAINT_SNIPPET" in code
    assert code.index("theme-first-paint") < code.index('data-shell="s0"')


def test_the_snippet_never_throws_and_never_writes_system() -> None:
    """那一段 NEVER 抛：在首帧之前抛错会把后面的解析也带停，
    而它做的只是一个优化。

    并且它**只认 light / dark**——`system` 那一态本来就不该写属性。
    """
    code = FIRST_PAINT.read_text(encoding="utf-8")
    snippet = code.split("THEME_FIRST_PAINT_SNIPPET = `")[1].split("`;")[0]

    assert "try{" in snippet and "catch" in snippet
    assert "'light'" in snippet and "'dark'" in snippet
    assert "'system'" not in snippet


def test_the_cookie_is_a_hint_and_says_so() -> None:
    """cookie 是**提示**不是第二个真相——文件头 MUST 把这条写死。

    清掉它之后用户的选择仍然在库里、换台设备也还在，丢的只是「首帧不闪」。
    **提示丢了只是慢一点，真相丢了是数据没了。**
    """
    code = FIRST_PAINT.read_text(encoding="utf-8")

    assert "不是第二个真相" in code
    assert "服务端赢" in code, "没写清两者分叉时谁说了算"
    assert "THEME_COOKIE" in code


def test_the_cookie_name_is_defined_once() -> None:
    """名字**一处定义**：两处各写一个的话，首帧永远读不到刚存下的选择，
    而屏上一切正常。"""
    control = CONTROL.read_text(encoding="utf-8")
    first = FIRST_PAINT.read_text(encoding="utf-8")

    assert first.count('THEME_COOKIE = "') == 1
    assert "THEME_COOKIE" in control
    assert 'flint_theme_hint' not in control, "控件里又写了一遍 cookie 名"


def test_the_server_value_reconciles_the_hint() -> None:
    """服务端那份到手时**纠正** DOM 与 cookie——两者分叉时服务端赢。"""
    code = CONTROL.read_text(encoding="utf-8")

    assert "applyTheme(serverTheme)" in code
    assert "rememberThemeHint(serverTheme)" in code


# ───────────────────────── 四、真浏览器：三态都真的切得动，且首帧不闪


_RUNNER = r"""
import json, sys
from playwright.sync_api import sync_playwright

out, base = sys.argv[1], sys.argv[2]
got = {}


def theme_of(page):
    return page.evaluate("() => document.documentElement.getAttribute('data-theme')")


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900},
                        color_scheme="light")
    page = ctx.new_page()
    page.goto(base + "/plaza", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("[data-testid='shell-theme-select']", timeout=30000)
    page.wait_for_timeout(1200)
    got["options"] = page.eval_on_selector_all(
        "[data-testid='shell-theme-select'] option", "els => els.map(e => e.value)")

    page.select_option("[data-testid='shell-theme-select']", "dark")
    page.wait_for_timeout(1500)
    got["after_dark"] = theme_of(page)

    # 刷新：存得住 + 首帧就是最终主题
    # **在 `domcontentloaded` 读**：`commit` 是导航刚提交、HTML 一个字节还没解析的时刻，
    # 那时候读到的恒是 null——量的是「浏览器还没开始」，不是「首帧」。
    # `domcontentloaded` 时那段同步脚本已经跑完，而 React 还没水合、取数也没回来——
    # 这正是「首帧就是最终主题」要量的那一刻。
    page.reload(wait_until="domcontentloaded", timeout=60000)
    got["first_paint_after_reload"] = theme_of(page)
    got["hydrated_at_read"] = page.evaluate(
        "() => !!document.querySelector('[data-theme-choice]')")
    page.wait_for_selector("[data-testid='shell-theme-select']", timeout=30000)
    page.wait_for_timeout(1200)
    got["after_reload"] = theme_of(page)
    got["choice_after_reload"] = page.eval_on_selector(
        "[data-testid='shell-theme']", "e => e.getAttribute('data-theme-choice')")

    page.select_option("[data-testid='shell-theme-select']", "system")
    page.wait_for_timeout(1500)
    got["after_system"] = theme_of(page)

    page.select_option("[data-testid='shell-theme-select']", "light")
    page.wait_for_timeout(1500)
    got["after_light"] = theme_of(page)
    page.screenshot(path=".ui-probe/shell02-theme.png")
    b.close()
open(out, "w", encoding="utf-8").write(json.dumps(got, ensure_ascii=False, indent=1))
"""


def _probe() -> dict[str, object]:
    if ARTIFACT.exists():
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外）")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "shell02_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(PWENV), str(runner), str(ARTIFACT), WEB],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False)
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动：{done.stderr[-800:]}")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_all_three_states_are_on_the_screen() -> None:
    got = _probe()

    assert got["options"] == ["system", "light", "dark"], got["options"]


def test_switching_to_dark_really_sets_the_attribute() -> None:
    got = _probe()

    assert got["after_dark"] == "dark", got


def test_the_first_frame_after_a_reload_is_already_dark() -> None:
    """acceptance⑥ 的可观测形式：**刷新之后第一帧就是最终主题**。

    探针在 `wait_until="commit"` 那一刻就读——那时 React 还没水合、
    取数也没回来。属性已经在了，说明那一段同步脚本干了活。
    """
    got = _probe()

    assert got["first_paint_after_reload"] == "dark", (
        f"首帧不是暗色（会闪白再变暗）：{got}")


def test_the_choice_survived_the_reload() -> None:
    got = _probe()

    assert got["after_reload"] == "dark"
    assert got["choice_after_reload"] == "dark", "服务端那份没存住"


def test_follow_system_takes_the_attribute_off_again() -> None:
    """切回「跟随系统」= 属性被拿掉，颜色交还给 `prefers-color-scheme`。"""
    got = _probe()

    assert got["after_system"] is None, f"「跟随系统」没有移除属性：{got}"


def test_switching_to_light_beats_a_dark_system() -> None:
    """显式亮色压过系统偏好（另一个方向）。"""
    got = _probe()

    assert got["after_light"] == "light", got
