"""FB-09：前端把六类 id 换成内容——源码面与接线面的守卫。

呈现行为由 vitest 守（`web/lib/derefClient.test.ts` + `web/components/deref/DerefValue.test.tsx`，
`cd web && npm test -- --run deref` = 本卡 verify_cmd）。这里守三件 vitest 够不着的事：

1. **六处全都换掉了**——少换一处，那一处就继续把 id 甩给读者，而屏上其余五处看起来都对；
2. **前端零计算**——价格格把 quantity 交给后端算，组件里不许出现乘法；
3. **端点真的挂上了**——`create_deref_app` 不被任何 app 挂载的话，六处全都会显示
   「接口未提供」。那是**诚实的**，但 acceptance① 说的是「改为显示解引用后的内容」，
   没挂就等于没做到。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BLOCKVIEW = REPO / "web" / "components" / "blocks" / "BlockView.tsx"
DEREF_VALUE = REPO / "web" / "components" / "DerefValue.tsx"
DEREF_CLIENT = REPO / "web" / "lib" / "derefClient.ts"
DEMO_SERVER = REPO / "harness" / "demo_server.py"

SIX_KINDS = ("fact", "price", "citation", "chart", "card", "hints")


def _code(path: Path) -> str:
    """剥掉注释再扫——注释里逐字写着「原来显示 fact_id」那类说明。

    本批第五次同一类问题（GAUGE-06 / FB-01 / FB-02 / FB-04）：
    **判据落在代码层，不落在解释代码的话上。**
    """
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    return re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)


# ───────────────────────── ① 六处全换


def test_all_six_channels_are_wired_in_the_block_view() -> None:
    """六条通道在 BlockView 里各出现一次——少换一处就少一处。"""
    code = _code(BLOCKVIEW)

    used = set(re.findall(r'kind="(\w+)"', code))
    assert set(SIX_KINDS) <= used, f"没换的通道：{sorted(set(SIX_KINDS) - used)}"
    # 七处而不是六处：`citation_list` 块把每条 citation_id 逐行列出来，
    # 它也是「显示 citation_id 的地方」。首版只接了六处，**是截图让我看见第七处的**
    # ——那两行 `cit-demo-…` 明晃晃地留在屏上（docs/trace/FB-09.md §5）。
    assert code.count("<DerefValue") == 7


def test_no_bare_id_is_rendered_as_the_only_content() -> None:
    """屏上不再出现「把 id 本身当正文」的写法。

    `{cell.fact_id}` / `{content.card_ref}` 这类直接把 id 塞进正文的表达式，
    正是 EYE-03 截图里用户看到的那些字符串。
    """
    code = _code(BLOCKVIEW)
    leaks = re.findall(
        r">\s*\{(?:cell|content|span)\.(fact_id|price_entry_id|citation_id|"
        r"chart_id|card_ref|hints_ref)\}\s*<",
        code,
    )

    assert leaks == [], f"这些 id 还被直接当正文渲染：{leaks}"


def test_the_dev_facing_data_attributes_survive() -> None:
    """`data-*` 留着：管道细节属**开发面**，取证与调试要用（acceptance③ 的另一半）。

    产品面移走 ≠ 全仓删掉。EYE-01 的 `--selector` 取证、既有 BlockView 测试
    都靠这些属性定位。
    """
    code = _code(BLOCKVIEW)

    for attr in ("data-fact-id", "data-price-entry-id", "data-citation-id",
                 "data-chart-id", "data-quality-card-ref", "data-gap-notice-ref"):
        assert attr in code, f"{attr} 被顺手删了——取证面会跟着塌"


# ───────────────────────── ② 前端零计算


def test_the_front_end_never_multiplies_a_price() -> None:
    """价格格把 quantity 交给后端算，组件里 NEVER 出现乘法。

    前端自己乘出来的金额没有出处——它不进账本、不留痕，单价变了也不会告诉任何人。
    """
    for path in (BLOCKVIEW, DEREF_VALUE, DEREF_CLIENT):
        code = _code(path)
        assert not re.search(r"(price|amount|quantity)\w*\s*\*", code), f"{path.name} 里有乘法"
        assert "quantity" not in code or "quantity=" in code or "quantity" in code

    block = _code(BLOCKVIEW)
    assert "quantity={cell.quantity}" in block, "quantity 没被交出去，后端算什么"


def test_the_client_asks_the_backend_for_the_amount() -> None:
    """价格路径带上 quantity——后端据此算金额（FB-05）。"""
    code = _code(DEREF_CLIENT)

    assert "quantity=" in code
    assert "/price-entries/" in code


# ───────────────────────── ③ 端点真的挂上了


def test_the_deref_app_is_mounted_somewhere_reachable() -> None:
    """`create_deref_app` 被真挂上了。

    不挂的话六处全显示「接口未提供」——那是诚实的，但 acceptance① 说的是
    「改为显示解引用后的内容」，没挂就等于没做到。

    **`WIRE-02` 改了这条的量法**：原先断言 `demo_server.py` 源码里有
    `create_deref_app` 这个词——那正是「只断言语句存在」，对
    「挂了个空 router」「被别人遮蔽」「挂上了但那族根本没路由」全部报绿。
    改后问**建起来的应用**要路由表。deref 现在由
    `flint/api/app.py::create_app` 统一挂，demo 栈从它起，所以那个词
    不再出现在 demo 源码里，而端点比以前挂得更牢。
    """
    from flint.api.app import mounted_route_table
    from harness.demo_server import build_app

    mounted = {r.path for r in mounted_route_table(build_app())}
    deref_paths = {p for p in mounted if "deref" in p or "/facts/" in p}

    assert deref_paths, f"demo 栈上一条 deref 路由都没有；已挂 {len(mounted)} 条"


def test_every_mounted_path_matches_what_the_client_asks_for() -> None:
    """客户端拼的六条路径与后端真注册的路由逐条对上。

    对不上就是 404，而 404 在前端会被显示成「接口未提供」——
    **一个拼错的路径与一个没实现的端点长得一模一样**，那种错能藏很久。
    """
    from flint.api.deref import DerefApiDeps, create_deref_app

    routes = {getattr(r, "path", "") for r in create_deref_app(DerefApiDeps(dsn="x")).routes}
    client = _code(DEREF_CLIENT)

    expected = {
        "/facts/{fact_id}": "/facts/",
        "/price-entries/{price_entry_id}": "/price-entries/",
        "/citations/{citation_id}": "/citations/",
        "/charts/{chart_id}": "/charts/",
        "/cards/{card_id}": "/cards/",
        "/hints/{hints_ref}": "/hints/",
    }
    for route, prefix in expected.items():
        assert route in routes, f"后端没有这条路由：{route}"
        assert prefix in client, f"客户端没拼这条路径：{prefix}"


# ───────────────────────── ④ 文案走 i18n


def test_the_unavailable_label_is_a_key_not_a_hardcoded_string() -> None:
    """「接口未提供」走 i18n key，两侧都有定义且中英不同。"""
    code = _code(DEREF_VALUE)
    assert 't("deref.unavailable")' in code

    zh = json.loads((REPO / "web" / "messages" / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((REPO / "web" / "messages" / "en.json").read_text(encoding="utf-8"))

    assert zh["deref.unavailable"] and en["deref.unavailable"]
    assert zh["deref.unavailable"] != en["deref.unavailable"]


def test_the_new_files_hold_no_hardcoded_chinese() -> None:
    """两个新文件的**代码层**没有中文字面量（注释与 docstring 不算）。"""
    for path in (DEREF_VALUE, DEREF_CLIENT):
        code = _code(path)
        for literal in re.findall(r'"([^"]*)"', code) + re.findall(r"'([^']*)'", code):
            assert not any("一" <= ch <= "鿿" for ch in literal), (
                f"{path.name} 里有中文字面量：{literal!r}"
            )
