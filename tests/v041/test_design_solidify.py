"""DESIGN-03：固化为模板 + 那个缺的第四态。

## 改前

`DesignWorkbench` 的 `registryAvailable` 是**三态**（`boolean | null`），
而后端 `WIRE-12` 之后给的是**第四种**：

```
200 /design/templates {"status":"not_provided","reason":"模板注册表不可用（迁移里没有 templates 表）…"}
```

`docs/blocked/UI-DESIGN-SCREEN-NEEDS-A-FOURTH-STATE.md` 把「塞进任一已有值都是谎」
逐条列过：

- 塞进 `false`（坏了）→ 屏上写「不可用，请稍后重试」，而真相是**重试一万次也不会有**；
- 塞进 `null`（没查过）→ 我们**明明查过了**；
- 写死一句「接口未提供」→ 话碰巧对，但后端哪天真上了那张表，这一屏不会知道。

## 本卡做的

四态 `not_checked / not_provided / down / ok`；固化真打 `POST /design/templates`；
**只有 `ok` 放开**，其余三种都阻断且各说各的话。

阴性对照四条在 vitest（`web/components/design-workbench/registryStates.test.tsx`）：
每一态单独构造，并**逐条断言另外三态的话不在场**——
只断言「本态的话在」的话，一个把四句话全渲染出来的实现照样全绿。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
COMPONENT = WEB / "components" / "design-workbench" / "DesignWorkbench.tsx"
SESSION = WEB / "components" / "design-workbench" / "designSession.ts"
PAGE = WEB / "app" / "design" / "page.tsx"
CONTROLS = WEB / "components" / "design-workbench" / "registryStates.test.tsx"
ZH = WEB / "messages" / "zh.json"
EN = WEB / "messages" / "en.json"
SHEET = REPO / "docs" / "blocked" / "UI-DESIGN-SCREEN-NEEDS-A-FOURTH-STATE.md"

STATES = ("not_checked", "not_provided", "down", "ok")


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


def _messages(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8"))


# ───────────────────────── 一、四态真的是四个


def test_the_registry_prop_has_exactly_four_states() -> None:
    code = _code_only(COMPONENT)

    assert "RegistryState" in code, "没有具名的四态类型"
    for state in STATES:
        assert f'"{state}"' in code, f"少了 {state} 这一态"
    # 三态版的形状 NEVER 残留：布尔位一回来，第四种又没地方放了。
    assert "registryAvailable: boolean | null" not in code


def test_only_ok_unblocks_solidifying() -> None:
    """规格 #2.17 第二条：注册表不可用时**固化与生产渲染阻断，探索期不阻断**。"""
    code = _code_only(COMPONENT)

    assert 'registryAvailable !== "ok"' in code, "阻断条件不是「只有 ok 放开」"
    assert "design.explore.still_open" in code, "没说清还能做什么（E6 的另一半）"


def test_each_blocked_state_carries_its_own_marker() -> None:
    """判别位就是那四态本身——共用一个的话，三种阻断在取证里长得一模一样。"""
    code = _code_only(COMPONENT)

    assert "data-design-blocked={registryAvailable}" in code


# ───────────────────────── 二、四句话互不相同（中英各一份）


def test_the_four_lines_are_four_different_sentences() -> None:
    zh, en = _messages(ZH), _messages(EN)
    keys = ("design.solidify.not_checked", "design.solidify.not_provided",
            "design.solidify.registry_down")

    for table, lang in ((zh, "zh"), (en, "en")):
        said = [table[k] for k in keys]
        assert len(set(said)) == 3, f"[{lang}] 三种阻断共用了话术：{said}"
        for line in said:
            assert len(line) > 4, f"[{lang}] 这句话太短，说不清是哪一种：{line!r}"


def test_the_not_provided_line_says_retrying_will_not_help() -> None:
    """「这里没有」与「坏了」的分界就在这一句上。

    不说这句的话，用户会照着「不可用」的直觉去重试——而重试一万次也不会有。
    """
    zh, en = _messages(ZH), _messages(EN)

    assert "重试" in zh["design.solidify.not_provided"]
    assert "retry" in en["design.solidify.not_provided"].lower()


# ───────────────────────── 三、固化真打端点，且不预判


def test_solidifying_posts_to_the_real_endpoint() -> None:
    code = _code_only(SESSION)

    assert '"/design/templates"' in code or "/design/templates" in code
    assert 'method: "POST"' in code


def test_the_front_end_never_decides_whether_it_may_solidify() -> None:
    """能不能固化由**服务端**答复决定；屏那侧只做置灰与说明。

    前端预判的那份判断会与后端各自漂移——后端哪天补上了校验，
    屏上仍然按旧规则放行或拦下。
    """
    code = _code_only(SESSION)

    # NEVER 在客户端里复刻后端的校验（水印、template_id 之类）。
    assert "watermark" not in code.lower(), "客户端复刻了后端的校验"


def test_the_registry_state_comes_from_a_real_probe() -> None:
    """四态是**查回来的**，不是写死的。"""
    code = _code_only(SESSION) + _code_only(PAGE)

    assert "probeRegistry" in code
    assert 'return "not_provided"' in _code_only(SESSION)
    # 连不上 = 查过了、坏了。**NEVER 回 not_checked**：我们确实查过。
    assert 'return "down"' in _code_only(SESSION)


def test_the_screen_starts_at_not_checked_never_at_down() -> None:
    """初值是「还没查过」。初成 `down` 就是替后端下结论，而我们还没问过。"""
    code = _code_only(PAGE)

    assert '<RegistryState>("not_checked")' in code


# ───────────────────────── 四、阴性对照四条真的在


def test_the_four_negative_controls_exist() -> None:
    """卡面 acceptance③ 的原话：四种状态分别构造，断言屏上四种话互不相同。"""
    controls = CONTROLS.read_text(encoding="utf-8")

    for state in STATES:
        assert state in controls, f"vitest 里没有 {state} 的对照"
    assert "另外三态的话都不在场" in controls, "只断言了「本态在」——那是弱断言"


# ───────────────────────── 五、那张问题单可以关了


def test_the_fourth_state_sheet_is_closed() -> None:
    """卡面 acceptance④：关闭那张单。

    **关的条件是它说的事已经做完**，不是「这张卡跑完了」——
    所以这里先验四态在位，再验单据的状态行。
    """
    code = _code_only(COMPONENT)
    for state in STATES:
        assert f'"{state}"' in code

    head = SHEET.read_text(encoding="utf-8").splitlines()[:6]
    state_line = next((ln for ln in head if ln.startswith("**状态**")), "")

    assert state_line.startswith("**状态** closed"), f"单据还开着：{state_line!r}"
    assert "DESIGN-03" in " ".join(head), "关单没写是谁关的"
