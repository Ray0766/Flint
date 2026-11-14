"""SCHEMA-07 验收：I7 Deliverable/Block 增 lang + 同语一致断言。

acceptance（tasks-v04.json#SCHEMA-07）：
  Block.lang 与所属 Deliverable.lang 不一致时**构造/落库被拒**。

## 为什么这条不能靠 dataclass 自己拦

`Block` 拿不到它所属的 `Deliverable`——`Block.deliverable_id` 只是个字符串。
一致性是**跨对象**不变量，只能由一个显式的校验入口来守。
把它散在各处「记得比一下」就等于没有：一份中英混排的产物，
导出时读者看到的是半篇中文半篇英文，而系统全程认为一切正常。

`I12` 的三不变量里也有这条（SCHEMA-12 会复用同一个校验入口，NEVER 另写一份）。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"


def _load() -> object:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _load()
NOW = datetime(2026, 8, 2, tzinfo=UTC)


def _deliverable(lang: str = "zh") -> object:
    return M.Deliverable(
        deliverable_id="del-1", project_id="proj-1", type="report", version=1,
        supersedes=None, inputs=[], ledger_version=1, generation_record_id="gr-1",
        stale_reasons=[], created_at=NOW, lang=lang)


def _block(block_id: str, lang: str = "zh") -> object:
    return M.Block(
        block_id=block_id, deliverable_id="del-1", section_id="s1", order=1,
        type="paragraph", content=M.TextSpan(kind="text", text="正文"),
        claim_ids=[], fact_ids=[], author="system", revision=1, locked=False,
        lang=lang)


def test_both_carry_lang_with_zh_default() -> None:
    assert "lang" in M.Deliverable.__dataclass_fields__
    assert "lang" in M.Block.__dataclass_fields__
    assert _deliverable().lang == "zh" and _block("b1").lang == "zh", "A1：zh 为默认"


def test_matching_languages_pass() -> None:
    """阴性对照：一致时 MUST 通过，否则下面的拒绝可能只是「什么都拒」。"""
    M.check_deliverable_language(_deliverable("en"), [_block("b1", "en"), _block("b2", "en")])


def test_mismatched_block_language_is_rejected() -> None:
    d = _deliverable("zh")
    blocks = [_block("b1", "zh"), _block("b2", "en"), _block("b3", "zh")]
    with pytest.raises(ValueError, match="b2") as err:
        M.check_deliverable_language(d, blocks)
    message = str(err.value)
    assert "zh" in message and "en" in message, f"报错要说清两侧语言：{message}"
    assert "b1" not in message and "b3" not in message, "只报不一致的那个 block"


def test_empty_block_list_passes() -> None:
    """空 block 列表不是不一致——刚建的 Deliverable 还没有块。"""
    M.check_deliverable_language(_deliverable("zh"), [])


def test_blocks_belonging_to_another_deliverable_are_rejected() -> None:
    """传错 deliverable 的块 MUST 报错，而不是被当成语言不一致含糊过去。"""
    other = M.Block(
        block_id="bx", deliverable_id="del-OTHER", section_id="s1", order=1,
        type="paragraph", content=M.TextSpan(kind="text", text="x"),
        claim_ids=[], fact_ids=[], author="system", revision=1, locked=False, lang="zh")
    with pytest.raises(ValueError, match="del-OTHER"):
        M.check_deliverable_language(_deliverable("zh"), [other])
