"""DS-03：枚举原值直接上屏——`D_insufficient` 是数据库的值，不是给人看的话。

## 改前的实况

- `HotspotCard` 的判定槽把 `verdict` 原样渲染（`C_opportunity` 上屏）；
- `GateView` 的判定行同样（`{t("gate.verdict")}: {verdict.verdict}`）；
- `ProjectOverview` 的行状态直接渲染后端的 `status`。

三处坏在同一件事上：**切英文时它们不变**——于是中英两版看起来「都已经翻过了」，
而屏上那几个词谁也不是人话。

## 这份验收守的四件事

| # | 判什么 | 失败时说明什么 |
|---|---|---|
| ① | 每族枚举的成员与**真相源逐字对齐**（冻结件 / 后端源码解析出来的，NEVER 手抄） | 表漏了一个成员 |
| ② | 每个成员在 zh 与 en **各有一条**、且都不等于原值 | 标签没给全，或拿原值凑数 |
| ③ | 「未知 / 没查过 / 接口未提供」三者**互不同词**（中英各比一次） | 三种「没有」被混成一句 |
| ④ | **屏上不出现下划线小写的枚举原值**（真栈取证） | 有一处还在渲染原值 |

④ 是本卡的主判据：前三条都能在源码层作弊（表写得漂亮而组件根本没调它），
只有真屏上那一眼作不了弊。
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
REGISTRY = WEB / "lib" / "i18n" / "enumLabel.ts"
ZH = WEB / "messages" / "zh.json"
EN = WEB / "messages" / "en.json"
CONTRACTS = REPO / "contracts" / "models.py"
COVERAGE = REPO / "flint" / "competitor" / "coverage.py"
ARTIFACT = REPO / ".ui-probe" / "enum_labels.json"

PWENV = Path(r"C:\pwenv\Scripts\python.exe")
# 屏上出现枚举原值最容易被抓到的两屏：卡面（判定槽）与项目总览（行状态）。
SCREENS = [
    "http://localhost:3000/plaza",
    "http://localhost:3000/gate/job-gate1-live-qwen",
]

# 已登记的例外：**后端散文里嵌着原值**，不是前端渲染出来的。
# `flint/gate/rule_d.py:44` 写着 `missing_what=f"竞品扫描覆盖未达标（{coverage.reason}）"`——
# 那句话是后端拼的，前端只负责原样呈现（`GateView` 原样渲染 `missing_what` 是对的：
# 后端自己的说明改写一遍就把唯一有用的线索丢了）。
# 改它要动 v0.4 已 verified 的实现，按 worker.md §9.2 停下报 owner：
# 单据 `docs/blocked/BACKEND-PROSE-EMBEDS-RAW-ENUM.md`。
# 下面那条判据盯着这条例外**必须还在**——修好了就来删，NEVER 留永久豁免。
BACKEND_PROSE_EXCEPTIONS = ("竞品扫描覆盖未达标（not_saturated）",)

# 下划线小写：`D_insufficient` / `not_saturated` / `empty_unconfirmed` 都长这样。
# 单词型枚举（`unknown` / `failed`）不在这条里——它们由 ③ 那条守可分辨性。
RAW_ENUM = re.compile(r"\b[A-Za-z]+(?:_[a-z]+)+\b")


def _registry() -> dict[str, dict[str, object]]:
    """从 `enumLabel.ts` 解析族表。判据与实现同源，NEVER 在测试里再抄一份清单。"""
    text = REGISTRY.read_text(encoding="utf-8")
    out: dict[str, dict[str, object]] = {}
    for m in re.finditer(
        r'prefix:\s*"([\w]+)",\s*source:\s*"([^"]+)",\s*values:\s*\[([^\]]*)\]',
        text, re.DOTALL,
    ):
        values = re.findall(r'"([^"]+)"', m.group(3))
        out[m.group(1)] = {"source": m.group(2), "values": values}
    assert out, "enumLabel.ts 里解析不到任何族"
    return out


def _literal(path: Path, name: str) -> list[str]:
    """从 Python 源码解析 `X = Literal[...]` 的成员。**真相源是那一行，不是我记的**。"""
    text = path.read_text(encoding="utf-8")
    m = re.search(rf"^{name} = Literal\[(.*?)\]", text, re.DOTALL | re.MULTILINE)
    assert m, f"{path.name} 里找不到 {name} = Literal[…]"
    return re.findall(r'"([^"]+)"', m.group(1))


def _messages(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8"))


# ───────────────────────── ① 族表与真相源逐字对齐


@pytest.mark.parametrize(("prefix", "path", "name"), [
    ("verdict", CONTRACTS, "Verdict"),
    ("job_state", CONTRACTS, "JobState"),
    ("fact_status", CONTRACTS, "FactStatus"),
    ("alignment", CONTRACTS, "Alignment"),
    ("coverage", COVERAGE, "CoverageReason"),
])
def test_the_family_matches_its_source_verbatim(
        prefix: str, path: Path, name: str) -> None:
    """冻结件多一个成员而这里没给标签 → 当场红。**这就是「新增枚举没给标签则判红」。**"""
    registered = _registry()[prefix]["values"]

    assert set(registered) == set(_literal(path, name)), (
        f"{prefix} 族与 {path.name}::{name} 对不上：多 "
        f"{sorted(set(registered) - set(_literal(path, name)))}，少 "
        f"{sorted(set(_literal(path, name)) - set(registered))}"
    )


def test_every_registered_family_names_its_source() -> None:
    """没有真相源的族 = 一份手抄清单，它会悄悄与后端分开。"""
    for prefix, family in _registry().items():
        assert family["source"], f"{prefix} 族没写真相源"


# ───────────────────────── ② 中英各一份，且都不是原值


def test_every_value_has_a_label_in_both_languages() -> None:
    zh, en = _messages(ZH), _messages(EN)

    missing: list[str] = []
    for prefix, family in _registry().items():
        for value in family["values"]:
            key = f"enum.{prefix}.{value}"
            if key not in zh:
                missing.append(f"zh:{key}")
            if key not in en:
                missing.append(f"en:{key}")

    assert missing == [], f"这些枚举没有标签：{missing}"


def test_no_label_is_just_the_raw_value_again() -> None:
    """拿原值当标签是最容易的作弊法：两份文件都在、判据全绿、屏上照旧是原值。"""
    zh, en = _messages(ZH), _messages(EN)

    for prefix, family in _registry().items():
        for value in family["values"]:
            key = f"enum.{prefix}.{value}"
            assert zh[key] != value, f"{key} 的中文标签就是原值"
            # 英文这一侧的判据只能是「不是下划线小写形态」：单词型枚举（`failed`）的
            # 英文人话本来就是那个词（`Failed`），要求它「与原值不同」等于逼人编一个
            # 更啰嗦的同义词——那是判据在制造坏文案。真正要挡的是原值形态本身。
            assert "_" not in en[key], f"{key} 的英文标签仍是下划线形态"
            if "_" in value:
                assert en[key].lower() != value.lower(), f"{key} 的英文标签就是原值"


def test_no_component_hardcodes_a_label_of_its_own() -> None:
    """标签只有一处。各组件自己写一句的话，同一个值在两屏上会是两句话。"""
    offenders = [
        str(p.relative_to(WEB)) for p in WEB.rglob("*.tsx")
        if "node_modules" not in p.parts
        and not p.name.endswith(".test.tsx")
        and re.search(r'"(证据不足|不可行|红海|机会)[^"]*"', p.read_text(encoding="utf-8"))
    ]

    assert offenders == [], f"这些组件自己写了判定标签：{offenders}"


# ───────────────────────── ③ 三种「没有」互不同词


def test_the_three_kinds_of_absence_never_share_a_word() -> None:
    """「未知」「没查过」「接口未提供」是三件事，NEVER 用同一个词。

    - `unknown`：**查过了**，答案是「不知道」；
    - `not_checked`：**还没查**；
    - `not_provided`：**这个能力还没接**。

    混成一句，用户会拿「还没查」当成「查过了没有」——本仓一路在守的同一条纪律
    （`WIRE-12` 的假空态、`UI-09` 的「没查过 ≠ 是 0」、`GAUGE-11` 的四类分诊）。
    """
    for lang, table in (("zh", _messages(ZH)), ("en", _messages(EN))):
        words = {
            "unknown": table["enum.authority.unknown"],
            "not_checked": table["enum.availability.not_checked"],
            "not_provided": table["enum.availability.not_provided"],
        }
        assert len(set(words.values())) == 3, f"[{lang}] 三种「没有」共用了词：{words}"


def test_the_unknown_label_says_it_was_checked() -> None:
    """「未知」必须说得出「查过了」——只写「未知」两个字，它与「没查过」还是分不开。"""
    zh, en = _messages(ZH), _messages(EN)

    assert "查过" in zh["enum.authority.unknown"]
    assert "checked" in en["enum.authority.unknown"].lower()


# ───────────────────────── ④ 真屏上不出现下划线小写原值


_RUNNER = r"""
import json, sys
from playwright.sync_api import sync_playwright

