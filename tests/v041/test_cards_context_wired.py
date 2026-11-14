"""BL-02：生产 combo 路径填 `{cards}` 强接地（此前只有 harness 走通）。

## 缝在哪

`generate_topic(..., cards_context: str = "")` 的参数**早就在**，`{cards}` 占位也在
提示词里。缺的是接线：`orchestrate_combo` 一路默认空串，于是生产路径上
`{cards}` 被替换成**空**——@2 提示词那一句「以下是被引卡的真实内容与日期」
后面跟着一片空白。

**空串与没接线长得一模一样**：模型照常生成，校验器照常判，只是模型手上从来没有
卡的真实内容，所谓强接地退化成无接地。harness（`topic_caliber.py`）走的是另一条
自己拼上下文的路，所以它一直是绿的——**两条路分叉，绿的那条不是生产那条**。

## 接不到卡要出声

卡面原话：「接不到卡时**显式报出「无可用证据卡」**并让上层决定，NEVER 用空串静默继续」。
所以 `build_cards_context([])` 抛 `NoUsableEvidenceCards`，由 API 层决定怎么答复——
静默继续等于把「没有证据」写成「有证据但模型没引」，两者的处置完全不同。
"""
from __future__ import annotations

import asyncio
import inspect
import os
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from flint.domain.models import JSON, Principal, TopicSeed
from flint.embed import DeterministicHashBackend, EmbeddingService
from flint.topic.cards_context import (
    CardFacts,
    NoUsableEvidenceCards,
    build_cards_context,
    card_day_from_id,
)
from flint.topic.generate import TOPIC_PROMPT_NAME, generate_topic
from flint.topic.orchestrate import orchestrate_combo

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
PROMPTS = REPO_ROOT / "prompts"
TS = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
OWNER = Principal(kind="user", id="u-1")
SEED = TopicSeed(seed_id="s-1", origin_id="o-1", keywords=["扩散模型"],
                 hypothesis="跨热点联想", context_text="关联假设：跨热点联想")
FACTS = [
    CardFacts(card_id="card-20260715-c1", texts=["扩散模型", "推理成本"],
              day=date(2026, 7, 15)),
    CardFacts(card_id="card-20260716-c2", texts=["端侧推理"], day=date(2026, 7, 16)),
]


class RecordingProvider:
    """把每次收到的**完整提示词**留下来——本卡要断言的正是提示词里那一段。"""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        self.prompts.append(prompt)
        n = len(self.prompts)
        return {
            "one_liner": f"主题方向 {n}",
            "target_user_tag": f"tu-{n}",
            "form_factor_tag": f"ff-{n}",
            "why_now": {
                "claim": "时机",
                "evidences": [{
                    "event": "e", "event_date": "2026-07-01",
                    "citation_id": "card-20260715-c1",
                }],
            },
            "keyword_mapping": {"扩散模型": ["kw"]},
        }


def _embed() -> EmbeddingService:
    return EmbeddingService(DeterministicHashBackend(dim=1024))


# ───────────────────────── 上下文怎么拼


def test_the_context_carries_the_real_texts_and_dates() -> None:
    """acceptance②：卡的**真实内容与日期**都在串里。"""
    context = build_cards_context(FACTS)

    assert "card-20260715-c1" in context
    assert "扩散模型" in context and "推理成本" in context
    assert "2026-07-15" in context
    assert "2026-07-16" in context


def test_every_card_gets_its_own_line_in_the_given_order() -> None:
    """一卡一行，顺序照给定的来——顺序变了，模型引的「第一张卡」就不是同一张。"""
    lines = build_cards_context(FACTS).split("\n")

    assert len(lines) == 2
    assert lines[0].startswith("card-20260715-c1")
    assert lines[1].startswith("card-20260716-c2")


def test_a_card_with_no_text_says_so_instead_of_going_blank() -> None:
    """卡里没内容就**明写**，NEVER 留一个只有 id 的空壳。

    空壳会让模型以为那张卡的内容是空的，进而放开手编——而真相是这一侧没读到。
    """
    line = build_cards_context([CardFacts(card_id="card-1", texts=[], day=None)])

    assert "card-1" in line
    assert "内容缺失" in line


def test_a_card_without_a_parsable_day_shows_an_empty_date_not_a_guess() -> None:
    """日期解不出就留空，**NEVER 拿今天顶上**——那会让模型把今天写成事件发生日。"""
    line = build_cards_context([CardFacts(card_id="odd-id", texts=["x"], day=None)])

    assert "日期 " in line
    assert "2026" not in line


def test_no_cards_at_all_is_an_explicit_error() -> None:
    """acceptance③：接不到卡 → **显式报出**，让上层决定。"""
    with pytest.raises(NoUsableEvidenceCards) as err:
        build_cards_context([])

    assert "无可用证据卡" in str(err.value)


