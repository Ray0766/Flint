"""TS-002：Origin 五类创建 + combo 校验 + Origin→TopicSeed（照冻结件）。

- combo 校验（[D1-a] + owner 裁 #2/#3）：card_ids 数目 2~5、每卡 ∈ evidence_cards、
  hypothesis 必填；**跨簇组合允许**（关联假设=跨热点联想，NEVER 限同簇）。
- 非 combo（idea/domain/competitor/document）各自 payload；seed keywords 留空待
  TS-003 抽取器（LLM）填。
- combo→seed：keywords 取所选卡 keyword_ids→canonical 去重、hypothesis 透传、
  context_text 据入口。校验/解析 NEVER 联网、NEVER 造数据——只读既有 evidence_cards/
  keywords 真实行。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Protocol, cast, get_args

import asyncpg

from flint.domain.models import JSON, Origin, OriginKind, Principal, TopicSeed
from flint.topic.cards_context import CardFacts, card_day_from_id

_COMBO_MIN = 2
_COMBO_MAX = 5


class OriginValidationError(ValueError):
    """入口创建/校验违规（越界、缺假设、未知卡、缺字段）。"""


class CardCatalog(Protocol):
    """证据卡目录（存在性 + keyword 解析），供 combo 校验与 seed 派生注入。"""

    async def existing(self, card_ids: list[str]) -> set[str]: ...

    async def keywords_of(self, card_ids: list[str]) -> list[str]: ...


def parse_kind(raw: str) -> OriginKind:
    """边界解析：raw 须 ∈ OriginKind 五类，否则拒（API 入口用）。"""
    if raw in get_args(OriginKind):
        return cast(OriginKind, raw)
    raise OriginValidationError(f"unknown origin kind {raw!r}")


def _require_str(payload: JSON, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise OriginValidationError(f"{key} required (non-empty str)")
    return value


async def create_origin(
    *,
    origin_id: str,
    kind: OriginKind,
    owner: Principal,
    payload: JSON,
    created_at: datetime,
    catalog: CardCatalog | None = None,
) -> Origin:
    if kind == "combo":
        card_ids = payload.get("card_ids")
        if not isinstance(card_ids, list) or not all(
            isinstance(c, str) for c in card_ids
        ):
            raise OriginValidationError("combo card_ids must be list[str]")
        if not _COMBO_MIN <= len(card_ids) <= _COMBO_MAX:
            raise OriginValidationError(
                f"combo card_ids count {len(card_ids)} out of {_COMBO_MIN}~{_COMBO_MAX}"
            )
        hypothesis = _require_str(payload, "hypothesis")
        if catalog is None:
            raise OriginValidationError("combo requires a card catalog")
        found = await catalog.existing(card_ids)
        missing = [c for c in card_ids if c not in found]
        if missing:
            raise OriginValidationError(f"unknown card_ids {missing}")
        # 跨簇组合允许：NEVER 校验同簇（#3 关联假设=跨热点联想）
        norm: JSON = {"card_ids": list(card_ids), "hypothesis": hypothesis}
    elif kind == "idea":
        norm = {"text": _require_str(payload, "text")}
    elif kind == "domain":
        category = payload.get("category_id")
        text = payload.get("text")
        has_cat = isinstance(category, str) and bool(category.strip())
        has_text = isinstance(text, str) and bool(text.strip())
        if not has_cat and not has_text:
            raise OriginValidationError("domain requires category_id or text")
        norm = {}
        if has_cat:
            norm["category_id"] = category
        if has_text:
            norm["text"] = text
    elif kind == "competitor":
        norm = {
            "name": _require_str(payload, "name"),
            "url": _require_str(payload, "url"),
        }
    else:  # document（OriginKind 已穷尽，此支即 document）
        norm = {"file_ref": _require_str(payload, "file_ref")}
    return Origin(
        origin_id=origin_id, kind=kind, owner=owner, payload=norm,
        created_at=created_at,
    )


def _context_of(origin: Origin) -> str:
    payload = origin.payload
    if origin.kind == "idea":
        return str(payload["text"])
    if origin.kind == "domain":
        return str(payload.get("category_id") or payload.get("text"))
    if origin.kind == "competitor":
        return f'{payload["name"]}\n{payload["url"]}'
    return str(payload["file_ref"])  # document


async def origin_to_seed(
    *, seed_id: str, origin: Origin, catalog: CardCatalog | None = None
) -> TopicSeed:
    if origin.kind == "combo":
        if catalog is None:
            raise OriginValidationError("combo seed requires a card catalog")
        card_ids = [str(c) for c in origin.payload["card_ids"]]
        keywords = await catalog.keywords_of(card_ids)
        hypothesis = str(origin.payload["hypothesis"])
        context_text = f"关联假设：{hypothesis}"
        return TopicSeed(
            seed_id=seed_id, origin_id=origin.origin_id, keywords=keywords,
            hypothesis=hypothesis, context_text=context_text,
        )
    # 非 combo：keywords 留空，待 TS-003 抽取器（LLM）填
    return TopicSeed(
        seed_id=seed_id, origin_id=origin.origin_id, keywords=[],
        hypothesis=None, context_text=_context_of(origin),
    )


class PgCardCatalog:
    """CardCatalog 的 PG 实现——只读既有 evidence_cards / keywords 真实行。"""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def existing(self, card_ids: list[str]) -> set[str]:
        conn = await asyncpg.connect(self._dsn)
        try:
            rows = await conn.fetch(
                "SELECT card_id FROM evidence_cards WHERE card_id = ANY($1::text[])",
                card_ids,
            )
        finally:
            await conn.close()
        return {str(r["card_id"]) for r in rows}

    async def keywords_of(self, card_ids: list[str]) -> list[str]:
        conn = await asyncpg.connect(self._dsn)
        try:
            rows = await conn.fetch(
                "SELECT keyword_ids FROM evidence_cards "
                "WHERE card_id = ANY($1::text[]) ORDER BY card_id",
                card_ids,
            )
            ordered_ids: list[str] = []
            seen_ids: set[str] = set()
            for r in rows:
                for kid in json.loads(r["keyword_ids"]):
                    if kid not in seen_ids:
                        seen_ids.add(kid)
                        ordered_ids.append(str(kid))
            if not ordered_ids:
                return []
            krows = await conn.fetch(
                "SELECT keyword_id, canonical FROM keywords "
                "WHERE keyword_id = ANY($1::text[])",
                ordered_ids,
            )
        finally:
            await conn.close()
        canonical = {str(r["keyword_id"]): str(r["canonical"]) for r in krows}
        out: list[str] = []
        seen_c: set[str] = set()
        for kid in ordered_ids:
            name = canonical.get(kid)
            if name and name not in seen_c:
                seen_c.add(name)
                out.append(name)
        return out

    async def contents_of(self, card_ids: list[str]) -> list[CardFacts]:
        """BL-02：每张卡**各自**的关键词与日期（`keywords_of` 给的是全批去重后的一份）。

        两者不能互相替代：`{cards}` 要的是「哪张卡里有什么」，
        混成一份清单之后，模型就无从知道某个词属于哪一张卡——而 why_now 的
        每条证据 MUST 指到具体一张卡。

        顺序照 `card_ids` 给的来，缺行的卡**照样出现**（`texts` 空）：
        悄悄少一行会让上层以为那张卡不在集合里。
        """
        conn = await asyncpg.connect(self._dsn)
        try:
            rows = await conn.fetch(
                "SELECT card_id, keyword_ids FROM evidence_cards "
                "WHERE card_id = ANY($1::text[])",
                card_ids,
            )
            by_card = {str(r["card_id"]): list(json.loads(r["keyword_ids"])) for r in rows}
            wanted = sorted({str(k) for ids in by_card.values() for k in ids})
            krows = (
                await conn.fetch(
                    "SELECT keyword_id, canonical FROM keywords "
                    "WHERE keyword_id = ANY($1::text[])",
                    wanted,
                )
                if wanted
                else []
            )
        finally:
            await conn.close()
        canonical = {str(r["keyword_id"]): str(r["canonical"]) for r in krows}
        return [
            CardFacts(
                card_id=cid,
                texts=[
                    canonical[str(k)] for k in by_card.get(cid, []) if str(k) in canonical
                ],
                day=card_day_from_id(cid),
            )
            for cid in card_ids
        ]
