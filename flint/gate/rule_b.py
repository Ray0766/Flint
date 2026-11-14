"""B 档规则（M2-035，数量或强度双路径；审1）。

红海的本质是竞争强度：数量路径（>=3 个竞品、各有可达来源）之外，
>=1 个 strength="strong" 竞品单独触发——两家寡头盘踞的市场不该判 C。
可达来源 = http(s) 形态 URL（M2-030 抽取层已硬校验，此处再守一遍，
防手工构造的 Competitor 绕过）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from flint.domain.models import Competitor

COUNT_THRESHOLD: Final[int] = 3


@dataclass
class RuleBResult:
    satisfied: bool
    by_count: bool
    by_strength: bool
    reachable_count: int
    strong_names: list[str] = field(default_factory=list)


def evaluate_rule_b(competitors: list[Competitor]) -> RuleBResult:
    reachable = [
        c for c in competitors if c.url.startswith(("http://", "https://"))
    ]
    strong = [c.name for c in competitors if c.strength == "strong"]
    by_count = len(reachable) >= COUNT_THRESHOLD
    by_strength = len(strong) >= 1
    return RuleBResult(
        satisfied=by_count or by_strength,
        by_count=by_count,
        by_strength=by_strength,
        reachable_count=len(reachable),
        strong_names=strong,
    )
