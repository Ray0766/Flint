"""M4-007 acceptance tests: vibe_pack full assembly (S1~S9 + digest).

Acceptance (tasks.json M4-007):
  - nine chapters bound in order + Human Digest attachment kept out of the
    AI-context markdown
  - whole pack passes the S2-8 self-check (banned_word_hits zero)
"""
from __future__ import annotations

import pytest

from flint.compose.vibe_core import (
    assemble_s1_charter,
    assemble_s2_invariants,
    assemble_s4_decisions,
)
from flint.domain.models import TaskSpec
from flint.spec.pack_assemble import (
    PackAssemblyError,
    assemble_pack,
    assemble_s3_contracts,
)
from flint.spec.vibe_s5 import build_s5
from flint.spec.vibe_s6 import build_s6
from flint.spec.vibe_s7 import build_s7
from flint.spec.vibe_s89 import build_s8, build_s9

pytestmark = pytest.mark.compose


def ai_card(task_id: str, depends_on: list[str]) -> TaskSpec:
    return TaskSpec(
        task_id=task_id, title=f"任务 {task_id}", inputs=["repo-skeleton"],
        outputs=[f"mod.{task_id}"], acceptance=["验收一"],
        depends_on=depends_on, milestone="M1", estimate_days=None,
        estimate_cycles=1.0, oneshot=True,
        verify_cmd=f"pytest tests/test_{task_id}.py -q",
        context_refs=["contracts/models.py#TaskSpec"], review_gate=False,
    )


def chapters() -> dict[str, str]:
    tasks = [ai_card("T-1", []), ai_card("T-2", ["T-1"])]
    return {
        "S1": assemble_s1_charter(
            {"goal": "目标一", "non_goals": ["实时热点"], "scope": "M1 全量"}
        ),
        "S2": assemble_s2_invariants(
            [{"kind": "MUST", "rule": "结论必有引用"}]
        ),
        "S3": assemble_s3_contracts(
            pins=["Python 3.11", "FastAPI 0.140"],
            layout="flint/\n  domain/",
        ),
        "S4": assemble_s4_decisions(
            [{"id": "D1", "decision": "多入口 Origin", "source": "M0-决策记录.md"}]
        ),
        "S5": build_s5(tasks).markdown,
        "S6": build_s6(
            tasks, known_anchors=frozenset({"contracts/models.py#TaskSpec"})
        ),
        "S7": build_s7(tasks, global_gate="ruff check . && pytest -q"),
        "S8": build_s8(),
        "S9": build_s9(),
    }


DIGEST = "现在在做什么：M1 数据层。怎么看进度：progress.jsonl 尾部。"


def test_nine_chapters_bound_in_order_digest_kept_out() -> None:
    pack = assemble_pack(chapters(), human_digest=DIGEST)
    positions = [pack.markdown.index(f"## S{i} ") for i in range(1, 10)]
    assert positions == sorted(positions), "S1~S9 strictly in order"
    assert DIGEST not in pack.markdown, "digest never enters AI context"
    assert pack.human_digest == DIGEST


def test_missing_chapter_rejected() -> None:
    partial = chapters()
    del partial["S6"]
    with pytest.raises(PackAssemblyError, match="S6"):
        assemble_pack(partial, human_digest=DIGEST)


def test_wrong_header_rejected() -> None:
    swapped = chapters()
    swapped["S3"] = "## S4 Decision Log\n\n伪装章"
    with pytest.raises(PackAssemblyError, match="S3"):
        assemble_pack(swapped, human_digest=DIGEST)


def test_banned_word_self_check_blocks_pack() -> None:
    dirty = chapters()
    dirty["S4"] = assemble_s4_decisions(
        [{"id": "D9", "decision": "阈值取合理值", "source": "口头"}]
    )
    with pytest.raises(PackAssemblyError) as err:
        assemble_pack(dirty, human_digest=DIGEST)
    assert "合理" in str(err.value) and "S4" in str(err.value)


def test_compound_deng_exempt() -> None:
    clean = chapters()
    clean["S2"] = assemble_s2_invariants(
        [{"kind": "MUST", "rule": "接口保持幂等"}]
    )
    pack = assemble_pack(clean, human_digest=DIGEST)
    assert "幂等" in pack.markdown
