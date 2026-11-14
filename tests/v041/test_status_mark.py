"""UIX-03 · `StatusMark`：A4 规则终于有可量对象了。

## 为什么「只靠颜色」不是无障碍加分项，是缺陷

只靠颜色的状态标记，在四种很常见的情况下**完全失效**：

1. **灰度打印**——报告被打出来交给评审，红绿两点变成一样的灰点；
2. **色觉差异**——红绿型最常见，而「成功/失败」偏偏最爱用红绿；
3. **强制暗色 / 高对比模式**——系统会覆写颜色；
4. **截图转黑白**——本仓 `.ui-probe` 的取证里就有。

所以每个状态**必带非颜色载体**：形状 + 文字。颜色是第三条线索，不是唯一那条。

## A4 此前在 `noSubject` 名单里——那不是「通过」

`AUDIT-02` 建这条规则时写着：「对象还不存在……没有对象不是『跑过了、干净』，
它进 `no_subject` 名单单独列出来，免得这条规则的绿被读成
『状态标记已经查过了』。」

本卡把对象建出来，并**撤掉那句豁免语**——留着它，哪天 `StatusMark`
被删掉或改名，规则会**悄悄退回豁免**：报告上写「无可量对象」，
而真相是「本来有，被弄没了」。两者在报告里长得一模一样。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
COMPONENT = WEB / "components" / "shell" / "StatusMark.tsx"
SCANNER = REPO / "tools" / "check_design_constraints.mjs"


def _scan(root: Path) -> dict[str, object]:
    done = subprocess.run(
        ["node", str(SCANNER), str(root), "--json"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False)
    assert done.stdout.strip(), done.stderr
    return json.loads(done.stdout)


def _code(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("//", "*"))
    )


# ───────────────────────── acceptance①：每个状态都有非颜色载体


def test_the_component_exists_and_exports_its_name() -> None:
    assert COMPONENT.exists()
    assert "export function StatusMark(" in COMPONENT.read_text(encoding="utf-8")


def test_every_known_state_carries_a_shape_not_just_a_tone() -> None:
    """**判等值**：每个状态都有 `glyph`，且形状**不是**每个都一样。

    「每个状态都有形状」还不够——六个状态全用同一个圆点、只换颜色，
    那和只靠颜色没有区别。所以还要判**形状本身是分得开的**。
    """
    code = _code(COMPONENT)
    entries = re.findall(r'(\w+):\s*\{\s*glyph:\s*"([^"]+)",\s*tone:\s*"(\w+)"',
                         code)

    assert len(entries) >= 5, f"只找到 {len(entries)} 个状态：扫描面塌了"
    for state, glyph, _tone in entries:
        assert glyph.strip(), f"{state} 的形状是空的"
    glyphs = {glyph for _s, glyph, _t in entries}
    tones = {tone for _s, _g, tone in entries}
    assert len(glyphs) >= 3, f"形状只有 {glyphs}——换汤不换药，还是只靠颜色"
    # 形状的种类**不少于**色调的种类：色调比形状多，说明有一组状态只靠颜色分。
    assert len(glyphs) >= len(tones), f"形状 {glyphs} 少于色调 {tones}"


def test_the_label_is_rendered_as_text_not_only_as_a_glyph() -> None:
    """文字是读屏软件**唯一**能念的那条线索。

    形状字符标了 `aria-hidden`（它对读屏软件是噪音），
    所以文字那一块 NEVER 也标 `aria-hidden`——两条都藏起来，
    用不了眼睛的人就完全不知道这一行是什么状态。
    """
    code = _code(COMPONENT)

    assert "status-mark__label" in code
    label_block = code.split("status-mark__label")[1][:120]
    assert "aria-hidden" not in label_block, "文字也被藏了"
    glyph_block = code.split("status-mark__glyph")[1][:120]
    assert "aria-hidden" in glyph_block, "形状字符没标 aria-hidden，会被念成乱码"


def test_an_unknown_state_is_still_shown_never_silently_dropped() -> None:
    """认不出的状态**照样显示**并给中性形状。

    不画的话，屏上看起来像「这一行没有状态」，
    而真相是「有状态，但我们没见过这个值」——两者要人做的事不同。
    """
    code = _code(COMPONENT)

    assert "UNKNOWN" in code
    assert "?? UNKNOWN" in code, "没见过的状态没有兜底形状"
    assert "label ?? state" in code, "认不出时没把原始状态串显示出来"


def test_the_front_end_never_decides_the_state_itself() -> None:
    """状态由后端给，前端只负责显示——**零判定**。

    出现比较、推导或合成，就是前端在自己判状态了。
    """
    code = _code(COMPONENT)

    assert "state ===" not in code and "state !==" not in code
    assert "if (" not in code, "组件里出现了分支——状态是查表来的，不是判出来的"


# ───────────────────────── acceptance②：A4 从 noSubject 移出


def test_a4_now_has_a_subject_and_reports_clean() -> None:
    report = _scan(WEB)

    assert report["applied"]["A4"] > 0, "A4 一个文件都没落到——它还是瞎的"
    assert [f for f in report["findings"] if f["rule"] == "A4"] == []


def test_a4_is_no_longer_excused() -> None:
    """**豁免语必须撤掉**。

    留着它，哪天 `StatusMark` 被删掉或改名，这条规则会**悄悄退回豁免**：
    报告上写「无可量对象」，而真相是「本来有，被弄没了」——
    两者在报告里长得一模一样。
    """
    excused = {row["id"] for row in _scan(WEB).get("noSubject", [])}
    scanner = SCANNER.read_text(encoding="utf-8")

    assert "A4" not in excused, "A4 还挂在 noSubject 名单里"
    assert "StatusMark 组件尚未建" not in scanner, "豁免语还留在源码里"


def test_no_other_rule_quietly_joined_the_excused_list() -> None:
    """**判等值**：豁免名单此刻是空的。

    这条与上一条不同：上一条只管 A4，这条盯着**整张名单**——
    有人给别的规则挂豁免语时，它会红并逼人解释。
    """
    report = _scan(WEB)

    assert report.get("noSubject", []) == [], report.get("noSubject")
    assert report.get("blind", []) == [], f"这些规则一个文件都没落到：{report.get('blind')}"


# ───────────────────────── acceptance③：阴性对照


def test_a_colour_only_status_mark_is_reported(tmp_path: Path) -> None:
    """**阴性对照**：造一个只靠颜色的状态标记 → A4 必须报红。

    没有这一条，「0 违规」可能只是因为规则认得出的那几个词恰好出现了。
    """
    fake = tmp_path / "components" / "StatusMark.tsx"
    fake.parent.mkdir(parents=True)
    fake.write_text(
        "export function StatusMark({ state }: { state: string }) {\n"
        '  const tone = state === "failed" ? "red" : "green";\n'
        '  return <span className={`mark mark--${tone}`} />;\n'
        "}\n",
        encoding="utf-8")

    findings = [f for f in _scan(tmp_path)["findings"] if f["rule"] == "A4"]

    assert findings, "只靠颜色的标记没被报出来——A4 是空的"
    assert "灰度" in findings[0]["detail"] or "颜色" in findings[0]["detail"]


def test_a_status_mark_with_a_shape_passes(tmp_path: Path) -> None:
    """正例：带形状的通过——见谁都报红的规则同样量不出东西。"""
    fake = tmp_path / "components" / "StatusMark.tsx"
    fake.parent.mkdir(parents=True)
    fake.write_text(
        "export function StatusMark({ state }: { state: string }) {\n"
        '  const shape = state === "failed" ? "✕" : "●";\n'
        "  return <span>{shape}{state}</span>;\n"
        "}\n",
        encoding="utf-8")

    assert [f for f in _scan(tmp_path)["findings"] if f["rule"] == "A4"] == []


def test_the_real_component_would_fail_if_its_shapes_were_removed(
        tmp_path: Path) -> None:
    """把**真组件**的形状抽掉再量一次——它必须红。

    上面两条用的是合成样例；这一条证明**真组件**是靠形状通过的，
    而不是碰巧命中了规则认得的某个词（比如注释里的 `border`）。
    """
    stripped = re.sub(r'glyph:\s*"[^"]+"', 'glyph: ""', _code(COMPONENT))
    stripped = re.sub(r"(shape|glyph|pattern|texture|hatch|dash|stripe|border)",
                      "colour", stripped, flags=re.IGNORECASE)
    fake = tmp_path / "components" / "StatusMark.tsx"
    fake.parent.mkdir(parents=True)
    fake.write_text(stripped, encoding="utf-8")

    assert [f for f in _scan(tmp_path)["findings"] if f["rule"] == "A4"], (
        "抽掉形状之后仍然绿——真组件不是靠形状通过的"
    )
