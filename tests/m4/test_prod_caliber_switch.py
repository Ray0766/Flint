"""Rulings 1-6 + 2-1: one-shot switch for the length-repair loop.

Default (switch off) behavior byte-identical to current: repair loop
runs. Switch on (--no-length-repair / FLINT_DISABLE_LENGTH_REPAIR=1):
exactly one draft call per section, zero repair calls.
"""
from __future__ import annotations

import json

import httpx
import pytest

from flint.llm.local import LocalProvider
from harness.prod_caliber import (
    MAX_LENGTH_REPAIRS,
    compose_sample,
    repair_disabled_from_env,
)

pytestmark = pytest.mark.compose


def counting_provider(reply: str) -> tuple[LocalProvider, list[str]]:
    prompts: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        prompts.append(body["messages"][-1]["content"])
        return httpx.Response(200, json={
            "id": "c", "object": "chat.completion", "model": "m",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": reply}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        })

    provider = LocalProvider(
        base_url="http://localhost:11434/v1", model="m",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    return provider, prompts


def test_switch_off_keeps_repair_loop() -> None:
    provider, prompts = counting_provider("字" * 100)  # 恒短 → 必触发修复
    compose_sample(lambda _mt: provider, "golddoc-generic-plain", "generic")
    per_section = 1 + MAX_LENGTH_REPAIRS
    assert len(prompts) == 7 * per_section, (
        "default = current behavior: draft + full repair rounds"
    )


def test_switch_on_disables_repairs() -> None:
    provider, prompts = counting_provider("字" * 100)
    compose_sample(
        lambda _mt: provider,
        "golddoc-generic-plain",
        "generic",
        repair_enabled=False,
    )
    assert len(prompts) == 7, "one draft per section, zero repairs"
    assert not any("草稿" in p for p in prompts), "no repair prompts issued"


def test_env_switch_parse() -> None:
    assert repair_disabled_from_env({}) is False
    assert repair_disabled_from_env({"FLINT_DISABLE_LENGTH_REPAIR": "1"}) is True
    assert repair_disabled_from_env({"FLINT_DISABLE_LENGTH_REPAIR": "0"}) is False


def test_check_questions_injected_verbatim() -> None:
    """Ruling 2-1: compose input carries the section's check_questions
    VERBATIM (SectionSpec carries them by design); no guidance table."""
    from pathlib import Path

    from eval.doc_metrics import TEMPLATES
    from flint.compose.templates import load_template

    provider, prompts = counting_provider("字" * 600)
    compose_sample(
        lambda _mt: provider,
        "golddoc-generic-plain",
        "generic",
        repair_enabled=False,
    )
    _spec, sections = load_template(Path(TEMPLATES) / "generic.yaml")
    by_id = {s.section_id: s.check_questions for s in sections}
    assert len(prompts) == len(by_id)
    for prompt, (sid, questions) in zip(prompts, by_id.items(), strict=True):
        for question in questions:
            assert question in prompt, (
                f"{sid}: check question not verbatim in prompt"
            )


def test_guidance_table_fully_removed() -> None:
    from pathlib import Path

    import harness.prod_caliber as pc

    assert not hasattr(pc, "_GUIDANCE_RULES"), "table must be deleted"
    assert not hasattr(pc, "_guidance_for"), "matcher must be deleted"
    source = Path(pc.__file__).read_text(encoding="utf-8")
    assert "PriceCell-n）标注；" not in source, "no guidance text residue"
    assert "判定档位（例：判定为" not in source, "no tier-sentence residue"
