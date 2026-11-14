"""DESIGN-12 验收（后端半）：「让 AI 处理」把评论注入下一 job 上下文。

acceptance（tasks-v04.json#DESIGN-12）第二条：
**「让 AI 处理」把评论注入下一 job 上下文（断言）**。

## 为什么注入的是「评论 + 它钉在哪」而不是只有评论正文

一句「这里太挤了」离开它所指的元素就没有意义——模型会去猜是哪一处挤，
猜错的代价是它改了另一个地方，而用户看到的是「我说的那处没动，别处倒变了」。
所以注入的载荷必须带上锚（data-loc 或降级坐标），让「这里」有确切所指。

## 已处理的评论不再注入

反复把同一条已经改完的意见塞给模型，它会反复改同一处——用户会觉得系统在跟自己较劲。
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from flint.design.comment_job import (
    CommentAnchor,
    DesignComment,
    build_comment_context,
    comment_payload,
)
from tests.v04._source_scan import code_names

NOW = datetime(2026, 8, 3, tzinfo=UTC)
SRC = Path(__file__).resolve().parents[3] / "flint" / "design" / "comment_job.py"


def _comment(
    cid: str = "c-1",
    *,
    text: str = "这里太挤了",
    loc: str | None = "4:3",
    point: tuple[float, float] | None = None,
    resolved: bool = False,
    ai_requested: bool = True,
) -> DesignComment:
    return DesignComment(
        comment_id=cid,
        text=text,
        anchor=CommentAnchor(loc=loc, point=point),
        created_at=NOW,
        resolved=resolved,
        ai_requested=ai_requested,
    )


def test_payload_carries_the_comment_and_where_it_points() -> None:
    """载荷 = 评论正文 + 锚。只给正文的话，「这里」没有所指。"""
    payload = comment_payload(_comment())

    assert payload["comment_id"] == "c-1"
    assert payload["text"] == "这里太挤了"
    assert payload["anchor"] == {"loc": "4:3", "point": None}


def test_degraded_anchor_is_carried_as_coordinates() -> None:
    """元素没了就带坐标：锚降级但**不消失**。"""
    payload = comment_payload(_comment(loc=None, point=(120.0, 340.0)))

    assert payload["anchor"] == {"loc": None, "point": [120.0, 340.0]}


def test_anchor_without_either_is_rejected() -> None:
    """两种锚都没有 = 这条评论指不出任何地方，NEVER 让它进上下文。"""
    with pytest.raises(ValueError):
        comment_payload(_comment(loc=None, point=None))


def test_empty_comment_text_is_rejected() -> None:
    """空评论不注入：模型会为一句空话生成一次改动。"""
    with pytest.raises(ValueError):
        comment_payload(_comment(text="   "))


def test_context_takes_only_requested_and_unresolved() -> None:
    """只注入「用户点了让 AI 处理」且**未解决**的那些。"""
    comments = [
        _comment("c-1"),                                  # 要处理
        _comment("c-2", ai_requested=False),              # 用户没点
        _comment("c-3", resolved=True),                   # 已处理
        _comment("c-4", loc=None, point=(10.0, 20.0)),    # 要处理（降级锚）
    ]

    context = build_comment_context(comments)

    assert [c["comment_id"] for c in context] == ["c-1", "c-4"]


def test_context_keeps_user_order() -> None:
    """顺序照用户给的来：重排会让「先改这个再改那个」这种意图丢掉。"""
    comments = [_comment("c-9"), _comment("c-2"), _comment("c-5")]

    context = build_comment_context(comments)

    assert [c["comment_id"] for c in context] == ["c-9", "c-2", "c-5"]


def test_context_is_empty_when_nothing_was_requested() -> None:
    """没人点「让 AI 处理」就是空列表——NEVER 顺手把所有评论都塞进去。"""
    assert build_comment_context([_comment("c-1", ai_requested=False)]) == []


def test_payload_is_a_plain_dict_not_the_entity() -> None:
    """交给 job 的是**数据**：直接塞实体会让 job 依赖前端的类型演进。"""
    payload = comment_payload(_comment())

    assert isinstance(payload, dict)
    assert set(payload) == {"comment_id", "text", "anchor", "created_at"}


def test_module_never_opens_its_own_job_channel() -> None:
    """本模块只**产上下文**，提交仍走既有 JobRunner（§6-H7）。"""
    names = code_names(SRC)

    assert "JobRunner" not in names
    for forbidden in ("submit", "asyncpg", "enqueue"):
        assert forbidden not in names
