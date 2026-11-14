"""CHAIN-05：受众分叉与干预页两屏（蓝本 P11/P10）——六屏里最后两屏。

## 改前的实况

四条干预动作的客户端与 `BlockInterventionPanel` **都建好了**
（`web/lib/interventionClient.ts` 的 lock / regenerate / dispute / inject），
`POST /projects/{id}/proposal` 也早就装配了——
而 `web/app/` 下**没有任何屏在用它们**（grep 零命中）。

## 本卡守的两条硬约束

1. **`CLAUDE.md#S2-5`**：受保护 block（`locked ∨ author=="user" ∨ user_modified`）
   NEVER 被 regenerate 改写。这条判断**只有一处实现**（`lib/types.ts#isProtected`，
   `availableBlockInterventions` 据它给出可用动作）。屏里再判一次就是两份规则，
   而分叉的那天用户会看到一个能点的重生成键，点下去改写了他自己写的段落。
2. **受众没有默认值**（`flint/compose/audience.py` 的原话
   `audience is mandatory with no default`）。给一个默认值等于替用户做了这个决定，
   而两条路产出的东西完全不同：五套人类模板是给人读的散文，
   `vibe_pack` 是喂给执行者的材料。

阴性对照（三种受保护各说各的话）在
`web/components/chain/protectedBlocks.test.tsx`。
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
INTERVENTIONS = WEB / "app" / "deliverables" / "[id]" / "interventions" / "page.tsx"
PROPOSAL = WEB / "app" / "projects" / "[id]" / "proposal" / "page.tsx"
CONTROLS = WEB / "components" / "chain" / "protectedBlocks.test.tsx"
TYPES = WEB / "lib" / "types.ts"
AUDIENCE = REPO / "flint" / "compose" / "audience.py"
ZH = WEB / "messages" / "zh.json"
EN = WEB / "messages" / "en.json"
ARTIFACT = REPO / ".ui-probe" / "chain_fork_screens.json"

PWENV = Path(r"C:\pwenv\Scripts\python.exe")
INTERVENTIONS_URL = (
    "http://localhost:3000/deliverables/del-demo-fixture-report/interventions")
PROPOSAL_URL = "http://localhost:3000/projects/proj-demo14bf9d94b0/proposal"


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


def _messages(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8"))


# ───────────────────────── 一、两屏在


def test_both_screens_exist() -> None:
    assert INTERVENTIONS.exists(), "干预页不在"
    assert PROPOSAL.exists(), "受众分叉屏不在"


# ───────────────────────── 二、S2-5：受保护判断只有一处


def test_the_screen_never_reimplements_the_protected_rule() -> None:
    """判两次的话，两处规则会在某天分叉——而分叉的那天用户会看到一个能点的重生成键。"""
    code = _code_only(INTERVENTIONS)

    assert "isProtected" in code, "屏上没走那条唯一的判断"
    # NEVER 把三条件自己再写一遍。
    assert not re.search(r"locked\s*\|\|\s*.*author", code), "屏里复刻了受保护的三条件"
    assert "user_modified ||" not in code


def test_the_protected_rule_is_still_the_three_conditions() -> None:
    """`S2-5` 的三条件逐字在唯一那处。少一条就是放行了一类受保护 block。"""
    code = TYPES.read_text(encoding="utf-8")
    fn = code[code.index("export function isProtected"):]
    fn = fn[: fn.index("}")]

    for condition in ("locked", 'author === "user"', "user_modified"):
        assert condition in fn, f"isProtected 少了 {condition}"


def test_a_protected_block_gets_no_action_panel() -> None:
    """受保护时**不渲染动作面板**——渲染了再逐个禁用，等于给了四个能看见的诱饵。"""
    code = _code_only(INTERVENTIONS)
    branch = code[code.index("isProtected(block) ?"):]
    branch = branch[: branch.index(") : (")]

    assert "BlockInterventionPanel" not in branch


def test_each_kind_of_protection_says_its_own_thing() -> None:
    """屏上**明说拒绝原因**（卡面 acceptance②）：三种各说各的话。"""
    code = _code_only(INTERVENTIONS)
    zh = _messages(ZH)

    for key in ("intervention.protected.locked", "intervention.protected.authored",
                "intervention.protected.modified"):
        assert key in code, f"屏上没有 {key}"
    said = {zh[f"intervention.protected.{k}"] for k in ("locked", "authored", "modified")}
    assert len(said) == 3, f"三种受保护共用了话术：{said}"
    # 判别位也要分得开——共用一个的话，取证里三者长得一模一样。
    assert 'data-protected-reason=' in code


def test_the_negative_controls_exist() -> None:
    controls = CONTROLS.read_text(encoding="utf-8")

    for kind in ("locked", "authored", "modified"):
        assert kind in controls, f"vitest 里没有 {kind} 的对照"
    assert "availableBlockInterventions" in controls


# ───────────────────────── 三、干预动作全走既有端点，NEVER 前端改 block 树


def test_the_screen_never_touches_the_block_tree_itself() -> None:
    """四个动作全走 `interventions` 族端点。前端自己改的话，库里那份不会跟着变。"""
    code = _code_only(INTERVENTIONS)

    assert "BlockInterventionPanel" in code
    for tell in ("setBlocks", "blocks.splice", "block.content =", "revision +"):
        assert tell not in code, f"屏里自己改了 block 树：{tell}"


def test_the_actions_come_from_the_single_action_table() -> None:
    code = _code_only(INTERVENTIONS)

    assert "availableBlockInterventions" in code
    # 屏里 NEVER 自己列四个动作名——列了就是第二份动作表。
    assert '"regenerate"' not in code and '"dispute"' not in code


# ───────────────────────── 四、受众没有默认值 + ai 锁 vibe_pack


def test_audience_has_no_default_on_screen() -> None:
    """后端原话：`audience is mandatory with no default`。

    给一个默认值等于替用户做了这个决定，而两条路产出的东西完全不同。
    """
    backend = AUDIENCE.read_text(encoding="utf-8")
    assert "mandatory with no default" in backend, "后端那句话变了，来这里同步"

    code = _code_only(PROPOSAL)
    assert "useState<Audience | null>(null)" in code, "受众有了默认值"
    assert "audience === null ||" in code, "受众没选时提交键仍能点"


def test_the_five_human_templates_mirror_the_backend_list() -> None:
    """前端那份是**镜像**。两边逐字相等，否则屏上会出现一个后端不认的模板。"""
    # 两边都**只取那个字面量本身**（后端的 `{...}`、前端的 `[...]`）。
    # 按固定字符数截一段的话，会把邻近的 `AI_TEMPLATE`、`Audience` 联合都刮进来
    # ——那种「多了三个」的红说的是判据切歪了，不是清单不一致。
    backend = AUDIENCE.read_text(encoding="utf-8")
    tail = backend[backend.index("HUMAN_TEMPLATES"):]
    listed = set(re.findall(r'"(\w+)"', tail[tail.index("{"): tail.index("}") + 1]))

    code = _code_only(PROPOSAL)
    tail = code[code.index("HUMAN_TEMPLATES ="):]
    mirrored = set(re.findall(r'"(\w+)"', tail[tail.index("["): tail.index("]") + 1]))

    assert mirrored == listed, f"前端 {sorted(mirrored)} vs 后端 {sorted(listed)}"
    assert len(listed) == 5, f"「五套人类模板」实际是 {len(listed)} 套：{sorted(listed)}"


def test_the_ai_path_never_sends_a_template_id() -> None:
    """`ai_executor` 的模板由**服务端**锁死。

    前端替它填上去的话，哪天后端换了名字，这里会开始发一个被拒的值。
    """
    code = _code_only(PROPOSAL)

    assert 'audience === "ai_executor" ? null : templateId' in code


def test_the_ai_path_explains_instead_of_greying_out_five_options() -> None:
    """灰掉的五个选项仍然在屏上，用户会以为「再等等就能选」。"""
    code = _code_only(PROPOSAL)

    assert "data-template-locked" in code
    assert "proposal.template.locked" in code


# ───────────────────────── 五、成功与失败分开呈现


def test_success_and_failure_are_not_merged_into_one_sentence() -> None:
    """卡面 acceptance④：四个动作各自的成功与失败态分开，NEVER 合并成「操作完成」。"""
    code = _code_only(PROPOSAL)

    assert "data-outcome-kind={outcome.kind}" in code
    assert "chain.submitted" in code and "chain.failed" in code
    # 后端自己的说明原样带出来。
    assert 'first?.["msg"]' in code


def test_the_new_copy_is_keyed_in_both_languages() -> None:
    zh, en = _messages(ZH), _messages(EN)

    for key in ("intervention.title", "proposal.title", "proposal.audience.label",
                "proposal.template.locked", "intervention.protected.locked"):
        assert key in zh, f"zh 缺 {key}"
        assert key in en, f"en 缺 {key}"
        assert zh[key] != en[key], f"{key} 中英同文——有一侧没翻"


def test_no_hardcoded_chinese_in_the_new_screens() -> None:
    for path in (INTERVENTIONS, PROPOSAL):
        code = _code_only(path)
        for literal in re.findall(r'"([^"]*)"', code):
            assert not re.search(r"[一-鿿]", literal), (
                f"{path.parent.name} 里有裸中文：{literal!r}"
            )


# ───────────────────────── 六、运行时


_RUNNER = r"""
import json, sys
from playwright.sync_api import sync_playwright

