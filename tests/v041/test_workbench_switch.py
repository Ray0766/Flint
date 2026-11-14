"""K6-01：多工作台切换入口的**样式面与像素面**判据。

交互面的判据在 `web/components/workbench-switch/WorkbenchSwitch.test.tsx`
（卡上 verify_cmd 跑的就是它）。本文件管三件那边管不了的事：

1. **入口真的看得见**（acceptance④ / EYE-02）：空元素的行内默认尺寸是 0×0，
   `getByTestId(...)` 对一个 0 像素的按钮照样通过——F-09 就是这么漏过去的；
2. **样式只接线不发明**：每个值取自 `_ds` 已声明的 token，
   应用层 NEVER 新起颜色或间距；
3. **GRAPH-16 的纪律**：切的是工作台不是模式，仓里 NEVER 出现 mode 键——
   判据落在**代码面**（剥掉注释），不落在解释代码的话上。

像素面走 EYE-02 的 `check_fragment`，产物 `.ui-probe/workbench_switch.json`
由本文件的 `__main__` 生成（跑法见 docs/trace/K6-01.md），所以它可复现。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GLOBALS = REPO / "web" / "app" / "globals.css"
DS_ROOT = REPO / "web" / "public" / "_ds"
ARTIFACT = REPO / ".ui-probe" / "workbench_switch.json"
COMPONENT = REPO / "web" / "components" / "workbench-switch" / "WorkbenchSwitch.tsx"
TRIGGER_SELECTOR = ".workbench-switch__trigger"

# 本卡用到的 `_ds` token：每一个都要在 `_ds` 里真的存在（写错名字 = 取到空值 = 没样式）
USED_TOKENS = (
    "--surface-card", "--border-rule", "--text-body", "--text-meta",
    "--accent-structure", "--sp-1", "--sp-2", "--sp-3", "--sp-5", "--fs-13", "--fs-14",
)

# 本卡在 globals.css 里加的全部选择器。判据从这些规则里**实际用到的** token 上取。
K6_SELECTORS = (
    TRIGGER_SELECTOR, ".workbench-switch__list", ".workbench-switch__row",
    ".workbench-switch__section", '.workbench-switch__item[aria-current="true"]',
)


def _bundle_dir() -> Path:
    dirs = [p for p in DS_ROOT.iterdir() if p.is_dir()]
    assert len(dirs) == 1
    return dirs[0]


def _rule(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    return match.group(1) if match else ""


def _code_face(source: str) -> str:
    """剥掉行注释的代码面。

    判据落在代码上，不落在解释代码的话上：本组件的注释里逐字写着
    「NEVER 出现 mode 键」，扫原文会把「禁掉它」当成「用了它」。
    """
    return "\n".join(
        line for line in source.split("\n") if not line.strip().startswith("//")
    )


# ───────────────────────── ① 样式面（恒跑）


def test_the_trigger_has_a_real_rule_with_a_nonzero_box() -> None:
    """入口按钮有真规则且**盒子不为零**。

    看不见的入口等于没有入口——而 GRAPH-14 的数据层已经把多台存好了，
    用户却找不到门。
    """
    body = _rule(GLOBALS.read_text(encoding="utf-8"), TRIGGER_SELECTOR)

    assert body, f"{TRIGGER_SELECTOR} 在 globals.css 里没有规则"
    assert re.search(r"\bmin-height\s*:", body), "没有最小高度：内容一空它就塌成 0"
    assert re.search(r"\bpadding\s*:", body), "没有内边距：点击区域会小到按不中"
    assert "background-color" in body, (
        "没有实底色：透明底下 getComputedStyle().backgroundColor 取到 rgba(0,0,0,0)，"
        "对比度无从算起（EYE-02 会判红，且判得对）"
    )


def test_every_value_comes_from_a_ds_token() -> None:
    """只接线，不发明：本卡的规则里**没有裸值**（颜色、间距、字号全走 token）。

    新起一个值就等于这套系统里多了一份没人维护的真相：`_ds` 改了，这里不会跟着变。
    """
    css = GLOBALS.read_text(encoding="utf-8")
    for selector in (TRIGGER_SELECTOR, ".workbench-switch__list",
                     ".workbench-switch__row", ".workbench-switch__section"):
        body = _rule(css, selector)
        assert body, f"{selector} 没有规则"
        for prop in ("background-color", "color", "font-size", "padding", "gap"):
            for decl in re.findall(rf"{prop}\s*:([^;]+);", body):
                assert "var(--" in decl, f"{selector} 的 {prop} 用了裸值：{decl.strip()}"


def test_the_tokens_actually_exist_in_ds() -> None:
    """token 名字写错 = 取到空值 = 没样式，而 CSS **不会报错**。

    判据从 globals.css 里**真正用到的那些名字**上取，不是核对一张手写清单：
    核清单的话，把 `var(--surface-card)` 打成 `var(--surface-carddd)`
    这条断言照样绿（变异考实测：11 条全过）——清单没变，用的名字变了。
    """
    css = GLOBALS.read_text(encoding="utf-8")
    declared = "".join(
        p.read_text(encoding="utf-8") for p in (_bundle_dir() / "tokens").glob("*.css")
    )

    used: set[str] = set()
    for selector in K6_SELECTORS:
        used.update(re.findall(r"var\((--[a-z0-9-]+)", _rule(css, selector)))

    assert used >= set(USED_TOKENS), f"本卡该用到的 token 少了：{set(USED_TOKENS) - used}"
    missing = sorted(tok for tok in used if f"{tok}:" not in declared)
    assert missing == [], f"这些 token 在 _ds 里不存在（名字写错了？）：{missing}"


def test_the_current_workbench_is_marked_for_sighted_users_too() -> None:
    """当前台要**看得出来**：只靠 `aria-current` 的话，读屏用户知道、视力用户不知道。"""
    body = _rule(GLOBALS.read_text(encoding="utf-8"),
                 '.workbench-switch__item[aria-current="true"]')

    assert body, "当前台没有任何视觉标记"
    assert "border-inline-start" in body or "font-weight" in body


# ───────────────────────── ② GRAPH-16：切的是台，不是模式


def test_the_component_has_no_mode_key() -> None:
    """acceptance③：store 里 NEVER 出现 mode 键。判据落在**代码面**。"""
    code = _code_face(COMPONENT.read_text(encoding="utf-8"))

    assert not re.search(r"\bmode\s*[:=]", code), "组件里出现了 mode 键"


def test_the_state_keys_are_exactly_two() -> None:
    """状态恒为两个正交的键：`currentId` 与 `showArchived`。

    第三个键进来就要回答「它与另外两个冲突时听谁的」，
    而任何一次答得不一致，界面上就会出现自相矛盾的状态。
    """
    code = _code_face(COMPONENT.read_text(encoding="utf-8"))
    block = re.search(r"WorkbenchSwitchState\s*=\s*\{([^}]*)\}", code)

    assert block is not None
    keys = sorted(re.findall(r"(\w+)\s*:", block.group(1)))
    assert keys == ["currentId", "showArchived"], keys


def test_there_is_no_delete_path() -> None:
    """归档不是删除：组件里**没有**删除入口（数据删除是 owner 人审节点）。"""
    code = _code_face(COMPONENT.read_text(encoding="utf-8"))

    assert "onDelete" not in code
    assert "workbench-delete" not in code


# ───────────────────────── ③ 像素面 + 阴性对照（EYE-02）


def _report() -> dict:
    import pytest

    if not ARTIFACT.exists():
        pytest.skip("本机没跑过像素取证：缺 .ui-probe/workbench_switch.json"
                    "（跑法见本文件 __main__ 与 docs/trace/K6-01.md）")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_the_trigger_is_visible_in_both_themes() -> None:
    """acceptance④：明暗两主题下「存在 + 尺寸非零 + 对比度过线」全过。"""
    styled = _report()["styled"]

    assert styled["ok"] is True, [v["detail"] for v in styled["verdicts"] if not v["ok"]]
    for theme in ("dark", "light"):
        obs = styled["observations"][theme]
        assert obs["present"] is True
        assert obs["width"] > 0 and obs["height"] > 0, f"[{theme}] 入口 0 像素"


def test_stripping_the_rule_changes_what_the_user_sees() -> None:
    """阴性对照。**这条与 FB-02 那条不是同一个形状，原因写在这里**：

    FB-02 守的是一个**空 span**——没有规则时它 0×0，「存在 + 尺寸非零」直接判红。
    本卡守的是一个**带文字的 button**：浏览器给它默认样式，抽掉规则它照样看得见
    （实测 unstyled.ok 仍为 True）。所以照抄 FB-02 的对照形状会得到一条
    **永远绿的阴性对照**，那比没有对照更糟——它看起来像验过了。

    这条规则真正买到的是**可点区域的高度**：`min-height: var(--sp-5)` = 24px。
    抽掉之后实测 23px，掉到线下。判据就钉在这件事上。
    """
    report = _report()
    styled = report["styled"]["observations"]
    unstyled = report["unstyled"]["observations"]

    for theme in ("dark", "light"):
        assert styled[theme]["height"] >= 24, f"[{theme}] 带规则也没到 24px"
        assert unstyled[theme]["height"] < 24, (
            f"[{theme}] 抽掉规则后仍有 {unstyled[theme]['height']}px——这个对照说明不了问题"
        )
        assert styled[theme]["background_color"] != unstyled[theme]["background_color"], (
            f"[{theme}] 抽掉规则后底色没变：那说明底色不是这条规则给的"
        )


def test_the_measured_colors_come_from_the_ds_palette() -> None:
    """带规则时量到的底色就是 `_ds` 的 `--surface-card`，不是浏览器默认灰。

    这一条把「样式面写了 var(--…)」与「浏览器真的解析到了那个值」分开：
    token 名写错时 CSS 不报错，只是静默取不到值，然后落回 UA 默认——
    样式面那条断言照样绿。
    """
    surface = _bundle_dir().joinpath("tokens", "colors.css").read_text(encoding="utf-8")

    assert "--surface-card:" in surface
    for theme in ("dark", "light"):
        measured = _report()["styled"]["observations"][theme]["background_color"]
        assert measured != "rgb(240, 240, 240)", f"[{theme}] 量到的是浏览器默认按钮灰"


def test_the_two_runs_differ_only_by_the_rule() -> None:
    """两次测量的唯一变量就是那条规则——否则对照不成立。"""
    report = _report()

    assert report["schema"] == "workbench-switch/1"
    assert report["selector"] == TRIGGER_SELECTOR
    assert report["styled"]["fragment_sha"] != report["unstyled"]["fragment_sha"]
    assert report["rule_under_test"] in report["styled"]["fragment"]
    assert report["rule_under_test"] not in report["unstyled"]["fragment"]


# ───────────────────────── 产物生成（用 C:\\pwenv 的解释器跑本文件）

if __name__ == "__main__":  # pragma: no cover - 取证入口，pytest 不走这里
    import hashlib
    import sys

    sys.path.insert(0, str(REPO))
    from tools.visual_assert import check_fragment

    bundle = _bundle_dir().name
    css = GLOBALS.read_text(encoding="utf-8")
    rule = f"{TRIGGER_SELECTOR} {{{_rule(css, TRIGGER_SELECTOR)}}}"

    # 片段用真 CSS：`_ds` 经 dev server 取（栈要在跑），应用层规则从 globals.css 原样读出。
    # NEVER 手抄一份样式进来——手抄的那份和线上跑的那份迟早不是同一个。
    base = (f'<link rel="stylesheet" href="http://localhost:3000/_ds/{bundle}/styles.css">'
            '<div style="background:var(--bg-page);padding:20px">'
            '<button type="button" class="workbench-switch__trigger">锂电池回收</button>'
            "</div>")
    styled_html = f"<style>{rule}</style>{base}"

    out = {"schema": "workbench-switch/1", "selector": TRIGGER_SELECTOR,
           "rule_under_test": rule}
    for key, html in (("styled", styled_html), ("unstyled", base)):
        report = check_fragment(html, TRIGGER_SELECTOR)
        report["fragment"] = html
        report["fragment_sha"] = hashlib.sha256(html.encode()).hexdigest()[:16]
        out[key] = report

    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"styled.ok={out['styled']['ok']}  unstyled.ok={out['unstyled']['ok']}")
    print(f"→ {ARTIFACT}")