def test_the_error_is_not_raised_when_at_least_one_card_has_text() -> None:
    """阴性对照：有一张能用就照常拼——**NEVER 因为另一张空就整批拒**。"""
    facts = [CardFacts("card-1", [], None), CardFacts("card-2", ["有内容"], None)]

    assert "有内容" in build_cards_context(facts)


# ───────────────────────── 日期从 card_id 里读


@pytest.mark.parametrize(
    ("card_id", "expected"),
    [
        ("card-20260715-c1", date(2026, 7, 15)),
        ("card-20260101-cluster-9", date(2026, 1, 1)),
        ("card-2026071-c1", None),          # 位数不对
        ("card-20261315-c1", None),         # 13 月
        ("kaart-20260715-c1", None),        # 前缀不对
        ("card-abcdefgh-c1", None),
    ],
)
def test_card_day_from_id(card_id: str, expected: date | None) -> None:
    """`evidence_cards` 表里**没有** day 列，日期编码在 card_id 上（`card-YYYYMMDD-…`）。

    解不出返回 None，而不是抛——一张 id 形状不同的卡不该让整批生成失败。
    """
    assert card_day_from_id(card_id) == expected


# ───────────────────────── 接线：编排器 → 生成器 → 提示词


def _run(cards_context: str, prompt_name: str) -> RecordingProvider:
    provider = RecordingProvider()
    counter = {"n": 0}

    def ids() -> tuple[str, str]:
        counter["n"] += 1
        return (f"t-{counter['n']}", f"gr-{counter['n']}")

    orchestrate_combo(
        provider, SEED, _embed(), id_factory=ids,
        allowed_citation_ids={"card-20260715-c1"}, model="m", job_id="j",
        ts=TS, project_id="p-1", owner=OWNER, target=5,
        cards_context=cards_context, prompt_name=prompt_name,
    )
    return provider


def test_the_orchestrator_passes_the_context_all_the_way_into_the_prompt() -> None:
    """acceptance①：生产编排器把 `cards_context` 一路送到 `{cards}` 占位。"""
    provider = _run(build_cards_context(FACTS), "topic_gen@2")

    assert provider.prompts, "一次都没生成"
    for prompt in provider.prompts:
        assert "card-20260715-c1" in prompt
        assert "2026-07-15" in prompt
        assert "{cards}" not in prompt, "占位没被替换"


def test_every_generation_in_the_batch_gets_it_not_just_the_first() -> None:
    """一批里**每一次**生成都要带上——只有第一条带，后面几条就是无接地的。"""
    provider = _run(build_cards_context(FACTS), "topic_gen@2")

    assert len(provider.prompts) >= 5
    assert all("card-20260715-c1" in p for p in provider.prompts)


def test_an_empty_context_is_exactly_the_degradation_this_card_removes() -> None:
    """现状对照：空串时 `{cards}` 变成空操作——**这正是本卡要消掉的那一档**。

    模型照常生成、校验器照常判，只是它手上从来没有卡的真实内容。
    """
    provider = _run("", "topic_gen@2")

    assert all("card-20260715-c1" not in p for p in provider.prompts)


def test_the_generator_itself_still_defaults_to_empty() -> None:
    """`generate_topic` 的默认值没动（本卡只接线，不改既有签名的语义）。"""
    assert inspect.signature(generate_topic).parameters["cards_context"].default == ""


# ───────────────────────── 提示词那一侧的现状


def test_the_at2_prompt_has_the_placeholder_and_at1_does_not() -> None:
    """`{cards}` 只在 @2/@3 里。@1 没有这个占位——**填了也是空操作**。"""
    assert "{cards}" in (PROMPTS / "topic_gen@2.md").read_text(encoding="utf-8")
    assert "{cards}" not in (PROMPTS / "topic_gen@1.md").read_text(encoding="utf-8")


def test_production_still_defaults_to_the_prompt_without_the_placeholder() -> None:
    """**现状登记**：生产默认提示词是 @1，它没有 `{cards}`。

    所以「生产路径强接地」这件事有两半：本卡接的是**上下文**这一半，
    另一半是把默认提示词换成 @2——那要动 `prompts.lock.json` 与口径实测结论，
    属 owner 面（trace §8 登记）。

    这一条在默认值改成 @2 的那天会红，提醒那时的人来更新登记。
    """
    assert TOPIC_PROMPT_NAME == "topic_gen@1"


# ───────────────────────── API 层：接不到卡不静默