out, interventions_url, proposal_url = sys.argv[1], sys.argv[2], sys.argv[3]
got = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

    page.goto(interventions_url, wait_until="networkidle", timeout=60000)
    page.wait_for_selector("[data-intervention-list]", timeout=30000)
    got["interventions"] = page.evaluate(
        '''() => {
            const rows = [...document.querySelectorAll("[data-block-id]")];
            const guarded = rows.filter(r => r.dataset.protected === "true");
            return {
              rows: rows.length,
              protectedRows: guarded.length,
              // 受保护的行里**一个动作键都不许有**。
              actionButtonsInProtectedRows: guarded.reduce(
                  (n, r) => n + r.querySelectorAll("button").length, 0),
              reasons: [...new Set(guarded.map(
                  r => r.querySelector("[data-protected-reason]")
                       ?.dataset.protectedReason))].filter(Boolean),
            };
        }''')
    page.screenshot(path=".ui-probe/chain-interventions.png")

    page.goto(proposal_url, wait_until="networkidle", timeout=60000)
    page.wait_for_selector("[data-proposal-fork]", timeout=30000)
    def submit_disabled():
        return page.query_selector("[data-testid='proposal-submit']").is_disabled()
    got["proposal"] = {"disabledAtStart": submit_disabled()}
    page.check("[data-audience='ai_executor']")
    got["proposal"]["templateLockedShown"] = page.query_selector(
        "[data-template-locked]") is not None
    got["proposal"]["templateSelectHidden"] = page.query_selector(
        "[data-testid='proposal-template']") is None
    page.fill("[data-testid='proposal-report']", "rep-1")
    got["proposal"]["enabledAfterChoice"] = not submit_disabled()
    page.check("[data-audience='human_reader']")
    got["proposal"]["templateSelectBackForHuman"] = page.query_selector(
        "[data-testid='proposal-template']") is not None
    page.screenshot(path=".ui-probe/chain-proposal.png")
    got["console_errors"] = errs
    b.close()
