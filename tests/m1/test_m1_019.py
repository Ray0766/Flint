"""M1-019 acceptance tests: canonical generation + alias merging.

Acceptance (tasks.json M1-019):
  - 30 synonym-group golden cases merge correctly at 100%
"""
from __future__ import annotations

from pathlib import Path

import pytest

from flint.norm.canonical import CanonicalKeyword, canonicalize
from flint.norm.terms import TermMap, load_term_map

REPO_ROOT = Path(__file__).resolve().parents[2]

# 30 golden synonym groups: every variant in a group must land on the same
# canonical form. Variants mix full/half width, case, t2s, aliases, zh/en.
GOLDEN_GROUPS: list[tuple[list[str], str]] = [
    (["LLM", "large language model", "大模型", "大语言模型"], "large language model"),
    (["AI", "人工智能", "人工智慧", "ＡＩ"], "artificial intelligence"),
    (["固态电池", "固態電池", "Solid-State Battery"], "solid-state battery"),
    (["RAG", "检索增强", "检索增强生成"], "retrieval augmented generation"),
    (["AGI", "通用人工智能"], "artificial general intelligence"),
    (["GAN", "生成对抗网络"], "generative adversarial network"),
    (["NLP", "自然语言处理"], "natural language processing"),
    (["GPU", "图形处理器", "ＧＰＵ"], "graphics processing unit"),
    (["FPGA", "现场可编程门阵列"], "field programmable gate array"),
    (["BCI", "脑机接口"], "brain-computer interface"),
    (["UAV", "无人机"], "drone"),
    (["SLAM", "同步定位与建图"], "simultaneous localization and mapping"),
    (["EV", "电动车", "电动汽车", "電動車"], "electric vehicle"),
    (["ADAS", "高级驾驶辅助系统"], "advanced driver assistance system"),
    (["eVTOL", "飞行汽车", "电动垂直起降"], "electric vertical takeoff and landing"),
    (["IoT", "物联网"], "internet of things"),
    (["VR", "虚拟现实"], "virtual reality"),
    (["AR", "增强现实"], "augmented reality"),
    (["NFT", "非同质化代币"], "non-fungible token"),
    (["DeFi", "去中心化金融"], "decentralized finance"),
    (["云计算", "云端运算", "云端運算", "Cloud Computing"], "cloud computing"),
    (["5G", "5G网络", "第五代移动通信", "５Ｇ"], "5g"),
    (["增材制造", "三维打印", "3D Printing"], "3d printing"),
    (["SaaS", "软件即服务"], "software as a service"),
    (["RPA", "机器人流程自动化"], "robotic process automation"),
    (["CRM", "客户关系管理"], "customer relationship management"),
    (["LFP", "磷酸铁锂"], "lithium iron phosphate"),
    (["SMR", "小型模块化反应堆"], "small modular reactor"),
    (["HBM", "高带宽内存", "ＨＢＭ"], "high bandwidth memory"),
    (["VTuber", "虚拟主播"], "virtual youtuber"),
]


@pytest.fixture(scope="module")
def terms() -> TermMap:
    return load_term_map(REPO_ROOT / "assets" / "term-map.yaml")


def test_thirty_groups_present() -> None:
    assert len(GOLDEN_GROUPS) == 30


@pytest.mark.parametrize(
    ("variants", "expected"),
    GOLDEN_GROUPS,
    ids=[g[1] for g in GOLDEN_GROUPS],
)
def test_synonym_group_merges_to_one_canonical(
    variants: list[str], expected: str, terms: TermMap
) -> None:
    results = {canonicalize(v, terms).canonical for v in variants}
    assert results == {expected}, f"group did not merge: {results}"


def test_unmapped_term_passes_through_cleaned(terms: TermMap) -> None:
    result = canonicalize("　Ｎｅｗ  Ｔｏｐｉｃ🔥", terms)
    assert result.canonical == "new topic"
    assert result.source == "cleaned"


def test_mapped_term_marks_source(terms: TermMap) -> None:
    assert canonicalize("大模型", terms).source == "term_map"


def test_lang_detection(terms: TermMap) -> None:
    assert canonicalize("大模型", terms).lang == "en"  # canonical form is english
    assert canonicalize("完全未收录的中文词", terms).lang == "zh"
    assert canonicalize("unmapped english phrase", terms).lang == "en"


def test_result_type(terms: TermMap) -> None:
    result = canonicalize("AI", terms)
    assert isinstance(result, CanonicalKeyword)
    assert result.canonical and result.lang and result.source
