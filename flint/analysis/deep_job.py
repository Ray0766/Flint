"""HOTSPOT-04：AI 深度分析按钮 → 既有 JobRunner（计费落点为配置开关）。

深度分析是产品里唯一一处「点一下就花钱」的动作，所以这个模块的分量全在边界上：

- **不新写 runner（§6-H7）**：`kind` 用契约里既有的 `gate1_analysis`，理由有两条，
  **都不是「新增 JobKind 会动冻结件」**——那句话与真件不符：`contracts_v04` 在同一个增量里
  就 additive 加过 `translate` / `design_generate` / `template_solidify` 三个值（走 additive
  通道 + `check_frozen_additive.py`，S2-1 没有被越过）。站得住的是这两条：
  ① **深度是档位，不是另一种作业**——同一件事做得更深，`tier="deep"` 进 payload；
  ② **自建一套提交路径会带来第二份幂等键与重试语义**——同一个按钮点两下可能跑出两笔账。
- **提交面零 LLM**：按钮按下到作业入队之间一次模型调用都没有。模型工作发生在
  worker 里（`flint/jobs/gate1.py`）；提交面碰 LLM 就意味着每次点开都在付钱。
  provider 恒由外部注入且本模块 NEVER 调用它——真实 API key 与真实网络是 §7 的
  事前必审项，NEVER 由一张功能卡引入。
- **计费落点是配置开关（K7 两态）**：免费/付费路线未定，故本模块两态皆可运行。
  开关走既有 `FeatureFlags` 的 `billing_enabled`（默认 false），NEVER 新写开关系统。

三条计费纪律，各自都对应一种事后很难查的坏状态：

1. 开关打开却没接落点 → **报错**，NEVER 静默跳过。静默跳过等于把付费运行免费送出去，
   且这些运行一条记录都没有。
2. 金额**只能由配置给出**，模块里 NEVER 藏默认价——一个内置默认价会在没人注意时
   变成实际收费口径，而它的出处只有代码本身（「数字必有出处」在这一处最要紧）。
3. 落点抛错时异常里**带上 job_id**：作业已经建好了，不带的话它就成了一次
   无人认领的运行——既没记账，也没人知道该去取消谁。

本模块只产生**计费意图**并交给注入的落点；真实付费接口的开通是 owner 人审节点
（S2-10），NEVER 在这里直接调支付。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, Protocol

from flint.config import FeatureFlags

# 契约既有值（contracts/models.py#JobKind）：深度是档位，不是另一种作业。
DEEP_ANALYSIS_JOB_KIND: Final = "gate1_analysis"
DEEP_TIER: Final = "deep"
# 既有开关名（flint/config.py#DEFAULT_FLAGS），默认 false。
BILLING_FLAG: Final = "billing_enabled"


class ChargeLandingMissing(Exception):
    """billing_enabled=true 却没有注入计费落点。"""

    def __init__(self, cluster_id: str) -> None:
        super().__init__(
            f"billing_enabled=true 但未注入计费落点（cluster={cluster_id}）："
            "NEVER 静默跳过计费"
        )


@dataclass(frozen=True)
class DeepAnalysisPricing:
    """一次深度档运行的预算与计费金额。两个字段都无默认值：出处必须是调用方配置。"""

    budget: float
    charge_cny: float


@dataclass(frozen=True)
class ChargeIntent:
    """计费意图。挂在具体那一次运行上（job_id），而不只是挂在热点上。"""

    cluster_id: str
    job_id: str
    amount_cny: float
    initiated_by: str


@dataclass(frozen=True)
class DeepAnalysisSubmission:
    job_id: str
    billed: bool
    charge: ChargeIntent | None


ChargeLanding = Callable[[ChargeIntent], None]


class _RunnerLike(Protocol):
    """既有 JobRunner 的提交面（contracts/protocols.py#JobRunner.submit）。"""

    async def submit(
        self,
        kind: Any,
        payload: Any,
        budget: float,
        owner_scope: Any,
        initiated_by: str,
    ) -> str: ...


def deep_analysis_payload(*, cluster_id: str, lang: str) -> dict[str, Any]:
    """构造深度档 payload。档位写在 payload 里，kind 保持契约值。"""
    if not cluster_id:
        raise ValueError(
            "cluster_id NEVER 为空：不指向任何热点的深度分析作业没有意义，"
            "而它一旦入队仍会照常计费"
        )
    return {"cluster_id": cluster_id, "tier": DEEP_TIER, "lang": lang}


async def submit_deep_analysis(
    runner: _RunnerLike,
    *,
    cluster_id: str,
    lang: str,
    owner_scope: Any,
    initiated_by: str,
    flags: FeatureFlags,
    pricing: DeepAnalysisPricing,
    charge: ChargeLanding | None = None,
    provider: Any = None,
) -> DeepAnalysisSubmission:
    """提交一次深度分析。

    `provider` 只是接口缝：调用方注入什么，本函数都**不会调用**它——
    模型工作在 worker 内发生。留着这个参数是为了让接线处有一个显式的落点，
    而不是让人到别处去 new 一个真 provider。
    """
    del provider  # 提交面 NEVER 调 LLM
    payload = deep_analysis_payload(cluster_id=cluster_id, lang=lang)
    billing_on = flags.is_enabled(BILLING_FLAG)
    if billing_on and charge is None:
        # 先于提交检查：不能既不计费又照跑
        raise ChargeLandingMissing(cluster_id)

    job_id = await runner.submit(
        DEEP_ANALYSIS_JOB_KIND, payload, pricing.budget, owner_scope, initiated_by,
    )
    if not billing_on:
        return DeepAnalysisSubmission(job_id=job_id, billed=False, charge=None)

    intent = ChargeIntent(
        cluster_id=cluster_id, job_id=job_id,
        amount_cny=pricing.charge_cny, initiated_by=initiated_by,
    )
    assert charge is not None  # 上面已挡；此处仅为类型收窄
    try:
        charge(intent)
    except Exception as err:  # 落点炸了：把已建好的作业报出去
        raise RuntimeError(
            f"计费落点失败，作业已创建：job_id={job_id} cluster={cluster_id}"
        ) from err
    return DeepAnalysisSubmission(job_id=job_id, billed=True, charge=intent)
