"""SHIP-01：免费额度计数与配额门（**零定价**）。

## 配置留空 = 整条计费路径关闭

单价、免费额度上限、币种、计费口径版本**四项全部从配置读**，且默认值都是 `None`。
K7/K8（定价与档位）尚未定 → 未配置时本门**一次都不拦**，行为与今天逐字相同。

四项**任缺其一**就算未配置：半套配置比没有更危险——它会让一半的运行被拦、
另一半照跑，而两边都以为自己是对的。

「没配」与「配成 0」必须分得开，所以默认值是 `None` 不是 `0`：
默认成 0 的话，「免费额度 0 次」与「还没定价」长得一模一样。

## 拦在 submit 之前

超额时在**建作业之前**抛。先建再发现没额度，那个作业就成了一次既没记账、
也没人知道该去取消谁的运行（`flint/analysis/deep_job.py` 的
`ChargeLandingMissing` 早就是这个形状：**先于提交检查**）。

拒绝时说**还差多少**：只说「超额」的话，用户不知道是差 1 次还是差 100 次。

## 本模块不认识提交那一侧

这里没有 runner、没有 submit、不构造 job_id。「拦在提交之前」这件事靠的正是
本模块根本够不着提交面——够得着就迟早会有人在里面顺手建一个作业。

**零真实支付**：本模块 NEVER 接任何支付网关（S2-10 红线）。
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from flint.domain.models import Principal


@dataclass(frozen=True)
class BillingConfig:
    """计费配置。四项默认 `None` = 未配置 = 整条路径关闭。

    NEVER 在这里写默认价：一个内置默认价会在没人注意时变成实际收费口径，
    而它的出处只有代码本身（「数字必有出处」在这一处最要紧）。
    """

    free_quota: int | None = None
    unit_price: Decimal | None = None
    currency: str | None = None
    pricing_version: str | None = None

    @property
    def configured(self) -> bool:
        """四项**全齐**才算配好。任缺其一都按未配置处理。"""
        return None not in (
            self.free_quota, self.unit_price, self.currency, self.pricing_version,
        )


class QuotaExceeded(Exception):
    """免费额度用完了。异常里带 owner 与**还差多少**——不带的话没法答复用户。"""

    def __init__(self, owner: Principal, used: int, limit: int) -> None:
        shortfall = used - limit + 1
        super().__init__(
            f"免费额度已用完（owner={owner.id}，已用 {used}/{limit}）："
            f"这一次还差 {shortfall} 次额度。NEVER 先建作业再发现没额度。"
        )
        self.owner = owner
        self.used = used
        self.limit = limit
        self.shortfall = shortfall


@dataclass(frozen=True)
class QuotaDecision:
    """一次配额判定。`limit is None` = 计费路径未配置（本门此刻不拦任何东西）。"""

    allowed: bool
    used: int
    limit: int | None
    shortfall: int
    note: str


def check_quota(*, used: int, owner: Principal, config: BillingConfig) -> QuotaDecision:
    """这一次运行放不放行。**不抛**——判定与处置分开，处置归调用方。"""
    if not config.configured:
        return QuotaDecision(
            allowed=True, used=used, limit=None, shortfall=0,
            note="计费路径未配置（零定价）：本门不拦，行为与未接计费时逐字相同",
        )
    limit = config.free_quota
    assert limit is not None                       # configured 已保证
    if used < limit:
        return QuotaDecision(
            allowed=True, used=used, limit=limit, shortfall=0,
            note=f"免费额度内（已用 {used}/{limit}，owner={owner.id}）",
        )
    shortfall = used - limit + 1
    return QuotaDecision(
        allowed=False, used=used, limit=limit, shortfall=shortfall,
        note=f"免费额度已用完（已用 {used}/{limit}）：还差 {shortfall} 次",
    )


def guard_before_submit(
    *, used: int, owner: Principal, config: BillingConfig
) -> QuotaDecision:
    """配额门。放行则返回判定，超额则**抛**。

    调用点 MUST 在提交作业**之前**——本函数拿不到 runner，也不该拿到。
    """
    decision = check_quota(used=used, owner=owner, config=config)
    if not decision.allowed:
        assert decision.limit is not None
        raise QuotaExceeded(owner, decision.used, decision.limit)
    return decision
