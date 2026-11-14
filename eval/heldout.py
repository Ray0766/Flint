"""held-out 题库装载器（owner 投放 v1.0；loader_contract 执行体）。

- 题库文件 assets/heldout_questions.yaml 是 **owner 侧只读输入**：工作 AI
  NEVER 增删改题目、NEVER 提升 bank_version、NEVER 从中派生任何组稿提示
  词内容；需要改题 → 按 S9 上报 owner。
- loader_contract 四断言（tests/m4/test_heldout_bank.py 全部先落失败测
  试）：① (template_id, section_id) 覆盖与六套模板完全一致（43 对，缺一
  或多一即错）；② 题 id 全局唯一（改题面须升 bank_version，id 不原地改
  写——历史留痕据 id 对齐）；③ 题面与全部模板 check_questions 零交集；
  ④ 本文件 NEVER 被组稿路径读取——取题函数与组稿注入路径分离不共用。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from eval.doc_metrics import TEMPLATES
from flint.compose.templates import load_template

DEFAULT_BANK_PATH = Path(__file__).resolve().parents[1] / "assets" / (
    "heldout_questions.yaml"
)

_TEMPLATE_IDS = (
    "generic", "thesis", "startup", "engineering", "grant", "vibe_pack",
)


class HeldoutBankError(Exception):
    pass


@dataclass(frozen=True)
class HeldoutQuestion:
    qid: str
    q: str


@dataclass(frozen=True)
class HeldoutBank:
    bank_version: str
    questions: dict[tuple[str, str], list[HeldoutQuestion]]

    def for_section(
        self, template_id: str, section_id: str
    ) -> list[HeldoutQuestion]:
        return self.questions.get((template_id, section_id), [])


def _template_pairs_and_pool(
    templates_dir: Path,
) -> tuple[set[tuple[str, str]], set[str]]:
    pairs: set[tuple[str, str]] = set()
    pool: set[str] = set()
    for template_id in _TEMPLATE_IDS:
        spec, sections = load_template(templates_dir / f"{template_id}.yaml")
        for section_id, _ratio in spec.sections:
            pairs.add((template_id, section_id))
        for section in sections:
            pool.update(section.check_questions)
    return pairs, pool


def load_heldout_bank(
    path: Path = DEFAULT_BANK_PATH,
    templates_dir: Path = TEMPLATES,
) -> HeldoutBank:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    templates = raw.get("templates")
    if not isinstance(templates, dict):
        raise HeldoutBankError('bank file must carry a "templates" mapping')
    bank_version = str(raw.get("bank_version", ""))

    questions: dict[tuple[str, str], list[HeldoutQuestion]] = {}
    seen_ids: set[str] = set()
    for template_id, sections in templates.items():
        if not isinstance(sections, dict):
            raise HeldoutBankError(f"{template_id}: sections must be a mapping")
        for section_id, items in sections.items():
            if not isinstance(items, list) or not items:
                raise HeldoutBankError(
                    f"{template_id}/{section_id}: non-empty question list "
                    "required"
                )
            entries: list[HeldoutQuestion] = []
            for item in items:
                qid = str(item["id"])
                if qid in seen_ids:
                    raise HeldoutBankError(f"duplicate question id: {qid}")
                seen_ids.add(qid)
                entries.append(HeldoutQuestion(qid=qid, q=str(item["q"])))
            questions[(str(template_id), str(section_id))] = entries

    template_pairs, template_pool = _template_pairs_and_pool(templates_dir)
    bank_pairs = set(questions)
    missing = sorted(f"{t}/{s}" for t, s in template_pairs - bank_pairs)
    extra = sorted(f"{t}/{s}" for t, s in bank_pairs - template_pairs)
    if missing or extra:
        raise HeldoutBankError(
            f"bank coverage mismatch: missing={missing} extra={extra} "
            f"(contract: exactly {len(template_pairs)} pairs)"
        )
    leaked = sorted(
        hq.q
        for entries in questions.values()
        for hq in entries
        if hq.q in template_pool
    )
    if leaked:
        raise HeldoutBankError(
            "held-out bank intersects template check_questions "
            f"(exam leakage): {leaked}"
        )
    return HeldoutBank(bank_version=bank_version, questions=questions)
