"""K2-01：抓取合规状态**照实记录但不阻断**（owner 2026-08-04 裁决：非商业用途先取数）。

## 这张卡改的是什么

K2 一直是未决项（`WORKORDER-v04.md#7` 的 K2 行：「owner/法务出各国 robots 与 ToS
合规结论」）。未决期间全仓的做法是**一律 `unknown`**，而 `unknown` 在 REGION-07 的门里
不放行抓取——于是九区一条源也抓不了。

owner 2026-08-04 裁决：**非商业用途下先取数**，合规状态**记录但不阻断**。

这条裁决拆成两件互不替代的事：

1. **照实记录**（acceptance①）：robots.txt 能取到就记**实测值**，取不到就记
   `unreachable`。`unknown` 从此只许出现在「真的还没测」的位置——
   **一律 unknown 是蒙混，不是谦虚**；
2. **不阻断**（acceptance②）：`restricted` 的源照抓，但把 `legal_status` 打在数据上，
   一路带到产物。

## 阻断能力**没有被删**（acceptance④）

`flint/region/fetch_gate.py` 一个字没动。变的是**上层策略**：
`legal_policy.py` 里的 `mode` 现为 `record_only`；改成 `block` 就回到原样——
本文件有一组断言专门盯这件事（`test_flipping_the_switch_back_blocks_again`）。

**「删掉门」与「把门开着」是两件事**：前者不可逆，后者是一个开关。
上线前要补的手续留在 `docs/blocked/K2-COMPLIANCE-BEFORE-LAUNCH.md`（acceptance③）。
"""
from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path

import pytest

