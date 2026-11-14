"""K1-02：把 K1-01 的候选源清单接进 `SourceRegistry` 的那条路。

## 本卡为什么没有新增源模块

K1-01 调研出四条候选。逐条看能不能真的写一个源模块：

| 候选 | 能写吗 | 为什么 |
|---|---|---|
| `naver_datalab` | **不能** | 请求契约有官方示例（URL/方法/头/请求体齐全），**响应契约拿不到** |
| `yahoo_jp_realtime` | **不能** | 公开文档没有端点契约（K1-01 结论） |
| `reddit_data_api` | **不能** | 自助注册已关闭 + 免费档仅限非商业（K1-01 结论） |
| `google_trends_api` | 已有 | `flint/sources/gtrends.py` 早就在 |

**编一个响应结构的后果很具体**：解析器与它的测试会**自洽**——两边都按编出来的形状
写，全绿；等哪天真连上，它一行也解析不出来。宁可没有解析器，也 NEVER 有一个
自洽的假解析器。

还有一道更硬的门：四条的 `fetch_legal_status` 全是 `unknown`（K2 未决），
而 REGION-07 对 `unknown` **不放行抓取**——今天连抓都不该抓。

## 所以本模块交的是「接入路径」

`load_candidate_registry()` 把种子表读成 `SourceRegistry`，**两道条件都满足才进表**：

1. 合规态过 `flint/region/legal_policy.py#admits()`——**问策略，不写死放行值**。
   现行裁决（owner 2026-08-04，非商业用途）是「记录但不阻断」，
   于是 `restricted` 与 `unknown` 也准进表；切回 `BLOCK` 就只放行 `allowed`；
2. `enabled is True`（owner 人审通过的标记）。

**入表口与抓取口必须问同一个裁决**：各判各的话，「不阻断」会在入表口被悄悄抵消——
`restricted` 的源根本进不了注册表，于是「照抓」永远轮不到发生。

今天一条都不满足第 2 条（K1-01 的候选全部待人审）→ 返回**空表**，
与 `flint/region/registry.py#load_seed_registry()` 的既有行为一致。

空表 → 每区落一条 `DegradationNote`（E6 缺数据行）：**「该区没有源」与「取源失败」
是两件事**，混起来会把「今天没数据」误报成故障。
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Final, Protocol

import yaml

from flint.region.legal_policy import admits
from flint.sources.degradation import DegradationNote

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
CANDIDATE_SEED: Final[Path] = REPO_ROOT / "assets" / "source_registry_seed.yaml"

# K1-01 的候选里**没有**写成源模块的，逐条给理由。
# 不写理由的话，下一个人只会看到「清单里有、代码里没有」，
# 然后要么以为漏了，要么随手补一个编出来的解析器。
NOT_IMPLEMENTED_REASONS: Final[dict[str, str]] = {
    "naver_datalab": (
        "请求契约有官方示例（POST https://openapi.naver.com/v1/datalab/search，"
        "X-Naver-Client-Id/Secret 头 + keywordGroups 请求体），但**响应契约**在可访问的"
        "公开文档里拿不到——写解析器就得编一个响应结构，而编出来的解析器与它的测试会自洽"
    ),
    "yahoo_jp_realtime": (
        "官方页面写明提供排行信息 API（面向合作方），但**公开文档没有端点契约与自助"
        "申请入口**（K1-01 结论）——连请求怎么发都不确定，更谈不上解析"
    ),
    "reddit_data_api": (
        "自助注册已关闭、新令牌需人工审批（2–4 周），且免费档**仅限非商业**，"
        "而本产品是商用 MVP（S1）——接入前置是商务协议，属 owner 面（K1-01 结论）"
    ),
}


class _Store(Protocol):
    def add(self, note: DegradationNote) -> None: ...


def _read_seed() -> dict[str, Any]:
    return dict(yaml.safe_load(CANDIDATE_SEED.read_text(encoding="utf-8")))


def load_candidate_registry(
    payload: dict[str, Any] | None = None, *, decision: Any = None,
) -> Any:
    """读候选清单 → `SourceRegistry`。**两道条件都满足才进表**（见模块 docstring）。

    `payload` 可注入：让「放行的会进表」这件事能被测——不注入的话，
    今天种子表里一条都进不来，「空表」与「这条路根本不通」长得一模一样。
    `decision` 可注入：让「切回 BLOCK 就恢复只放行 allowed」这件事能被测。
    """
    from contracts_v04.models_v04 import SourceEntry, SourceRegistry

    raw = payload if payload is not None else _read_seed()
    entries = []
    for item in raw.get("entries", []):
        if not admits(str(item.get("fetch_legal_status", "unknown")), decision=decision):
            continue
        if not item.get("enabled"):
            continue
        entries.append(SourceEntry(
            source_id=str(item["source_id"]),
            region=item["region"],
            country=str(item["country"]),
            name_native=str(item["name_native"]),
            homepage=str(item["homepage"]),
            authority_tier=item["authority_tier"],
            fetch_legal_status=item["fetch_legal_status"],
            enabled=bool(item["enabled"]),
        ))
    return SourceRegistry(entries=entries, updated_at=datetime.now(UTC))


def register_ingest_sources(
    *,
    store: _Store,
    day: date,
    regions: tuple[str, ...],
    payload: dict[str, Any] | None = None,
) -> dict[str, list[Any]]:
    """按区取采集选集；**没有源的区落一条 E6 缺数据行**。

    返回值只含**真有源**的区——空区不放一个空列表进去：
    调用方拿到 `{"KR": []}` 会以为「取过了、是空的」，而真相是「这区压根没源」。
    """
    registry = load_candidate_registry(payload)
    picked: dict[str, list[Any]] = {}
    for region in regions:
        found = list(registry.select(region))
        if found:
            picked[region] = found
            continue
        store.add(DegradationNote(
            day=day,
            source_id=f"region:{region}",
            reason="no_region_sources",
            detail=(
                f"地区 {region} 无可用源（候选清单里没有合规放行且已启用的源）："
                "当日该区无数据，其余区照常。这不是故障——"
                "「该区没有源」与「取源失败」是两件事"
            ),
        ))
    return picked
