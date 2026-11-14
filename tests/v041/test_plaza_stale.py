"""SLOT-02：卡面陈旧标记——**热点簇身上没有一样东西是 Revalidator 能判新旧的**。

## 这张卡为什么停在这里

卡面 acceptance①要「复用 Revalidator 统一 stale，NEVER 新写一套比对」。
适配器 `flint/analysis/stale_adapter.py#analysis_stale` 在，它要三样输入：
**项目 id · 账本前后版本 · 这份东西引用过哪些事实**。

`clusters` 表一样都没有——一个热点簇不是一份分析，它不引用事实，
它**是**事实的来源之一。要拿适配器去判它，就得给这三样各编一个值，
而那正是 acceptance①禁止的「新写一套比对」，只是换了个地方写。

完整取证与给 owner 的四选一在
`docs/blocked/SLOT-02-A-CLUSTER-HAS-NOTHING-THE-REVALIDATOR-CAN-JUDGE.md`。

## 那本文件判什么

blocked 不等于什么都没做。这一槽**在组件层**是可验的，acceptance②③ 本文件验完；
数据面维持隐藏，并把两条捷径钉死：

1. **三态互不相同**：没判过 / 判过且新鲜 / 判过且陈旧，屏上三个样子；
2. **NEVER 按时间戳推断**——`clusters.last_active` 就在手边，拿它跟今天一比
   就能算出「多少天没动了」。规格 `#2.15`、冻结件 `Favorite` 的 docstring、
   `flint/fav/stale.py` 三处白纸黑字禁止这一条；
3. **NEVER 在广场请求里触发一次重核**（acceptance④）——重核是会落库的写，
   挂在列表页上就是每刷一次写一次库；
4. **单据还开着**：问题没解决而单子被关掉时，这里当场红。
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
VIEWS = REPO / "flint" / "api" / "views.py"
MAPPER = WEB / "components" / "plaza" / "clusterToCard.ts"
CARD = WEB / "components" / "hotspot-card" / "HotspotCard.tsx"
PLAZA_DIR = WEB / "components" / "plaza"
PLAZA_PAGE = WEB / "app" / "plaza" / "page.tsx"
SHEET = REPO / "docs" / "blocked" / "SLOT-02-A-CLUSTER-HAS-NOTHING-THE-REVALIDATOR-CAN-JUDGE.md"

PWENV = Path(r"C:\pwenv\Scripts\python.exe")
ARTIFACT = REPO / ".ui-probe" / "plaza_stale_states.json"


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


def _plaza_chain() -> dict[str, str]:
    """广场那一条链的**代码面**：端点的 plaza 段 + 搬运层 + 呈现层 + 屏。"""
    views = VIEWS.read_text(encoding="utf-8")
    plaza_section = views[views.index('@app.get("/plaza/hot")'):views.index(
        '@app.get("/clusters/{cluster_id}/evidence-cards")')]
    chain = {"views.py::plaza": plaza_section, "page.tsx": _code_only(PLAZA_PAGE)}
    for path in PLAZA_DIR.rglob("*.ts*"):
        if not path.name.endswith(".test.tsx"):
            chain[path.name] = _code_only(path)
    return chain


# ───────────────────────── 一、数据面确实没有（本单的根据）


def test_the_adapter_needs_three_things_a_cluster_does_not_have() -> None:
    """适配器的签名就是本单的第一条证据。**判签名而不是判文字**：

    有人把 docstring 改一句不会让这条红，把签名改一个参数才会——
    而后者正是「这张卡能不能做」真正取决于的东西。
    """
    import inspect

    from flint.analysis.stale_adapter import analysis_stale

    params = set(inspect.signature(analysis_stale).parameters)

    assert {"project_id", "analysed_at_version", "cited_fact_ids"} <= params, (
        f"适配器签名变了，本单的前提要重查：{sorted(params)}"
    )


def test_the_plaza_endpoint_does_not_pretend_to_have_it() -> None:
    """广场那一段 NEVER 回一个 `stale` 键。

    回一个恒 `false` 的 `stale` 是最像「做完了」的做法——
    屏上永远不挂标记，看起来一切正常，而它说的是「已经查过，是新鲜的」。
    我们根本没能力知道这件事。
    """
    plaza_section = _plaza_chain()["views.py::plaza"]

    assert '"stale"' not in plaza_section, "广场端点回了一个我们判不出来的 stale"


def test_the_mapper_leaves_the_slot_unset() -> None:
    """搬运层**不传** `stale` —— `undefined` 就是「没判过」。

    传 `null` 也不行：`null` 在本仓的用法是「明确地没有值」，
    而这里的真相是**没人判过**，两者对下游的意思不同。
    """
    code = _code_only(MAPPER)

    assert not re.search(r"\bstale\s*:", code), "搬运层给这一槽赋了值"


# ───────────────────────── 二、两条捷径钉死


def test_nobody_infers_staleness_from_a_timestamp() -> None:
    """`clusters.last_active` 就在手边，拿它跟今天一比就能算出「多少天没动了」。

    三处禁止这一条：规格 `#2.15` · 冻结件 `Favorite` 的 docstring ·
    `flint/fav/stale.py`。理由是最后那一处写透的：
    **按时间戳推断看起来总是对的**——三个月前的东西「显然」旧了，
    可事实一个字没变时那个标记只让用户白重跑一次；
    而昨天的东西也可能因一次事实移除而彻底失效。
    """
    for name, code in _plaza_chain().items():
        assert "last_active" not in code, f"{name} 摸了 last_active——这是那条时间戳捷径"


def test_the_plaza_never_triggers_a_recheck(monkeypatch: pytest.MonkeyPatch) -> None:
    """acceptance④：本卡只读不写。

    重核是**会落库的写**（`flint/api/favorites.py` 的原话：
    「`evaluate_snapshot_stale` 会落库，所以它挂在 POST 上，不挂 GET——
    挂 GET 就是一个藏起来的写，而列表页每刷一次就写一次库」）。
    """
    for name, code in _plaza_chain().items():
        for endpoint in ("/staleness", "refresh-snapshot", "stale-notices"):
            assert endpoint not in code, f"{name} 在广场链上打了 {endpoint}"


def test_the_forbidden_shortcut_would_really_be_caught() -> None:
    """**判据自己的阴性对照**：把那条捷径写进链里，上面那条必须红。

    没有这一条的话，`last_active` 哪天改了名（或搬进另一个文件），
    上面那条会静静地变成一句永真的断言——**而它看起来仍然是绿的**。
    """
    tainted = dict(_plaza_chain())
    tainted["page.tsx"] += "\nconst stale = daysSince(cluster.last_active) > 7;\n"

    caught = [name for name, code in tainted.items() if "last_active" in code]

    assert caught == ["page.tsx"], f"注入的捷径没被抓住：{caught}"


# ───────────────────────── 三、组件层三态互不相同（acceptance②③）

_RUNNER = """
import json, sys
from playwright.sync_api import sync_playwright
url, out = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900})
    page.goto(url, wait_until="networkidle", timeout=60000)
    page.wait_for_selector('[data-testid="hotspot-card"]', timeout=30000)
    got = page.evaluate('''() => {
        const cards = [...document.querySelectorAll('[data-testid="hotspot-card"]')];
        return {
          total: cards.length,
          withStaleMark: cards.filter(
              c => c.querySelector('[data-testid="hotspot-stale"]')).length,
        };
    }''')
    b.close()
