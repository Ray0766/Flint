"""K1-02：源站接入——把 K1-01 的候选清单接进 `SourceRegistry` 的那条路。

## 本卡今天接得了什么，接不了什么

K1-01 调研出四条候选。逐条看**能不能真的写一个源模块**：

| 候选 | 能写吗 | 为什么 |
|---|---|---|
| `naver_datalab` | **不能** | 请求契约有官方示例（URL/方法/头/请求体齐全），**响应契约拿不到**——写解析器就得**编**一个响应结构 |
| `yahoo_jp_realtime` | **不能** | 公开文档根本没有端点契约（K1-01 的结论） |
| `reddit_data_api` | **不能** | 自助注册已关闭 + 免费档仅限非商业（K1-01 的结论） |
| `google_trends_api` | 已有 | `flint/sources/gtrends.py` 早就在（走 dailytrends 端点） |

**编一个响应结构的后果很具体**：解析器与它的测试会**自洽**——两边都按我编的形状写，
全绿；等哪天真连上，它一行也解析不出来。本仓一路在防的就是这种自洽。

还有一道更硬的门：四条的 `fetch_legal_status` 全是 `unknown`（K2 未决），
而 REGION-07 对 `unknown` **不放行抓取**。也就是说**今天连抓都不该抓**。

## 所以本卡交的是「接入路径」，不是「新源」

- `load_candidate_registry()`：把种子表读成 `SourceRegistry`；
- 进表要过两道：**合规态问 `legal_policy.admits()`** + `enabled`。
  今天候选全部 `enabled: false`（待 owner 人审），于是它返回**空表**，
  与 `load_seed_registry()` 的既有行为一致；
- 空表 → 每区落一条 `DegradationNote`（E6 缺数据行），**NEVER 用空数据冒充成功**。

> **K2-01（2026-08-04）之后改过一处**：合规那道门原本写死 `== "allowed"`，
> 现在问策略。owner 裁决非商业用途下「记录但不阻断」，入表口要跟着走——
> 各判各的话，「照抓」会在入表口被悄悄抵消。切回 `BLOCK` 即恢复原样，有断言守着。
"""
from __future__ import annotations

import inspect
from datetime import date
from pathlib import Path

import pytest