out, urls = sys.argv[1], json.loads(sys.argv[2])
rows = []
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900})
    for url in urls:
        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
        except Exception as exc:
            rows.append({"url": url, "error": str(exc)[:200]})
            continue
        page.wait_for_timeout(1500)
        # 只取**看得见的文字**：`data-*` 上留原值是有意的（取证与判据认原值），
        # 那些 NEVER 算「上屏」。
        text = page.evaluate("() => document.body.innerText")
        rows.append({"url": url, "text": text})
    b.close()
open(out, "w", encoding="utf-8").write(
    json.dumps({"schema": "enum-labels/1", "screens": rows},
               ensure_ascii=False, indent=1))
"""


def _artifact() -> dict[str, object]:
    if ARTIFACT.exists():
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外，NEVER 进项目依赖）")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "enum_labels_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(PWENV), str(runner), str(ARTIFACT), json.dumps(SCREENS)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False,
        )
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动：{done.stderr[-400:]}")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_no_raw_enum_value_is_visible_on_screen() -> None:
    """**本卡主判据**：真屏上的可见文字里不出现任何一个已登记的枚举原值。

    前三条都能在源码层作弊——表写得漂亮而组件根本没调它。只有这一条作不了弊。
    """
    registered = {
        value
        for family in _registry().values()
        for value in family["values"]
        if "_" in value                       # 单词型由第 ③ 条守，见 RAW_ENUM 的说明
    }

    seen: dict[str, list[str]] = {}
    for screen in _artifact()["screens"]:
        if "text" not in screen:
            continue
        text = screen["text"]
        for phrase in BACKEND_PROSE_EXCEPTIONS:
            text = text.replace(phrase, "")
        hits = sorted(set(RAW_ENUM.findall(text)) & registered)
        if hits:
            seen[screen["url"]] = hits

    assert seen == {}, f"这些屏上还在渲染枚举原值：{seen}"


def test_the_registered_backend_prose_still_shows_up() -> None:
    """登记的那条**必须还在**——修好了就该来这里删一行，NEVER 留一条永久豁免。

    留着一条已经修好的豁免，等于把尺子的一部分永久关掉，
    而报告上看起来仍是「0 处原值」。
    """
    joined = "".join(s.get("text", "") for s in _artifact()["screens"])

    for phrase in BACKEND_PROSE_EXCEPTIONS:
        assert phrase in joined, (
            f"登记的后端散文 {phrase!r} 已经不在屏上了——去 test_enum_labels.py 删掉这一行，"
            f"并关掉 docs/blocked/BACKEND-PROSE-EMBEDS-RAW-ENUM.md"
        )


def test_the_probe_actually_saw_something() -> None:
    """探针必须真取到文字——空字符串会让上一条无条件通过（那是最坏的绿）。"""
    screens = [s for s in _artifact()["screens"] if "text" in s]

    assert screens, f"一屏都没打开：{_artifact()['screens']}"
    for screen in screens:
        assert len(screen["text"]) > 40, f"{screen['url']} 几乎没有文字，取证不成立"


def test_the_ruler_would_catch_a_raw_value(tmp_path: Path) -> None:
    """**阴性对照**：把一个原值塞进「屏上文字」，上面那条必须红。

    没有这一条，`seen == {}` 可能只是因为正则根本认不出这些值。
    """
    registered = [
        value for family in _registry().values()
        for value in family["values"] if "_" in value
    ]
    fake = f"判定：{registered[0]} 已完成"

    assert set(RAW_ENUM.findall(fake)) & set(registered), (
        f"尺子认不出原值 {registered[0]}——它给出的 0 命中说明不了任何事"
    )
