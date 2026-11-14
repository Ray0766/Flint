"""TS-006：Project 建 + chosen_topic（owner #6，容器串 verdict↔topic）。

- build_project：Origin→TopicSeed→topics 落库后建 Project{origin_id, topic_ids}。
- choose_topic：选定 Topic 写 chosen_topic_id，chosen ∈ topic_ids 校验（越界拒）。
  verdict↔topic 经 Project.chosen_topic_id 链接（该 project 的 analysis job →
  snap-{job}-verdict）。持久化走 PgProjectStore（TS-001）。
"""
from __future__ import annotations

from datetime import datetime

from flint.domain.models import JSON, Principal, Project


class ProjectValidationError(ValueError):
    """选定的 topic 不在 project.topic_ids（越界）。"""


def build_project(
    *,
    project_id: str,
    owner: Principal,
    origin_id: str,
    topic_ids: list[str],
    created_at: datetime,
    status: str = "active",
) -> Project:
    return Project(
        project_id=project_id,
        owner=owner,
        origin_id=origin_id,
        topic_ids=list(topic_ids),
        chosen_topic_id=None,
        deliverable_ids=[],
        change_log=[],
        status=status,
        created_at=created_at,
    )


def choose_topic(project: Project, topic_id: str) -> Project:
    if topic_id not in project.topic_ids:
        raise ProjectValidationError(
            f"topic {topic_id!r} is not among project topics {project.topic_ids}"
        )
    entry: JSON = {"action": "choose_topic", "topic_id": topic_id}
    return Project(
        project_id=project.project_id,
        owner=project.owner,
        origin_id=project.origin_id,
        topic_ids=list(project.topic_ids),
        chosen_topic_id=topic_id,
        deliverable_ids=list(project.deliverable_ids),
        change_log=[*project.change_log, entry],
        status=project.status,
        created_at=project.created_at,
    )