def test_the_combo_route_builds_the_context_and_never_passes_an_empty_string() -> None:
    """`flint/api/combo.py` 真的把上下文接进去了（源码面）。

    行为面要一整套 PG 表（cards/keywords/clusters），归 §compose 那条；
    这一条守的是**接线本身还在**——它一旦被删，行为面那条在没有库的机器上是跳过的。
    """
    source = inspect.getsource(__import__("flint.api.combo", fromlist=["x"]))
    code = "\n".join(ln for ln in source.split("\n") if not ln.strip().startswith("#"))

    # 判据是**赋值形状**，不是「文件里有这个词」：变异考里把这一行换成
    # `cards_context = ""` 时，光查词的写法 22 条全绿地放过了它——
    # 而那正是本卡要消掉的那一档（导入行里的同名词把断言喂饱了）。
    assert re.search(r"cards_context\s*=\s*build_cards_context\(", code), "没有真的拼上下文"
    assert re.search(r'cards_context\s*=\s*("")|(\'\')', code) is None, "又退回空串了"
    assert "NoUsableEvidenceCards" in code, "接不到卡时没有显式处置"


def test_the_route_maps_the_no_cards_error_to_a_refusal_not_a_silent_run() -> None:
    """接不到卡 → 返回错误，NEVER 继续跑一次无接地的生成。"""
    source = inspect.getsource(__import__("flint.api.combo", fromlist=["x"]))
    # 从 **except 那一处**往后看，不是从 import 那一处——第一次出现是导入行，
    # 拿它当锚点等于在 import 段里找答复，永远找不到。
    body = source[source.index("except NoUsableEvidenceCards"):]

    assert "_error(" in body[:400], "捕获了却没有答复"
    assert "orchestrate_combo" not in body[:400], "报了错还往下跑"


def test_the_orchestrator_exposes_both_knobs() -> None:
    """编排器把两个旋钮都露出来：上下文与提示词名。

    提示词名不露出来的话，想验证「@2 + 真上下文」只能改默认值——
    而改默认值是 owner 面的事（见上面那条登记）。
    """
    params = inspect.signature(orchestrate_combo).parameters

    assert params["cards_context"].default == ""
    assert params["prompt_name"].default == TOPIC_PROMPT_NAME


# ───────────────────────── 真库：catalog 读得出内容与日期


@pytest.mark.compose
def test_the_pg_catalog_returns_real_texts_and_dates() -> None:
    """`PgCardCatalog.contents_of` 从真表读卡的关键词与日期。

    清理按**前缀**做（`bl02-%`）：整表清空会连带把别的用例的数据删掉，
    这个坑本批已经踩过六次。
    """
    facts = asyncio.run(_read_back())

    assert [f.card_id for f in facts] == ["card-20260715-bl02c1", "card-20260716-bl02c2"]
    assert facts[0].texts == ["扩散模型"]
    assert facts[0].day == date(2026, 7, 15)
    assert facts[1].texts == ["端侧推理"]


async def _read_back() -> list[CardFacts]:
    import asyncpg

    from flint.topic.create import PgCardCatalog

    conn = await asyncpg.connect(DSN)
    try:
        await _seed(conn)
        return await PgCardCatalog(dsn=DSN).contents_of(
            ["card-20260715-bl02c1", "card-20260716-bl02c2"]
        )
    finally:
        await _cleanup(conn)
        await conn.close()


async def _seed(conn: Any) -> None:
    zero = "[" + ",".join(["0"] * 1024) + "]"
    await _cleanup(conn)
    for kid, canon in (("bl02-k1", "扩散模型"), ("bl02-k2", "端侧推理")):
        await conn.execute(
            "INSERT INTO keywords (keyword_id, canonical, lang, embedding, first_seen) "
            f"VALUES ($1, $2, 'zh', '{zero}'::vector, '2026-07-01')",
            kid, canon,
        )
    await conn.execute(
        "INSERT INTO categories (category_id, name) VALUES ('bl02-cat', 'bl02 类目') "
        "ON CONFLICT DO NOTHING"
    )
    await conn.execute(
        "INSERT INTO clusters (cluster_id, canonical_name, category_id, centroid, "
        "status, first_seen, last_active) "
        f"VALUES ('bl02-cl', 'bl02 簇', 'bl02-cat', '{zero}'::vector, 'active', "
        "'2026-07-15', '2026-07-15')"
    )
    for cid, kid in (("card-20260715-bl02c1", "bl02-k1"), ("card-20260716-bl02c2", "bl02-k2")):
        await conn.execute(
            "INSERT INTO evidence_cards (card_id, cluster_id, keyword_ids) "
            "VALUES ($1, 'bl02-cl', $2::jsonb)",
            cid, f'["{kid}"]',
        )


async def _cleanup(conn: Any) -> None:
    await conn.execute("DELETE FROM evidence_cards WHERE card_id LIKE '%bl02%'")
    await conn.execute("DELETE FROM clusters WHERE cluster_id LIKE 'bl02-%'")
    await conn.execute("DELETE FROM keywords WHERE keyword_id LIKE 'bl02-%'")
    await conn.execute("DELETE FROM categories WHERE category_id LIKE 'bl02-%'")
