"""BE-04：陈旧与重核端点 `GET /deliverables/{id}/staleness`（蓝本 R4「端点未建」）。

## 补的是什么

`flint/revalidate/`（7 个模块）已经建好，但**零 API 出口**——
前端那条「陈旧/重核横幅位」（蓝本 R4）拿不到任何数据。本卡把它暴露出来。

## 陈旧判定**委托**既有件，NEVER 再写一份

`flint/analysis/stale_adapter.py#analysis_stale` 已经在判这件事，
而它自己的 docstring 写死了理由：

> 再写一套的后果不是重复劳动，而是同一份分析在两个地方被判成不同的新旧：
> 收藏页说它陈旧、分析页说它是最新的，用户不知道该信哪个。

所以本端点**一行比对逻辑都不写**：版本、diff 通道、引用过的事实交给适配器，
拿回 `StaleVerdict` 原样转出去。

## 陈旧不隐藏内容，只加标记

DESIGN-12 的既有纪律（失锚仍可见）在这里的形态是：
**陈旧的交付物与新鲜的交付物，响应形状逐字相同**——只有标记值不同。
少给一个键就是「因为旧了所以不给你看」，而那正是这条纪律要挡的。

## 「没判过」与「判过、不陈旧」分得开

版本信息缺失时**不报 fresh**——报 fresh 等于告诉用户「这份是最新的」，
而我们根本没能力知道（`fav/stale.py` 的 `StaleNotEvaluated` 就是这条）。
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from flint.api.staleness import (
    DeliverableStaleness,
    StalenessApiDeps,
    create_staleness_app,
)
from flint.domain.models import FactDiff

MODULE = REPO / "flint" / "api" / "staleness.py"

OWNER = "u-be04"
STRANGER = "u-other"
TODAY = date(2026, 8, 5)


def _meta(**over: object) -> DeliverableStaleness:
    base: dict[str, object] = {
        "owner": OWNER,
        "project_id": "p-1",
        "analysed_at_version": 1,
        "current_version": 1,
        "cited_fact_ids": ("fact-1",),
        "created_on": date(2026, 1, 1),
        "last_revalidated_on": None,
        "cluster_flags": (),
        "momentum": False,
        "refute_doc_ids": (),
        "recent_triggers": (),
    }
    base.update(over)
    return DeliverableStaleness(**base)  # type: ignore[arg-type]


def _client(
    *, meta: DeliverableStaleness | None = None, diff: FactDiff | None = None,
) -> TestClient:
    async def load(deliverable_id: str) -> DeliverableStaleness | None:
        del deliverable_id
        return meta

    def diff_channel(project_id: str, old: int, new: int) -> FactDiff:
        del project_id, old, new
        assert diff is not None, "版本没动时不该去查 diff"
        return diff

    return TestClient(create_staleness_app(StalenessApiDeps(
        load_staleness=load, diff_channel=diff_channel, today=lambda: TODAY)))


def _body(**kwargs: object) -> dict[str, object]:
    client = _client(**kwargs)  # type: ignore[arg-type]
    return client.get(
        "/deliverables/d-1/staleness", headers={"X-User-Id": OWNER}).json()


def _diff(**over: object) -> FactDiff:
    # 冻结件 FactDiff 只有三项：changed / removed / disputed，**没有 added**。
    base: dict[str, object] = {"changed": [], "removed": [], "disputed": []}
    base.update(over)
    return FactDiff(**base)  # type: ignore[arg-type]


# ───────────────────────── 一、陈旧判定委托既有件（acceptance①②）


def test_the_endpoint_exists() -> None:
    response = _client(meta=_meta()).get(
        "/deliverables/d-1/staleness", headers={"X-User-Id": OWNER})

    assert response.status_code == 200


def test_a_deliverable_at_the_current_version_is_fresh() -> None:
    """版本没动 → 不陈旧，且**不去查 diff**（适配器的第一条规则）。"""
    body = _body(meta=_meta())

    assert body["stale"]["status"] == "checked"
    assert body["stale"]["stale"] is False
    assert body["stale"]["severity"] is None


def test_a_removed_cited_fact_makes_it_stale_with_the_shared_severity() -> None:
    """严重度取自**既有那张表**，NEVER 在这里抄一份。

    `removed → blocking` 是 `flint/ledger/diff.py#_MARKS` 定的。
    抄一份最坏的形态不是抄错，是**日后只改了一处**。
    """
    body = _body(
        meta=_meta(analysed_at_version=1, current_version=2),
        diff=_diff(removed=["fact-1"]))

    assert body["stale"]["stale"] is True
    assert body["stale"]["severity"] == "blocking"
    assert body["stale"]["fact_ids"] == ["fact-1"]


def test_a_changed_cited_fact_is_advisory_not_blocking() -> None:
    """`changed → advisory`：两级混一起会把一份还能用的交付物挡下来。"""
    body = _body(
        meta=_meta(analysed_at_version=1, current_version=2),
        diff=_diff(changed=["fact-1"]))

    assert body["stale"]["severity"] == "advisory"


def test_a_change_to_an_uncited_fact_does_not_make_it_stale() -> None:
    """只看**这份分析真正引用过**的事实（零污染）。

    不然账本一动、全站统统标陈旧，「陈旧」这个标记就不再有信息量。
    """
    body = _body(
        meta=_meta(analysed_at_version=1, current_version=2),
        diff=_diff(removed=["fact-99"]))

    assert body["stale"]["stale"] is False


def test_the_module_delegates_and_writes_no_comparison_of_its_own() -> None:
    """源码级：调既有适配器，且**不出现严重度字面量**。

    出现 `"blocking"` / `"advisory"` 就说明有人在这里又摆了一张表。
    """
    source = MODULE.read_text(encoding="utf-8")
    code = "\n".join(
        ln for ln in source.splitlines() if not ln.strip().startswith("#"))
    code = code.split('"""', 2)[-1]

    assert "analysis_stale" in source, "没委托既有适配器"
    for literal in ('"blocking"', '"advisory"', "_MARKS"):
        assert literal not in code, f"模块里自己摆了严重度：{literal}"


