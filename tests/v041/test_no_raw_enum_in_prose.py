"""FIX-12：后端 NEVER 把枚举原值拼进给人看的句子。

## 改前屏上那句话

Gate 判定屏的缺口清单里写着：

> 竞品扫描覆盖未达标（not_saturated）（search）

`not_saturated` 是 `flint/competitor/coverage.py#CoverageReason` 的机器值，
拼这句话的是**后端**（`flint/gate/rule_d.py:44` 的 `missing_what` f-string）。

两处坏：

1. **前端换不掉**。那句话已经成型，`DS-03` 的标签表（`web/lib/i18n/enumLabel.ts`
   里 `coverage` 那一族，五个值都在）派不上用场；
2. **两边话术各自漂移**。后端改一个词，前端的标签表不会跟着改，
   而屏上同一个概念会出现两种说法。

## 修法：后端出**原因码 + 参数**，人话由前端说

`GapHint` 是冻结件（`missing_what / cause / suggested_sources / action / …`），
**加字段是 `S2-1` 禁止的**。所以结构化的那一半加在**序列化层**
（`flint/jobs/gate1.py` 拼的那个 dict，它不是冻结件），
而 `missing_what` 本身改成一句**不含机器值**的人话——
两条端点的消费者今天就正确，明天前端接上 `reason_code` 也不用改后端。

## 同一个毛病本仓还有第二处

`flint/sources/degradation.py#card_gap_annotations` 的 docstring 逐字写着
「E6 row 1 **user-facing copy**」，而它拼的是 `f"今日缺 {源} 数据（{n.reason}）"`——
`rate_limited` / `parse_drift` / `fetch_failed` 会原样上屏。

**本卡一并修**：acceptance③ 要「新增拼接会被拦住」，
而拦得住新的却留着旧的，那条判据从第一天起就是绿的谎。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FLINT = REPO / "flint"
RULE_D = FLINT / "gate" / "rule_d.py"
DEGRADATION = FLINT / "sources" / "degradation.py"
GATE1 = FLINT / "jobs" / "gate1.py"
LABELS = REPO / "web" / "lib" / "i18n" / "enumLabel.ts"
SHEET = REPO / "docs" / "blocked" / "BACKEND-PROSE-EMBEDS-RAW-ENUM.md"

# 下划线小写的机器值：`not_saturated` / `rate_limited` / `missing_data`…
_MACHINE_VALUE = re.compile(r"\b[a-z]{2,}(?:_[a-z]{2,})+\b")
_CJK = re.compile(r"[一-鿿]")


def _coverage_labels() -> set[str]:
    """`DS-03` 标签表里 `coverage` 那一族的全部值。"""
    text = LABELS.read_text(encoding="utf-8")
    block = text[text.index('prefix: "coverage"'):]
    block = block[: block.index("]")]
    return set(re.findall(r'"(\w+)"', block)) - {"coverage"}


# ───────────────────────── 一、那句话里不再有机器值


def test_the_coverage_gap_says_no_machine_value() -> None:
    """**本卡的核心**：`missing_what` 是一句人话，里面没有下划线机器值。"""
    from flint.competitor.coverage import CoverageResult
    from flint.gate.rule_c import RuleCResult
    from flint.gate.rule_d import derive_gaps

    derived = derive_gaps(
        RuleCResult(satisfied=False, failed_conditions=[], blocking_competitors=[]),
        CoverageResult(covered=False, reason="not_saturated", pending_queries=[]),
        competitors=[], missing_scopes=[])

    prose = [d.hint.missing_what for d in derived]
    assert prose, "一条缺口都没派生出来——这条判据在空转"
    for line in prose:
        leaked = _MACHINE_VALUE.findall(line)
        assert leaked == [], f"人话里混进了机器值 {leaked}：{line!r}"


def test_the_machine_value_moved_to_a_field_of_its_own() -> None:
    """原因码没有被**丢掉**，它换了个位置。

    只把括号里那截删掉的话，屏上确实干净了，而**「为什么没达标」这个信息没了**——
    那比印一个机器值更坏：用户从此不知道该去补什么。
    """
    from flint.competitor.coverage import CoverageResult
    from flint.gate.rule_c import RuleCResult
    from flint.gate.rule_d import derive_gaps

    derived = derive_gaps(
        RuleCResult(satisfied=False, failed_conditions=[], blocking_competitors=[]),
        CoverageResult(covered=False, reason="not_saturated", pending_queries=[]),
        competitors=[], missing_scopes=[])
    coverage_gap = next(d for d in derived if d.reason_code is not None)

    assert coverage_gap.reason_code == "not_saturated"


def test_the_reason_code_is_one_the_front_end_can_render() -> None:
    """原因码 MUST 是 `DS-03` 标签表里认得的值。

    出一个表里没有的码，前端只能把它原样印出来——
    **那就绕了一圈回到了改前的样子**。
    """
    from flint.competitor.coverage import CoverageResult
    from flint.gate.rule_c import RuleCResult
    from flint.gate.rule_d import derive_gaps

    known = _coverage_labels()
    assert "not_saturated" in known, f"标签表里 coverage 一族没解析出来：{known}"

    for reason in ("not_saturated", "empty_unconfirmed", "queries_pending"):
        derived = derive_gaps(
            RuleCResult(satisfied=False, failed_conditions=[], blocking_competitors=[]),
            CoverageResult(covered=False, reason=reason, pending_queries=[]),
            competitors=[], missing_scopes=[])
        codes = [d.reason_code for d in derived if d.reason_code is not None]
        assert codes == [reason], f"{reason} 没被带出来：{codes}"
        assert set(codes) <= known, f"{codes} 不在标签表里，前端渲染不了"


def test_the_serialised_gap_carries_both_halves() -> None:
    """端点回的那个 dict 里，人话与原因码**各占一格**。

    `GapHint` 是冻结件（加字段是 `S2-1` 禁止的），所以结构化的那一半
    加在**序列化层**——那个 dict 不是冻结件。
    """
    code = GATE1.read_text(encoding="utf-8")
    block = code[code.index('"gaps": ['):]
    block = block[: block.index("        ],")]

    for key in ('"missing_what"', '"cause"', '"action"', '"reason_code"'):
        assert key in block, f"序列化里没有 {key}：{block}"


# ───────────────────────── 二、同一个毛病的第二处


def test_the_degradation_copy_says_no_machine_value() -> None:
    """`card_gap_annotations` 的 docstring 逐字写着「user-facing copy」。

    而它拼的是 `f"今日缺 {源} 数据（{n.reason}）"`——`rate_limited` 会原样上屏。
    **拦得住新的却留着旧的，那条判据从第一天起就是绿的谎。**
    """
    from datetime import date

    from flint.sources.degradation import DegradationNote, card_gap_annotations

    notes = [
        DegradationNote(day=date(2026, 8, 8), source_id="weibo",
                        reason="rate_limited", detail="429"),
        DegradationNote(day=date(2026, 8, 8), source_id="arxiv",
                        reason="parse_drift", detail="选择器失配"),
    ]

    for line in card_gap_annotations(notes):
        leaked = _MACHINE_VALUE.findall(line)
        assert leaked == [], f"人话里混进了机器值 {leaked}：{line!r}"


def test_the_degradation_reason_is_still_reachable() -> None:
    """同样：原因**没被丢掉**，只是不在那句话里了。

    `DegradationNote.reason` 本来就是结构化字段，调用方按它取标签即可。
    """
    from datetime import date

    from flint.sources.degradation import DegradationNote

    note = DegradationNote(day=date(2026, 8, 8), source_id="weibo",
                           reason="rate_limited", detail="429")

    assert note.reason == "rate_limited"


# ───────────────────────── 三、新增拼接会被拦住（acceptance③）


def _prose_fstrings(path: Path) -> list[tuple[int, str]]:
    """这份源码里**把某个枚举字段插进中文句子**的 f-string。

    判据的口径**刻意窄**：

    - 只看 f-string（`JoinedStr`）——`"x" + y` 那种拼法本仓没有，加进来只会误伤；
    - 字符串里得**有中文**；
    - 插值的属性名得在那张已知的枚举字段表里；
    - **`raise` 里的那些不算**。

    最后一条是开工后加的。本仓的异常消息也写中文
    （`flint/design/graph_stale.py:60`「未知图谱变更类型 {kind!r}：NEVER 当成…」），
    而**异常是给我们自己看的**——把出问题的那个值印出来正是它该做的事，
    否则收到报错的人不知道是哪一个值出的问题。

    所以「中文」不足以分开「给人看的」与「给我们自己看的」，
    **「是不是 `raise` 的实参」才是**。
    窄不是放水：它换来的是**零误报**，而一把会误报的尺子迟早被人加白名单绕过。
    """
    enum_fields = {"reason", "cause", "status", "state", "kind",
                   "strength", "alignment", "verdict"}
    found: list[tuple[int, str]] = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    in_raise = {
        id(inner) for stmt in ast.walk(tree) if isinstance(stmt, ast.Raise)
        for inner in ast.walk(stmt)
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr) or id(node) in in_raise:
            continue
        literal = "".join(
            part.value for part in node.values if isinstance(part, ast.Constant)
            and isinstance(part.value, str))
        if not _CJK.search(literal):
            continue
        for part in node.values:
            if not isinstance(part, ast.FormattedValue):
                continue
            expr = part.value
            name = expr.attr if isinstance(expr, ast.Attribute) else None
            if name in enum_fields:
                found.append((node.lineno, ast.unparse(node)[:80]))
    return found


def test_no_module_interpolates_an_enum_into_chinese_prose() -> None:
    """扫全 `flint/`：中文句子里 NEVER 插一个枚举字段。

    **这一条是本卡真正留下来的东西**：那两处修好之后，
    下一次有人这么写会当场红——而不是等到有人在屏上看见。
    """
    offenders = [
        f"{path.relative_to(REPO)}:{line} {snippet}"
        for path in sorted(FLINT.rglob("*.py"))
        for line, snippet in _prose_fstrings(path)
    ]

    assert offenders == [], "中文句子里插了枚举原值：\n" + "\n".join(offenders)


def test_the_ruler_would_really_catch_a_fresh_one() -> None:
    """**判据自己的阴性对照**：把那种写法喂进去，必须抓得到。

    没有这一条，`_prose_fstrings` 哪天解析不出 f-string（换了 AST 结点名、
    改了字段表）就会让全仓都「干净」，而它看起来仍然是绿的。
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "bad.py"
        bad.write_text(
            'def f(x):\n    return f"今日缺 {x.source_id} 数据（{x.reason}）"\n',
            encoding="utf-8")
        assert _prose_fstrings(bad), "注入的拼接没被抓住——尺子坏了"

        good = Path(tmp) / "good.py"
        good.write_text(
            'def f(x):\n    return f"今日缺 {x.source_id} 数据"\n', encoding="utf-8")
        assert _prose_fstrings(good) == [], "干净的写法被误报了"

        # `raise` 里的那些**不算**：异常是给我们自己看的，
        # 把出问题的那个值印出来正是它该做的事。
        raising = Path(tmp) / "raising.py"
        raising.write_text(
            'def f(x):\n    raise ValueError(f"未知类型 {x.kind}：来这里加一支")\n',
            encoding="utf-8")
        assert _prose_fstrings(raising) == [], "异常消息被误报了"