from flint.region.legal_policy import (
    BLOCK,
    OWNER_DECISION,
    RECORD_ONLY,
    LegalDecision,
    admits,
    enforce_fetch_policy,
    legal_status_annotations,
)
from flint.region.legal_probe import (
    MEASURED_STATUS,
    MeasuredStatus,
    derive_fetch_legal_status,
    load_measured_status,
    robots_verdict,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DAY = date(2026, 8, 4)
BLOCKED_DOC = REPO_ROOT / "docs" / "blocked" / "K2-COMPLIANCE-BEFORE-LAUNCH.md"
# COMP-01（owner 2026-08-04 裁决：手续单独立档）把逐源清单搬到了这里，
# 问题单只留指针。本文件的判据跟着搬，**强度只增不减**：既要清单里逐源点名，
# 也要问题单确实指得过来（见 test_the_paperwork_names_every_source_that_needs_it）。
LAUNCH_CHECKLIST = REPO_ROOT / "docs" / "上线前合规手续清单.md"


class _Store:
    def __init__(self) -> None:
        self.notes: list[object] = []

    def add(self, note: object) -> None:
        self.notes.append(note)


# ───────────────────────── 一、照实记录（acceptance①）


def test_the_measured_status_file_is_on_disk() -> None:
    assert MEASURED_STATUS == REPO_ROOT / "assets" / "source_legal_status.yaml"
    assert MEASURED_STATUS.exists(), "实测结果不在盘上——那就还是「一律 unknown」"


def test_every_measured_source_carries_evidence_and_a_probe_date() -> None:
    """实测值要能被复核：**测的是哪个 URL、测到了什么、什么时候测的**。

    只写一个结论（`allowed`）而不留证据，与凭印象填没有区别——
    下一个人无从判断它是测出来的还是猜出来的。
    """
    for entry in load_measured_status().values():
        assert entry.robots_url.startswith("http"), f"{entry.source_id} 没记测的是哪个 URL"
        assert entry.evidence.strip(), f"{entry.source_id} 没留证据"
        assert isinstance(entry.probed_on, date), f"{entry.source_id} 没记什么时候测的"


def test_every_state_is_one_of_the_three_real_outcomes() -> None:
    """三种实测结果：放行 / 不放行 / **取不到**。取不到是一条结论，不是缺测。"""
    states = {e.state for e in load_measured_status().values()}

    assert states <= {"allowed", "disallowed", "unreachable"}, f"越界的实测态：{states}"


def test_the_unreachable_ones_say_what_went_wrong() -> None:
    """`unreachable` 的证据位要写**为什么取不到**（超时？403？域名不解析？）。

    不写的话，「取不到」与「没去测」在盘上长得一模一样。
    """
    for entry in load_measured_status().values():
        if entry.state != "unreachable":
            continue
        assert len(entry.evidence) >= 10, f"{entry.source_id} 说取不到，却没说为什么"


def test_not_everything_is_unknown_anymore() -> None:
    """acceptance①的正面断言：**至少有一个源测出了实际状态**。

    这是本卡的反向断言位——全表退回 `unknown` 时它会红。
    「一律 unknown」正是这张卡要终结的做法。
    """
    measured = load_measured_status()

    assert measured, "一条实测记录都没有"
    derived = {derive_fetch_legal_status(e) for e in measured.values()}
    assert derived != {"unknown"}, "全表还是 unknown——等于没测"


def test_unreachable_derives_unknown_and_nothing_else_does() -> None:
    """映射只有一条路：**取不到 → `unknown`**。

    反过来说：测到了就 NEVER 记 `unknown`——那是把实测结果扔掉。
    """
    for entry in load_measured_status().values():
        derived = derive_fetch_legal_status(entry)
        if entry.state == "unreachable":
            assert derived == "unknown"
        else:
            assert derived != "unknown", f"{entry.source_id} 测到了 {entry.state} 却记成 unknown"


def test_disallowed_derives_restricted() -> None:
    """robots 明写不许 → `restricted`。**这条不因为「不阻断」而改判**：

    不阻断的是**动作**，不是**结论**。把 `disallowed` 记成 `allowed` 才是蒙混。
    """
    probe = MeasuredStatus(
        source_id="x", robots_url="https://example.test/robots.txt", state="disallowed",
        evidence="Disallow: /", probed_on=DAY, tos_url=None,
    )

    assert derive_fetch_legal_status(probe) == "restricted"


# ───────────────────────── 二、robots 判读是纯函数（零网络）


@pytest.mark.parametrize("robots,path,expected", [
    ("User-agent: *\nDisallow: /", "/api/x", "disallowed"),
    ("User-agent: *\nDisallow: /private\n", "/api/x", "allowed"),
    ("User-agent: *\nDisallow: /private\n", "/private/x", "disallowed"),
    ("User-agent: *\nAllow: /\n", "/api/x", "allowed"),
    ("", "/api/x", "allowed"),
])
def test_robots_verdict_reads_the_file_not_the_vibe(
    robots: str, path: str, expected: str,
) -> None:
    """判读**只看 robots 文本**：给什么文本出什么结论，可逐条复核。"""
    verdict, _evidence = robots_verdict(robots, path=path)

    assert verdict == expected


def test_an_empty_disallow_line_means_everything_is_allowed() -> None:
    """`Disallow:` 后面留空 = 全放行（robots 协议原义）。

    照字面判成「不许抓 ''」会把每条路径都判红——而 `"" in "/任何路径"` 恒为真。
    """
    verdict, _ = robots_verdict("User-agent: *\nDisallow:\n", path="/api/x")

    assert verdict == "allowed"


@pytest.mark.parametrize("path,expected", [("/", "allowed"), ("/x", "disallowed")])
def test_the_dollar_anchor_only_matches_that_exact_path(path: str, expected: str) -> None:
    """`Allow: /$` 只匹配根路径本身（RFC 9309 §2.2.3 的行尾锚）。

    照前缀判的话 `/$` 会命中每一条路径，把整站都放行——**判宽比判严更危险**：
    一个本该 restricted 的源会被记成 allowed，而这张表要拿去做上线前的合规清单。
    实测撞上过：`openapi.naver.com` 的 robots 就是 `Allow: /$` + `Disallow: /`。
    """
    verdict, _ = robots_verdict("User-agent: *\nAllow: /$\nDisallow: /\n", path=path)

    assert verdict == expected


@pytest.mark.parametrize("path,expected", [
    ("/api/v1/x.json", "disallowed"), ("/api/v1/x.html", "allowed"),
])
def test_the_star_wildcard_matches_any_run(path: str, expected: str) -> None:
    """`Disallow: /api/*.json` 里的 `*` 是任意串，不是字面星号。"""
    verdict, _ = robots_verdict(
        "User-agent: *\nDisallow: /api/*.json\n", path=path)

    assert verdict == expected


def test_a_longer_rule_beats_a_shorter_one() -> None:
    """命中多条时最长的赢（RFC 9309 §2.2.2）：`Disallow: /` + `Allow: /api/` → 放行。

    按出现顺序判的话，同一份 robots 会因为作者调换两行的位置而给出相反结论。
    """
    verdict, evidence = robots_verdict(
        "User-agent: *\nDisallow: /\nAllow: /api/\n", path="/api/x")

    assert verdict == "allowed"
    assert "/api/" in evidence


def test_rules_for_other_agents_are_not_ours_to_obey() -> None:
    """只认 `User-agent: *` 与精确匹配我们的两组——别的爬虫的段落混进来会判错。"""
    robots = "User-agent: Baiduspider\nDisallow: /\n\nUser-agent: *\nDisallow: /admin\n"

    assert robots_verdict(robots, path="/top/summary")[0] == "allowed"


def test_a_file_with_no_group_for_us_says_so() -> None:
    """「没有适用于我们的规则组」与「有规则但没命中」是两件事，证据位要能分开。

    写成同一句话，读的人无从判断这个源到底管不管我们。
    实测撞上过：`s.weibo.com` 的 robots 有 9152 字节，**一条通用规则都没有**。
    """
    only_named, no_group = robots_verdict("User-agent: Baiduspider\nDisallow: /\n", path="/x")
    _, missed = robots_verdict("User-agent: *\nDisallow: /admin\n", path="/x")

    assert only_named == "allowed"
    assert no_group != missed
    assert "没有适用于本 agent 的规则组" in no_group


def test_the_probe_module_never_fetches_anything() -> None:
    """判读模块**一次网络调用都没有**——抓 robots 的动作在 harness 里，不在 flint 里。

    门自己发请求去「看看能不能抓」，门就成了第一次越界的人（REGION-07 原话）。
    """
    from flint.region import legal_probe
    from tools.check_no_live_network import scan_source as net_scan

    assert net_scan(inspect.getsource(legal_probe), "flint/region/legal_probe.py") == []


# ───────────────────────── 三、记录但不阻断（acceptance②）


def test_the_owner_decision_is_recorded_with_its_scope_and_date() -> None:
    """裁决本身要落成机读记录：**谁、什么时候、什么范围内、为什么**。

    只把 mode 改成 record_only 而不写来由，下一个人只会看到「门开着」，
    无从判断这是裁决还是遗漏。
    """
    assert OWNER_DECISION.mode == "record_only"
    assert OWNER_DECISION.decided_on == DAY
    assert OWNER_DECISION.scope == "non_commercial"
    assert len(OWNER_DECISION.rationale) >= 20


def test_a_restricted_source_is_fetched_and_stamped() -> None:
    """acceptance②：`restricted` 照抓，但**返回的戳就是实测结论**。"""
    stamp = enforce_fetch_policy(
        source_id="s1", fetch_legal_status="restricted", day=DAY, store=_Store(),
    )

    assert stamp == "restricted", "戳被改写了——不阻断不等于改判"


def test_the_unresolved_ones_are_fetched_too() -> None:
    """`unknown` 同样照抓：裁决的范围是**非商业用途下先取数**。"""
    stamp = enforce_fetch_policy(
        source_id="s2", fetch_legal_status="unknown", day=DAY, store=_Store(),
    )

    assert stamp == "unknown"


def test_fetching_under_a_non_allowed_status_is_not_a_degradation() -> None:
    """照抓成功**不落降级行**：那条记录会被读成「今日缺 s1 数据」，而数据在。

    `card_gap_annotations` 的文案就是「今日缺 {源} 数据」——把合规标注塞进降级通道，
    产物上就会出现一条不存在的缺口。
    """
    store = _Store()

    enforce_fetch_policy(
        source_id="s1", fetch_legal_status="restricted", day=DAY, store=store,
    )

    assert store.notes == []


def test_the_stamp_reaches_the_product(tmp_path: Path) -> None:
    """acceptance②后半：戳**一路带到产物**——从注册表到 Doc 再到产物脚注。

    走的是既有那条链（`with_provenance` 注入 `fetch_legal_status`），不另开通道。
    """
    from contracts_v04.models_v04 import SourceEntry, SourceRegistry
    from flint.region.ingest_fields import with_provenance

    class _Doc:
        def __init__(self, **kw: object) -> None:
            self.__dict__.update(kw)

    registry = SourceRegistry(entries=[SourceEntry(
        source_id="s1", region="CN", country="CN", name_native="源一",
        homepage="https://example.test/", authority_tier="mainstream",
        fetch_legal_status="restricted", enabled=True,
    )], updated_at=None)  # type: ignore[arg-type]

    doc = with_provenance({"source_id": "s1"}, registry=registry, model=_Doc)
    lines = legal_status_annotations([doc])

    assert doc.fetch_legal_status == "restricted"
    assert any("s1" in ln and "restricted" in ln for ln in lines), lines


def test_an_allowed_source_gets_no_annotation() -> None:
    """阴性对照：合规放行的源**不加脚注**——每条都加等于没加。"""

    class _Doc:
        source_id = "s9"
        fetch_legal_status = "allowed"

    assert legal_status_annotations([_Doc()]) == []


def test_the_annotation_says_the_paperwork_is_still_owed() -> None:
    """产物上的那句话要写明**这是裁决下的先行取数，上线前要补手续**。

    只写「restricted」的话，读者无从知道这是被允许的还是漏网的。
    """

    class _Doc:
        source_id = "s1"
        fetch_legal_status = "restricted"

    line = legal_status_annotations([_Doc()])[0]

    assert "上线前" in line
    assert "非商业" in line


# ───────────────────────── 四、阻断能力保留不删（acceptance④）


def test_flipping_the_switch_back_blocks_again() -> None:
    """acceptance④：**改一个开关就恢复阻断**。

    这一条是本卡最要紧的反向断言：没有它，「不阻断」与「门被删了」长得一模一样。
    """
    from flint.region.fetch_gate import FetchDenied

    store = _Store()

    with pytest.raises(FetchDenied):
        enforce_fetch_policy(
            source_id="s1", fetch_legal_status="restricted", day=DAY,
            store=store, decision=BLOCK,
        )

    assert [n.reason for n in store.notes] == ["fetch_denied_by_legal_status"]


def test_the_gate_module_itself_is_untouched() -> None:
    """`fetch_gate.py` 一个字没动：本卡改的是**上层策略**，不是门。

    改门等于把 REGION-07 的语义搬走；那道门还要在 block 模式下原样工作。
    """
    from flint.region import fetch_gate

    code = inspect.getsource(fetch_gate)

    assert "K2-01" not in code
    assert code.count("_ALLOWED = \"allowed\"") == 1
    assert fetch_gate.may_fetch("restricted") is False
    assert fetch_gate.may_fetch("unknown") is False


def test_block_mode_still_lets_allowed_through() -> None:
    """阴性对照：block 模式不是「全拦」——`allowed` 照样放行。"""
    stamp = enforce_fetch_policy(
        source_id="s1", fetch_legal_status="allowed", day=DAY,
        store=_Store(), decision=BLOCK,
    )

    assert stamp == "allowed"


def test_the_two_modes_are_the_only_two() -> None:
    """开关只有两档，且两档都在用（`RECORD_ONLY` 是现值，`BLOCK` 有测试在跑）。"""
    assert {RECORD_ONLY.mode, BLOCK.mode} == {"record_only", "block"}
    assert OWNER_DECISION is RECORD_ONLY


def test_admission_follows_the_same_decision() -> None:
    """**入表口与抓取口用同一个裁决**，NEVER 各判各的。

    两处各写一套的话，「不阻断」会在入表口被悄悄抵消：restricted 的源
    根本进不了注册表，于是「照抓」永远轮不到发生。
    """
    assert admits("restricted") is True
    assert admits("unknown") is True
    assert admits("restricted", decision=BLOCK) is False
    assert admits("allowed", decision=BLOCK) is True


def test_the_candidate_registry_asks_the_policy_instead_of_hardcoding_allowed() -> None:
    """K1-02 的入表口改成问策略——源码里不再有写死的放行值比较。

    判据钉在 **AST 上**，不是「文件里有没有 admits 这几个字」：
    模块自己的 docstring 里就写着 `legal_policy.py#admits()`，
    按字面判会被那句解释喂饱（变异考实测：把调用换回硬编码，31 条全绿）。
    本仓第十四次同型。
    """
    import ast

    from flint.sources import candidates

    tree = ast.parse(inspect.getsource(candidates))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "admits"
    ]
    literal_gates = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Compare)
        and any(isinstance(c, ast.Constant) and c.value == "allowed" for c in node.comparators)
    ]

    assert calls, "入表口没调 admits()——策略没在起作用"
    assert literal_gates == [], "还留着写死的放行值比较"


