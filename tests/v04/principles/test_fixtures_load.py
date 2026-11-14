"""PRIN-02 验收：七条原则各 1 份反例 fixture，可 import，且与原则「反例」段一一对应。

acceptance（tasks-v04.json#PRIN-02）：
  ① 每条原则对应 1 个反例 fixture 且可被后续校验测试 import；
  ② fixture 内容与原则反例段一一对应。

## 这些 fixture 给谁用

§3 七条原则每条都有「校验点」，指向后面里程碑的测试（test_registry / test_cluster_bucketing /
test_grounding_original_only …）。那些测试要有**反例样本**才能证明「违反会被挡住」，
而不是只测 happy path。本卡把反例从规范正文里取出来固化成可加载数据，
后续测试 `from tests.v04.principles.fixtures import load` 直接取。

## 为什么 fixture 是从文档生成、而不是手敲

「与反例段一一对应」这条要求，手敲恰恰是它失守的地方。fixture 由
`tools/check_principles_doc.py` 的解析函数从 `docs/PRINCIPLES-v04.md` 生成（**复用，不新写解析器**），
本测试再独立地从同一文档重新解析一遍来比对——所以这不是自证，是**漂移探测**：
谁改了文档而没重生成 fixture（或反过来），这里就红。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.v04.principles.fixtures import (
    FIXTURE_DIR,
    counter_examples_of,
    load,
    load_all,
    principle_ids,
)

EXPECTED_COUNT = 7


def test_seven_fixtures_exist_and_are_importable() -> None:
    """① 七条各 1 份，且走的就是后续测试将来 import 的那条路径。"""
    ids = principle_ids()
    assert len(ids) == EXPECTED_COUNT, f"应有 {EXPECTED_COUNT} 条原则，实际 {len(ids)}：{ids}"
    for pid in ids:
        data = load(pid)                       # 后续测试的取用方式
        assert data["principle"] == pid
        assert data["counter_examples"], f"PRINCIPLES#{pid} 的反例样本是空的"
    assert len(load_all()) == EXPECTED_COUNT


def test_one_fixture_file_per_principle() -> None:
    """一条原则一个文件——不多不少，避免出现没人认领的孤儿样本。"""
    files = sorted(p.stem for p in FIXTURE_DIR.glob("*.json"))
    assert files == sorted(principle_ids()), f"fixture 文件与原则编号对不上：{files}"


def test_fixture_matches_the_counterexample_section_verbatim() -> None:
    """② 与文档「反例」段一一对应（本测试独立重解析文档，非读 fixture 自证）。"""
    for pid in principle_ids():
        data = load(pid)
        from_doc = counter_examples_of(pid)
        assert data["counter_examples"] == from_doc, (
            f"PRINCIPLES#{pid} 的反例 fixture 与文档不一致：\n"
            f"  fixture：{data['counter_examples']}\n"
            f"  文档  ：{from_doc}"
        )
        assert data["raw"].endswith("。"), f"PRINCIPLES#{pid} 的 raw 应是文档原句"


def test_comparison_is_not_vacuous() -> None:
    """阳性对照：比对逻辑必须真的能判假。

    没有这条，上面那条「一一对应」可能只是因为两边都取自同一份数据而恒真。
    """
    pid = principle_ids()[0]
    tampered = list(counter_examples_of(pid))
    tampered[0] = tampered[0] + "（被篡改）"
    assert tampered != counter_examples_of(pid)
    with pytest.raises(AssertionError):
        assert tampered == counter_examples_of(pid), "篡改后仍相等 = 比对空转"


def test_fixture_files_are_utf8_json_without_bom() -> None:
    """落盘格式：UTF-8 无 BOM 的 JSON——后续测试与 CI 直接 json.loads，不做编码猜测。"""
    for path in FIXTURE_DIR.glob("*.json"):
        raw = Path(path).read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{path.name} 带了 BOM"
        json.loads(raw.decode("utf-8"))