from flint.sources.candidates import (
    CANDIDATE_SEED,
    NOT_IMPLEMENTED_REASONS,
    load_candidate_registry,
    register_ingest_sources,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DAY = date(2026, 8, 4)
REGIONS = ("CN", "US", "AU", "SG", "JP", "KR", "GB", "IT", "FR")


class _Store:
    def __init__(self) -> None:
        self.notes: list[object] = []

    def add(self, note: object) -> None:
        self.notes.append(note)


# ───────────────────────── 一、种子读得进来，但一条都不放行


def test_the_seed_file_is_the_one_k1_01_produced() -> None:
    assert CANDIDATE_SEED == REPO_ROOT / "assets" / "source_registry_seed.yaml"
    assert CANDIDATE_SEED.exists()


def test_the_registry_is_empty_while_the_legal_status_is_unknown() -> None:
    """acceptance②的前置：合规态 `unknown` → **一条都不进表**。

    REGION-07 对 `unknown` 不放行抓取。放进表就等于替 K2 下了结论。
    """
    registry = load_candidate_registry()

    assert registry.entries == []


def test_an_allowed_and_enabled_candidate_would_get_in() -> None:
    """阴性对照：合规态放行且启用的**会**进表——这道门拦的是 `unknown`，不是拦所有。

    没有这一条，「今天空表」与「这条路根本不通」长得一模一样。
    """
    payload = {
        "entries": [{
            "source_id": "demo_src", "region": "KR", "country": "KR",
            "name_native": "데모", "homepage": "https://example.test/",
            "authority_tier": "official", "fetch_legal_status": "allowed",
            "enabled": True, "source_url": "https://example.test/doc",
            "researched_on": DAY,
            "admission": {"data_availability": "pass", "update_frequency": "pass",
                          "structure_stability": "pass"},
        }]
    }

    registry = load_candidate_registry(payload=payload)

    assert [e.source_id for e in registry.entries] == ["demo_src"]
    assert registry.select("KR")[0].region == "KR"


@pytest.mark.parametrize("blocker", ["unknown", "restricted"])
def test_a_not_allowed_candidate_is_admitted_or_not_by_the_policy(blocker: str) -> None:
    """入表口**问策略**，不自己判（K2-01 之后改的）。

    - 现行裁决（owner 2026-08-04，非商业用途「记录但不阻断」）→ `unknown` 与
      `restricted` **也进表**：不然「照抓」会在入表口被悄悄抵消；
    - 切回 `BLOCK` → 回到「只放行 allowed」的原样。

    这两半必须一起断言：只测一半的话，「策略在起作用」与「写死了某个值」
    长得一模一样。
    """
    from flint.region.legal_policy import BLOCK, OWNER_DECISION

    payload = {
        "entries": [{
            "source_id": "demo_src", "region": "KR", "country": "KR",
            "name_native": "데모", "homepage": "https://example.test/",
            "authority_tier": "official", "fetch_legal_status": blocker,
            "enabled": True, "source_url": "https://example.test/doc",
            "researched_on": DAY,
            "admission": {"data_availability": "pass", "update_frequency": "pass",
                          "structure_stability": "pass"},
        }]
    }

    assert OWNER_DECISION.mode == "record_only"
    admitted = load_candidate_registry(payload=payload)
    assert [e.source_id for e in admitted.entries] == ["demo_src"]

    blocked = load_candidate_registry(payload=payload, decision=BLOCK)
    assert blocked.entries == []


def test_enabled_false_also_keeps_it_out() -> None:
    """两道条件是**与**关系：合规放行了但没启用，同样不进。"""
    payload = {
        "entries": [{
            "source_id": "demo_src", "region": "KR", "country": "KR",
            "name_native": "데모", "homepage": "https://example.test/",
            "authority_tier": "official", "fetch_legal_status": "allowed",
            "enabled": False, "source_url": "https://example.test/doc",
            "researched_on": DAY,
            "admission": {"data_availability": "pass", "update_frequency": "pass",
                          "structure_stability": "pass"},
        }]
    }

    assert load_candidate_registry(payload=payload).entries == []


# ───────────────────────── 二、空表照实降级（acceptance②）


def test_every_region_gets_a_degradation_note_today() -> None:
    """acceptance②：拿不到源就**照实降级**，NEVER 用空数据冒充成功。"""
    store = _Store()

    picked = register_ingest_sources(store=store, day=DAY, regions=REGIONS)

    assert picked == {}
    assert len(store.notes) == len(REGIONS)
    assert {n.reason for n in store.notes} == {"no_region_sources"}


def test_the_note_names_the_region_and_says_it_is_not_a_fault() -> None:
    """「该区没有源」与「取源失败」是两件事——混起来会把「今天没数据」误报成故障。"""
    store = _Store()

    register_ingest_sources(store=store, day=DAY, regions=("KR",))

    note = store.notes[0]
    assert "KR" in note.source_id
    assert "其余区照常" in note.detail


def test_a_region_with_a_source_gets_no_note() -> None:
    """阴性对照：有源的区不落降级行——否则那条记录会被读成「这区也没数据」。"""
    payload = {
        "entries": [{
            "source_id": "demo_src", "region": "KR", "country": "KR",
            "name_native": "데모", "homepage": "https://example.test/",
            "authority_tier": "official", "fetch_legal_status": "allowed",
            "enabled": True, "source_url": "https://example.test/doc",
            "researched_on": DAY,
            "admission": {"data_availability": "pass", "update_frequency": "pass",
                          "structure_stability": "pass"},
        }]
    }
    store = _Store()

    picked = register_ingest_sources(
        store=store, day=DAY, regions=("KR", "JP"), payload=payload,
    )

    assert [e.source_id for e in picked["KR"]] == ["demo_src"]
    assert [n.source_id for n in store.notes] == ["region:JP"]


# ───────────────────────── 三、没实现的三条，逐条写明为什么


def test_every_unimplemented_candidate_has_a_reason() -> None:
    """K1-01 的四条候选里，没写成源模块的**逐条给理由**。

    不写理由的话，下一个人只会看到「清单里有、代码里没有」，
    然后要么以为漏了，要么随手补一个编出来的解析器。
    """
    for source_id in ("naver_datalab", "yahoo_jp_realtime", "reddit_data_api"):
        reason = NOT_IMPLEMENTED_REASONS.get(source_id, "")
        assert len(reason) >= 20, f"{source_id} 没写清为什么没实现：{reason}"


def test_the_already_implemented_one_is_not_listed_as_missing() -> None:
    """`google_trends_api` 早就有实现（`gtrends.py`），不该出现在「没实现」表里。"""
    assert "google_trends_api" not in NOT_IMPLEMENTED_REASONS


def test_no_invented_parser_exists_for_the_unimplemented_ones() -> None:
    """**没有为它们编解析器**：`flint/sources/` 下不存在这三个模块。

    编一个响应结构的后果很具体：解析器与它的测试会自洽——两边都按编的形状写，
    全绿；等哪天真连上，它一行也解析不出来。
    """
    for name in ("naver_datalab", "yahoo_jp", "reddit"):
        assert not (REPO_ROOT / "flint" / "sources" / f"{name}.py").exists(), (
            f"{name}.py 存在——它的响应契约今天拿不到，不该有解析器"
        )


def test_the_reasons_are_grounded_in_the_k1_01_findings() -> None:
    """理由要指回 K1-01 的调研结论，而不是另起一套说法。"""
    doc = (REPO_ROOT / "docs" / "源站清单-v041.md").read_text(encoding="utf-8")

    for source_id in NOT_IMPLEMENTED_REASONS:
        assert source_id in doc, f"{source_id} 不在 K1-01 的清单里"


# ───────────────────────── 四、零硬编码地区假设（acceptance④）


def test_the_region_comes_from_the_registry_not_from_the_code() -> None:
    """acceptance④：地区从注册表读——模块里**没有**写死的地区字面量分支。

    BL-09 的尺子（`tools/check_no_live_network.py` 的同族
    `tools/check_locale_seam.py`）全仓扫这件事；这里再钉一次本模块。
    """
    from flint.sources import candidates
    from tools.check_locale_seam import scan_source

    assert scan_source(inspect.getsource(candidates), "flint/sources/candidates.py") == []


def test_the_loader_never_fetches_anything() -> None:
    """本模块**一次网络调用都没有**：接入路径与抓取是两件事。

    今天合规态全 `unknown`，抓取本身就不该发生（REGION-07）。
    """
    from flint.sources import candidates
    from tools.check_no_live_network import scan_source as net_scan

    assert net_scan(inspect.getsource(candidates), "flint/sources/candidates.py") == []


def test_the_existing_four_sources_are_untouched() -> None:
    """既有四源一个字没动——本卡只加接入路径。"""
    for name in ("gtrends", "weibo", "ghtrend", "arxiv"):
        source = (REPO_ROOT / "flint" / "sources" / f"{name}.py").read_text(encoding="utf-8")
        assert "K1-02" not in source
