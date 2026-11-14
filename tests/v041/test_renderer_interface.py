"""GAUGE-06 / 终检 F-04 + F-03/F-06：接口断言真化 + 两处措辞与真件对齐。

## F-04：`hasattr` 冒充接口断言

DESIGN-31 卡面 acceptance②「两路径共用 Renderer 接口不同实现（断言）」，而实现里
`ExploreRenderer.render(html)` 与 `ProductionRenderer.render(template_id, slot_values)`
**签名互不兼容、无共同基类**，也不实现契约里的 `Renderer`（`contracts/protocols.py` 的那个
签名是 `render(deliverable_id, fmt)`，与两者都不是一回事）。守它的断言是
`hasattr(prod, "render") and hasattr(explore, "render")`——**「都有一个叫 render 的方法」
不等于「共用接口」**。

### 二选一：本卡选 ②「入参形状互斥」，NEVER 抽共同 Protocol

卡上给了两条路：① 抽一个 `DesignRenderer` Protocol 两边实现；② 把口径改成
「两路径入参形状互斥」并按形状断言。**选 ②，理由三条**：

1. **① 做不出诚实的 Protocol**。两个 `render` 的参数表没有交集（`html` vs
   `template_id + slot_values`）。要让它们实现同一个 Protocol，只能把签名放宽成
   `render(*args: Any)` 之类——那是 `hasattr` 换了身衣服，正是本卡要消灭的东西；
   要么改其中一个的签名，而那会动一个已封版模块的公开面。
2. **共同接口会削弱这道门**。这条 acceptance 的产品意义是「**生产路径不收 html**」
   （终检原话，且由另一条测试真守着）。抽一个共同 Protocol 等于给两条路径造一个共同
   调用点——调用方从此可以拿着一个 `DesignRenderer` 变量在两条路径间切换，
   而「生产渲染器没有接受 html 的口子」这件事就不再是类型层面的事实。
3. **真件本来就是这么写的**。`ProductionRenderer` 的 docstring 原话就是
   「只接受 `template_id` + 插槽值。**没有接受 html 的口子**」——措辞对齐的是它，
   不是反过来让代码去迁就一句写错的 acceptance。

所以本文件断的是**形状互斥**，并配一条反例探针（把生产渲染器换成一个收 html 的版本，
这些断言必须红）——用 GAUGE-03 建的 `tests/_meta/probe_bites.py` 咬。

## F-03/F-06：两处「新增 JobKind 要改冻结件」与真件不符

`contracts_v04/models_v04.py:801-804` 在**同一个增量里**就 additive 加过
`translate` / `design_generate` / `template_solidify` 三个 JobKind 值，走的是
`contracts_v04/` additive 通道 + `check_frozen_additive.py`——S2-1 一次都没被越过。
所以「造一个新的 JobKind 要改冻结件（S2-1 NEVER）」这句站不住。

站得住的是另外两条：**深度是档位不是另一种作业**、**自建提交路径会带来第二份幂等键与
重试语义**。两处措辞（`docs/异见清单-v04.md#A4` 与 `flint/analysis/deep_job.py` 的 docstring）
本卡都改了，下面的断言守着它们不回潮。

`deep_job.py` **只动 docstring**：`CODE_AST` 是改动前采集的「剥掉全部 docstring 之后的
AST 指纹」，本文件逐次比对——函数、签名、常量、控制流一个字节都没变。
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import re
from pathlib import Path
from typing import Any

from flint.design import prod_render
from tests._meta.probe_bites import Replacement, assert_bites

REPO = Path(__file__).resolve().parents[2]
DEEP_JOB = REPO / "flint" / "analysis" / "deep_job.py"
DISSENT = REPO / "docs" / "异见清单-v04.md"

# 改 docstring **之前**采集（2026-08-04，命令见 docs/trace/GAUGE-06.md）。
CODE_AST_SHA256 = "4836466c3854743d5b091fb25c36837cb1c3a9d0e0b3fff7c5f389219ee838ff"

# 与真件不符、本卡改掉的说法；两处都 NEVER 再出现。
STALE_REASON = "新增 JobKind"
STALE_REASON_CODE = "造一个新的 JobKind 要改冻结件"


def _strip_docstrings(tree: ast.Module) -> ast.Module:
    """把每个模块/类/函数的首条字符串表达式摘掉，只留代码层。"""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        body = node.body
        first = body[0] if body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return tree


def _code_fingerprint(path: Path) -> str:
    tree = _strip_docstrings(ast.parse(path.read_text(encoding="utf-8")))
    return hashlib.sha256(ast.dump(tree, annotate_fields=True).encode()).hexdigest()


def _production_render_params() -> set[str]:
    """**真造一个**生产渲染器，问它的 `render` 收什么。

    问类不问实例是不够的：`probe_bites` 的第四道检查要求「替换件真的被用到了」，
    而只读类属性的写法在换掉整个类之后**一次调用都不会发生**——那样得到的红与被换掉的
    东西无关（这条是本卡实测撞出来的，见 trace §4）。造一个实例既满足那道检查，
    断言也更贴近真相：客户拿到的是这个对象，不是那个类。

    构造参数给的是空壳：`ProductionRenderer` 是 dataclass，`__init__` 不做校验，
    模板查找发生在 `render` 里——本条只问签名，NEVER 触发查找。
    """
    prod = prod_render.ProductionRenderer(registry=object(), owner=object())
    return set(inspect.signature(prod.render).parameters)


def _explore_render_params() -> set[str]:
    return set(inspect.signature(prod_render.ExploreRenderer().render).parameters)


# ───────────────────────── F-04：形状互斥，不是「都有个 render」


def test_the_two_render_signatures_have_no_parameter_in_common() -> None:
    """acceptance①（选 ②）：两条路径的入参**没有交集**。

    这是 `hasattr` 那条断言该被换成的东西：它量的是签名，而签名正是
    「生产路径没有接受 html 的口子」这件事在类型层面的落点。
    """
    explore = _explore_render_params()
    production = _production_render_params()

    assert explore == {"html"}
    assert production == {"template_id", "slot_values"}
    assert explore & production == set(), f"两条路径出现了共同入参：{explore & production}"


def test_production_render_has_no_hole_that_takes_html() -> None:
    """正题：生产渲染器**没有**接受 html 的口子——不是「检查了一下 html」。"""
    production = _production_render_params()

    assert "html" not in production
    assert not any("html" in name for name in production), f"疑似 html 口子：{production}"


def test_neither_renderer_is_pinned_to_a_shared_base() -> None:
    """两者无共同基类、互不是对方的实例——**共用接口这句话本来就不成立**。

    这一条与「抽一个 Protocol 出来」是对立的：本卡选择让口径去对齐真件，
    NEVER 反过来改真件去对齐一句写错的 acceptance（理由见模块 docstring）。
    """
    assert prod_render.ProductionRenderer.__mro__[1:] == (object,)
    assert prod_render.ExploreRenderer.__mro__[1:] == (object,)
    assert not issubclass(prod_render.ProductionRenderer, prod_render.ExploreRenderer)
    assert not issubclass(prod_render.ExploreRenderer, prod_render.ProductionRenderer)


def _renderer_that_takes_html() -> type:
    """反例探针：一个**收 html 的生产渲染器**。这正是这道门要挡住的东西。"""

    class LeakyProductionRenderer:
        def __init__(self, **_: Any) -> None:
            """与真件同样的构造面（dataclass 关键字参数），换掉之后调用方一无所觉。"""

        def render(self, template_id: str, slot_values: dict[str, str], html: str = "") -> str:
            return html or template_id

    return LeakyProductionRenderer


def test_these_assertions_really_bite_when_production_grows_an_html_hole() -> None:
    """反例探针：把生产渲染器换成收 html 的版本，上面两条形状断言必须红。

    没有这一条，「形状互斥」和它替换掉的 `hasattr` 是同一种东西——**都是没人验过
    强度的断言**。咬合由 `tests/_meta/probe_bites.py`（GAUGE-03）判：它另外还会检查
    「替换之前是绿的」与「替换件真的被用到了」，缺一道结论就是假的。
    """
    assert_bites(
        Replacement(
            module="flint.design.prod_render",
            attr="ProductionRenderer",
            build=_renderer_that_takes_html,
            why="给生产渲染器开一个收 html 的口子",
        ),
        [
            test_the_two_render_signatures_have_no_parameter_in_common,
            test_production_render_has_no_hole_that_takes_html,
        ],
    )


def test_the_old_hasattr_claim_is_gone_from_the_v04_gate() -> None:
    """`hasattr` NEVER 再冒充接口断言：旧文件里那条已换成真断言。

    只在新文件里写一条真断言是不够的——旧那条还在的话，下一个读它的人仍然会以为
    「共用接口」被验过了。

    比的是**代码层**不是原文：那份文件的新 docstring 里逐字引用了旧断言（说明它错在哪），
    按原文比会把「解释它」当成「还在用它」——那种断言只会逼着后人把病史抹掉。
    """
    old = ast.parse(
        (REPO / "tests" / "v04" / "design" / "test_prod_render_gate.py").read_text(encoding="utf-8")
    )
    calls = [
        node.func.id for node in ast.walk(old)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    names = [node.name for node in ast.walk(old) if isinstance(node, ast.FunctionDef)]

    assert "hasattr" not in calls, "这份文件里还有 hasattr 在当断言用"
    assert "test_both_renderers_share_one_interface" not in names
    assert "test_the_two_renderers_are_two_implementations_not_one_interface" in names


# ───────────────────────── F-03/F-06：措辞与真件对齐


def test_the_three_v04_job_kinds_really_went_through_the_additive_channel() -> None:
    """先证明「新增 JobKind 要改冻结件」为假：三个新值就在 additive 副本里。

    这是下面两条措辞断言的**前提**。前提不验，改措辞就成了另一种「因为有人这么说」。
    """
    from typing import get_args

    from contracts.models import JobKind as FrozenJobKind
    from contracts_v04.models_v04 import JobKind as V04JobKind

    frozen = set(get_args(FrozenJobKind))
    v04 = set(get_args(V04JobKind))

    assert frozen < v04, "v04 副本不是冻结件的真超集"
    assert v04 - frozen == {"translate", "design_generate", "template_solidify"}


def test_the_module_docstring_no_longer_blames_the_frozen_contract() -> None:
    """`deep_job.py` 的 docstring 换成了两条真理由。"""
    text = DEEP_JOB.read_text(encoding="utf-8")
    doc = ast.get_docstring(ast.parse(text)) or ""

    assert STALE_REASON_CODE not in doc
    assert "档位" in doc and "第二份幂等键" in doc
    assert "additive" in doc, "要说明「为什么那句话不对」，而不只是把它删掉"


def test_the_dissent_row_carries_the_two_real_reasons() -> None:
    """`docs/异见清单-v04.md#A4` 同步改到位，并留下改动痕迹。

    先摘掉 `〔…〕` 里的改动说明再判：那段里逐字引了被改掉的旧说法（「原写 X，与真件不符」），
    连它一起判就等于要求改动说明**不许提到自己改了什么**——留痕与判据不该互相取消。
    """
    row = next(
        line for line in DISSENT.read_text(encoding="utf-8").splitlines()
        if line.startswith("| A4 ")
    )
    body = re.sub(r"〔[^〕]*〕", "", row)

    assert "GAUGE-06" in row, "改了别人写的判词，NEVER 不留痕"
    assert f"{STALE_REASON} 要动冻结件" not in body
    assert "档位" in body and "第二份幂等键" in body


def test_deep_job_changed_only_its_docstring() -> None:
    """acceptance③：`deep_job.py` 的**代码层**一个字节都没变。

    比的是「剥掉全部 docstring 之后的 AST」，指纹在改动前采集。用 AST 而不是文件哈希：
    文件哈希会被 docstring 改动本身带偏，证明不了「只改了 docstring」这件事。
    """
    assert _code_fingerprint(DEEP_JOB) == CODE_AST_SHA256

    tree = ast.parse(DEEP_JOB.read_text(encoding="utf-8"))
    names = [
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    ]
    assert names == [
        "ChargeLandingMissing", "DeepAnalysisPricing", "ChargeIntent",
        "DeepAnalysisSubmission", "_RunnerLike", "deep_analysis_payload",
        "submit_deep_analysis", "__init__", "submit",
    ]


def test_the_fingerprint_would_notice_a_code_change() -> None:
    """指纹自证：改一行代码（不是 docstring）会让它变。

    否则「指纹没变」可能只是因为这把尺子对什么都不敏感——那种绿什么都没证明。
    """
    source = DEEP_JOB.read_text(encoding="utf-8")
    tampered: Any = _strip_docstrings(ast.parse(source))
    tampered.body.append(ast.parse("MARKER = 1").body[0])
    changed = hashlib.sha256(ast.dump(tampered, annotate_fields=True).encode()).hexdigest()

    assert changed != CODE_AST_SHA256
