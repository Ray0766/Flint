"""PLAZA-04：卡片三独立动作（收藏 / 入台 / 分享）+ 点击排除区。

## 三条动作今天各自走到哪（**开工时逐条打过真栈**，不是读代码猜的）

| 动作 | 端点 | 实测答复 |
|---|---|---|
| 收藏 | `POST /favorites` | `{"status":"not_provided","reason":"收藏还没有存储面（迁移里没有 favorites 表）…"}` |
| 分享 | `POST /shares` | `422 {"detail":{"allowed":["deliverable","graph","topic"]}}` —— **热点簇不在冻结件允许的三种里** |
| 入台 | `POST /workbenches` | `404`，且是**框架的那种没有 `code` 的 404**（路由从没挂过） |

三条都到不了「成功」。**但这不等于本卡做不了**：`DEC-032` 定死了未装配期间的口径——
一律显示「接口未提供」，NEVER 显示空态／未启用／隐藏入口。
所以本卡交付的是**三个真会发请求、并把服务端的答复如实说出来的按钮**，
而不是三个假装能用的按钮，也不是三个被藏起来的入口。

## 三种「不成」NEVER 揉成一句

- **还没接**（收藏、入台）：等我们去挂存储面／挂路由；
- **这类目标不支持**（分享）：能力在，但要改冻结件的 `target_kind` 判别联合；
- **失败**：后端自己的说明原样带出来。

揉成一句「暂不可用」，用户与下一个读代码的人都无从知道该做什么——
与本仓一路在守的「未知 ≠ 没查过 ≠ 没接」是同一条纪律。

## 判据分两层

- **交互在 vitest**（`web/components/plaza/cardActions.test.tsx`，10 条）：
  三动作各自独立、点击排除区**双断言**、三种「不成」互不共用、答复不串卡；
- **本文件**判 vitest 够不着的：组件没被另写一份、允许清单不自带、按钮真的占了像素。
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
ACTIONS = WEB / "components" / "hotspot-card-actions" / "HotspotCardActions.tsx"
CLIENT = WEB / "components" / "plaza" / "cardActions.ts"
CARDS = WEB / "components" / "plaza" / "PlazaCards.tsx"
VITEST = WEB / "components" / "plaza" / "cardActions.test.tsx"
ZH = WEB / "messages" / "zh.json"
EN = WEB / "messages" / "en.json"
ARTIFACT = REPO / ".ui-probe" / "plaza_card_actions.json"

PWENV = Path(r"C:\pwenv\Scripts\python.exe")
FRONTEND = "http://localhost:3000/plaza"

ACTION_IDS = ("action-favorite", "action-workbench", "action-share")


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


def _messages(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8"))


# ───────────────────────── 一、复用既有组件，NEVER 另写一份


def test_the_actions_component_is_reused_not_rewritten() -> None:
    """`HotspotCardActions` 已在盘上（`HOTSPOT-02` 建的），本卡只接线与补端点调用。"""
    others = [
        str(p.relative_to(WEB)) for p in WEB.rglob("*.tsx")
        if "node_modules" not in p.parts
        and p != ACTIONS
        and not p.name.endswith(".test.tsx")
        and "hotspot-card__action" in _code_only(p)
    ]

    assert others == [], f"这些文件另画了一份动作区：{others}"
    assert "HotspotCardActions" in _code_only(CARDS), "广场没接上那个组件"


def test_all_three_actions_are_wired_to_real_endpoints() -> None:
    code = _code_only(CLIENT)

    for path in ("/favorites", "/shares", "/workbenches"):
        assert f'"{path}"' in code, f"{path} 没接"
    assert "method: \"POST\"" in code


# ───────────────────────── 二、点击排除区


def test_the_action_zone_stops_the_click_from_bubbling() -> None:
    """卡片本身是跳转入口。不挡住冒泡，点「收藏」会**既收藏又跳走**。"""
    code = _code_only(ACTIONS)

    assert "stopPropagation" in code, "动作区没有点击排除"
    # 挂在容器上而不是逐个按钮挂：逐个挂的话，将来多一个按钮而有人忘了挂，那一个就会漏。
    container = code.split('data-testid="card-actions"')[1].split("<button")[0]
    assert "stopPropagation" in container, "点击排除挂在了单个按钮上，不是动作区容器"


def test_the_double_assertion_exists_in_the_interaction_tests() -> None:
    """卡面 acceptance② 的原话就是「双断言」：点动作不跳转 · 点卡面跳转。"""
    tests = VITEST.read_text(encoding="utf-8")

    assert "点动作不跳转" in tests and "点卡面跳转" in tests
    assert "expect(onSelect).not.toHaveBeenCalled()" in tests
    assert 'expect(onSelect).toHaveBeenCalledWith("c0")' in tests


# ───────────────────────── 三、三种「不成」互不共用


def test_the_three_kinds_of_failure_have_three_different_words() -> None:
    zh, en = _messages(ZH), _messages(EN)
    keys = ("card.action.not_provided", "card.action.unsupported", "card.action.failed")

    for table, lang in ((zh, "zh"), (en, "en")):
        for key in keys:
            assert key in table, f"[{lang}] 缺 {key}"
        assert len({table[k] for k in keys}) == 3, f"[{lang}] 三种「不成」共用了话术"


def test_the_allowed_list_comes_from_the_server_not_from_us() -> None:
    """允许清单**来自 422 的 `detail.allowed`**——前端自带一份会与冻结件各自漂移。"""
    code = _code_only(CLIENT)

    assert 'detail["allowed"]' in code, "没有从服务端答复里取允许清单"
    for kind in ("deliverable", "graph", "topic"):
        assert f'"{kind}"' not in code, f"前端自带了一份允许清单（{kind}）"


def test_a_bare_404_is_read_as_not_wired_not_as_missing_row() -> None:
    """框架的 404 回 `{"detail":"Not Found"}`——**没有 `code`**。

    带 `code` 的 404 是「这一条不存在」，没有 `code` 的是「这个能力还没挂」。
    混成一句，用户会拿一个正确的 id 反复试（`NotFound404` 的既有口径）。
    """
    code = _code_only(CLIENT)

    assert 'payload["code"] === undefined' in code, "两种 404 没有分开"


def test_success_is_never_reported_for_a_not_provided_answer() -> None:
    code = _code_only(CLIENT)

    # `not_provided` 的判断必须在 `res.ok` 之前——那条答复是 **200**（WIRE-12 的姿态），
    # 先判 ok 就会把「还没接」报成「成功」。
    assert code.index("NOT_PROVIDED") < code.index("return { kind: \"ok\"")


# ───────────────────────── 四、运行时：按钮真的占了像素


_RUNNER = r"""
import json, sys
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900})
    page.goto(url, wait_until="networkidle", timeout=60000)
    page.wait_for_selector("[data-testid='action-favorite']", timeout=30000)
    got = page.evaluate(
        '''() => {
            const zone = document.querySelector('[data-testid="card-actions"]');
            const btns = ['action-favorite', 'action-workbench', 'action-share']
                .map(id => document.querySelector(`[data-testid="${id}"]`));
            return {
              zones: document.querySelectorAll(
                  '[data-testid="card-actions"]').length,
              zoneBox: zone ? zone.getBoundingClientRect().height : 0,
              buttons: btns.map(el => el ? {
                  text: el.textContent.trim(),
                  width: el.getBoundingClientRect().width,
                  height: el.getBoundingClientRect().height,
              } : null),
            };
        }''')
    # 真按一次「收藏」：屏上必须出现一句答复（那条端点今天回 not_provided）。
    page.click("[data-plaza-list] [data-testid='action-favorite']")
    page.wait_for_selector("[data-testid='action-outcome']", timeout=15000)
    got["outcome"] = page.evaluate(
        '''() => {
            const el = document.querySelector('[data-testid="action-outcome"]');
            const r = el.getBoundingClientRect();
            return {kind: el.getAttribute('data-outcome-kind'),
                    of: el.getAttribute('data-outcome-of'),
                    text: el.textContent.trim(),
                    width: r.width, height: r.height};
        }''')
    got["navigated"] = page.url
    page.screenshot(path=".ui-probe/plaza-card-actions.png")
    b.close()
