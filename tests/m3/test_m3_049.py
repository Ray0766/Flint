"""M3-049 acceptance tests: scheduled revalidation trigger (age ladder).

Acceptance (tasks.json M3-049):
  - <30 no scan / 30~90 every 30 days / >90 every 60 days, each tier cased
  - due list deterministic under a fake clock
"""
from __future__ import annotations

from datetime import date

from flint.revalidate.schedule import DueProject, due_projects, next_due_on

TODAY = date(2026, 7, 29)


def test_under_30_days_never_scanned() -> None:
    created = date(2026, 7, 10)  # 19 天
    assert next_due_on(created, last_run=None) > TODAY


def test_30_to_90_every_30_days() -> None:
    created = date(2026, 6, 1)  # 58 天
    first = next_due_on(created, last_run=None)
    assert first == date(2026, 7, 1), "first due at age 30"
    after_run = next_due_on(created, last_run=date(2026, 7, 1))
    assert after_run == date(2026, 7, 31), "then every 30 days"


def test_over_90_every_60_days() -> None:
    created = date(2026, 3, 1)  # 150 天
    due = next_due_on(created, last_run=date(2026, 6, 15))
    assert due == date(2026, 8, 14), "60-day cadence past age 90"


def test_due_list_deterministic() -> None:
    projects = [
        ("p-new", date(2026, 7, 20), None),           # 太新，不扫
        ("p-mid", date(2026, 6, 1), None),             # 到期（首扫 7-01 已过）
        ("p-mid-fresh", date(2026, 6, 1), date(2026, 7, 20)),  # 刚扫过
        ("p-old", date(2026, 1, 1), date(2026, 5, 1)),  # 上扫时 121 天，60 天节奏
    ]
    due = due_projects(projects, today=TODAY)
    assert due == [
        DueProject(project_id="p-mid", due_on=date(2026, 7, 1)),
        DueProject(project_id="p-old", due_on=date(2026, 6, 30)),
    ]
    assert due == due_projects(projects, today=TODAY), "deterministic"