# ───────────────────────── 二、触发原因（acceptance①）


def test_the_scheduled_trigger_uses_the_existing_ladder() -> None:
    """到期日走既有 `revalidate/schedule.py#next_due_on`，NEVER 另算一遍阶梯。"""
    body = _body(meta=_meta(created_on=date(2026, 1, 1)))

    assert body["triggers"]["scheduled"]["next_due_on"] == "2026-01-31"
    assert body["triggers"]["scheduled"]["due"] is True


def test_a_young_project_is_not_due_yet() -> None:
    """项目年龄不满 30 天不扫——反向：到期永远为真的话，这个字段没意义。"""
    body = _body(meta=_meta(created_on=date(2026, 8, 1)))

    assert body["triggers"]["scheduled"]["due"] is False


def test_event_triggers_come_from_the_existing_deriver() -> None:
    """事件触发走既有 `revalidate/events.py#derive_event_triggers`。"""
    body = _body(meta=_meta(cluster_flags=("revival",), momentum=True))

    kinds = [t["event_kind"] for t in body["triggers"]["events"]]
    assert kinds == ["cluster_revival", "momentum"]


def test_a_recent_trigger_is_suppressed_by_the_dedup_window() -> None:
    """14 天去重窗口由既有件负责——本端点照样受它管。"""
    body = _body(meta=_meta(
        cluster_flags=("revival",),
        recent_triggers=(("d-1", "cluster_revival", date(2026, 8, 1)),)))

    assert [t["event_kind"] for t in body["triggers"]["events"]] == []


def test_no_signal_means_an_empty_event_list_not_a_missing_key() -> None:
    """没有事件时给**空数组**，不是缺这个键。"""
    body = _body(meta=_meta())

    assert body["triggers"]["events"] == []


# ───────────────────────── 三、陈旧不隐藏内容，只加标记（acceptance③）


def test_a_stale_deliverable_answers_with_the_same_shape_as_a_fresh_one() -> None:
    """DESIGN-12 在这里的形态：**陈旧与新鲜的响应形状逐字相同**，只有标记值不同。

    少给一个键就是「因为旧了所以不给你看」——那正是这条纪律要挡的。
    """
    fresh = _body(meta=_meta())
    stale = _body(
        meta=_meta(analysed_at_version=1, current_version=2),
        diff=_diff(removed=["fact-1"]))

    assert set(fresh) == set(stale)
    assert set(fresh["stale"]) == set(stale["stale"])   # type: ignore[arg-type]
    assert set(fresh["triggers"]) == set(stale["triggers"])   # type: ignore[arg-type]


