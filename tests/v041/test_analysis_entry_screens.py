"""CHAIN-04：发起分析与 combo 入口两屏（蓝本 P6/P3）——实仓此前没有。

## 改前的实况

两条端点第 4 批就装配了，**而没有任何界面能触发它们**：

```
POST /projects/{project_id}/analysis   ← 发起分析（P6）
POST /projects/combo                   ← combo 入口（P3）
```

`ComboEntryView` 组件建好了，全仓只有 `DemoFlow` 那个演示串屏在用；
发起分析那屏连组件都没有。

## 一处规格与实况对不上（立单，本卡按实况交付）

规格 `#2.3`：「空假设由服务端判 `EMPTY_HYPOTHESIS`，前端本地预检话术与之**逐字一致**」。
实测两条端点对同一件事的答复**不是同一句**：

```
POST /projects/combo 空 hypothesis → 400 {"code":"VALIDATION_FAILED",
                                          "message":"hypothesis required (non-empty str)"}
flint/api/graph_edges.py:71        → 422 EMPTY_HYPOTHESIS
```

前端要逐字一致就得存一句，而**存哪一句都会与另一条端点对不上**。
所以本卡的做法是：**前端一句拒绝话都不写**——提交键的禁用只做物理约束，
被拒时把服务端的 `message` 原样带回屏上。
单据 `docs/blocked/EMPTY-HYPOTHESIS-TWO-CODES.md`。

## 第 6 批 `FIX-10` 之后：两条端点统一了，而这两屏的做法**不变**

`FIX-10` 把映射收到一处（`flint/api/errors.py`），两条端点现在同码同句。
于是「存哪一句都会对不上」这个理由消失了——**但这两屏仍然一句都不写**，
换了个理由：**屏上显示的拒绝话恒由服务端说**。屏自己存一句的话，
后端改措辞时屏上还是旧的，而两句话都言之凿凿。

`web/lib/topicClient.ts` 是**另一回事**：它做的是本地预检（省一次注定被拒的往返），
用的那句话**从后端取**（`FIX-10` 的判据逐字比对）。
「用同一句」与「自己编一句」是两件事。
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
ANALYSIS_PAGE = WEB / "app" / "projects" / "[id]" / "analysis" / "page.tsx"
COMBO_PAGE = WEB / "app" / "combo" / "page.tsx"
CLIENT = WEB / "components" / "chain" / "chainClient.ts"
COMBO_VIEW = WEB / "components" / "views" / "ComboEntryView.tsx"
SHEET = REPO / "docs" / "blocked" / "EMPTY-HYPOTHESIS-TWO-CODES.md"
ZH = WEB / "messages" / "zh.json"
EN = WEB / "messages" / "en.json"
ARTIFACT = REPO / ".ui-probe" / "chain_entry_screens.json"

PWENV = Path(r"C:\pwenv\Scripts\python.exe")
ANALYSIS_URL = "http://localhost:3000/projects/proj-demo14bf9d94b0/analysis"
COMBO_URL = "http://localhost:3000/combo"


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


def _messages(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8"))


# ───────────────────────── 一、两屏在，各打各的真端点


def test_both_screens_exist() -> None:
    assert ANALYSIS_PAGE.exists(), "发起分析屏不在"
    assert COMBO_PAGE.exists(), "combo 入口屏不在"


def test_each_screen_posts_to_its_own_endpoint() -> None:
    code = _code_only(CLIENT)

    assert "/analysis`" in code, "没打 POST /projects/{id}/analysis"
    assert '"/projects/combo"' in code or "/projects/combo" in code
    # `CHAIN-UI-01-a` 加了第三条：成文（`POST /projects/{id}/report`，带 `analysis_job_id`）。
    assert "/report`" in code, "没打 POST /projects/{id}/report"
    assert code.count('method: "POST"') == 3, "写端点的条数变了——来这里对一遍是哪一条"


def test_the_analysis_body_matches_the_frozen_request_shape() -> None:
    """`AnalysisSubmitRequest` 的必填项是 `budget_cny`——少一个字段就是 422。"""
    code = _code_only(CLIENT)

    for field in ("keywords", "budget_cny", "locale", "topic_id"):
        assert field in code, f"请求体少了 {field}"


# ───────────────────────── 二、提交后进 Job 屏，NEVER 在本屏轮询


def test_submitting_goes_to_the_job_screen() -> None:
    code = _code_only(ANALYSIS_PAGE)

    assert "/jobs/" in code, "提交后没去 Job 进度屏"
    assert "job_id" in code


def test_this_screen_never_polls() -> None:
    """同一个作业有两处在看的话，两处的进度**永远差一拍**，用户不知道该信哪一个。"""
    code = _code_only(ANALYSIS_PAGE)

    for tell in ("setInterval", "setTimeout", "fetchJobSnapshot", "openJobStream"):
        assert tell not in code, f"发起分析屏里出现了 {tell}——它在自己看作业"


# ───────────────────────── 三、403 / 两种 404 各说各的（AUTH-03）


def test_the_three_kinds_of_refusal_are_told_apart() -> None:
    """403（没权限）· 带 `code` 的 404（这一条不存在）· 裸 404（能力没挂）是三件事。

    混成一句，用户会拿一个正确的 id 反复试，或者去要一个他本来就有的权限。
    """
    code = _code_only(CLIENT)

    assert 'payload["code"] === undefined' in code, "两种 404 没分开"
    assert "not_provided" in code and "failed" in code


def test_the_backend_message_is_carried_through_verbatim() -> None:
    """后端自己的说明原样带出来，NEVER 改写成一句通用的「参数不对」。

    FastAPI 的 422 把说明放在 `detail` 数组里——取不到那一条就等于把唯一的线索丢掉。
    """
    code = _code_only(CLIENT)

    assert 'first?.["msg"]' in code, "422 的 detail 数组没被读出来"
    assert 'payload["message"]' in code


# ───────────────────────── 四、前端一句拒绝话都不写


def test_the_front_end_writes_no_refusal_sentence_of_its_own() -> None:
    """这两屏**一句拒绝话都不写**，被拒时把服务端的 `message` 原样带回。

    理由在 `FIX-10` 之后换了一个（见本文件 docstring 末段），**结论没变**：
    屏自己存一句的话，后端改措辞时屏上还是旧的，而两句话都言之凿凿。

    注意与 `web/lib/topicClient.ts` 区分：那里的本地预检**用的是后端那一句**
    （`FIX-10` 判据逐字比对）。「用同一句」与「自己编一句」是两件事。
    """
    for path in (ANALYSIS_PAGE, COMBO_PAGE, CLIENT):
        code = _code_only(path)
        for tell in ("EMPTY_HYPOTHESIS", "hypothesis required", "假设不能为空"):
            assert tell not in code, f"{path.name} 里存了一句拒绝话术：{tell}"


def test_the_submit_button_only_guards_the_physical_precondition() -> None:
    """禁用只做「还不能提交」，**不解释为什么会被拒**——那句话恒由服务端说。"""
    code = _code_only(ANALYSIS_PAGE)

    assert "disabled={busy || !budgetOk}" in code
    # NEVER 在禁用旁边写一句自己的解释。
    assert "budgetOk ?" not in code


def test_the_two_codes_gap_was_closed() -> None:
    """这条判据**改过一次**，改因记在这里。

    改前它写的是「两码不一致的单必须还开着」。
    `FIX-10`（v0.4.1 第 6 批）把映射收到一处，两条端点现在同码同句，
    于是那条断言红了——**它红的是自己的前提过期，不是事情没做完**。

    现在判的是那件事真的做完了：映射模块在、单据关。
    """
    from flint.api.errors import origin_validation_error

    assert callable(origin_validation_error), "统一映射不在"
    state = SHEET.read_text(encoding="utf-8").splitlines()[2]
    assert state.startswith("**状态** closed"), f"映射统一了，单据却还开着：{state!r}"


# ───────────────────────── 五、复用与「不猜」


def test_the_combo_screen_reuses_the_existing_view() -> None:
    """`ComboEntryView` 已在盘上。另写一份的话，两处的选卡规则会各自漂移。"""
    code = _code_only(COMBO_PAGE)

    assert "ComboEntryView" in code
    assert "COMBO_MIN" not in code and "comboCountValid" not in code, (
        "combo 屏自己复刻了选卡下界——那条规则在 ComboEntryView 里"
    )
    assert "data-combo-card" not in code, "combo 屏自己画了卡片选择器"


def test_no_cluster_id_means_no_request() -> None:
    """猜一个簇去问，取回来的是**另一个热点的证据卡**，而用户会拿它们去建项。

    这与广场屏拒绝猜 `verdictJob`（`DEC-012`）是同一条。
    """
    code = _code_only(COMBO_PAGE)

    assert 'get("cluster")' in code
    # 改前这里钉的是字面量 `if (!found) return;`。`ENTRY-04` 让这一屏接多簇
    # （`?clusters=a,b,c`）之后守卫改成了 `if (wanted.length === 0) return;`——
    # **红的是那句字面量过期了，不是守卫没了**。
    #
    # 所以改判**这条纪律本身**：取数之前有一个提前 return，
    # 而它判的是「一个簇都没带」。钉字面量的话，下一次改写法还要再来一趟，
    # 而每来一趟都要重新判断「这次红是真的吗」。
    # 锚点取**取数那一句**（`Promise.all(`），不是 `fetchEvidenceCards`——
    # 后者第一次出现在 import 行上，按它切会把整个 effect 切掉，
    # 于是这条判据读到的是一段只有 import 的文本。
    guard = code.split("Promise.all(")[0]

    assert "return;" in guard, "取数之前没有任何提前 return——没带簇 id 也会发请求"
    assert ("wanted.length === 0" in guard or "!found" in guard), (
        "那个提前 return 判的不是「一个簇都没带」")


def test_a_failed_card_fetch_is_an_empty_table_not_invented_cards() -> None:
    code = _code_only(COMBO_PAGE)

    assert "setCards([])" in code, "取不到证据卡时没有走空表"


# ───────────────────────── 六、文案走 i18n


def test_the_new_copy_is_keyed_in_both_languages() -> None:
    zh, en = _messages(ZH), _messages(EN)

    for key in ("analysis.title", "analysis.submit", "combo.screen.title",
                "combo.need_cluster", "chain.not_provided"):
        assert key in zh, f"zh 缺 {key}"
        assert key in en, f"en 缺 {key}"
        assert zh[key] != en[key], f"{key} 中英同文——有一侧没翻"


def test_no_hardcoded_chinese_in_the_new_screens() -> None:
    for path in (ANALYSIS_PAGE, COMBO_PAGE, CLIENT):
        code = _code_only(path)
        for literal in re.findall(r'"([^"]*)"', code):
            assert not re.search(r"[一-鿿]", literal), (
                f"{path.name} 里有裸中文：{literal!r}"
            )


# ───────────────────────── 七、运行时：两屏真的占了像素


_RUNNER = r"""
import json, sys
from playwright.sync_api import sync_playwright

