"""BL-03：`CHECK_ANSWER_LINE = 0.90` 的**范围守卫**（核实 + 补守卫，NEVER 改值）。

## 这个常量为什么留着

0.90 治的是**旧模板 check_questions 结构考核面**（`check_answer_report`：规则派生、
合成 golddocs 上自证）。**生产**答作率的绝对 0.90 线已依 owner 裁决 @2026-07-30 作废，
生产口径改走 `eval/semantic_answers.py#relative_answer_gate`（相对付费参照）。

**它不是残留，是范围被收窄的既有门。** 删掉它，`tests/m3/test_m3_066.py` 的
里程碑自证就失去依据——那条断言的正是 `check_answer_report(...)["rate"] >= 0.9`。
所以本卡**一个字都不改**，只把「范围」从注释变成机器可验的东西。

## 注释挡不住复制

`eval/doc_metrics.py` 里已经写了十行范围界定注释。注释只能劝住读它的人——
**下一个人在生产路径里写 `from eval.doc_metrics import CHECK_ANSWER_LINE` 时，
没有任何东西会红**。本文件补的就是那一下红。

## 判断只看代码面

同一个名字出现在**文档字符串与注释**里是正当的（那是在说明为什么不能沿用它），
出现在**代码**里才是越界。所以一律先剥注释与 docstring 再判——
这条纪律本仓前后踩过六次同型的坑（`web/test-utils/source.ts` 的由来）。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

import eval.doc_metrics as dm
import eval.semantic_answers as sa

REPO_ROOT = Path(__file__).resolve().parents[2]
NAME = "CHECK_ANSWER_LINE"
SKIP_DIRS = {".venv", "node_modules", ".next", "__pycache__", ".git", ".ui-probe", "web"}

# 允许在**代码里**引用这个常量的地方，逐个写明角色。
# 名单是闭集：新增一处就要在这里说清它属于哪一面，而不是默默多一个引用点。
ALLOWED_CODE_REFS = {
    "eval/doc_metrics.py": "定义处 + 旧模板结构考核面的门表达式",
    "tests/m4/test_doc_metrics_scope.py": "既有范围守卫（owner 卫生清理 @2026-07-30）",
    "tests/v041/test_answer_line_scope.py": "本守卫",
    "tests/v041/test_caliber_realign.py":
        "JUDGE-05 的「本卡没动阈值」判据：钉住四个现存阈值的当前值。"
        "它**只读不写**，且钉的正是这条守卫要保住的那个 0.90——"
        "两条守的是同一件事的两半（这条守范围，那条守值）",
}
# 生产口径那一侧：**代码面**一次都不许出现。
PRODUCTION_PATHS = ("eval/semantic_answers.py", "harness/prod_caliber.py")


def code_face(source: str) -> str:
    """剥掉注释与 docstring，只留代码。

    注释与 docstring 里提这个名字是**正当的**——那是在说明为什么不能沿用它。
    把它们也算成引用，等于逼着后人删掉解释才能让尺子闭嘴，而那正是本仓
    一路在守的反面（判据不该与留痕互相取消）。
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        body = node.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            body[0].value.value = ""          # docstring 清空，位置结构不动
    return ast.unparse(tree)