open(out, "w", encoding="utf-8").write(
    json.dumps({"schema": "chain-fork/1", **got}, ensure_ascii=False, indent=1))
"""


def _artifact() -> dict[str, object]:
    if ARTIFACT.exists():
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外，NEVER 进项目依赖）")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "chain_fork_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(PWENV), str(runner), str(ARTIFACT), INTERVENTIONS_URL, PROPOSAL_URL],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False,
        )
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动：{done.stderr[-500:]}")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_a_protected_block_shows_no_action_button_on_the_real_screen() -> None:
    """`S2-5` 在真浏览器里也成立：受保护的行里**一个动作键都没有**。"""
    rows = _artifact()["interventions"]

    assert rows["rows"] > 0, "干预页一块都没渲染"
    assert rows["protectedRows"] > 0, "demo 交付物里没有受保护的块，这条对照不成立"
    assert rows["actionButtonsInProtectedRows"] == 0, (
        f"受保护的行里出现了 {rows['actionButtonsInProtectedRows']} 个动作键"
    )
    assert rows["reasons"], "受保护却没说是哪一种"


def test_the_audience_must_be_picked_before_submitting() -> None:
    """受众没有默认值——**没选之前点不动**是这条规则在屏上的形状。"""
    fork = _artifact()["proposal"]

    assert fork["disabledAtStart"] is True, "还没选受众就能提交"
    assert fork["enabledAfterChoice"] is True, "选了受众填了报告 id 仍然点不动"


def test_the_ai_path_hides_the_template_picker_and_says_why() -> None:
    fork = _artifact()["proposal"]

    assert fork["templateLockedShown"] is True, "没说清模板被服务端锁死"
    assert fork["templateSelectHidden"] is True, "给执行者那条路还留着模板选择器"
    assert fork["templateSelectBackForHuman"] is True, "切回给人读时选择器没回来"


def test_both_screens_are_clean() -> None:
    assert _artifact()["console_errors"] == [], _artifact()["console_errors"]
