"""REGION-06：authority 轴接入证据强度体系（K3-01 定值，替掉 1.0 占位）。

## 1.0 为什么退场

K3 未决期间的口径是「唯一诚实的权重是 1.0」——不替 owner 拍板。
代价是这条轴**接了等于没接**：五档权威度打出来的分一模一样，
`authority_tier` 沦为记在 `components` 里没人用的字符串。

K3-01 照**公认方法论**定初值（不是拿本项目数据拟合——金标集还不到位），
每条推导附出处，依据见 `docs/authority权重-v041.md`：

| 档 | 锚在哪 | 权重 |
|---|---|---|
| `official` | 官方一手 / 同行评议——WP:RS 层级顶端、证据金字塔顶端 | 1.15 |
| `mainstream` | 有编辑部与事实核查的主流媒体（**锚点**） | 1.00 |
| `industry` | 行业机构 / 厂商发布：有署名有专业度，但利益相关 | 0.77 |
| `community` | 社区 / 自出版：无独立事实核查（WP:RS 明列为最低一档） | 0.57 |
| `unknown` | 未评级。**不知道来路 NEVER 比已知最弱的更强** | 0.57 |

数值取自 NewsGuard 公布的评级分档中点（100 / 87 / 67 / 49.5），
**以主流档为分母归一**——改的是相对分量，不是整体分数水位。
五档全部 >1 的话，接轴会让所有分数一起涨，此前的金标结论要全部重跑。

## 初值是初值

`calibrated` 仍是 `False`：**方法论初值不等于标定过**。金标集到位后走既有调参通道
（`flint/config.py#load_tuning`，键 `authority.*`）标定，改配置不改代码。
这份来源说明一路带到 `EvidenceScore.components["authority_basis"]`——
产物上看得见「这个权重是哪来的」。

## 轴落在 components 而不是 axis 字段

冻结件 `EvidenceScore.axis: EvidenceOrigin` 只有 retrieved / user_provided 两值,
加第三值就是改冻结契约。按 worker.md §1.4「以 contracts/ 为准」, authority 记进
`components`, `axis` 保持双尺语义不动。措辞偏离已留单
`docs/blocked/REGION-06-AXIS-WORDING.md`。

## 与 REGION-03 前置门的分工

门（tier_gate）是**布尔**的: 仅 unknown 支撑时判 A/B 直接拒。
轴是**连续**的: 给不同权威度不同权重。两者互不替代——
门挡的是「来路不明的东西堆数量」, 轴调的是「已知来路者之间的相对分量」。
**给 unknown 定了权重不等于放行 unknown**：混起来的话，一个权重值就悄悄
改掉了判定门槛。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from flint.domain.models import EvidenceScore


@dataclass(frozen=True)
class AuthorityWeights:
    """五档权威度的乘数。**初值只有这一处**（既有调参通道的规矩）：

    抄第二份就有了第二个真相，而两个真相里总有一个是旧的。
    推导见模块 docstring 的表与 `docs/authority权重-v041.md`。
    """

    official: float = 1.15
    mainstream: float = 1.00
    industry: float = 0.77
    community: float = 0.57
    unknown: float = 0.57


AUTHORITY_BASIS: Final[str] = (
    "权重初值来自方法论调研（NewsGuard 评级分档 / WP:RS 来源层级 / 证据金字塔），"
    "非本项目实测；依据见 docs/authority权重-v041.md，待金标集到位后可再标定"
)

_MAX_STRENGTH: Final[int] = 100


def weight_for(authority_tier: str, weights: AuthorityWeights | None = None) -> float:
    """取一档的权重。**认不出的档位按最低权重算**，NEVER 按 1.0 放行——

    按 1.0 放行等于「拼错一个字符串就自动获得主流媒体的分量」。
    """
    table = weights or AuthorityWeights()
    known = {
        "official": table.official, "mainstream": table.mainstream,
        "industry": table.industry, "community": table.community,
        "unknown": table.unknown,
    }
    return known.get(authority_tier, min(known.values()))


def apply_authority_axis(
    score: EvidenceScore,
    *,
    authority_tier: str,
    weights: AuthorityWeights | None = None,
) -> EvidenceScore:
    """把 authority 轴接到一份既有分数上。

    - `strength` 按档位乘权重并**截在 0~100 内**：`official` 是 >1 的乘数，
      满分证据不能被顶出界；
    - `axis` **不变**: 冻结件只有双尺两值;
    - `components` **只增三个键**, 既有分量一个不改——改了质量卡口径就变了;
    - 幂等: 同一档重复接轴原样返回。**叠乘会让同一份证据因为多走一遍流水线
      而变强**，而权重不再是 1.0 之后，叠乘是真的会发生的事。
    """
    already = score.components.get("authority_tier")
    if already is not None:
        if already == authority_tier:
            return score
        raise ValueError(
            f"这份分数已按 tier={already} 接过轴，NEVER 换成 {authority_tier} 再接一次："
            "第二次乘的是已经加过权的分，不是底分"
        )
    factor = weight_for(authority_tier, weights)
    strength = min(_MAX_STRENGTH, max(0, round(score.strength * factor)))
    components = dict(score.components)
    components.update({
        "authority_tier": authority_tier,
        "authority_weight": factor,
        "authority_basis": AUTHORITY_BASIS,
    })
    return EvidenceScore(strength=strength, axis=score.axis, components=components)
