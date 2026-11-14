"""FIX-11：取数层缺 `not_found` 态——「这一条不存在」被说成「系统出错了」。

## 改前

后端对未知资源回的形状是**对的**：`404` + `{"code": "NOT_FOUND", …}`
（`BE-09` 的「404 不 403」口径）。而 `web/lib/screenClient.ts` 的五态里
**没有一个对应它**：带 `code` 的 404 掉进 `failed`，于是屏上显示

> 取数出错 · 后端回了一个错误状态

**「这一条不存在」与「系统出错了」，用户该做的事完全不同**：
前者换一个 id 或回上一层，后者等一会儿再试或来找我们。
`NotFound404` 组件 `UIX-02` 就建好了，**因为取数层没有这一态而一直用不上**。

## 三种「拿不到」NEVER 挤进两个表示

| 后端回什么 | 意思 | 屏上 |
|---|---|---|
| 404 **带** `code` | 这个能力在，这一条不存在 | `not_found` → `NotFound404` |
| 404 **不带** `code`（框架的） | 这条路由没挂上 | `not_provided` →「接口未提供」 |
| 5xx / 其它非 2xx | 坏了 | `failed` → 原样带出状态码与后端的说明 |

三者要人做的事各不相同：换 id / 去挂路由 / 等或来找我们。
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
CLIENT = WEB / "lib" / "screenClient.ts"
STATE = WEB / "lib" / "ScreenFetchState.tsx"
NOT_FOUND = WEB / "components" / "shell" / "NotFound404.tsx"
VITEST = WEB / "lib" / "screenFetchState.test.tsx"
SHEET = REPO / "docs" / "blocked" / "FETCH-LAYER-HAS-NO-NOT-FOUND-STATE.md"


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//"))


# ───────────────────────── 一、取数层多了一态，且与既有两态并列


def _union() -> str:
    """`Fetched` 联合的正文。

    **切到空行，不是切到第一个 `;`**：`{ kind: "ready"; data: T }` 里面就有一个，
    照那个切的话只能拿到头两行——而判据会因此报「联合里没有 not_found」，
    那句话是假的。第一版就是这么写的，红在这里而不是在产品上。
    """
    code = _code_only(CLIENT)
    body = code[code.index("export type Fetched"):]
    return body[: body.index("\n\n")]


def test_the_union_has_a_not_found_member() -> None:
    union = _union()

    for kind in ("loading", "ready", "not_found", "not_provided",
                 "not_configured", "failed"):
        assert f'kind: "{kind}"' in union, f"`Fetched` 里没有 {kind}：{union}"


def test_not_found_carries_the_backend_code_and_message() -> None:
    """带上后端自己的 `code` 与说明。

    只留一个 `kind` 的话，屏上只能说一句自己编的「找不到」——
    而后端可能说的是「无权查看」（`BE-09` 把无权与不存在收进同一条路，
    **那是有意的**：分开说等于告诉未授权的人这个 id 存在）。
    """
    member = next(ln for ln in _union().splitlines() if '"not_found"' in ln)

    assert "code" in member and "detail" in member, f"not_found 太瘦：{member}"


# ───────────────────────── 二、三种「拿不到」各走各的分支


def test_a_404_with_a_code_becomes_not_found() -> None:
    code = _code_only(CLIENT)

    assert re.search(
        r'res\.status === 404 && typeof body\.code === "string"', code), (
        "没有「404 带 code」那一支"
    )


def test_a_404_without_a_code_stays_not_provided() -> None:
    """框架的路由未命中回 `{"detail":"Not Found"}`——**没有 `code`**。

    这一支**不能动**：它说的是「这条路由不在」，与「这一条不存在」相反。
    """
    code = _code_only(CLIENT)

    assert re.search(
        r'res\.status === 404 && typeof body\.code !== "string"', code), (
        "「404 不带 code」那一支被改坏了"
    )


def test_the_three_branches_are_three_different_kinds() -> None:
    """**阴性对照（源码层）**：三种情况映到三个不同的 `kind`。

    把 `not_found` 实现成 `not_provided` 的别名也能让上面两条各自为真——
    这一条断言它们真的不是同一个。
    """
    code = _code_only(CLIENT)
    body = code[code.index("export async function fetchScreen"):]
    kinds = re.findall(r'kind: "(\w+)"', body)

    assert kinds.count("not_found") >= 1
    assert kinds.count("not_provided") >= 1
    assert len({"not_found", "not_provided", "failed"} & set(kinds)) == 3, (
        f"三种拿不到没有三个 kind：{kinds}"
    )


# ───────────────────────── 三、屏上接到 `NotFound404`


def test_the_state_renderer_uses_the_existing_component() -> None:
    """`NotFound404` `UIX-02` 就建好了，**因为取数层没有这一态而一直用不上**。

    另写一个的话，同一件事在两个组件里各说一句，而它们迟早分叉。
    """
    code = _code_only(STATE)

    assert "NotFound404" in code, "没接既有组件"
    assert 'state.kind === "not_found"' in code


def test_not_found_and_not_provided_render_differently() -> None:
    """**它们 NEVER 用同一个表示**（`NotFound404` 的 docstring 逐字写着）。

    混成一句「找不到」，用户会拿一个正确的 id 反复试；
    反过来混，用户会以为自己的数据被删了。
    """
    code = _code_only(STATE)

    assert 'data-screen-state="not_provided"' in code
    assert "NotFound404" in code
    # 两支各自独立：`not_found` 那一支 NEVER 落进 `not_provided` 的兜底 return。
    branch = code[code.index('state.kind === "not_found"'):]
    branch = branch[: branch.index("}\n") + 1]
    assert "not_provided" not in branch, "not_found 那一支里混进了 not_provided"


def test_the_three_states_carry_three_distinct_markers() -> None:
    """`data-screen-state` 三个值互不相同——取证与判据都按它读。"""
    code = _code_only(STATE)
    markers = set(re.findall(r'data-screen-state="(\w+)"', code))
    from_component = set(
        re.findall(r'data-screen-state="(\w+)"', _code_only(NOT_FOUND)))

    assert {"not_provided", "failed"} <= markers
    assert "not_found" in from_component, "NotFound404 没标出自己的态"
    # `not_found` 由组件自己标，**屏这边不重复标**：两处都标的话，
    # 取证会拿到两个嵌套的 `data-screen-state`，而按它读的判据只取第一个——
    # 那时改错了哪一处都看不出来。
    assert "not_found" not in markers, "屏这边又标了一次 not_found"


# ───────────────────────── 四、行为判据在 vitest 里，且真的构造了三种


def test_the_behaviour_is_covered_by_a_real_render_test() -> None:
    """三种话互不相同**只能在渲染上量**——源码层看不出两个分支渲染出同一句。

    所以行为判据在 vitest 里，这里断言它**真的分别构造了三种**，
    NEVER 只测一种然后声称覆盖。
    """
    assert VITEST.exists(), "没有渲染层判据"
    text = VITEST.read_text(encoding="utf-8")

    for kind in ('kind: "not_found"', 'kind: "not_provided"', 'kind: "failed"'):
        assert kind in text, f"vitest 里没有构造 {kind}"
    assert "toBe" in text or "toEqual" in text, "vitest 里没有断言"


# ───────────────────────── 五、单据关掉


def test_the_sheet_is_closed() -> None:
    text = SHEET.read_text(encoding="utf-8")
    state = next(ln for ln in text.splitlines()[:8] if ln.startswith("**状态**"))

    assert state.startswith("**状态** closed"), f"单据还开着：{state!r}"
    assert "FIX-11" in text
