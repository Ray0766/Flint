"""WIRE-03 · 九张新屏从「接口未提供」切到真数据。

## 本卡做到了哪一半，没做到哪一半

`WIRE-01` 把 42 条路径挂上了，于是九张屏的端点**都在**。但「端点在」不等于
「切过去就诚实」——`WIRE-03` 开工探端点，实测出两类：

| 类 | 屏 | 端点回什么 | 切过去诚实吗 |
|---|---|---|---|
| 可切 | account · billing · settings · project-overview | `not_checked` / `not_enabled`+理由 / 声明过的默认值 / 带 `code` 的 404 | **是** |
| 不可切 | favorites · design · graph(workbench) · share | `{"items": []}`，来自**内存件** | **否，是假空态** |

第二类切过去，屏上会写「还没有收藏」——而真相是「这个功能还没有库」。
`DEC-032` 的原话正是这件事。已停下登记：
`docs/blocked/WIRE-03-EMPTY-FROM-A-STORE-THAT-HAS-NO-DATABASE.md`（owner 三选一）。

所以本卡切了**四张**，另五张（含两张 503 族）留在原态**并由本文件判等值**——
多切一张少切一张都会红，逼人回到那张单上。

## 四种结果，四个 `data-screen-state`

`loading` / `not_provided` / `not_configured` / `failed`，外加 `ready` 时交给子组件。
**`not_provided` 与 `not_configured` NEVER 合并**：前者要人去挂路由，
后者要人去配一个后端。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
APP = WEB / "app"
LIB = WEB / "lib"
TICKET = REPO / "docs" / "blocked" / "WIRE-03-EMPTY-FROM-A-STORE-THAT-HAS-NO-DATABASE.md"

# 本卡切了的四张（页面文件 → 它打的端点前缀）。
WIRED: dict[str, str] = {
    "account/page.tsx": "/account",
    "billing/page.tsx": "/billing",
    "settings/locale/page.tsx": "/settings/locale",
    "projects/[id]/page.tsx": "/projects/",
    # `WIRE-12` 把后端那句假空态改掉之后切的第五张：
    # `not_provided` → 「接口未提供」；`{"items": […]}` → 真列表（`[]` 就是真没有）。
    "favorites/page.tsx": "/favorites",
}
# 端点挂上了、但本卡**有意不切**的（理由逐条在单子里）。
HELD_BACK: dict[str, str] = {
    # `WIRE-12` 之后这条的理由**换了**：后端不再回假空表了，
    # 但这一屏要显示的是**第四种**状态（没有存储面），而组件只有三种
    # （没查过 / 坏了 / 可用）。把它塞进「坏了」正是本批禁止的事，
    # 加第四种要改组件契约——大于本卡 outputs。见
    # `docs/blocked/UI-DESIGN-SCREEN-NEEDS-A-FOURTH-STATE.md`。
    "design/page.tsx": "组件缺第四态：没有存储面 ≠ 坏了 ≠ 没查过",
    "share/[token]/page.tsx": "内存件里每个 token 都「不存在」= 假否定",
    "workbenches/[id]/page.tsx": "graph 内存件的空 = 假空态",
    "deliverables/[id]/quality/page.tsx": "quality 族没有后端，端点回 503（FIX 见单）",
    "deliverables/[id]/pack/page.tsx": "pack 族没有后端，端点回 503",
}


def _calls_endpoint(code: str) -> bool:
    """判的是**调用点**，不是标识符在不在。

    变异考逼出来的：只扫 `"useScreenData" in code`，把屏改成
    `const state = {kind:"not_provided"}` 之后 **import 那行仍然含这个词**，
    判据照样绿。取数没了，判据不知道。
    """
    return "useScreenData<" in code or "useScreenData(" in code


def _code(path: Path) -> str:
    """去掉注释：注释里出现的路径不算「屏在打这条端点」。"""
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("//", "*"))
    )


# ───────────────────────── acceptance①：切到真端点


def test_the_wired_screens_actually_call_their_endpoint() -> None:
    """四张切了的屏，源码里真的在取那条端点。"""
    for rel, endpoint in WIRED.items():
        code = _code(APP / rel)

        assert _calls_endpoint(code), f"{rel} 没有取数（import 在不算）"
        assert endpoint in code, f"{rel} 没打 {endpoint}"


def test_the_held_back_screens_are_exactly_the_registered_ones() -> None:
    """**判等值**：本卡有意不切的那几张，逐张对上单子。

    多切一张 = 造了个假空态；少切一张 = 该切的没切。两种都要有人来这里确认。
    """
    not_fetching = {
        rel for rel in (*WIRED, *HELD_BACK)
        if not _calls_endpoint(_code(APP / rel))
    }

    assert not_fetching == set(HELD_BACK), (
        f"不取数的屏与登记面对不上：多出 {sorted(not_fetching - set(HELD_BACK))}，"
        f"少了 {sorted(set(HELD_BACK) - not_fetching)}"
    )
    assert TICKET.exists(), "留着不切却没有单子——那与忘了切长得一样"


def test_the_ticket_explains_each_held_back_screen() -> None:
    """单子里要讲清每一张为什么不切，不是一句「有问题」。"""
    text = TICKET.read_text(encoding="utf-8")

    for name in ("favorites", "design", "share", "graph_edges"):
        assert name in text, f"单子没提 {name}"
    assert "假空态" in text
    assert "DEC-032" in text


# ───────────────────────── acceptance②：三态 + 两种「没有」不合并


def test_the_four_outcomes_have_four_different_state_names() -> None:
    """`loading` / `not_provided` / `not_configured` / `failed` 各是一个名字。

    合并任意两个，读屏的人就得自己去猜是哪一种。
    """
    code = _code(LIB / "ScreenFetchState.tsx")
    states = set(re.findall(r'data-screen-state="([a-z_]+)"', code))

    assert states == {"loading", "not_provided", "not_configured", "failed"}


def test_not_provided_and_not_configured_are_never_merged() -> None:
    """两种「没有」分开：一个要人去挂路由，一个要人去配后端。"""
    client = _code(LIB / "screenClient.ts")

    assert '"not_provided"' in client and '"not_configured"' in client
    # 判别靠 `code` 键：框架的 404 没有它，应用自己发的都有。
    assert "FAMILY_NOT_CONFIGURED" in client
    assert 'body.code !== "string"' in client


def test_a_backend_404_with_a_code_is_not_read_as_not_provided() -> None:
    """带 `code` 的 404 是「挂上了，它说这东西不存在」，NEVER 读成「接口未提供」。

    `BE-09` 的「404 不 403」口径就是这么发的；把两者混起来，
    「分享链接不存在」会被显示成「这个功能没做」。
    """
    client = _code(LIB / "screenClient.ts")

    assert re.search(r"res\.status === 404 && typeof body\.code !== \"string\"", client)


def test_loading_is_never_rendered_as_the_empty_or_missing_state() -> None:
    """取数中 NEVER 借用空态或「接口未提供」——那是本批一路在治的病。"""
    code = _code(LIB / "ScreenFetchState.tsx")
    loading_block = code.split('data-screen-state="loading"')[1].split("}")[0]

    assert "screen.loading" in loading_block
    assert "not_provided" not in loading_block


# ───────────────────────── acceptance③：适配层只改形状


def test_the_adapter_turns_the_backend_not_checked_object_into_null() -> None:
    """后端用 `{"status":"not_checked"}` 表示「没查过」，组件用 `null`。

    **不翻译直接喂**的话，那个对象是真值，组件会把「没查过」渲染成
    「查过了、有内容」——正好是本批一路在治的那个错。
    """
    code = _code(LIB / "screenAdapters.ts")

    assert 'box.status === "not_checked"' in code
    assert "return null" in code


def test_the_adapter_never_invents_a_default() -> None:
    """适配层只改形状：NEVER 补默认值、NEVER 把缺的算出来。"""
    code = _code(LIB / "screenAdapters.ts")

    # 前端零计算：金额恒是字符串原样转出，不做加总。
    assert "reduce(" not in code
    assert "parseFloat" not in code and "Number(row.amount" not in code


# ───────────────────────── acceptance④：既有前端测试不倒


def test_the_new_i18n_keys_exist_on_both_sides() -> None:
    zh = json.loads((WEB / "messages" / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((WEB / "messages" / "en.json").read_text(encoding="utf-8"))

    for key in ("screen.loading", "screen.failed", "screen.failed_hint",
                "screen.not_configured", "screen.not_configured_hint"):
        assert key in zh and key in en, key
        assert zh[key] != en[key], f"{key} 中英文案是同一个字符串"


def test_no_screen_hardcodes_a_base_url() -> None:
    """基址只从 `API_BASE` 来——写死一个 localhost 会在别的环境静默打空。"""
    for rel in WIRED:
        code = _code(APP / rel)

        assert "localhost" not in code, f"{rel} 里写死了 localhost"
        assert "http://" not in code, f"{rel} 里写死了基址"


def test_every_string_shown_to_the_user_goes_through_i18n() -> None:
    for rel in WIRED:
        for literal in re.findall(r"[\"'`]([^\"'`]*)[\"'`]", _code(APP / rel)):
            assert not re.search(r"[一-龥]", literal), f"{rel} 里有裸中文：{literal!r}"
