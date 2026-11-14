"""ASM-01：组稿生成器注入——首次组稿产出真正文，不再是占位 heading。

缺陷背景（steward 2026-08-03 实测，`docs/steward/项目实况报告-2026-08-03.md#四`）：
全仓 `generator_factory=` 只有一个赋值点（`flint/jobs/compose.py:142`），赋的是
`_default_generator` 占位——它只产一个 heading，text 是 `section_id` 字面量。真 LLM
生成器 `llm_generator_factory` 只接在单块重生成路径（`flint/jobs/regenerate_job.py`）。

本卡新增 `flint/jobs/compose_deps.py` 做生产装配：generator_factory 绑真生成器，
provider 缺失显式抛错（NEVER 静默回落到占位——静默回落正是当前缺陷的根因）。
`build_offline_compose_deps` 与 `_default_generator` 一字不动（工单 §3 零修改边界）。

测试全程离线：LocalProvider 走 httpx.MockTransport（M1-008 录制回放机理），块内容取
M4 已录制的真实 qwen3.6 产出，CI 零联网零付费（S2-7）。
"""
from __future__ import annotations

import inspect
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from flint.compose.draft_channels import draft_section_with_channels
from flint.domain.models import (
    Fact,
    FactsLedger,
    Principal,
    SectionSpec,
    UserProfile,
)
from flint.jobs import compose as compose_mod
from flint.jobs.compose_deps import (
    ComposeProviderMissing,
    build_production_compose_deps,
)
from flint.llm.local import LocalProvider

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test"
)
SPEC = SectionSpec(
    section_id="summary", inputs=[], check_questions=["项目一句话是什么？"], charts=[]
)


def _real_qwen_prose() -> str:
    """取一段 M4 已录制的真实 qwen3.6 正文（贴合真实模型行为，非人造字符串）。"""
    data = json.loads(
        (REPO / "assets" / "prod_caliber" / "qwen3.6_27b.json").read_text(
            encoding="utf-8"
        )
    )
    comp = next(iter(data["compositions"].values()))
    return str(comp["sections"]["summary"])[:100]


def _profile() -> UserProfile:
    return UserProfile(
        profile_id="p-1", owner=Principal(kind="user", id="u-1"),
        identity={}, research={}, team=[], assets={}, constraints={},
        track_record=[], locale="zh-CN", sensitivity_overrides={}, updated_at=NOW,
    )


def _ledger(fact_ids: list[str]) -> FactsLedger:
    facts = [
        Fact(fact_id=fid, statement=f"陈述-{fid}", value=None, unit=None,
             citation_ids=[], status="frozen", origin="injected",
             created_in_version=1)
        for fid in fact_ids
    ]
    return FactsLedger(
        ledger_id="led-1", project_id="proj-1", version=1, parent_version=None,
        derivation_reason="freeze", facts=facts, created_from=[], created_at=NOW,
        actor="u-1",
    )


def _replay_provider(block_json: dict[str, object]) -> LocalProvider:
    """录制回放 provider：MockTransport，零真实网络。"""
    def respond(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {
                "content": json.dumps(block_json, ensure_ascii=False),
                "tool_calls": [],
            }}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        })
    return LocalProvider(
        base_url="http://local/v1", model="qwen3.6:27b",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )


def _deps(provider: LocalProvider | None):  # type: ignore[no-untyped-def]
    return build_production_compose_deps(
        dsn=DSN, repo_root=REPO, profile=_profile(), now=NOW, provider=provider,
    )


# ── acceptance ①：generator_factory 绑真生成器，NEVER 是占位 ──────────────

def test_generator_factory_is_bound_to_llm_generator_factory() -> None:
    deps = _deps(_replay_provider({"blocks": []}))
    factory = deps.generator_factory
    assert factory is not compose_mod._default_generator, (
        "生产装配绑上了占位生成器——这正是 ASM-01 要根治的缺陷"
    )
    assert factory.__module__ == "flint.compose.llm_generator", (
        f"generator_factory 来自 {factory.__module__}，应来自 llm_generator 模块"
    )
    assert factory.__qualname__ == "llm_generator_factory.<locals>.factory", (
        f"generator_factory 的 qualname 是 {factory.__qualname__}，"
        "应是 llm_generator_factory 产出的闭包"
    )


# ── acceptance ②：草拟一节产出 paragraph 且正文非空（占位只产 heading） ──

def test_drafted_section_contains_non_empty_paragraph() -> None:
    prose = _real_qwen_prose()
    deps = _deps(_replay_provider({"blocks": [
        {"type": "heading", "level": 2, "text": "项目摘要"},
        {"type": "paragraph", "text": prose, "fact_ids": ["fact-1"]},
    ]}))
    blocks = draft_section_with_channels(
        SPEC, _ledger(["fact-1"]),
        deps.generator_factory(SPEC, "del-asm01"),
        entries_by_id={}, profile=deps.profile,
    )
    paragraphs = [b for b in blocks if b.type == "paragraph"]
    assert paragraphs, f"草稿里没有 paragraph（块型={[b.type for b in blocks]}）——占位生成器只产 heading，此断言认得出退化"
    content = paragraphs[0].content
    assert content.kind == "paragraph"
    text = "".join(s.text for s in content.spans if s.kind == "text")
    assert text.strip(), "paragraph 正文为空"
    assert text == prose


def test_placeholder_degradation_is_detected_by_the_same_assertion() -> None:
    """反例：占位生成器的产出**不含** paragraph，且正文是 section_id 字面量。

    证明上一条断言不是空转——它真能把退化认出来。
    """
    blocks = draft_section_with_channels(
        SPEC, _ledger(["fact-1"]),
        compose_mod._default_generator(SPEC, "del-placeholder"),
        entries_by_id={}, profile=_profile(),
    )
    assert [b.type for b in blocks] == ["heading"]
    heading = blocks[0].content
    assert heading.kind == "heading"
    assert heading.text == SPEC.section_id, "占位的正文就是 section_id 字面量"