# ───────────────────────── 五、上线前的手续留成机读待办（acceptance③）


def test_the_paperwork_is_a_file_not_a_conversation() -> None:
    """acceptance③：**NEVER 只留在对话里**。"""
    assert BLOCKED_DOC.exists()


def test_the_paperwork_names_every_source_that_needs_it() -> None:
    """每个**非 allowed** 的源都要在待办里点名——漏一个就是上线时的一个雷。

    COMP-01 之后待办分两个文件：问题单留指针、`docs/上线前合规手续清单.md` 留清单。
    所以这里判两件事——**指针指得过来**，且**清单里逐源点名**。
    只判其中一件的话，清单被搬走而指针没跟上（或反过来）都会绿。
    """
    pointer = BLOCKED_DOC.read_text(encoding="utf-8")
    checklist = LAUNCH_CHECKLIST.read_text(encoding="utf-8")

    assert LAUNCH_CHECKLIST.name in pointer, "问题单没有指向上线前手续清单"
    for source_id, entry in load_measured_status().items():
        if derive_fetch_legal_status(entry) == "allowed":
            continue
        assert source_id in checklist, f"{source_id} 非放行态，却没进上线前待办"


def test_the_paperwork_says_what_flipping_it_back_takes() -> None:
    """待办要写清**怎么恢复阻断**——一句可执行的话，不是「届时再议」。"""
    doc = BLOCKED_DOC.read_text(encoding="utf-8")

    assert "legal_policy" in doc
    assert "OWNER_DECISION" in doc


def test_the_decision_type_is_frozen() -> None:
    """裁决记录是不可变值：运行期被改写的话，产物上的说法与代码里的就对不上了。"""
    with pytest.raises(FrozenInstanceError):
        OWNER_DECISION.mode = "block"  # type: ignore[misc]

    assert LegalDecision.__dataclass_params__.frozen  # type: ignore[attr-defined]
