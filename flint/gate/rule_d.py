"""D 兜底与缺口清单（M2-037；审8 分流硬条款）。

- 落 D MUST 输出非空缺口清单（GapHint）；派生为空即抛错——那是编程
  错误（有 D 判定却说不出缺什么），不是降级路径。
- missing_permission NEVER 伪装成缺资料：cause="missing_permission" 时
  action="request_permission"、required_scope 必填、suggested_sources 为空。

## FIX-12：人话里 NEVER 有机器值

改前 `missing_what` 拼的是 `f"竞品扫描覆盖未达标（{coverage.reason}）"`——
`not_saturated` 会**原样上屏**。两处坏：前端换不掉那句话（`DS-03` 的标签表
`coverage` 一族五个值都在，却派不上用场），且两边话术会各自漂移。

**原因码没有被丢掉，它换了个位置**：只把括号里那截删掉的话，屏上确实干净了，
而「为什么没达标」这个信息没了——那比印一个机器值更坏，
用户从此不知道该去补什么。

`GapHint` 是冻结件（加字段是 `S2-1` 禁止的），所以本模块返回 `DerivedGap`：
冻结件那一份原样装在 `hint` 里，原因码与参数并排放。
序列化层（`flint/jobs/gate1.py`）把两半一起发出去。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from flint.competitor.coverage import CoverageResult, unknown_competitor_gap
from flint.domain.models import JSON, Competitor, GapHint
from flint.gate.rule_c import RuleCResult


@dataclass(frozen=True)
class DerivedGap:
    """一条缺口：**给人看的那一份** + **给机器看的那一份**。

    `hint` 是冻结件 `GapHint` 原样（判定语义一字不动）；
    `reason_code` 是 `DS-03` 标签表认得的机器值——前端按它取人话，
    NEVER 由后端拼一句成型的话交出去（拼了前端就换不掉）。

    没有原因码的缺口（证伪未执行之类）`reason_code` 为 `None`：
    **NEVER 编一个** ——编出来的那个码不在标签表里，前端只能原样印出来，
    绕一圈回到改前的样子。
    """

    hint: GapHint
    reason_code: str | None = None
    params: JSON = field(default_factory=dict)


def derive_gaps(
    rule_c: RuleCResult,
    coverage: CoverageResult,
    competitors: list[Competitor],
    missing_scopes: list[str],
    alignment_demoted: bool = False,
) -> list[DerivedGap]:
    gaps: list[DerivedGap] = []
    if "refute_not_executed" in rule_c.failed_conditions:
        gaps.append(DerivedGap(GapHint(
            missing_what="证伪检索未执行",
            cause="missing_data",
            suggested_sources=["refute 模板族五类检索"],
            action="search",
        )))
    if "refute_hit_rate_below_theta" in rule_c.failed_conditions:
        gaps.append(DerivedGap(GapHint(
            missing_what="证伪检索相关率未达 θ_rel",
            cause="missing_data",
            suggested_sources=["关键词改写重检（上限 R 轮）"],
            action="search",
        )))
    if not coverage.covered:
        # FIX-12：人话里 NEVER 有机器值。原因码走 `reason_code`，
        # 由前端按 `DS-03` 的标签表（`coverage` 一族）说人话。
        gaps.append(DerivedGap(
            GapHint(
                missing_what="竞品扫描覆盖未达标",
                cause="missing_data",
                suggested_sources=coverage.pending_queries or ["竞品源补充扫描"],
                action="search",
            ),
            reason_code=coverage.reason,
            params={"pending_queries": list(coverage.pending_queries)},
        ))
    if "no_aligned_support" in rule_c.failed_conditions:
        if alignment_demoted or rule_c.demote_to_d:
            gaps.append(DerivedGap(GapHint(
                missing_what="关键证据对齐未过（绝不带病判定）",
                cause="missing_data",
                suggested_sources=["替换或补充关键证据"],
                action="upload",
            )))
        else:
            gaps.append(DerivedGap(GapHint(
                missing_what="缺少对齐通过的支持证据",
                cause="missing_data",
                suggested_sources=["支持向检索", "用户补充材料"],
                action="search",
            )))
    elif alignment_demoted:
        gaps.append(DerivedGap(GapHint(
            missing_what="关键证据对齐未过（绝不带病判定）",
            cause="missing_data",
            suggested_sources=["替换或补充关键证据"],
            action="upload",
        )))
    unknown_gap = unknown_competitor_gap(competitors)
    if unknown_gap is not None:
        # 那个模块回的是冻结件 `GapHint`（它不知道本模块的 `DerivedGap`）。
        # **NEVER 在这里给它编一个 reason_code**：编出来的码不在标签表里，
        # 前端只能原样印出来，绕一圈回到改前的样子。
        gaps.append(DerivedGap(unknown_gap))
    for scope in missing_scopes:
        gaps.append(DerivedGap(GapHint(
            missing_what=f"生成所需字段组不可访问：{scope}",
            cause="missing_permission",
            suggested_sources=[],
            action="request_permission",
            required_scope=scope,
        )))
    if not gaps:
        raise ValueError(
            "rule D requires a non-empty gap list (audit 8): "
            "no gap could be derived from the inputs"
        )
    return gaps