# ── acceptance ③：未注入 provider → 显式抛错，NEVER 静默回落 ────────────

def test_missing_provider_raises_and_names_what_is_missing() -> None:
    with pytest.raises(ComposeProviderMissing) as err:
        _deps(None)
    msg = str(err.value)
    assert "provider" in msg, f"报错未点名缺什么：{msg}"
    assert "LLMProvider" in msg, f"报错未说明需要的类型：{msg}"


def test_missing_provider_never_falls_back_to_placeholder() -> None:
    """静默回落是当前缺陷的根因——这里断言它不会以任何形式返回 deps。"""
    result: object = None
    try:
        result = _deps(None)
    except ComposeProviderMissing:
        result = None
    assert result is None, "provider 缺失时仍返回了 deps——存在静默回落路径"


def test_missing_template_raises_instead_of_silently_proceeding() -> None:
    with pytest.raises(FileNotFoundError) as err:
        build_production_compose_deps(
            dsn=DSN, repo_root=REPO, profile=_profile(), now=NOW,
            provider=_replay_provider({"blocks": []}),
            template_name="no_such_template.yaml",
        )
    assert "no_such_template.yaml" in str(err.value)


# ── acceptance ④：占位保留但只供显式 offline，其调用点不在生产装配路径 ──

def test_default_generator_kept_for_explicit_offline_use() -> None:
    """桩保留（NEVER 删）：离线装配仍绑它，名字里就写着 offline。"""
    assert callable(compose_mod._default_generator)
    offline = compose_mod.build_offline_compose_deps(DSN, REPO)
    assert offline.generator_factory is compose_mod._default_generator


def test_production_assembly_never_references_default_generator() -> None:
    """AST 面断言：生产装配的**代码**里没有 `_default_generator` 这个标识符。

    看 AST 而不是看文本：docstring 里说明「占位为什么留在 offline 路径」是应该的，
    真正不该出现的是**引用/调用**。文本 in 判断会把注释当违规（假红），也会把
    `getattr(m, "_default_gener" + "ator")` 放过（假绿）。
    """
    import ast

    from flint.jobs import compose_deps

    tree = ast.parse(inspect.getsource(compose_deps))
    names = {
        n.id for n in ast.walk(tree) if isinstance(n, ast.Name)
    } | {
        n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
    } | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
        for a in n.names
    }
    assert "_default_generator" not in names, (
        "生产装配代码里引用了 _default_generator——占位的调用点必须只在 offline 路径"
    )
    # 反例：同款 AST 检查在 compose.py 上必须**认得出**那里确实有引用（证明不空转）。
    compose_names = {
        n.id for n in ast.walk(ast.parse(inspect.getsource(compose_mod)))
        if isinstance(n, ast.Name)
    }
    assert "_default_generator" in compose_names


def test_default_generator_is_not_invoked_on_the_production_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """把占位换成会炸的函数：生产路径若还调它，本测立刻红。"""
    def _boom(_spec: SectionSpec, _did: str):  # type: ignore[no-untyped-def]
        raise AssertionError("生产路径调用了占位生成器 _default_generator")

    monkeypatch.setattr(compose_mod, "_default_generator", _boom)
    deps = _deps(_replay_provider({"blocks": [
        {"type": "paragraph", "text": "真正文", "fact_ids": ["fact-1"]},
    ]}))
    blocks = draft_section_with_channels(
        SPEC, _ledger(["fact-1"]),
        deps.generator_factory(SPEC, "del-asm01"),
        entries_by_id={}, profile=deps.profile,
    )
    assert [b.type for b in blocks] == ["paragraph"]


# ── 装配面其余不变量 ──────────────────────────────────────────────

def test_deps_is_the_frozen_compose_deps_shape() -> None:
    """装配返回的就是 compose.py 既有的 ComposeDeps（NEVER 另立一份形状）。"""
    deps = _deps(_replay_provider({"blocks": []}))
    assert isinstance(deps, compose_mod.ComposeDeps)
    assert deps.dsn == DSN
    assert deps.now == NOW
    assert deps.template_path.exists()


def test_prompt_text_comes_from_locked_prompt_file() -> None:
    """prompt 取自 prompts/section_draft@1.md 且过 lock 校验，NEVER 内嵌一份副本。"""
    from flint.llm.prompts import load_prompt
    expected = load_prompt(REPO / "prompts", "section_draft@1", enforce_lock=True).text
    provider = _replay_provider({"blocks": []})
    deps = build_production_compose_deps(
        dsn=DSN, repo_root=REPO, profile=_profile(), now=NOW, provider=provider,
    )
    seen: list[str] = []

    class _Spy:
        def generate(self, prompt: str, tools: object) -> object:
            raise AssertionError("unused")

        def generate_structured(
            self, prompt: str, schema: object, max_retries: int
        ) -> dict[str, object]:
            seen.append(prompt)
            return {"blocks": []}

    spy_deps = build_production_compose_deps(
        dsn=DSN, repo_root=REPO, profile=_profile(), now=NOW,
        provider=_Spy(),  # type: ignore[arg-type]
    )
    spy_deps.generator_factory(SPEC, "del-asm01")([])
    assert seen and seen[0].startswith(expected), (
        "生成 prompt 的开头不是 section_draft@1 的正文"
    )
    assert deps.generator_factory is not spy_deps.generator_factory
