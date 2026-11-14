"""scheduled 触发：项目年龄阶梯（M3-049，技术方案 E4）。

阶梯（写死）：项目年龄 <30 天不扫；30~90 天每 30 天一次；>90 天每 60 天
一次。next_due_on 给出下次到期日（无 last_run 时 = 年龄满 30 天当日）；
due_projects 按 (project_id 序) 产出确定到期清单（假时钟注入）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

_MIN_AGE_DAYS = 30
_MID_CADENCE_DAYS = 30
_OLD_AGE_DAYS = 90
_OLD_CADENCE_DAYS = 60


@dataclass(frozen=True)
class DueProject:
    project_id: str
    due_on: date


def next_due_on(created: date, last_run: date | None) -> date:
    if last_run is None:
        return created + timedelta(days=_MIN_AGE_DAYS)
    age_at_last_run = (last_run - created).days
    cadence = (
        _OLD_CADENCE_DAYS if age_at_last_run >= _OLD_AGE_DAYS
        else _MID_CADENCE_DAYS
    )
    return last_run + timedelta(days=cadence)


def due_projects(
    projects: list[tuple[str, date, date | None]], today: date
) -> list[DueProject]:
    due: list[DueProject] = []
    for project_id, created, last_run in projects:
        due_on = next_due_on(created, last_run)
        if due_on <= today:
            due.append(DueProject(project_id=project_id, due_on=due_on))
    return due
