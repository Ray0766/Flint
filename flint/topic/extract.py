"""TS-003：非 combo 入口关键词抽取器（LLMProvider 注入、prompt 版本化）。

- idea/domain/competitor/document 入口的上下文 → keywords（combo 走 TS-002 卡派生，
  不经此层）。模型无关：注入 LLMProvider，V1 默认免费档 qwen3.6（适配器后）。
- prompt 版本化 prompts/keyword_extract@1.md（enforce_lock 装载，就地改动被拒）。
- 结构化输出主路 tool use + schema 校验，失败回喂重试 ≤2（S2-3）；仍败
  StructuredOutputExhausted 传播（job failed），NEVER 猜测兜底（第三铁律）。
- 无词（全空/去重后空）→ KeywordExtractionError，NEVER 造词。
- CI 离线：真机 qwen3.6 = 资源触点，测试全用合成 provider。
"""
from __future__ import annotations

from pathlib import Path
from typing import Final

from flint.domain.models import JSON, TopicSeed
from flint.domain.protocols import LLMProvider
from flint.llm.prompts import load_prompt

PROMPTS_DIR: Final[Path] = Path(__file__).resolve().parents[2] / "prompts"
KEYWORD_PROMPT_NAME: Final[str] = "keyword_extract@1"

KEYWORD_SCHEMA: Final[JSON] = {
    "type": "object",
    "properties": {
        "keywords": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        }
    },
    "required": ["keywords"],
    "additionalProperties": False,
}


class KeywordExtractionError(Exception):
    """抽取产出为空（去重/去空后无词）——NEVER 造词，上报 job failed。"""


def _dedupe_strip(raw: list[object]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        word = str(item).strip()
        if word and word not in seen:
            seen.add(word)
            out.append(word)
    return out


def extract_keywords(
    provider: LLMProvider,
    context_text: str,
    *,
    max_retries: int = 2,
    prompts_dir: Path | None = None,
) -> list[str]:
    directory = prompts_dir or PROMPTS_DIR
    prompt = load_prompt(directory, KEYWORD_PROMPT_NAME, enforce_lock=True)
    payload = provider.generate_structured(
        prompt.text.replace("{context}", context_text), KEYWORD_SCHEMA, max_retries
    )
    keywords = _dedupe_strip(list(payload["keywords"]))
    if not keywords:
        raise KeywordExtractionError(
            "keyword extractor produced no keywords (NEVER 造词, job failed)"
        )
    return keywords


def seed_with_keywords(
    provider: LLMProvider,
    seed: TopicSeed,
    *,
    max_retries: int = 2,
    prompts_dir: Path | None = None,
) -> TopicSeed:
    """非 combo seed（TS-002 留空 keywords）→ 回填抽取词，其余字段不变。"""
    keywords = extract_keywords(
        provider, seed.context_text, max_retries=max_retries, prompts_dir=prompts_dir
    )
    return TopicSeed(
        seed_id=seed.seed_id,
        origin_id=seed.origin_id,
        keywords=keywords,
        hypothesis=seed.hypothesis,
        context_text=seed.context_text,
    )
