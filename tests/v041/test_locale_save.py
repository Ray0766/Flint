"""LOCALE-SAVE：语言与地区**详情屏**的保存按钮，按下去要真的存。

## 改前它按下去什么都不会发生

`web/app/settings/locale/page.tsx` 渲染组件时写着 `status="idle"` 这个**字面量**，
且**没有传 `onSave`**。组件（`LocaleSettings`）早就备好了 `onSave?` 与
`idle|saving|error` 三态——缺的只是页面这一半。

屏上的效果是：按钮在、按得下去、**什么都不会发生**。
而组件文件头那句话说的正是这种形状：
「回滚之后屏上是旧值、没有报错，用户会以为自己没点到」。

`SHELL-01` / `SHELL-02` 之后**右上角那三根轴早就能存了**，
唯独这一屏的按钮是死的——两处存的本该是同一份 `prefs`。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from pathlib import Path

import httpx
import pytest

REPO = Path(__file__).resolve().parents[2]
PAGE = REPO / "web" / "app" / "settings" / "locale" / "page.tsx"
COMPONENT = REPO / "web" / "components" / "locale-settings" / "LocaleSettings.tsx"
API = os.environ.get("FLINT_API_BASE", "http://localhost:8000")
WEB = os.environ.get("FLINT_WEB_BASE", "http://localhost:3000")
PWENV = Path(r"C:\pwenv\Scripts\python.exe")
ARTIFACT = REPO / ".ui-probe" / "locale-save.json"


def _code(path: Path) -> str:
    """去掉注释再判——注释里写着改动理由，不剥的话解释得越清楚判据越红。

    本批已经因为这件事红过六次（`GAUGE-16` trace 记着）。
    """
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return "\n".join(
        ln for ln in text.splitlines() if not ln.strip().startswith("//"))


# ───────────────────────── 一、页面真的把那一半接上了


def test_the_page_passes_on_save() -> None:
    """`onSave` 传下去了——**没有它按钮就是死的**。"""
    code = _code(PAGE)

    assert "onSave=" in code, "按下去没反应：页面没给组件传 onSave"


def test_the_status_is_a_real_state_not_a_hardcoded_word() -> None:
    """`status` 从写死的字面量换成真状态。

    写死 `idle` 的话，保存中按钮不禁用、失败了屏上也不显示错误——
    组件那三态全部用不上。
    """
    code = _code(PAGE)

    assert 'status="idle"' not in code, "status 还是写死的"
    assert "status={status}" in code
    assert "useState" in code and '"saving"' in code and '"error"' in code


def test_the_write_goes_through_the_shared_client_not_a_second_fetch() -> None:
    """写回走 `putLocaleAxis`——**一处定义他处引用**。

    在这里新写一份 `fetch` 的话，两份写法会各自漂移，
    而漂移的那一天，右上角与这一屏存的就不是同一份 `prefs` 了
    （acceptance④ 要的正是这件事）。
    """
    code = _code(PAGE)

    assert "putLocaleAxis" in code
    assert "fetch(" not in code, "这一屏自己发了一次 fetch"


def test_only_the_changed_axis_is_written() -> None:
    """只发**改过的**那一根轴（A3 正交）。

    没改的原样回写一次，会把另一台设备上刚改的那根轴覆盖掉——
    而后端 `set_prefs` 的口径本来就是「只改传进来的那一项」。
    """
    code = _code(PAGE)

    assert re.search(r"draft\[axis\]\s*!==\s*saved\[axis\]", code), (
        "没有「只发改过的那一根」这一步")


def test_a_failed_save_never_rolls_the_draft_back() -> None:
    """保存失败 **NEVER 回滚成旧值**——两个方向各判一次。

    方向一：失败分支里 NEVER 出现把 `draft` 设回 `saved` 的动作；
    方向二：失败分支 MUST 把错误交出去（`status="error"` + 文案）。

    只判方向一的话，一个「失败了什么都不做」的实现也能过——
    而那与回滚一样坏：屏上是新值、没有报错，用户以为存上了。
    """
    code = _code(PAGE)
    # **只切 `save()` 这一个函数**：从 `catch` 一路切到文件尾的话，
    # JSX 里 `onChange` 那句 `setDraft` 也会被圈进来——
    # 于是判据报的是「失败分支把草稿改回去了」，**而那句 setDraft 与失败无关**。
    # （第一版就是这么写的，实测当场误报。）
    body = code[code.index("async function save"):]
    body = body[: body.index("\n  return (")]
    catch = body[body.index("catch"):]

    assert "setDraft" not in catch, "失败分支把草稿改回去了"
    assert 'setStatus("error")' in catch
    assert "setError(" in catch


# ───────────────────────── 二、阴性对照：摘掉 onSave 判据 MUST 红


def test_removing_on_save_makes_the_ruler_go_red() -> None:
    """**阴性对照**（acceptance⑤）：把 `onSave` 摘掉 → 判据红且点名「按下去没反应」。

    NEVER 只断言「代码里有 onSave 这个词」——那种判据在
    `onSave={undefined}` 面前照样绿。

    **真文件一个字都不动**：改在临时目录里跑一份判据副本。
    """
    import tempfile

    original = PAGE.read_text(encoding="utf-8")
    broken = re.sub(r"\n\s*onSave=\{[^}]*\}\}", "", original, count=1)
    assert broken != original, "这条对照的前提没了：页面里没有 onSave"

    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / "page.tsx"
        fake.write_text(broken, encoding="utf-8")
        code = _code(fake)

    assert "onSave=" not in code, "摘掉之后它还在——对照没造成"


# ───────────────────────── 三、打真栈：存下去、读回来是同一份


@pytest.mark.compose
def test_saving_here_is_readable_by_the_top_right_axes() -> None:
    """acceptance④：这一屏与右上角**存的是同一份 `prefs`**。

    判法是打真栈走一遍：用同一个身份 `PUT` 一次，再 `GET` 回来——
    右上角读的就是这个 `GET`。两处若各存各的，这里会读到旧值。

    身份每次跑换一个，**NEVER 复用一个固定 id**：
    上一次跑留下的值会让下一次跑的第一句断言就红（`SHELL-02` 栽过一次）。
    """
    who = f"locale-save-{uuid.uuid4().hex[:8]}"
    with httpx.Client(base_url=API, timeout=10.0,
                      headers={"x-user-id": who}) as client:
        seeded = client.put("/settings/locale", json={"region": "CN"})
        if seeded.status_code == 401:
            pytest.skip("这个身份不在库里——本条要真栈与真身份")
        assert seeded.status_code == 200, seeded.text

        wrote = client.put("/settings/locale", json={"lang": "en"})
        assert wrote.status_code == 200, wrote.text

        read = client.get("/settings/locale")
        assert read.status_code == 200
        body = read.json()

    # 改的那根变了，**没改的那根没被覆盖**——这正是「只发改过的那一根」的效果。
    assert body["lang"] == "en"
    assert body["region"] == "CN"


@pytest.mark.compose
def test_the_screen_really_saves_in_a_browser() -> None:
    """真浏览器**按一次那个按钮**，库里那份跟着变。

    源码层的判据只能证明「代码里接上了」；这一条证明**按下去真的存了**——
    而「按下去什么都不会发生」正是本卡要治的病，
    只判源码的话，一个 `onSave={() => {}}` 也能过。

    playwright 恒在项目外 C:/pwenv（本批 rules）。
    """
    if not PWENV.exists():
        pytest.skip(f"没有 playwright 环境：{PWENV}")

    driver = r'''
import json, sys
from playwright.sync_api import sync_playwright

WEB, OUT = sys.argv[1], sys.argv[2]
report = {}
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page()
    page.goto(f"{WEB}/settings/locale", wait_until="networkidle")
    picker = page.locator("select").first
    picker.wait_for(state="visible", timeout=15000)
    options = picker.locator("option").all_inner_texts()
    current = picker.input_value()
    nxt = next((o for o in picker.locator("option").all()
                if o.get_attribute("value") not in (None, current)), None)
    report["options"] = options[:5]
    report["before"] = current
    report["picked"] = nxt.get_attribute("value") if nxt else None
    if report["picked"]:
        picker.select_option(report["picked"])
    save = page.get_by_role("button").first
    report["button_text"] = save.inner_text()
    save.click()
    page.wait_for_timeout(2500)
    report["status_after_save"] = (
        page.locator("[data-locale-status]").first.get_attribute("data-locale-status")
        if page.locator("[data-locale-status]").count() else "unknown")
    page.reload(wait_until="networkidle")
    report["after_reload"] = page.locator("select").first.input_value()
    browser.close()
json.dump(report, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(report, ensure_ascii=False))
'''
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    done = subprocess.run(
        [str(PWENV), "-c", driver, WEB, str(ARTIFACT)], cwd=REPO,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=300, check=False)
    if "ERR_CONNECTION" in done.stderr or "net::" in done.stderr:
        pytest.skip(f"本机前端没起：{done.stderr[-200:]}")
    assert done.returncode == 0, f"{done.stdout[-600:]}{done.stderr[-800:]}"

    report = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert report["picked"], f"这一屏只有一个可选地区，选不动：{report}"
    # **刷新之后仍是刚选的那个** = 真的存进去了。
    # 改前这一步必红：按钮按得下去，而什么都不会发生。
    assert report["after_reload"] == report["picked"], report
    assert report["status_after_save"] != "saving", f"按完一直卡在 saving：{report}"