open(out, "w", encoding="utf-8").write(
    json.dumps({"schema": "plaza-stale/1", "url": url, **got},
               ensure_ascii=False, indent=1))
"""


def test_the_card_keeps_the_three_states_apart() -> None:
    """acceptance②：三态在**卡面组件**上分明。

    三态的行为判据在 `web/components/hotspot-card/HotspotCard.test.tsx`（vitest，
    三种分别构造：`true` 挂标记 / `false` 不挂 / 未传不挂）。
    这里只钉住最容易被「简化」掉的那一点：**挂标记的条件恒是 `=== true`**。

    写成 `{stale && …}` 的话，`false` 与 `undefined` 仍然都不挂——看起来一样，
    但下一个人把它改成 `{stale !== false && …}` 时不会有任何判据响，
    而那一版会给**没判过**的簇挂上陈旧标记。
    """
    code = _code_only(CARD)

    assert "stale === true ? (" in code, "陈旧标记的条件不再是严格的 === true"


def test_no_plaza_card_shows_a_stale_mark_today() -> None:
    """真栈：今天广场上**一张卡都不该有**这个标记。

    数据面不存在而屏上出现了标记，那只可能是有人编了一个值。
    """
    if ARTIFACT.exists():
        art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    else:
        if not PWENV.exists():
            pytest.skip(f"本机没有 {PWENV}（playwright 恒在项目外）")
        ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            runner = Path(tmp) / "plaza_stale_runner.py"
            runner.write_text(_RUNNER, encoding="utf-8")
            done = subprocess.run(
                [str(PWENV), str(runner), "http://localhost:3000/plaza", str(ARTIFACT)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=REPO, check=False,
            )
        if done.returncode != 0:
            pytest.skip(f"前端没起或探针跑不动：{done.stderr[-500:]}")
        art = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    assert art["total"] > 0, "屏上一张卡都没有，这条判据在空转"
    assert art["withStaleMark"] == 0, (
        f"{art['withStaleMark']} 张卡挂了陈旧标记，而后端判不出这件事"
    )


# ───────────────────────── 四、单据已由 owner 裁决关掉（DEC-039 / STALE-01）


def test_the_sheet_is_closed_by_a_ruling_and_keeps_the_options() -> None:
    """**改前这条判的是「单据仍然 open」**——owner 2026-08-08 挑了甲之后它红了。

    **红的是自己描述的那个状态过去了，不是有人偷偷关单**：
    `DEC-039` 落进 `DECISIONS-v04.md`，`STALE-01` 执行，单据随之 closed。

    判据的**意图**一字未改，只是换了要守的那件事：
    改前守「别在没答复时把单子关掉」（悄悄关单 = 本仓最贵的一种丢失——
    卡在 DAG 上不再挡任何人，于是它从此不出现在任何视野里）；
    改后守「关单必须留下答复」——关了却不说 owner 挑的是哪一项，
    与悄悄关掉的**后果完全一样**：下一个人还是不知道当初定了什么。

    四个选项**仍然要在单子里**：答案是「甲」，而「甲相对乙丙丁好在哪」
    是这次裁决唯一的推理过程，删掉选项等于把推理擦掉只留结论。
    """
    text = SHEET.read_text(encoding="utf-8")
    state = next((ln for ln in text.splitlines()[:6] if ln.startswith("**状态**")), "")

    assert state.startswith("**状态** closed"), f"单据状态不对：{state!r}"
    assert "DEC-039" in state or "DEC-039" in text, "关单没写依据哪条裁决"
    assert "STALE-01" in text, "关单没写是被哪张卡执行掉的"
    for option in ("甲", "乙", "丙", "丁"):
        assert f"| **{option}** |" in text or f"| {option} |" in text, (
            f"选项 {option} 不在单子里了——推理过程被擦掉只剩结论"
        )
