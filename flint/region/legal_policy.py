"""K2-01：合规状态**记录但不阻断**的策略层（owner 2026-08-04 裁决）。

## 裁决内容

非商业用途下**先取数**：`restricted` 与 `unknown` 的源照抓，
但把 `legal_status` 打在数据上，一路带到产物。

## 门没有被删

`flint/region/fetch_gate.py` **一个字没动**。变的是这一层：`OWNER_DECISION.mode`
现在是 `record_only`；换成 `BLOCK` 就原样回到 REGION-07 的阻断行为——
`enforce_fetch_policy` 在 block 模式下直接委托 `guard_fetch`，不复制它的逻辑。

**「删掉门」与「把门开着」是两件事**：前者不可逆，后者是一个开关。
上线前要补的手续留在 `docs/blocked/K2-COMPLIANCE-BEFORE-LAUNCH.md`。

## 入表口与抓取口用同一个裁决

`admits()` 是给源注册表入表口用的（`flint/sources/candidates.py`），
`enforce_fetch_policy()` 是给抓取前置用的，两者读同一个 `LegalDecision`。
各判各的话，「不阻断」会在入表口被悄悄抵消：`restricted` 的源根本进不了注册表，
于是「照抓」永远轮不到发生。

## 照抓成功不是降级

`restricted` 源抓成功**不落 DegradationNote**：那条记录的用户文案是
「今日缺 {源} 数据」（`card_gap_annotations`），而数据在。
把合规标注塞进降级通道，产物上就会出现一条不存在的缺口。
合规标注走的是产物脚注（`legal_status_annotations`）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Final, Literal, Protocol

from flint.region.fetch_gate import guard_fetch
from flint.sources.degradation import DegradationNote

PolicyMode = Literal["record_only", "block"]


class _Store(Protocol):
    def add(self, note: DegradationNote) -> None: ...


@dataclass(frozen=True)
class LegalDecision:
    """一条合规裁决：**谁、什么时候、什么范围内、为什么**。

    只把 mode 改成 `record_only` 而不写来由，下一个人只会看到「门开着」，
    无从判断这是裁决还是遗漏。frozen：运行期被改写的话，
    产物上写的说法与代码里实际执行的就对不上了。
    """

    mode: PolicyMode
    decided_on: date
    decided_by: str
    scope: str
    rationale: str


RECORD_ONLY: Final[LegalDecision] = LegalDecision(
    mode="record_only",
    decided_on=date(2026, 8, 4),
    decided_by="owner",
    scope="non_commercial",
    rationale=(
        "非商业用途下先取数：合规状态照实记录并带到产物，但不拿它拦抓取。"
        "全部源一律 unknown 时九区一条也抓不了，整条链路验不了；"
        "上线（商用）前必须补手续，见 docs/blocked/K2-COMPLIANCE-BEFORE-LAUNCH.md"
    ),
)

BLOCK: Final[LegalDecision] = LegalDecision(
    mode="block",
    decided_on=date(2026, 8, 4),
    decided_by="owner",
    scope="commercial",
    rationale=(
        "恢复 REGION-07 的原行为：只放行 allowed。商用上线时切回这一档——"
        "改这一个常量即可，门本身一直在"
    ),
)

# 现行裁决。改这一个名字就能切档（acceptance④ 的那个开关）。
OWNER_DECISION: Final[LegalDecision] = RECORD_ONLY


def admits(fetch_legal_status: str, *, decision: LegalDecision | None = None) -> bool:
    """源注册表入表口：这个合规态今天准不准进表。"""
    if (decision or OWNER_DECISION).mode == "record_only":
        return True
    return fetch_legal_status == "allowed"


def enforce_fetch_policy(
    *,
    source_id: str,
    fetch_legal_status: str,
    day: date,
    store: _Store,
    decision: LegalDecision | None = None,
) -> str:
    """抓取前置。返回**要打在数据上的戳**（就是实测结论本身）。

    - `record_only`：一律放行，戳照实返回——**不阻断不等于改判**；
    - `block`：委托 `guard_fetch`（落降级 + 抛 `FetchDenied`），不复制它的逻辑。
    """
    if (decision or OWNER_DECISION).mode == "block":
        guard_fetch(
            source_id=source_id, fetch_legal_status=fetch_legal_status,
            day=day, store=store,
        )
    return fetch_legal_status


def legal_status_annotations(docs: list[Any]) -> list[str]:
    """产物脚注：本次产物里有哪些源是在**非放行**合规态下取的。

    放行的源不加脚注——每条都加等于没加。
    """
    lines: list[str] = []
    for source_id in sorted({
        str(getattr(doc, "source_id", ""))
        for doc in docs
        if getattr(doc, "fetch_legal_status", "allowed") != "allowed"
    } - {""}):
        status = next(
            str(getattr(d, "fetch_legal_status", ""))
            for d in docs if getattr(d, "source_id", None) == source_id
        )
        lines.append(
            f"源 {source_id} 的抓取合规状态为 {status}："
            f"依 owner {OWNER_DECISION.decided_on} 裁决，非商业用途下记录但不阻断；"
            "上线前须补手续（见 docs/blocked/K2-COMPLIANCE-BEFORE-LAUNCH.md）"
        )
    return lines
