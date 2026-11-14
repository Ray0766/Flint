"""EYE-01：`scripts/ui_probe.py` 的**契约**验收——让「看得见」能当 verify_cmd 用。

## 这份测试为什么不起浏览器

playwright 恒在项目外的 `C:\\pwenv`（本卡 acceptance④ 断言它不在本项目三处依赖清单里），
所以项目 `.venv` 下的 `pytest` **起不了浏览器**，也不该起。能在这里验的是探针的**契约**：

- `--json` 报告的**结构**稳定（键名、层级、类型），断言消费方才敢照着写；
- `--assert` 的**判据解析与判定**是纯函数，与浏览器无关；
- **退出码分层**：判据不满足 / 前端没起 / playwright 缺失，**三种码互不冒充**。

第三条是本卡最要紧的一条。终检那批缺陷里有一半是「红被读成绿」或「红被读成另一种红」——
前端没起报成「判据不满足」，人会去改前端代码找一个并不存在的 bug，而真正要做的是
`start-demo.bat`。**两者的修法完全不同，所以它们的码必须不同。**

真起浏览器的那半（跑通一次真实断言）由 EYE-03 的前端 e2e 冒烟接手；本卡的产物是
「可被机器消费的判据面」，验的是这个面本身。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import ui_probe

REPO = Path(__file__).resolve().parents[2]
DEPENDENCY_FILES = ("requirements.lock", "pyproject.toml", "web/package.json")


def _page(**over: object) -> dict:
    """一份最小的、全绿的页面观测。用它当基线，逐条改坏来测判据。"""
    base = {
        "name": "home", "url": "http://localhost:3001/", "theme": "dark",
        "viewport": "desktop", "screenshot": "home-dark-desktop.png",
        "page_height": 2400, "scroll_width": 1440, "viewport_width": 1440,
        "horizontal_overflow": False,
        "console_errors": [], "console_error_count": 0,
        "html_class": "dark", "data_theme": "dark",
        "tokens": {"--surface": "#111"},
        "selectors": {},
    }
    base.update(over)
    return base


# ───────────────────────── acceptance①：--json 结构稳定


def test_the_report_shape_is_the_documented_one() -> None:
    """报告的键集是写死的契约——断言消费方照着这份键集写，改键就是破约。"""
    report = ui_probe.build_report([_page()], criteria=[])

    assert report["schema"] == ui_probe.SCHEMA
    assert set(report) == {"schema", "pages", "problems", "assertions", "ok", "frontend_down"}
    assert set(report["pages"][0]) == {
        "name", "url", "theme", "viewport", "screenshot",
        "page_height", "scroll_width", "viewport_width", "horizontal_overflow",
        "console_errors", "console_error_count",
        "html_class", "data_theme", "tokens", "selectors",
    }


def test_a_selector_observation_carries_its_box_and_visibility() -> None:
    """选择器观测带 boundingBox 与可见判定——F-09 那个「占 0 像素的空 span」正是这么现形的。"""
    page = _page(selectors={
        "[data-testid='disputed-mark']": {"present": True, "width": 0.0, "height": 0.0,
                                          "visible": False},
    })
    report = ui_probe.build_report([page], criteria=[])
    seen = report["pages"][0]["selectors"]["[data-testid='disputed-mark']"]

    assert seen == {"present": True, "width": 0.0, "height": 0.0, "visible": False}


# ───────────────────────── acceptance②：--assert 判据


def test_visible_criterion_fails_a_zero_sized_element_and_names_it() -> None:
    """「选择器 X 的宽高均 >0」——记号在 DOM 里但占 0 像素时必须红，并**点名是哪条判据**。

    这正是终检 F-09 的形状：`querySelector(...) !== null` 对一个不可见的空 span 照样通过。
    """
    criterion = ui_probe.parse_criterion("visible:[data-testid='disputed-mark']")
    page = _page(selectors={
        "[data-testid='disputed-mark']": {"present": True, "width": 0.0, "height": 12.0,
                                          "visible": False},
    })

    results = ui_probe.evaluate([page], [criterion])

    assert [r["ok"] for r in results] == [False]
    assert results[0]["criterion"] == "visible:[data-testid='disputed-mark']"
    assert "宽高" in results[0]["detail"]


def test_visible_criterion_passes_a_real_box() -> None:
    """正例：真有尺寸就该绿——一把见谁都报红的尺子同样量不出东西。"""
    criterion = ui_probe.parse_criterion("visible:.mark")
    page = _page(selectors={".mark": {"present": True, "width": 8.0, "height": 8.0,
                                      "visible": True}})

    assert [r["ok"] for r in ui_probe.evaluate([page], [criterion])] == [True]


def test_a_missing_selector_is_red_and_says_it_was_not_found() -> None:
    """选择器根本不在页面上：也红，但**说的是「找不到」**，不是「尺寸为 0」。"""
    criterion = ui_probe.parse_criterion("visible:.nope")
    page = _page(selectors={".nope": {"present": False, "width": 0.0, "height": 0.0,
                                      "visible": False}})

    result = ui_probe.evaluate([page], [criterion])[0]

    assert result["ok"] is False
    assert "找不到" in result["detail"]


def test_console_and_overflow_criteria_bite() -> None:
    """另两条判据：控制台报错数 == 0、无横向溢出。"""
    errors = ui_probe.parse_criterion("no-console-errors")
    overflow = ui_probe.parse_criterion("no-horizontal-overflow")
    bad = _page(console_errors=["error: boom"], console_error_count=1,
                horizontal_overflow=True, scroll_width=1600)

    results = ui_probe.evaluate([bad], [errors, overflow])

    assert [r["ok"] for r in results] == [False, False]
    assert "1" in results[0]["detail"]
    assert "1600" in results[1]["detail"]
    assert [r["ok"] for r in ui_probe.evaluate([_page()], [errors, overflow])] == [True, True]


def test_every_page_is_judged_not_just_the_first() -> None:
    """判据对**每一屏**都判：桌面绿、移动红时整体必须红。

    只判第一屏是这类工具最常见的偷懒方式，而移动端恰恰是横向溢出最容易出现的地方。
    """
    criterion = ui_probe.parse_criterion("no-horizontal-overflow")
    pages = [_page(viewport="desktop"),
             _page(viewport="mobile", horizontal_overflow=True, scroll_width=500)]

    results = ui_probe.evaluate(pages, [criterion])

    assert [r["ok"] for r in results] == [True, False]
    assert results[1]["page"] == "home/dark/mobile"
    assert ui_probe.build_report(pages, criteria=[criterion])["ok"] is False


def test_an_unknown_criterion_is_rejected_at_parse_time() -> None:
    """认不出的判据当场报错，NEVER 当成「通过」。

    默默跳过一条不认识的判据，等于让写判据的人以为自己守住了某件事。
    """
    with pytest.raises(ValueError, match="认不出的判据"):
        ui_probe.parse_criterion("looks-nice")


# ───────────────────────── acceptance③：三种红互不冒充


def test_a_refused_connection_is_classified_as_frontend_down() -> None:
    """`ERR_CONNECTION_REFUSED` = 前端没起，**不是**判据不满足。"""
    assert ui_probe.looks_like_frontend_down(
        "net::ERR_CONNECTION_REFUSED at http://localhost:3001/")
    assert ui_probe.looks_like_frontend_down("ECONNREFUSED 127.0.0.1:3001")


def test_a_real_page_error_is_not_classified_as_frontend_down() -> None:
    """页面自己报的错不算「前端没起」——把它算进去会把真 bug 藏起来。"""
    assert not ui_probe.looks_like_frontend_down("TypeError: x is not a function")
    assert not ui_probe.looks_like_frontend_down("Timeout 60000ms exceeded")


def test_the_three_failures_have_three_different_exit_codes() -> None:
    """退出码分层：判据不满足 1 / 前端没起 3 / playwright 缺失 2，两两不同。

    码相同就等于把「去起前端」和「去改代码」这两件事混成一件。
    """
    assert ui_probe.EXIT_OK == 0
    assert ui_probe.EXIT_ASSERT_FAILED == 1
    assert ui_probe.EXIT_NO_PLAYWRIGHT == 2
    assert ui_probe.EXIT_FRONTEND_DOWN == 3
    assert len({ui_probe.EXIT_OK, ui_probe.EXIT_ASSERT_FAILED,
                ui_probe.EXIT_NO_PLAYWRIGHT, ui_probe.EXIT_FRONTEND_DOWN}) == 4


def test_frontend_down_beats_assertion_failure() -> None:
    """前端没起时报的是「前端未运行」，NEVER 报成判据不满足。

    前端没起时判据当然全不满足——但那时候报「选择器不可见」会把人送去改一个
    并不存在的 bug。所以这个分类优先于判据结论。
    """
    report = ui_probe.build_report([], criteria=[], frontend_down=True)

    assert report["frontend_down"] is True
    assert ui_probe.exit_code(report) == ui_probe.EXIT_FRONTEND_DOWN

    with_failures = ui_probe.build_report(
        [_page(console_error_count=3, console_errors=["error: x"])],
        criteria=[ui_probe.parse_criterion("no-console-errors")],
        frontend_down=True,
    )
    assert ui_probe.exit_code(with_failures) == ui_probe.EXIT_FRONTEND_DOWN


def test_a_clean_run_with_no_criteria_still_exits_zero() -> None:
    """不给判据时是纯观测：干净就 0，有问题（溢出/控制台）仍然非零。"""
    assert ui_probe.exit_code(ui_probe.build_report([_page()], criteria=[])) == ui_probe.EXIT_OK
    noisy = ui_probe.build_report([_page(console_error_count=2,
                                         console_errors=["error: a", "error: b"])], criteria=[])
    assert ui_probe.exit_code(noisy) == ui_probe.EXIT_ASSERT_FAILED


def test_the_cli_reports_frontend_down_without_a_browser() -> None:
    """端到端一次：项目解释器跑 `--assert`，playwright 不在 → 必须报 playwright 缺失（码 2）。

    这一条同时钉住「本项目 .venv 里 NEVER 有 playwright」——真装进去了，这条会红。
    """
    done = subprocess.run(
        [sys.executable, "scripts/ui_probe.py", "--json", "--assert", "no-console-errors"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False,
    )

    assert done.returncode == ui_probe.EXIT_NO_PLAYWRIGHT, done.stdout + done.stderr
    assert "playwright" in (done.stdout + done.stderr).lower()
    assert "C:\\pwenv" in (done.stdout + done.stderr)


# ───────────────────────── acceptance④：playwright 恒在项目外


def test_playwright_is_absent_from_all_three_dependency_files() -> None:
    """三处依赖清单里 playwright 命中恒为 0。

    它是取证工具不是产品依赖：进了 lock 文件，CI 就要装一个浏览器，
    而 CI 恒不联网（S2-7）。
    """
    for rel in DEPENDENCY_FILES:
        text = (REPO / rel).read_text(encoding="utf-8").lower()
        assert "playwright" not in text, f"{rel} 里出现了 playwright"


def test_the_probe_module_imports_without_playwright() -> None:
    """模块本身在没有 playwright 的解释器里可以 import——判据面与浏览器解耦。

    否则这份契约测试自己就跑不起来，而「跑不起来的测试」等于没有测试。
    """
    assert "playwright" not in sys.modules
    assert callable(ui_probe.parse_criterion)


def test_the_json_report_round_trips() -> None:
    """报告可 JSON 序列化——`--json` 的输出要能被别的门直接吃。"""
    report = ui_probe.build_report([_page()], criteria=[ui_probe.parse_criterion("visible:.x")])

    assert json.loads(json.dumps(report, ensure_ascii=False))["schema"] == ui_probe.SCHEMA
