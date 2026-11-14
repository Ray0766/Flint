"""TS-002：Origin 五类创建 + combo 校验 + Origin→TopicSeed。

combo 校验：card_ids∈evidence_cards、数目 2~5、hypothesis 必填、**跨簇允许**（#3
关联假设=跨热点联想，NEVER 限同簇）。非 combo 四类各自 payload；seed keywords 留空
待 TS-003 抽取。combo seed keywords 取所选卡 keyword_ids→canonical 去重、hypothesis
透传。读端只读既有 evidence_cards/keywords（真实行，零写零污染）。
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from flint.domain.models import Origin, Principal
from flint.topic.create import (
    OriginValidationError,
    PgCardCatalog,
    create_origin,
    origin_to_seed,
    parse_kind,
)

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
OWNER = Principal(kind="user", id="u-1")
CAT = PgCardCatalog(dsn=DSN)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _pick_cross_cluster(n: int) -> list[str]:
    """取 n 张来自 **不同簇** 的真实证据卡（证明跨簇组合被允许）。"""
    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch(
            "SELECT card_id, cluster_id FROM evidence_cards "
            "WHERE jsonb_array_length(keyword_ids) > 0 ORDER BY card_id"
        )
    finally:
        await conn.close()
    picks: list[str] = []
    used: set[str] = set()
    for r in rows:
        cid = str(r["cluster_id"])
        if cid in used:
            continue
        used.add(cid)
        picks.append(str(r["card_id"]))
        if len(picks) == n:
            break
    if len(picks) < n:
        pytest.skip(f"local PG has <{n} distinct-cluster cards")
    assert len(used) == n  # 每卡来自不同簇 = 跨簇
    return picks


def test_parse_kind_rejects_unknown() -> None:
    assert parse_kind("combo") == "combo"
    for k in ("idea", "domain", "competitor", "document"):
        assert parse_kind(k) == k
    with pytest.raises(OriginValidationError):
        parse_kind("nope")


def test_combo_valid_cross_cluster() -> None:
    cards = run(_pick_cross_cluster(2))
    origin = run(create_origin(
        origin_id="ts-o-combo", kind="combo", owner=OWNER,
        payload={"card_ids": cards, "hypothesis": "跨热点联想一句话"},
        created_at=NOW, catalog=CAT))
    assert isinstance(origin, Origin) and origin.kind == "combo"
    assert origin.payload["card_ids"] == cards
    assert origin.payload["hypothesis"] == "跨热点联想一句话"
    seed = run(origin_to_seed(seed_id="ts-s-combo", origin=origin, catalog=CAT))
    assert seed.origin_id == "ts-o-combo"
    assert seed.hypothesis == "跨热点联想一句话"           # 透传
    assert len(seed.keywords) >= 1                          # 卡 keyword_ids→canonical
    assert len(seed.keywords) == len(set(seed.keywords))   # 去重
    assert "跨热点联想一句话" in seed.context_text


def test_combo_count_out_of_range() -> None:
    one = run(_pick_cross_cluster(1))
    with pytest.raises(OriginValidationError):
        run(create_origin(origin_id="ts-o-1", kind="combo", owner=OWNER,
                          payload={"card_ids": one, "hypothesis": "h"},
                          created_at=NOW, catalog=CAT))
    six = [f"ts-fake-{i}" for i in range(6)]
    with pytest.raises(OriginValidationError):
        run(create_origin(origin_id="ts-o-6", kind="combo", owner=OWNER,
                          payload={"card_ids": six, "hypothesis": "h"},
                          created_at=NOW, catalog=CAT))


def test_combo_missing_hypothesis() -> None:
    cards = run(_pick_cross_cluster(2))
    with pytest.raises(OriginValidationError):
        run(create_origin(origin_id="ts-o-nh", kind="combo", owner=OWNER,
                          payload={"card_ids": cards}, created_at=NOW, catalog=CAT))
    with pytest.raises(OriginValidationError):  # 空白也拒
        run(create_origin(origin_id="ts-o-nh2", kind="combo", owner=OWNER,
                          payload={"card_ids": cards, "hypothesis": "  "},
                          created_at=NOW, catalog=CAT))


def test_combo_unknown_card() -> None:
    good = run(_pick_cross_cluster(1))
    with pytest.raises(OriginValidationError):
        run(create_origin(origin_id="ts-o-uc", kind="combo", owner=OWNER,
                          payload={"card_ids": [good[0], "ts-card-nonexistent"],
                                   "hypothesis": "h"},
                          created_at=NOW, catalog=CAT))


def test_idea_origin_and_seed() -> None:
    origin = run(create_origin(origin_id="ts-o-idea", kind="idea", owner=OWNER,
                               payload={"text": "一个点子"}, created_at=NOW))
    assert origin.kind == "idea" and origin.payload == {"text": "一个点子"}
    seed = run(origin_to_seed(seed_id="ts-s-idea", origin=origin))
    assert seed.keywords == []           # 待 TS-003 抽取
    assert seed.hypothesis is None
    assert seed.context_text == "一个点子"


def test_domain_requires_category_or_text() -> None:
    with pytest.raises(OriginValidationError):
        run(create_origin(origin_id="ts-o-d0", kind="domain", owner=OWNER,
                          payload={}, created_at=NOW))
    origin = run(create_origin(origin_id="ts-o-d", kind="domain", owner=OWNER,
                               payload={"category_id": "cat-ai"}, created_at=NOW))
    seed = run(origin_to_seed(seed_id="ts-s-d", origin=origin))
    assert seed.context_text == "cat-ai" and seed.hypothesis is None


def test_competitor_and_document() -> None:
    comp = run(create_origin(origin_id="ts-o-c", kind="competitor", owner=OWNER,
                             payload={"name": "对手", "url": "https://x.example"},
                             created_at=NOW))
    assert comp.payload == {"name": "对手", "url": "https://x.example"}
    with pytest.raises(OriginValidationError):
        run(create_origin(origin_id="ts-o-c2", kind="competitor", owner=OWNER,
                          payload={"name": "对手"}, created_at=NOW))
    doc = run(create_origin(origin_id="ts-o-doc", kind="document", owner=OWNER,
                            payload={"file_ref": "file-123"}, created_at=NOW))
    seed = run(origin_to_seed(seed_id="ts-s-doc", origin=doc))
    assert seed.context_text == "file-123"