def references_in_code(path: Path) -> bool:
    """这个文件的**代码**里是否引用了那个常量。"""
    try:
        return NAME in code_face(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return False


def _python_files() -> list[Path]:
    return [
        p for p in REPO_ROOT.rglob("*.py")
        if not any(part in SKIP_DIRS for part in p.parts)
    ]


# ───────────────────────── acceptance①：值一字不改


def test_the_value_is_untouched() -> None:
    """0.90 逐字不变——本卡是**范围**守卫，NEVER 顺手改门值。"""
    assert dm.CHECK_ANSWER_LINE == 0.90


def test_the_literal_is_still_written_out_in_the_source() -> None:
    """源码里仍是写死的 `0.90`，不是从别处算出来的。

    算出来的门会跟着别处的数一起漂，而这道门的意义正是「钉在那个历史值上」。
    """
    source = (REPO_ROOT / "eval" / "doc_metrics.py").read_text(encoding="utf-8")

    assert f"{NAME} = 0.90" in source


def test_the_gate_expression_is_untouched() -> None:
    """门表达式仍是 `>= CHECK_ANSWER_LINE`——范围界定不动执法逻辑。"""
    import inspect

    assert ">= CHECK_ANSWER_LINE" in inspect.getsource(dm.main)
    assert callable(dm.check_answer_report)


# ───────────────────────── acceptance②：把注释里的范围变成机器可验


def test_every_code_reference_is_on_the_structural_side() -> None:
    """全仓扫一遍：**代码里**引用这个常量的文件必须在名单内，逐个点名越界的。

    这一条替下面那条注释干活：
    「NEVER 表述为生产口径达标线、NEVER 顺手改 0.90 值」——
    注释只能劝住读它的人，红才拦得住复制。
    """
    strays = [
        p.relative_to(REPO_ROOT).as_posix()
        for p in _python_files()
        if references_in_code(p)
        and p.relative_to(REPO_ROOT).as_posix() not in ALLOWED_CODE_REFS
    ]

    assert strays == [], f"这些地方在代码里引用了结构考核面的 0.90：{strays}"


def test_the_allowlist_has_no_dead_entries() -> None:
    """反向：名单里每一条今天仍**真的**引用它。

    只增不减的名单会慢慢变成一张许可证，而许可证不是判据。
    """
    dead = [
        rel for rel in ALLOWED_CODE_REFS
        if not references_in_code(REPO_ROOT / rel)
    ]

    assert dead == [], f"名单里这些条目已经不引用它了，该删：{dead}"


@pytest.mark.parametrize("rel", PRODUCTION_PATHS)
def test_the_production_paths_never_touch_it_in_code(rel: str) -> None:
    """生产口径那一侧的**代码面**一次都不出现它。

    生产答作率的绝对 0.90 线已作废（owner 裁决 @2026-07-30）；
    在生产路径里引它，等于把一条被撤销的线偷偷装回去。
    """
    assert not references_in_code(REPO_ROOT / rel)


@pytest.mark.parametrize("rel", PRODUCTION_PATHS)
def test_the_production_paths_still_explain_why_not(rel: str) -> None:
    """而它们的**注释里**仍要写着为什么不能沿用——留痕不能被判据挤掉。

    删掉那句话，下一个人只会看到「生产这边没有门」，然后顺手补一个 0.90。
    """
    source = (REPO_ROOT / rel).read_text(encoding="utf-8")

    assert NAME in source, "解释为什么不沿用的那句话没了"


def test_the_two_gates_are_different_numbers() -> None:
    """两条门算出来的数不一样——不是同一件事换了个名字。"""
    required = sa.REFERENCE_RATE_UNIFIED_JUDGE * sa.GATE_RATIO

    assert required != dm.CHECK_ANSWER_LINE
    assert (sa.REFERENCE_RATE_UNIFIED_JUDGE, sa.GATE_RATIO) == (0.434, 0.85)


# ───────────────────────── 尺子自证（阴性对照）


def test_the_scanner_catches_a_real_reference(tmp_path: Path) -> None:
    """阴性对照：把引用写进代码就必须被扫出来。

    没有这一条，上面那条「零越界」与「尺子瞎了」长得一模一样。
    """
    offender = tmp_path / "fake_production.py"
    offender.write_text(
        "from eval.doc_metrics import CHECK_ANSWER_LINE\n"
        "def gate(rate: float) -> bool:\n"
        "    return rate >= CHECK_ANSWER_LINE\n",
        encoding="utf-8",
    )

    assert references_in_code(offender)


def test_the_scanner_ignores_comments_and_docstrings(tmp_path: Path) -> None:
    """只写在注释与 docstring 里的**不算**引用。"""
    innocent = tmp_path / "explains_only.py"
    innocent.write_text(
        '"""这里说明 CHECK_ANSWER_LINE 为什么不能沿用。"""\n'
        "# CHECK_ANSWER_LINE = 0.90 是旧考核面的门\n"
        "def gate(rate: float) -> bool:\n"
        '    """也提一句 CHECK_ANSWER_LINE。"""\n'
        "    return rate >= 0.5\n",
        encoding="utf-8",
    )

    assert not references_in_code(innocent)


def test_a_string_literal_still_counts_as_a_reference(tmp_path: Path) -> None:
    """写在**字符串**里的算引用（`getattr(dm, "CHECK_ANSWER_LINE")` 是真用法）。

    docstring 是唯一的例外，因为它按位置就能认出来；普通字符串认不出意图，
    宁可报出来让人看一眼。
    """
    sneaky = tmp_path / "sneaky.py"
    sneaky.write_text(
        "import eval.doc_metrics as dm\n"
        'LINE = getattr(dm, "CHECK_ANSWER_LINE")\n',
        encoding="utf-8",
    )

    assert references_in_code(sneaky)


# ───────────────────────── acceptance③：删不得


def test_the_milestone_self_check_still_depends_on_it() -> None:
    """M3-066 的里程碑自证依赖 `check_answer_report`——删了常量它就失去依据。

    这一条是「为什么不删」的机器版：删掉那个度量器，这里当场红。
    """
    m3 = (REPO_ROOT / "tests" / "m3" / "test_m3_066.py").read_text(encoding="utf-8")

    assert "check_answer_report" in m3
    assert hasattr(dm, "check_answer_report")


def test_the_scope_annotation_is_still_in_the_source() -> None:
    """范围界定注释仍在（它是这道门唯一的说明书）。"""
    source = (REPO_ROOT / "eval" / "doc_metrics.py").read_text(encoding="utf-8")

    for token in ("旧模板", "非生产口径", "分治", "作废", "2026-07-30",
                  "relative_answer_gate"):
        assert token in source, f"范围界定注释里少了：{token}"
