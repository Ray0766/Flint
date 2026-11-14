"""DESIGN-12：评论 →「让 AI 处理」的上下文载荷（G17，后端半）。

## 注入的是「评论 + 它钉在哪」

一句「这里太挤了」离开它所指的元素就没有意义——模型会去猜是哪一处挤，
猜错的代价是它改了另一个地方，而用户看到的是「我说的那处没动，别处倒变了」。
所以载荷必须带锚：`data-loc`，或元素已消失时的降级坐标。

两种锚都没有的评论**不进上下文**：它指不出任何地方，塞进去只会让模型凭空动手。

## 只注入「点了让 AI 处理」且未解决的

反复把同一条已经改完的意见塞给模型，它会反复改同一处——用户会觉得系统在跟自己较劲。
也 NEVER 把用户没点过的评论一起带上：那些是他写给自己或同事看的。

## 顺序照用户给的来

重排会让「先改这个再改那个」这种意图丢掉。

## 只产上下文，不自己发作业

提交仍走既有 JobRunner（§6-H7）。本模块不 import 它、不碰队列——
多一条提交路径就多一份幂等键与重试语义。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class CommentAnchor:
    """评论钉在哪。`loc` 是 data-loc；元素消失后降级为画布坐标 `point`。"""

    loc: str | None
    point: tuple[float, float] | None


@dataclass(frozen=True)
class DesignComment:
    comment_id: str
    text: str
    anchor: CommentAnchor
    created_at: datetime
    resolved: bool = False
    # 用户是否点了「让 AI 处理」——没点的评论是他写给自己或同事看的
    ai_requested: bool = False


def comment_payload(comment: DesignComment) -> dict[str, Any]:
    """把一条评论变成交给 job 的**数据**（不是实体本身）。"""
    if comment.text.strip() == "":
        raise ValueError(
            f"comment {comment.comment_id} 正文为空：模型会为一句空话生成一次改动"
        )
    if comment.anchor.loc is None and comment.anchor.point is None:
        raise ValueError(
            f"comment {comment.comment_id} 两种锚都没有：它指不出任何地方，"
            "塞进上下文只会让模型凭空动手"
        )
    return {
        "comment_id": comment.comment_id,
        "text": comment.text,
        "anchor": {
            "loc": comment.anchor.loc,
            "point": list(comment.anchor.point) if comment.anchor.point else None,
        },
        "created_at": comment.created_at.isoformat(),
    }


def build_comment_context(comments: list[DesignComment]) -> list[dict[str, Any]]:
    """下一次生成要带上的评论上下文：点了「让 AI 处理」且未解决的，按原顺序。"""
    return [
        comment_payload(c)
        for c in comments
        if c.ai_requested and not c.resolved
    ]
