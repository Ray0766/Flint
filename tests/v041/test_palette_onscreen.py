"""PAL-03：换板之后重拍取证——**屏上量到的就是 token 里的值**。

换板改的是一个 CSS 文件里的十几行值；「它真的到屏上了吗」只有真浏览器答得出来。
本文件判四件事：

1. **屏上量到的 == 声明的**：`getComputedStyle(body).backgroundColor` 归一到 `rgb()`
   之后与 `tokens/colors.css` 里 `--paper` 的声明**逐字相等**，明暗各一次；
2. **两个主题量到的不同**：相同就说明主题没切（`EYE-02` 那个洞的原形）；
3. **换板是看得见的**：同一屏同一主题的换板前后截图**字节不同**
   （`FB-01`/`EYE-03` 记过反面：主题开关什么都没改时，两张图逐字节相同）；
4. **旧照片不许留着当现状**：没重拍的产物在同目录留一行说明它是换板前的。

`EYE-04` 那四条老线（一行药丸条 / 铺满 / 零横向溢出 / 零控制台报错）
由 `tests/v041/test_eye04.py` 照旧判——本文件重拍它读的那份产物，**不放宽它的口径**。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / ".ui-probe"
PALETTE = PROBE / "palette"
ONSCREEN = PALETTE / "onscreen.json"
BEFORE_DIR = PALETTE / "before"
INVENTORY = PALETTE / "inventory.json"
NOTICE = PROBE / "换板前的旧图说明.md"
PWENV = Path(r"C:\pwenv\Scripts\python.exe")
PROBE_TOOL = REPO / "tools" / "ui_probe_palette.py"
COLORS = (REPO / "web" / "public" / "_ds"
          / "flint-design-system-8fd95ba3-cf31-49b6-b9d8-c863f3dc2724"
          / "tokens" / "colors.css")

_INPUTS = (COLORS, PROBE_TOOL)


def _inputs_stamp() -> str:
    import hashlib

    h = hashlib.sha256()
    for path in _INPUTS:
        h.update(path.read_bytes() if path.exists() else b"")
    return h.hexdigest()[:16]


def _report() -> dict[str, object]:
    """屏上那份取证；**板改了就重拍**（指纹里含 `colors.css` 本身）。"""
    if ONSCREEN.exists():
        cached = json.loads(ONSCREEN.read_text(encoding="utf-8"))
        if cached.get("inputs_stamp") == _inputs_stamp():
            return dict(cached)
        ONSCREEN.unlink()
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外）")
    done = subprocess.run(
        [str(PWENV), str(PROBE_TOOL)], capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=REPO, check=False)
    if done.returncode != 0 or not ONSCREEN.exists():
        pytest.skip(f"真栈没起或探针跑不动：{(done.stderr or done.stdout)[-500:]}")
    got = json.loads(ONSCREEN.read_text(encoding="utf-8"))
    got["inputs_stamp"] = _inputs_stamp()
    ONSCREEN.write_text(json.dumps(got, ensure_ascii=False, indent=1), encoding="utf-8")
    return dict(got)


def _screens() -> dict[str, dict[str, str]]:
    return dict(_report()["screens"])  # type: ignore[arg-type]


# ═════════════════ 一、屏上量到的就是 token 里的值


@pytest.mark.parametrize("key", ("1920-light", "1440-light", "390-light",
                                 "1920-dark", "1440-dark", "390-dark"))
def test_the_body_background_is_exactly_the_declared_paper(key: str) -> None:
    """六屏逐一：`body` 的底色 == `--paper` 的声明值（归一到 `rgb()` 之后逐字相等）。

    判「相等」而不是「像」：换板最容易的坏法是**只换了一半**——
    某一层还留着旧值，而屏上看起来只是「有几处颜色不太对」。
    """
    row = _screens()[key]

    assert row["bodyBackground"] == row["declaredPaper"], (
        f"{key}：屏上 {row['bodyBackground']}，_ds 声明 {row['declaredPaper']}")


def test_the_two_themes_really_measure_two_different_things() -> None:
    """明暗两次量到的底色**不同**——相同就说明主题根本没切。

    这正是 `EYE-02` 那个洞的原形（两次量到一位不差的同一组数而判据放行），
    `PAL-03` 在换板这条路上把同一条问一遍。
    """
    screens = _screens()
    light = {screens[k]["bodyBackground"] for k in screens if k.endswith("-light")}
    dark = {screens[k]["bodyBackground"] for k in screens if k.endswith("-dark")}

    assert len(light) == 1 and len(dark) == 1, f"同主题三个视口量到了不同的底色：{light} / {dark}"
    assert light != dark, f"两个主题量到同一组数：{light}"


def test_the_declared_values_come_from_the_palette_file_not_from_the_probe() -> None:
    """判准取自 `tokens/colors.css` 本身：探针只负责量，判准不许是它自己算的。"""
    text = COLORS.read_text(encoding="utf-8")
    root = re.search(r"^:root\{(.*?)\n\}", text, re.DOTALL | re.MULTILINE)
    assert root
    paper = re.search(r"--paper\s*:\s*([^;]+);", root.group(1))
    assert paper
    value = paper.group(1).split("/*")[0].strip().lstrip("#")
    wanted = f"rgb({int(value[0:2], 16)}, {int(value[2:4], 16)}, {int(value[4:6], 16)})"

    assert _screens()["1920-light"]["declaredPaper"] == wanted


# ═════════════════ 二、换板是**看得见**的


def test_the_swap_changed_the_pixels_not_just_the_file() -> None:
    """同一屏同一主题，换板前后的截图**字节不同**。

    反面记在 `FB-01`/`EYE-03`：主题开关什么都没改时，两张图逐字节相同——
    「改了配置」与「屏上真的变了」是两件事，这一条把后者钉住。
    """
    before = BEFORE_DIR / "plaza-1920x1080-light.png"
    after = PROBE / "eye04" / "plaza-1920x1080-light.png"
    if not before.exists():
        pytest.skip("换板前那张没留（`PAL-03` 开跑时才开始留）")

    assert after.exists(), "换板后那张没拍"
    assert before.read_bytes() != after.read_bytes(), (
        "换板前后两张图逐字节相同——那说明换的东西没到屏上")
    assert after.stat().st_size > 10_000, (
        f"重拍那张只有 {after.stat().st_size} 字节（0 字节的文件也叫「在盘上」）")


# ═════════════════ 三、清点：哪些产物有判据在读，哪些没重拍


def test_the_inventory_lists_which_artifacts_have_judges_reading_them() -> None:
    """先数清楚再重拍：清单落盘，且它是**跑出来的**，不是手写的。"""
    assert INVENTORY.exists(), "没有清点清单"
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

    assert inventory["counts"]["png"] > 100, inventory["counts"]
    assert inventory["counts"]["json"] > 30, inventory["counts"]
    assert inventory["read_by_tests"], "清单里没有「有判据在读」的那一类"
    assert inventory["reshot"], "清单里没有「本卡重拍了哪些」"


def test_the_old_shots_are_labelled_instead_of_left_as_current() -> None:
    """没重拍的旧图**留一行说明它是换板前的**，NEVER 留着当现状。

    旧板的图与新板的图混在一个目录里，下一个人无从分辨——
    而他会把先看到的那张当成今天的样子。
    """
    assert NOTICE.exists(), "旧图没有任何说明"
    body = NOTICE.read_text(encoding="utf-8")

    assert "PAL-03" in body and "换板" in body
    for must in ("重拍", "没重拍"):
        assert must in body, f"说明里缺「{must}」那一半"
