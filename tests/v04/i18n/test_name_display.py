"""I18N-04-a 验收：name_display 派生管道（translate JobKind），后端半边。

原卡 I18N-04 按 §4.5 拆分：
  · **-a（本卡）**：`flint/i18n/name_display_job.py` + 本测试
    → acceptance「主行 == native **字节等同**」「translate 作业**注册进既有 JobRunner**（H7）」；
  · -b（blocked）：`web/…/native-name/` 次要行组件 → acceptance「次要行带机翻标记」。
拆分 NEVER 改变原卡 acceptance 总集。

## 派生管道最要紧的一条：原文一个字节都不能动

派生 name_display 的作业**只写 display 槽**。`name_native` 是 B7 的唯一权威，
派生流程碰它一下（哪怕只是归一化空白）就等于让译文管道有权改写原文——
那正是 B7 要禁的。
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"


def _models() -> object:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _models()
NOW = datetime(2026, 8, 2, tzinfo=UTC)
NATIVE = "全固体電池の量産ライン"

from flint.i18n import name_display_job as job_module
from flint.i18n.name_display_job import (
    TRANSLATE_JOB_KIND,
    derive_name_display,
    translate_payload,
)
from flint.i18n.translator import IdentityTranslator, TranslationCache


class _Down:
    version = "down@v1"

    def translate(self, text: str, target: str) -> str:
        from flint.i18n.translator import TranslationUnavailable

        raise TranslationUnavailable("fixture: service down")


def _cluster(name_native: str = NATIVE, display: object = None) -> object:
    return M.Cluster(
        cluster_id="c1", canonical_name="固态电池", category_id="cat-ai",
        centroid=[0.0], status="active", first_seen=date(2026, 8, 1),
        last_active=date(2026, 8, 2), parent_cluster_ids=[], merged_into=None,
        aliases=[], name_native=name_native, name_lang="ja", name_display=display)


# ── 主行 == native 字节等同 ────────────────────────────────────

def test_native_is_untouched_byte_for_byte() -> None:
    cluster = _cluster()
    before = cluster.name_native.encode("utf-8")
    derive_name_display(
        cluster, targets=("en",),
        translator=IdentityTranslator(version="identity@v1"), cache=TranslationCache())
    assert cluster.name_native.encode("utf-8") == before, "派生管道动了原文"


def test_derivation_only_writes_the_display_slot() -> None:
    cluster = _cluster()
    updated = derive_name_display(
        cluster, targets=("en",),
        translator=IdentityTranslator(version="identity@v1"), cache=TranslationCache())
    assert updated.name_native == NATIVE
    assert updated.name_display is not None
    assert set(updated.name_display) == {"en"}


def test_display_entry_carries_translation_markers() -> None:
    """译文槽必带 translated / translator / source_field（B8 的机翻标记依据）。"""
    updated = derive_name_display(
        _cluster(), targets=("en",),
        translator=IdentityTranslator(version="identity@v2"), cache=TranslationCache())
    entry = updated.name_display["en"]
    assert entry.translated is True
    assert entry.translator == "identity@v2"
    assert entry.source_field == "name_native", "译文 MUST 指回它派生自的原文字段"


def test_multiple_targets_are_derived_independently() -> None:
    updated = derive_name_display(
        _cluster(), targets=("en", "zh"),
        translator=IdentityTranslator(version="identity@v1"), cache=TranslationCache())
    assert set(updated.name_display) == {"en", "zh"}


def test_a7_degradation_leaves_display_empty_not_faked() -> None:
    """翻译不可用 → display 槽**留空**，NEVER 用原文填充冒充译文（A7 + B8）。"""
    updated = derive_name_display(
        _cluster(), targets=("en",), translator=_Down(), cache=TranslationCache())
    assert updated.name_native == NATIVE
    assert not updated.name_display, "降级时 NEVER 拿原文冒充译文"


def test_existing_display_entries_are_preserved() -> None:
    """已有的译文槽不被覆盖清空——重跑派生只补缺的那几种语言。"""
    existing = {"zh": M.TranslatedText(
        text="固态电池量产线", translated=True, translator="old@v1",
        source_field="name_native")}
    updated = derive_name_display(
        _cluster(display=existing), targets=("en",),
        translator=IdentityTranslator(version="identity@v1"), cache=TranslationCache())
    assert set(updated.name_display) == {"zh", "en"}
    assert updated.name_display["zh"].translator == "old@v1"


# ── H7：translate 作业注册进既有 JobRunner ─────────────────────

def test_translate_job_kind_is_a_contract_value() -> None:
    from typing import get_args

    assert TRANSLATE_JOB_KIND == "translate"
    assert TRANSLATE_JOB_KIND in get_args(M.JobKind), "JobKind 必须来自契约，NEVER 自定义字符串"


def test_payload_targets_the_existing_runner_signature() -> None:
    """H7：走既有 JobRunner.submit(kind, payload, budget, owner_scope, initiated_by)。"""
    from flint.jobs.runner import PgJobRunner

    payload = translate_payload(project_id="proj-1", target_ids=["c1"], targets=("en",))
    assert payload["project_id"] == "proj-1"
    sig = inspect.signature(PgJobRunner.submit)
    assert {"kind", "payload", "budget", "owner_scope", "initiated_by"} <= set(sig.parameters)


def test_module_defines_no_second_runner() -> None:
    source = inspect.getsource(job_module)
    for forbidden in ("class TranslateRunner", "class JobRunner", "def run_job"):
        assert forbidden not in source, f"新写了 runner：{forbidden}（H7 禁止）"


def test_payload_rejects_empty_target_list() -> None:
    with pytest.raises(ValueError, match="target_ids"):
        translate_payload(project_id="proj-1", target_ids=[], targets=("en",))
