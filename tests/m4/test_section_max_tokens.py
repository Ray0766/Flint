"""max_tokens 右尺寸化（owner 裁决 @2026-07-29）：按本节最大字数 × 安全
系数封顶生成 token，替代平摊 16384（防慢模型朝上限长跑 ~35 分）。只下调、
不上调——tokens 单位节保持原 16384 上限，NEVER 因换算被截更短。
"""
from __future__ import annotations

import json
from math import ceil
from pathlib import Path

import httpx

from eval.doc_metrics import TEMPLATES
from flint.compose.templates import load_template
from flint.domain.models import Ratio
from flint.llm.local import LocalProvider
from harness.prod_caliber import (
    SECTION_MAX_TOKENS_CEILING,
    SECTION_MAX_TOKENS_FLOOR,
    SECTION_MAX_TOKENS_SAFETY,
    _section_max_tokens,
    compose_sample,
)


def test_words_unit_sized_by_max_words_times_safety() -> None:
    r = Ratio(share=0.3, min_words=600, max_words=1800, unit="words")
    assert _section_max_tokens(r) == ceil(1800 * SECTION_MAX_TOKENS_SAFETY)
    assert _section_max_tokens(r) < SECTION_MAX_TOKENS_CEILING  # 确已下调


def test_tokens_unit_capped_at_ceiling_never_truncated_further() -> None:
    # vibe_pack 节 max_words 以 token 计（可达 16800）——右尺寸后不得低于
    # 原 16384 上限（否则比现状更短，属回归截断）
    r = Ratio(share=0.2, min_words=8000, max_words=16800, unit="tokens")
    assert _section_max_tokens(r) == SECTION_MAX_TOKENS_CEILING


def test_tiny_section_floored() -> None:
    r = Ratio(share=0.01, min_words=20, max_words=50, unit="words")
    assert _section_max_tokens(r) == SECTION_MAX_TOKENS_FLOOR


def test_all_template_sections_never_exceed_old_ceiling() -> None:
    tdir = Path("assets/templates")
    for f in sorted(tdir.glob("*.yaml")):
        spec, _meta = load_template(f)
        for sid, r in spec.sections:
            mt = _section_max_tokens(r)
            assert SECTION_MAX_TOKENS_FLOOR <= mt <= SECTION_MAX_TOKENS_CEILING, (
                f"{f.stem}/{sid} max_tokens {mt} out of [floor, ceiling]"
            )


def test_words_templates_are_downsized_below_ceiling() -> None:
    # 五套 words 模板每节都应显著低于 16384（右尺寸生效的证据）
    for name in ("generic", "engineering", "grant", "startup", "thesis"):
        spec, _meta = load_template(Path(TEMPLATES) / f"{name}.yaml")
        for sid, r in spec.sections:
            assert _section_max_tokens(r) < SECTION_MAX_TOKENS_CEILING, (
                f"{name}/{sid} not downsized"
            )


def test_compose_uses_per_section_max_tokens() -> None:
    """组稿逐节向工厂请求本节右尺寸后的 max_tokens（关修复环 = 每节一次）。"""
    seen: list[int] = []

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": "字" * 80}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 10},
        })

    def make(max_tokens: int) -> LocalProvider:
        seen.append(max_tokens)
        return LocalProvider(
            base_url="http://local/v1", model="m",
            http_client=httpx.Client(transport=httpx.MockTransport(respond)),
            max_tokens=max_tokens,
        )

    compose_sample(make, "golddoc-generic-plain", "generic",
                   repair_enabled=False)
    spec, _meta = load_template(Path(TEMPLATES) / "generic.yaml")
    expected = [_section_max_tokens(r) for _sid, r in spec.sections]
    assert seen == expected


def test_compose_signature_still_isolated_from_bank() -> None:
    """右尺寸重构不得把题库 token 引入组稿路径（loader_contract ④ 复核）。"""
    import inspect

    import harness.prod_caliber as pc

    src = inspect.getsource(pc.compose_sample) + inspect.getsource(
        pc._section_max_tokens
    )
    for token in ("heldout", "bank", "load_heldout"):
        assert token not in src


# 保留一个可 json 序列化性质检查，防常量被误设为非法
def test_constants_sane() -> None:
    assert SECTION_MAX_TOKENS_SAFETY >= 1.0
    assert SECTION_MAX_TOKENS_CEILING == 16384  # 原平摊值 = 绝对上限
    assert 0 < SECTION_MAX_TOKENS_FLOOR < SECTION_MAX_TOKENS_CEILING
    json.dumps({"safety": SECTION_MAX_TOKENS_SAFETY})
