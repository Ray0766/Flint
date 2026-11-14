"""M3-061 文书金标生成器（生成器直出真值判例：M1-039 / M2-044 延伸）。

- 12 样例：五套人类模板 ×2 变体（plain：仅 Fact 通道；channels：三通道
  并用）+ vibe_pack ×2（plain / channels）。
- expected 由构造直出：章节结构 = 模板声明序；通道清单 = 变体规格注入的
  引用集；保护位 = declaration 恒锁。生成器仅 import 标准库 + 模板资产
  读取（不跑组稿引擎——反循环标注）。
运行：python -m fixtures._generate_golddocs（写 assets/golddocs/golddocs.json）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = REPO_ROOT / "assets" / "templates"
OUT = REPO_ROOT / "assets" / "golddocs" / "golddocs.json"

TEMPLATE_IDS = ["generic", "thesis", "startup", "engineering", "grant", "vibe_pack"]


def _sections(template_id: str) -> list[str]:
    payload = yaml.safe_load(
        (TEMPLATES / f"{template_id}.yaml").read_text(encoding="utf-8")
    )
    return [str(s["section_id"]) for s in payload["sections"]]


def build_sample(template_id: str, variant: str) -> dict[str, Any]:
    sections = _sections(template_id)
    facts = [f"fact-{template_id}-{i}" for i in range(1, 3)]
    price_entries = ["pe-compute-01"] if variant == "channels" else []
    profile_paths = ["identity.org"] if variant == "channels" else []
    return {
        "sample_id": f"golddoc-{template_id}-{variant}",
        "template_id": template_id,
        "variant": variant,
        "audience": "ai_executor" if template_id == "vibe_pack" else "human_reader",
        "facts": facts,
        "price_entries": price_entries,
        "profile_paths": profile_paths,
        "expected": {
            "sections": sections,
            "channel_manifest": {
                "facts": facts,
                "price_entries": price_entries,
                "profile_paths": profile_paths,
            },
            "declaration_locked": True,
        },
    }


def build() -> dict[str, Any]:
    return {
        "version": 1,
        "generated_by": "fixtures/_generate_golddocs.py",
        "samples": [
            build_sample(template_id, variant)
            for template_id in TEMPLATE_IDS
            for variant in ("plain", "channels")
        ],
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(build(), ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
