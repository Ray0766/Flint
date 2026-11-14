"""生产组稿装配（ASM-01）：把真 LLM 生成器接进 compose 主链。

## 为什么要新开一个文件

`flint/jobs/compose.py` 的 `build_offline_compose_deps` 名字里就写着 offline，它绑的
`_default_generator` 只产一个 heading、正文是 `section_id` 字面量——那是离线确定性用途
的桩，NEVER 删也 NEVER 改。但它此前是全仓**唯一**的 `generator_factory=` 赋值点，于是
真跑一次组稿只能得到占位标题（steward 2026-08-03 实测，`docs/steward/项目实况报告
-2026-08-03.md#四`）。真生成器 `llm_generator_factory` 当时只接在单块重生成路径。

本模块是生产侧的装配入口：`generator_factory` 绑 `llm_generator_factory`，prompt 取自
锁定的 `prompts/section_draft@1.md`，模板取自 `assets/templates/`。

## 缺件一律抛，NEVER 静默回落

provider 缺失时**显式抛 `ComposeProviderMissing`**。静默回落到占位生成器正是上述缺陷的
根因：作业会「成功」，产物看着有结构，正文却是 section_id——失败信号被吃掉了。模板文件
缺失同理（抛 `FileNotFoundError` 并点名文件）。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from flint.compose.llm_generator import llm_generator_factory
from flint.domain.models import UserProfile
from flint.domain.protocols import LLMProvider
from flint.jobs.compose import ComposeDeps
from flint.llm.prompts import load_prompt

SECTION_PROMPT_NAME = "section_draft@1"
DEFAULT_TEMPLATE_NAME = "generic.yaml"


class ComposeProviderMissing(RuntimeError):
    """生产组稿装配缺 provider。NEVER 被 build_production_compose_deps 之外的路径吞掉。"""


def build_production_compose_deps(
    *,
    dsn: str,
    repo_root: Path,
    profile: UserProfile,
    now: datetime,
    provider: LLMProvider | None,
    template_name: str = DEFAULT_TEMPLATE_NAME,
    guidance: str | None = None,
    aligner_provider: LLMProvider | None = None,
) -> ComposeDeps:
    """装出生产 ComposeDeps：generator_factory 绑真 LLM 生成器。

    provider=None → 抛 ComposeProviderMissing（缺件不静默）。
    模板文件不存在 → 抛 FileNotFoundError 并点名文件（同上）。
    aligner_provider 留 None = 走 compose.py 既有的离线确定性对齐（CI 恒此路，M4-039）。
    """
    if provider is None:
        raise ComposeProviderMissing(
            "生产组稿装配缺 provider：需要一个 LLMProvider（免费档 LocalProvider / "
            "录制回放 provider 均可）。拒绝回落到离线占位生成器——占位只产 heading，"
            "回落会让作业「成功」而正文是 section_id 字面量。"
        )
    template_path = repo_root / "assets" / "templates" / template_name
    if not template_path.is_file():
        raise FileNotFoundError(
            f"组稿模板不存在：{template_name}（找的是 {template_path}）。"
            f"可用模板见 {repo_root / 'assets' / 'templates'}。"
        )
    prompt_text = load_prompt(
        repo_root / "prompts", SECTION_PROMPT_NAME, enforce_lock=True
    ).text
    return ComposeDeps(
        dsn=dsn,
        template_path=template_path,
        profile=profile,
        now=now,
        generator_factory=llm_generator_factory(provider, prompt_text, guidance),
        aligner_provider=aligner_provider,
    )