out, analysis_url, combo_url = sys.argv[1], sys.argv[2], sys.argv[3]
got = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

    page.goto(analysis_url, wait_until="networkidle", timeout=60000)
    page.wait_for_selector("[data-testid='analysis-submit']", timeout=30000)
    def box(sel):
        el = page.query_selector(sel)
        r = el.bounding_box() if el else None
        return {"width": r["width"], "height": r["height"]} if r else None
    got["analysis"] = {
        "keywords": box("[data-testid='analysis-keywords']"),
        "budget": box("[data-testid='analysis-budget']"),
        "submit": box("[data-testid='analysis-submit']"),
        "submitDisabled": page.query_selector(
            "[data-testid='analysis-submit']").is_disabled(),
    }
    # 填上预算：提交键必须从「点不动」变成「能点」。
    page.fill("[data-testid='analysis-budget']", "12")
    got["analysis"]["submitEnabledAfterBudget"] = not page.query_selector(
        "[data-testid='analysis-submit']").is_disabled()
    page.screenshot(path=".ui-probe/chain-analysis.png")

    page.goto(combo_url, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(800)
    hint = page.query_selector("[data-combo-no-cluster]")
    got["combo"] = {
        "noClusterHint": hint.inner_text().strip() if hint else "",
        "cards": page.query_selector("[data-combo-cards]") is not None,
    }
    page.screenshot(path=".ui-probe/chain-combo.png")
    got["console_errors"] = errs
    b.close()
open(out, "w", encoding="utf-8").write(
    json.dumps({"schema": "chain-entry/1", **got}, ensure_ascii=False, indent=1))
"""


def _artifact() -> dict[str, object]:
    if ARTIFACT.exists():
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if not PWENV.exists():
        pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外，NEVER 进项目依赖）")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "chain_entry_runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        done = subprocess.run(
            [str(PWENV), str(runner), str(ARTIFACT), ANALYSIS_URL, COMBO_URL],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO, check=False,
        )
    if done.returncode != 0:
        pytest.skip(f"前端没起或探针跑不动：{done.stderr[-500:]}")
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_the_analysis_form_occupies_pixels() -> None:
    """源码层判得出「有没有」，判不出「是不是 0 像素」（`F-09` 就是那个形状）。"""
    form = _artifact()["analysis"]

    for name in ("keywords", "budget", "submit"):
        box = form[name]
        assert box is not None, f"{name} 不在屏上"
        assert box["width"] > 20 and box["height"] > 10, f"{name} 几乎没有面积：{box}"


def test_the_submit_button_unlocks_only_after_the_required_field() -> None:
    """预算是端点的必填项。填之前点不动、填之后能点——**这是物理约束，不是话术**。"""
    form = _artifact()["analysis"]

    assert form["submitDisabled"] is True, "预算还没填就能提交"
    assert form["submitEnabledAfterBudget"] is True, "填了预算仍然点不动"


def test_the_combo_screen_says_how_to_get_here_without_a_cluster() -> None:
    """没带簇 id 是**用法**问题，不是故障：说清该怎么进来，且一张卡都不编。"""
    combo = _artifact()["combo"]

    assert combo["noClusterHint"], "没带簇 id 时屏上什么都没说"
    assert combo["cards"] is False, "没带簇 id 却画出了证据卡"


def test_both_screens_are_clean() -> None:
    assert _artifact()["console_errors"] == [], _artifact()["console_errors"]
