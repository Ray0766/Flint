"""K1-01：九区源站清单调研的机读种子表（**候选，待 owner 人审**）。

## 这张表现在**不能**被自动装载

`flint/region/registry.py#load_seed_registry` 的 docstring 写着：种子表**是空的**，
「实现里 NEVER 内置任何真实站点」，因为「各国源的合规结论（FetchLegalStatus）
没有 owner 结论前，任何具体站点都是猜的」。

本卡产出的是**调研结论**（卡面 `owner_review: true`），不是把它接进实现。
所以：

- `assets/source_registry_seed.yaml` 是**候选清单**，逐条带出处链接与调研日期；
- `load_seed_registry()` **仍然返回空表**——这一条有断言守着；
- 每条 `enabled: false` 且 `fetch_legal_status: unknown`（K2 未决）——
  `unknown` 在 REGION-07 的门里**不放行抓取**，也就是说这张表填完**也还不能抓**。

## 判据都盯着「有没有出处」

卡面 acceptance④：「调研结论 NEVER 写成『据了解』这类无出处表述；
查不到就写『未找到公开端点』」。所以每条候选都要有 `source_url` 与
`researched_on`，缺一即红——**没有出处的源站名与凭印象列的没有区别**。
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED = REPO_ROOT / "assets" / "source_registry_seed.yaml"
DOC = REPO_ROOT / "docs" / "源站清单-v041.md"

# 九区（`contracts_v04/models_v04.py:23` 的 Region 字面量）
REGIONS = ("CN", "US", "AU", "SG", "JP", "KR", "GB", "IT", "FR")
TIERS = ("official", "mainstream", "industry", "community", "unknown")
LEGAL = ("allowed", "unknown", "restricted")
# `SourceEntry` 的八个字段 + 本卡加的两个出处字段
ENTRY_FIELDS = (
    "source_id", "region", "country", "name_native", "homepage",
    "authority_tier", "fetch_legal_status", "enabled",
    "source_url", "researched_on",
)


def _seed() -> dict[str, object]:
    return yaml.safe_load(SEED.read_text(encoding="utf-8"))


def _entries() -> list[dict[str, object]]:
    return list(_seed()["entries"])  # type: ignore[arg-type,index]


# ───────────────────────── 一、格式与既有契约对齐（acceptance③）


def test_the_seed_file_exists() -> None:
    assert SEED.exists(), "种子表不在盘上"


def test_every_entry_has_all_ten_fields() -> None:
    """八个契约字段 + 两个出处字段，缺一即红。"""
    missing = [
        (entry.get("source_id"), field)
        for entry in _entries()
        for field in ENTRY_FIELDS
        if field not in entry
    ]

    assert missing == [], f"这些条目缺字段：{missing}"


def test_the_field_names_match_the_contract() -> None:
    """字段名与 `contracts_v04.SourceEntry` **逐字**对上。

    对不上的话，owner 批准之后还要再改一遍名字——而改名字最容易漏。
    """
    from contracts_v04.models_v04 import SourceEntry

    contract_fields = set(SourceEntry.__annotations__)
    seed_fields = set(ENTRY_FIELDS) - {"source_url", "researched_on"}

    assert seed_fields == contract_fields


@pytest.mark.parametrize("field,allowed", [
    ("region", REGIONS), ("authority_tier", TIERS), ("fetch_legal_status", LEGAL),
])
def test_enumerated_fields_stay_inside_the_contract(field: str, allowed: tuple[str, ...]) -> None:
    """三个枚举字段的取值都在契约的字面量集合里。"""
    bad = [
        (e["source_id"], e[field]) for e in _entries()
        if e[field] not in allowed and e[field] != "multi"
    ]

    assert bad == [], f"{field} 取值越界：{bad}"


def test_the_country_is_iso_alpha2() -> None:
    """`country` 是 ISO 3166-1 alpha-2（两个大写字母）。"""
    bad = [e["source_id"] for e in _entries() if not re.fullmatch(r"[A-Z]{2}", str(e["country"]))]

    assert bad == []


# ───────────────────────── 二、每条都有出处（acceptance①④）


def test_every_entry_carries_a_source_url() -> None:
    """acceptance①：**每条附出处链接**——没有出处的源站名与凭印象列的没有区别。"""
    bad = [
        e["source_id"] for e in _entries()
        if not str(e.get("source_url", "")).startswith("http")
    ]

    assert bad == [], f"这些条目没有出处链接：{bad}"


def test_every_entry_carries_a_research_date() -> None:
    """调研日期要能看出「这是什么时候查的」——源站会改版，结论会过期。"""
    for entry in _entries():
        researched = entry["researched_on"]
        assert isinstance(researched, date), f"{entry['source_id']} 的调研日期不是日期"


def test_no_entry_uses_hearsay_wording() -> None:
    """acceptance④：**NEVER 出现「据了解」这类无出处表述**。"""
    text = SEED.read_text(encoding="utf-8") + DOC.read_text(encoding="utf-8")
    # 先剥掉「」引号里的内容：**引用一个禁用词正是禁掉它的方式**。
    # 首版没剥，被自己那句「NEVER 出现「据了解」这类无出处表述」判红了——
    # 判据与留痕互相取消，本仓第十三次。
    used = re.sub(r"「[^」]*」", "", text)

    for weasel in ("据了解", "据说", "应该有", "大概是", "众所周知"):
        assert weasel not in used, f"出现了无出处表述：{weasel}"


def test_regions_without_a_finding_say_so_explicitly() -> None:
    """acceptance④：查不到就写**「未找到公开端点」**。

    九区里每一区都要在文档里有交代——**没写**与**写了「没找到」**是两回事：
    前者让人以为还没查，后者是一条结论。
    """
    doc = DOC.read_text(encoding="utf-8")
    covered = {str(e["region"]) for e in _entries()}

    for region in REGIONS:
        if region in covered:
            continue
        # 判据落在**提到这个区的那一行上**，不是全文任意处：
        # 退回全文的话，别的区那句「未找到公开端点」就把断言喂饱了
        # （变异考实测：删掉这五区的交代，18 条全绿）。
        lines = [
            ln for ln in doc.splitlines()
            if f"`{region}`" in ln and "未找到公开端点" in ln
        ]

        assert lines, f"{region} 既没有候选源，也没在自己那一行写「未找到公开端点」"


# ───────────────────────── 三、准入打分照实（acceptance②）


def test_every_entry_is_scored_against_the_admission_criteria() -> None:
    """acceptance②：逐条对照 REGION-01 准入标准打分（三项）。"""
    for entry in _entries():
        admission = entry.get("admission")
        assert isinstance(admission, dict), f"{entry['source_id']} 没有准入打分"
        for key in ("data_availability", "update_frequency", "structure_stability"):
            assert key in admission, f"{entry['source_id']} 的准入打分缺 {key}"


def test_a_failing_score_carries_a_reason() -> None:
    """不达标的**照实标注并说明为什么仍列/不列**——分低不是问题，不说理由才是。"""
    for entry in _entries():
        admission = dict(entry["admission"])  # type: ignore[call-overload]
        if any(v == "fail" for v in admission.values()):
            assert admission.get("note"), f"{entry['source_id']} 有不达标项却没写理由"


# ───────────────────────── 四、这张表还不能用（本卡的边界）


def test_every_entry_is_disabled() -> None:
    """全部 `enabled: false`——**候选清单，不是启用清单**。"""
    enabled = [e["source_id"] for e in _entries() if e["enabled"]]

    assert enabled == [], f"这些条目被启用了，而 owner 还没人审：{enabled}"


def test_every_legal_status_is_unknown_until_k2() -> None:
    """合规态一律 `unknown`：K2 未决前这是**唯一诚实的填法**。

    填 `allowed` 等于替 K2 下了结论，而 `unknown` 在 REGION-07 的门里不放行抓取——
    也就是说这张表填完**也还不能抓**。
    """
    bad = [e["source_id"] for e in _entries() if e["fetch_legal_status"] != "unknown"]

    assert bad == [], f"这些条目的合规态不是 unknown（K2 未决）：{bad}"


def test_the_implementation_seed_is_still_empty() -> None:
    """`load_seed_registry()` **仍然返回空表**——本卡 NEVER 把候选接进实现。

    `flint/region/registry.py` 的原话：「实现里 NEVER 内置任何真实站点」。
    接进去要等 owner 人审 + K2 合规结论。
    """
    from flint.region.registry import load_seed_registry

    assert load_seed_registry().entries == []


def test_the_registry_module_still_names_no_real_site() -> None:
    """实现文件里也不许出现具体站点域名。"""
    import inspect

    from flint.region import registry

    code = inspect.getsource(registry)

    for domain in ("google.com", "naver.com", "weibo.com", "yahoo.co.jp", "reddit.com"):
        assert domain not in code, f"实现里内置了真实站点：{domain}"


def test_the_doc_says_the_table_is_not_usable_yet() -> None:
    """文档明写这张表**还不能用**，以及卡在什么上。"""
    doc = DOC.read_text(encoding="utf-8")

    assert "待 owner 人审" in doc
    assert "K2" in doc