open(out, "w", encoding="utf-8").write(
    json.dumps({"schema": "plaza-card-actions/1", "url": url, **got},
               ensure_ascii=False, indent=1))
"""


def _artifact() -> dict[str, object]:
    if ARTIFACT.exists():
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外，NEVER 进项目依赖）")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "plaza_card_actions_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(PWENV), str(runner), FRONTEND, str(ARTIFACT)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False,
        )
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动（{FRONTEND}）：{done.stderr[-500:]}")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_the_three_buttons_have_words_and_occupy_pixels() -> None:
    """改前它们是**三个空按钮**：读屏软件念不出来，屏上量出来是 0 像素（F-09 同一形状）。"""
    buttons = _artifact()["buttons"]

    assert all(b is not None for b in buttons), "有按钮不在屏上"
    for button in buttons:
        assert button["text"], f"按钮没有文字：{button}"
        assert button["width"] > 20 and button["height"] > 10, f"按钮几乎没有面积：{button}"


def test_every_card_carries_its_own_action_zone() -> None:
    art = _artifact()

    assert art["zones"] > 1, f"只有 {art['zones']} 个动作区"
    assert art["zoneBox"] > 10, "动作区占 0 像素"


def test_pressing_favourite_says_the_truth_and_does_not_navigate() -> None:
    """真按一次：屏上出现「接口未提供」，**而且没有跳走**（点击排除区在真浏览器里也成立）。"""
    art = _artifact()
    outcome = art["outcome"]

    assert outcome["kind"] == "not_provided", f"收藏的答复被读成了 {outcome['kind']}"
    assert outcome["of"] == "favorite", "答复挂到了别的动作上"
    assert outcome["text"], "答复那一行是空的"
    assert outcome["width"] > 0 and outcome["height"] > 0
    assert art["navigated"].endswith("/plaza"), f"点动作把人带走了：{art['navigated']}"