def test_the_response_carries_no_content_and_no_hidden_flag() -> None:
    """本端点只出**标记**：它不返回正文，也 NEVER 出一个「已隐藏」的开关。

    有那个开关，就迟早有人照它把内容藏起来。
    """
    flat = json.dumps(_body(meta=_meta()), ensure_ascii=False)

    for banned in ("content", "hidden", "suppressed", "blocks"):
        assert banned not in flat, f"响应里出现了内容/隐藏相关字段：{banned}"


# ───────────────────────── 四、「没判过」与「判过、不陈旧」分得开


def test_a_deliverable_without_version_info_is_not_checked_not_fresh() -> None:
    """版本缺失时**不报 fresh**——报 fresh 等于告诉用户「这份是最新的」，
    而我们根本没能力知道（同 `fav/stale.py#StaleNotEvaluated`）。"""
    body = _body(meta=_meta(analysed_at_version=None))

    assert body["stale"]["status"] == "not_checked"
    assert "stale" not in body["stale"]


def test_a_not_checked_response_still_carries_the_triggers() -> None:
    """判不了新旧不代表触发原因也没有——两件事各说各的。"""
    body = _body(meta=_meta(analysed_at_version=None, cluster_flags=("revival",)))

    assert [t["event_kind"] for t in body["triggers"]["events"]] == ["cluster_revival"]


# ───────────────────────── 五、多租户与 404（acceptance④⑤）


def test_an_unknown_deliverable_is_404() -> None:
    response = _client(meta=None).get(
        "/deliverables/nope/staleness", headers={"X-User-Id": OWNER})

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_another_owners_deliverable_is_404_not_403() -> None:
    response = _client(meta=_meta(owner=STRANGER)).get(
        "/deliverables/d-1/staleness", headers={"X-User-Id": OWNER})

    assert response.status_code == 404


def test_the_two_kinds_of_404_share_one_error_code() -> None:
    """判在**源码**上：两种情况走同一行，逐条比状态码杀不掉「换个错误码」。"""
    import ast

    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    codes = [
        ast.unparse(call.args[1])
        for call in ast.walk(tree)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
        and call.func.id == "_error" and len(call.args) >= 2
        and ast.unparse(call.args[0]) == "404"
    ]

    assert codes and set(codes) == {"'NOT_FOUND'"}, f"404 错误码不一致：{codes}"


def test_the_owner_still_sees_their_own() -> None:
    response = _client(meta=_meta(owner=STRANGER)).get(
        "/deliverables/d-1/staleness", headers={"X-User-Id": STRANGER})

    assert response.status_code == 200


def test_identity_is_required() -> None:
    assert _client(meta=_meta()).get(
        "/deliverables/d-1/staleness").status_code == 422


# ───────────────────────── 六、只读 + NEVER 造字段（acceptance④⑥）


def test_the_module_never_writes() -> None:
    import ast

    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    docstrings = {ast.get_docstring(n) for n in ast.walk(tree)
                  if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef
                                | ast.AsyncFunctionDef)}
    literals = " ".join(
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node.value not in docstrings
    )

    for verb in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER"):
        assert not re.search(rf"\b{verb}\b", literals, re.IGNORECASE), f"模块里有 {verb}"


def test_the_response_shape_is_exactly_three_things() -> None:
    """卡上写的三样：陈旧判定 / 触发原因 / 可重核项。**NEVER 造第四样。**"""
    body = _body(meta=_meta())

    assert set(body) == {"deliverable_id", "stale", "triggers", "revalidatable"}


def test_revalidatable_says_why_when_it_is_false() -> None:
    """不可重核时要说**为什么**——只给一个 false，用户不知道该怎么办。"""
    body = _body(meta=_meta(analysed_at_version=None))

    assert body["revalidatable"]["can"] is False
    assert body["revalidatable"]["reason"]


def test_revalidatable_is_true_when_there_is_something_to_recheck() -> None:
    body = _body(meta=_meta(cluster_flags=("revival",)))

    assert body["revalidatable"]["can"] is True


def test_no_score_is_synthesised() -> None:
    """NEVER 合成「陈旧度 0.7」这类分值——只回布尔、枚举与日期。"""
    flat = json.dumps(_body(meta=_meta()), ensure_ascii=False)

    for banned in ("percent", "ratio", "score", "staleness_level", "freshness"):
        assert banned not in flat, f"合成了一个分值：{banned}"
