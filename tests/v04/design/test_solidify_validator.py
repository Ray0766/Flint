"""DESIGN-29 验收（隔离带·G4）：固化校验器（四判据 + 行号 + 反例实测输出）。

acceptance：
① **插槽完整/无占位残留/无水印残留/Block 类型对齐 四判据**；
② **违规拒绝并输出行号；反例 fixture 断言实际输出文本**。

## 为什么反例要断「实际输出文本」而不只是「有没有报错」

「模板不合格」这句话对改的人没有任何帮助。这道检查真正的产物是**那张清单**：
第几行、哪条判据、原文是什么、该怎么改。只断 `raises` 的话，
清单退化成一句话也照样绿——而那正是这张卡要防的形态。
"""
from __future__ import annotations

from flint.design.solidify_validator import format_report, validate_template

BLOCKS = frozenset({"b-1", "b-2"})
KEYS = frozenset({"title", "subtitle"})

CLEAN_LINES = [
    "<section>",
    "  <h1>{{t:title}}</h1>",
    "  <p>{{block:b-1}}</p>",
    "</section>",
]
CLEAN = "\n".join(CLEAN_LINES)


def _validate(html: str, slots: tuple[str, ...]):
    return validate_template(
        html, declared_slots=slots, known_block_ids=BLOCKS, known_text_keys=KEYS
    )


def test_clean_template_passes() -> None:
    """阴性对照：干净模板必须过（否则「拒绝」可能只是它谁都拒）。"""
    report = _validate(CLEAN, ("block:b-1", "t:title"))

    assert report.ok is True
    assert report.issues == []
    assert format_report(report) == "模板校验通过：四条判据全过"


# ───────────────────────── 判据 1：插槽完整（两个方向）


def test_declared_but_unused_slot_is_reported() -> None:
    report = _validate(CLEAN, ("block:b-1", "t:title", "block:b-2"))

    kinds = [i.criterion for i in report.issues]
    assert "slot_declared_not_used" in kinds
    assert any("block:b-2" == i.detail for i in report.issues)


def test_used_but_undeclared_slot_is_reported_with_its_line() -> None:
    report = _validate(CLEAN, ("t:title",))

    issue = next(i for i in report.issues if i.criterion == "slot_used_not_declared")
    assert issue.detail == "block:b-1"
    assert issue.line == 3            # `<p>{{block:b-1}}</p>` 在第 3 行


# ───────────────────────── 判据 2：占位残留


def test_example_number_is_reported_with_line_and_text() -> None:
    html = CLEAN.replace("</section>", "  <p>增速 42.7%</p>\n</section>")

    report = _validate(html, ("block:b-1", "t:title"))

    issue = next(i for i in report.issues if i.criterion == "example_number")
    assert issue.line == 4
    assert "42.7" in issue.detail


def test_slot_digits_are_not_mistaken_for_example_numbers() -> None:
    """`{{block:b-1}}` 里的 1 不是示例数字——检查器 NEVER 拦下自己要的东西。"""
    report = _validate(CLEAN, ("block:b-1", "t:title"))

    assert [i for i in report.issues if i.criterion == "example_number"] == []


def test_example_source_is_reported() -> None:
    html = CLEAN.replace("</section>", "  <p>来源 SRC-1234</p>\n</section>")

    report = _validate(html, ("block:b-1", "t:title"))

    assert any(i.criterion == "example_source" for i in report.issues)


# ───────────────────────── 判据 3：水印残留


def test_watermark_left_is_reported_with_line() -> None:
    html = CLEAN.replace("<section>", '<section data-mock-watermark="true">')

    report = _validate(html, ("block:b-1", "t:title"))

    issue = next(i for i in report.issues if i.criterion == "watermark_left")
    assert issue.line == 1


# ───────────────────────── 判据 4：插槽类型对齐


def test_unknown_block_id_is_reported() -> None:
    html = CLEAN.replace("{{block:b-1}}", "{{block:b-404}}")

    report = _validate(html, ("block:b-404", "t:title"))

    issue = next(i for i in report.issues if i.criterion == "unknown_block")
    assert issue.detail == "block:b-404"
    assert issue.line == 3


def test_unknown_text_key_is_reported() -> None:
    html = CLEAN.replace("{{t:title}}", "{{t:nope}}")

    report = _validate(html, ("block:b-1", "t:nope"))

    assert any(i.criterion == "unknown_text_key" for i in report.issues)


def test_unknown_slot_kind_is_reported() -> None:
    html = CLEAN.replace("{{t:title}}", "{{chart:c-1}}")

    report = _validate(html, ("block:b-1", "chart:c-1"))

    assert any(i.criterion == "unknown_slot_kind" for i in report.issues)


# ───────────────────────── 四条并列 + 输出文本


def test_all_four_criteria_reported_together() -> None:
    """四条都违反时**四条都列出来**，NEVER 命中第一条就返回。"""
    dirty_lines = [
        '<section data-mock-watermark="true">',      # 判据 3
        "  <h1>{{t:nope}}</h1>",                      # 判据 4
        "  <p>增速 42.7%</p>",                        # 判据 2
        "</section>",
    ]
    html = "\n".join(dirty_lines)

    report = _validate(html, ("block:b-1",))              # 判据 1（声明了没用）

    kinds = {i.criterion for i in report.issues}
    assert {"watermark_left", "unknown_text_key", "example_number"} <= kinds
    assert "slot_declared_not_used" in kinds


def test_report_text_is_actionable() -> None:
    """acceptance②：断**实际输出文本**——行号、判据、原文、怎么办四样都在。"""
    html = CLEAN.replace("</section>", "  <p>增速 42.7%</p>\n</section>")

    text = format_report(_validate(html, ("block:b-1", "t:title")))

    assert "L4" in text
    assert "example_number" in text
    assert "42.7" in text
    assert "→" in text                       # 每条都带「怎么办」
    assert "XX.X%" in text                   # 说得出换成什么


def test_report_lists_one_line_per_issue() -> None:
    dirty_lines = [
        '<section data-mock-watermark="true">',
        "  <p>增速 42.7%</p>",
        "</section>",
    ]
    html = "\n".join(dirty_lines)

    text = format_report(_validate(html, ()))

    assert len(text.split("\n")) == len(_validate(html, ()).issues)


def test_crlf_input_reports_the_same_lines() -> None:
    """CRLF 文件的行号与 LF 一致：Windows 上编辑过的模板不该报错位。"""
    html = CLEAN.replace("</section>", "  <p>增速 42.7%</p>\n</section>")

    lf = _validate(html, ("block:b-1", "t:title"))
    crlf = _validate(html.replace("\n", "\r\n"), ("block:b-1", "t:title"))

    assert [ (i.criterion, i.line) for i in lf.issues ] == [
        (i.criterion, i.line) for i in crlf.issues
    ]