# ───────────────────────── 四、判定语义一字不动（acceptance④）


def test_the_verdict_rules_were_not_touched() -> None:
    """只改呈现载体，**NEVER 改判定规则**。

    判的是「派生出几条缺口、各是什么 cause/action」——那才是判定语义。
    改前改后这些必须逐字相同。
    """
    from flint.competitor.coverage import CoverageResult
    from flint.gate.rule_c import RuleCResult
    from flint.gate.rule_d import derive_gaps

    derived = derive_gaps(
        RuleCResult(
            satisfied=False,
            failed_conditions=["refute_not_executed", "no_aligned_support"],
            blocking_competitors=[]),
        CoverageResult(covered=False, reason="not_saturated", pending_queries=[]),
        competitors=[], missing_scopes=[])

    assert [(d.hint.cause, d.hint.action) for d in derived] == [
        ("missing_data", "search"),      # 证伪未执行
        ("missing_data", "search"),      # 覆盖未达标
        ("missing_data", "search"),      # 缺对齐通过的支持证据
    ]


# ───────────────────────── 五、单据关掉


def test_the_sheet_is_closed() -> None:
    text = SHEET.read_text(encoding="utf-8")
    state = next(ln for ln in text.splitlines()[:8] if ln.startswith("**状态**"))

    assert state.startswith("**状态** closed"), f"单据还开着：{state!r}"
    assert "FIX-12" in text
