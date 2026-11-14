"""确定性接地校验器（(a)-① 量尺 = 未来 M2 gate）。

对每条 why_now 引用，按三规则判 clean / dirty / unverifiable：
- ① 日期一致：引用的 event_date（及 event 文本中的年份）须落在被引卡时间范围，
  或该年份现于被引卡原文；否则 dirty（日期幻觉）。
- ② 数字必现：event 文本中的数字（%/金额/倍数，年份归 ① 处理）须能在被引卡原文
  找到——归一化 26%↔0.26、去千分位；相对容差 number_tolerance（默认 0=精确）；
  否则 dirty（数字幻觉）。
- ③ 实体必现（可选加严，默认关）：event 文本中的机构/公司专名须现于卡原文，
  否则 flag（不单独升 dirty，除非开启后作证据）。

无引用（speculative 留白）→ unverifiable（诚实留白，NEVER 判 dirty）。
被引卡内容缺失（无法核）→ unverifiable。

纯函数、零依赖、零联网：既是口径量尺（回填「取证干净」列，校验器判非人眼），也是
未来 gate（dirty 处置策略——拒/重试/降级——归 gate 层可配，本模块只判不处置）。

冻结件不动：本模块 NEVER 依赖/修改 contracts；仅消费 WhyNowEvidence 的三字段
（event / event_date / citation_id）的值。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from flint.grounding.cjk_numerals import find_cjk_numerals

Verdict = Literal["clean", "dirty", "unverifiable"]
Rule = Literal["date", "number", "entity"]


@dataclass(frozen=True)
class CardContent:
    """被引卡的可核真相：时间锚点 + 原文语料（canonical 关键词文本拼接）。

    day_from/day_to 为空时，时间范围退化为 [day, day]（card_id 编码的单日锚点）。
    """

    card_id: str
    day: date
    corpus: str
    day_from: date | None = None
    day_to: date | None = None

    def year_range(self) -> tuple[int, int]:
        lo = (self.day_from or self.day).year
        hi = (self.day_to or self.day).year
        return (lo, hi) if lo <= hi else (hi, lo)


@dataclass(frozen=True)
class GroundingConfig:
    number_tolerance: float = 0.0   # 数字相对容差（|a-b|/max(|b|,1) ≤ tol）；默认精确
    check_entity: bool = False      # ③ 实体必现（可选加严），默认关
    year_min: int = 1980            # 年份识别窗（避免把 2 位数误当年）
    year_max: int = 2099


@dataclass(frozen=True)
class RuleFinding:
    rule: Rule
    verdict: Verdict
    detail: str


@dataclass(frozen=True)
class CitationCheck:
    citation_id: str
    verdict: Verdict
    findings: tuple[RuleFinding, ...] = field(default_factory=tuple)
    reason: str = ""


@dataclass(frozen=True)
class TopicGrounding:
    topic_id: str
    verdict: Verdict
    citations: tuple[CitationCheck, ...] = field(default_factory=tuple)


_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
_QTY_UNIT = "%％倍万亿千元＄$"          # 紧跟数字的量词单位 → 判为数量而非年份
# 中文数字（如「二十六%」）走 `cjk_numerals`（BL-01 补）。此前的登记原话是
# 「真实失败态均为阿拉伯数字，本器精确覆盖之」——那描述的是当时见过的失败态，
# 不是保证：模型换一次口径，正文里的中文数字就一个字都不会被查，
# 而**没查到与查过没问题在报告上长得一模一样**。


@dataclass(frozen=True)
class _Number:
    kind: Literal["year", "quantity"]
    raw: str
    value: Decimal | None
    is_percent: bool


def _to_decimal(digits: str) -> Decimal | None:
    try:
        return Decimal(digits.replace(",", ""))
    except InvalidOperation:
        return None


def extract_numbers(text: str, cfg: GroundingConfig) -> list[_Number]:
    """抽取 event 文本中的数字，分类为 year / quantity。

    - 紧跟量词单位（%/倍/万/亿/千/元/$）→ quantity；
    - 4 位纯整数且落在 [year_min, year_max] → year；
    - 其余 → quantity。

    中文数字与阿拉伯数字**同一套分类口径**（BL-01）：分两套的话，
    「二〇二六年」会被当成数量拿去 number 规则里查出处，而它是年份。
    结果按各自在正文里的位置排序——顺序错了，`missing` 清单的读法就变了。
    """
    at: list[tuple[int, _Number]] = []
    for m in _NUM_RE.finditer(text):
        raw = m.group()
        tail = text[m.end():m.end() + 1]
        val = _to_decimal(raw)
        # `tail != ""` 这一半**不能省**：Python 里**空串是任何字符串的子串**，
        # 于是正文以数字结尾（`tail == ""`）时 `"" in "%％"` 与
        # `"" in _QTY_UNIT` **双双为真**。两个后果都是**放松**：
        #
        # 1. `has_unit=True` → 四位年份不再判成 year，落进 quantity。
        #    而 `_check_date` 只收 `kind == "year"`，**日期幻觉那一路少了一个检查项**；
        # 2. `is_percent=True` → `_number_present` 会额外试一次 `value/100`
        #    （26 → 0.26），**一个本不是百分数的数字凭空多了一种「找得到」的方式**。
        #
        # 少查在报告上与「查过了没问题」长得一模一样——这是它难被发现的原因。
        # （同一个坑下面第 155 行 `_cjk_numbers` 那处 BL-01 已经修过，这里漏了。）
        is_percent = tail != "" and tail in "%％"
        has_unit = tail != "" and tail in _QTY_UNIT
        digits = raw.replace(",", "")
        is_year_shape = (
            digits.isdigit()
            and len(digits) == 4
            and val is not None
            and cfg.year_min <= int(digits) <= cfg.year_max
        )
        if is_year_shape and not has_unit:
            at.append((m.start(), _Number(kind="year", raw=raw, value=val, is_percent=False)))
        else:
            at.append((
                m.start(),
                _Number(kind="quantity", raw=raw, value=val, is_percent=is_percent),
            ))
    at.extend(_cjk_numbers(text, cfg))
    at.sort(key=lambda pair: pair[0])
    return [num for _, num in at]


def _cjk_numbers(text: str, cfg: GroundingConfig) -> list[tuple[int, _Number]]:
    """中文数字走同一套 year / quantity 分类（BL-01）。

    分类口径与阿拉伯那条**一字不差**：分两套的话，「二〇二六年」会被当成数量
    拿去 number 规则里查出处，而它是年份。
    """
    out: list[tuple[int, _Number]] = []
    for found in find_cjk_numerals(text):
        tail = text[found.start + len(found.raw):][:1]
        has_unit = tail != "" and tail in _QTY_UNIT     # `"" in ...` 恒 True，见 §BL-01
        is_year_shape = (
            found.value is not None
            and found.value == found.value.to_integral_value()
            and cfg.year_min <= int(found.value) <= cfg.year_max
            and len(found.raw) == 4
        )
        kind: Literal["year", "quantity"] = (
            "year" if is_year_shape and not has_unit and not found.is_percent else "quantity"
        )
        out.append((
            found.start,
            _Number(
                kind=kind,
                raw=found.raw,
                value=found.value,
                is_percent=found.is_percent if kind == "quantity" else False,
            ),
        ))
    return out


def _corpus_numbers(corpus: str) -> list[Decimal]:
    vals: list[Decimal] = []
    for m in _NUM_RE.finditer(corpus):
        v = _to_decimal(m.group())
        if v is not None:
            vals.append(v)
    return vals


def _number_present(num: _Number, card: CardContent, cfg: GroundingConfig) -> bool:
    """数字 num 是否可在被引卡原文找到（归一化 + 容差）。"""
    corpus = card.corpus
    # 候选归一化串：原样、去千分位；百分比再加 26↔0.26 两形。
    bare = num.raw.replace(",", "")
    candidates = {num.raw, bare}
    if num.value is not None:
        candidates.add(str(num.value))
        if num.is_percent:
            candidates.add(str(num.value / 100))   # 26% → 0.26
    if any(c and c in corpus for c in candidates):
        return True
    # 数值容差比对（含百分比的比率形）。
    if num.value is None:
        return False
    targets = [num.value]
    if num.is_percent:
        targets.append(num.value / 100)
    for cv in _corpus_numbers(corpus):
        for t in targets:
            if abs(cv - t) <= Decimal(str(cfg.number_tolerance)) * max(abs(t), Decimal(1)):
                return True
    return False


def _check_date(
    event: str, event_date: date, card: CardContent, cfg: GroundingConfig
) -> RuleFinding:
    lo, hi = card.year_range()
    years = {event_date.year}
    for n in extract_numbers(event, cfg):
        if n.kind == "year" and n.value is not None:
            years.add(int(n.value))
    bad = [
        y for y in sorted(years)
        if not (lo <= y <= hi) and str(y) not in card.corpus
    ]
    if bad:
        return RuleFinding(
            rule="date", verdict="dirty",
            detail=f"年份 {bad} 越出被引卡范围 [{lo},{hi}] 且不在卡原文",
        )
    return RuleFinding(rule="date", verdict="clean", detail=f"年份 ∈ [{lo},{hi}]")


def _check_numbers(event: str, card: CardContent, cfg: GroundingConfig) -> RuleFinding:
    missing = [
        n.raw for n in extract_numbers(event, cfg)
        if n.kind == "quantity" and not _number_present(n, card, cfg)
    ]
    if missing:
        return RuleFinding(
            rule="number", verdict="dirty",
            detail=f"数字 {missing} 不在被引卡原文（疑编造）",
        )
    return RuleFinding(rule="number", verdict="clean", detail="数字均可溯或无数字")


# 机构/公司专名的轻量识别（③ 可选加严）：常见后缀锚定，NEVER 依赖模型。
_ENTITY_RE = re.compile(
    r"[一-鿿]{2,}(?:大学|学院|公司|集团|研究院|研究所|实验室|部|局|中心|协会)"
)


def _check_entity(event: str, card: CardContent) -> RuleFinding:
    missing = [e for e in _ENTITY_RE.findall(event) if e not in card.corpus]
    if missing:
        return RuleFinding(
            rule="entity", verdict="dirty",
            detail=f"专名 {missing} 不在被引卡原文",
        )
    return RuleFinding(rule="entity", verdict="clean", detail="专名均可溯或无专名")


def check_citation(
    event: str,
    event_date: date,
    card: CardContent | None,
    config: GroundingConfig | None = None,
) -> CitationCheck:
    """单条引用三规则校验。card=None（被引卡内容缺失）→ unverifiable。"""
    cfg = config or GroundingConfig()
    if card is None:
        return CitationCheck(
            citation_id="", verdict="unverifiable",
            reason="被引卡内容缺失，无法核验",
        )
    findings = [
        _check_date(event, event_date, card, cfg),
        _check_numbers(event, card, cfg),
    ]
    if cfg.check_entity:
        findings.append(_check_entity(event, card))
    verdict: Verdict = "dirty" if any(f.verdict == "dirty" for f in findings) else "clean"
    reason = "；".join(f.detail for f in findings if f.verdict == "dirty") or "三规则通过"
    return CitationCheck(
        citation_id=card.card_id, verdict=verdict,
        findings=tuple(findings), reason=reason,
    )


def check_topic(
    topic_id: str,
    evidences: list[tuple[str, date, str]],
    cards: dict[str, CardContent],
    config: GroundingConfig | None = None,
) -> TopicGrounding:
    """主题级聚合：无引用→unverifiable；任一 dirty→dirty；有 clean→clean。"""
    if not evidences:
        return TopicGrounding(topic_id=topic_id, verdict="unverifiable")
    checks: list[CitationCheck] = []
    for event, event_date, cid in evidences:
        card = cards.get(cid)
        c = check_citation(event, event_date, card, config)
        checks.append(
            c if card is not None
            else CitationCheck(citation_id=cid, verdict="unverifiable",
                               reason="被引卡不在白名单语料")
        )
    if any(c.verdict == "dirty" for c in checks):
        verdict: Verdict = "dirty"
    elif any(c.verdict == "clean" for c in checks):
        verdict = "clean"
    else:
        verdict = "unverifiable"
    return TopicGrounding(topic_id=topic_id, verdict=verdict, citations=tuple(checks))


def load_card_corpus(path: str | Path) -> dict[str, CardContent]:
    """加载真机冻结的被引卡原文（assets/topic_caliber/card_corpus.json）。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, CardContent] = {}
    for cid, entry in data.items():
        day = date.fromisoformat(str(entry["day"]))
        corpus = " ".join(str(t) for t in entry.get("texts", []))
        out[cid] = CardContent(card_id=cid, day=day, corpus=corpus)
    return out


def grade_asset(
    asset: dict[str, Any],
    cards: dict[str, CardContent],
    config: GroundingConfig | None = None,
) -> dict[str, Any]:
    """对一份录制资产的全部主题跑校验器，产出可回填「取证干净」列的聚合。

    返回 clean/dirty/unverifiable（引用级计数）+ *_topics（主题级计数）+ 逐主题明细。
    """
    topics_out: list[dict[str, Any]] = []
    n_clean = n_dirty = n_unv = 0
    t_clean = t_dirty = t_unv = 0
    for t in asset.get("topics", []):
        evidences: list[tuple[str, date, str]] = [
            (str(e["event"]), date.fromisoformat(str(e["event_date"])),
             str(e["citation_id"]))
            for e in t.get("why_now_evidences", [])
        ]
        tg = check_topic(str(t["topic_id"]), evidences, cards, config)
        for c in tg.citations:
            if c.verdict == "clean":
                n_clean += 1
            elif c.verdict == "dirty":
                n_dirty += 1
            else:
                n_unv += 1
        if tg.verdict == "clean":
            t_clean += 1
        elif tg.verdict == "dirty":
            t_dirty += 1
        else:
            t_unv += 1
        topics_out.append({
            "topic_id": tg.topic_id, "verdict": tg.verdict,
            "citations": list(tg.citations),
        })
    return {
        "model": asset.get("model"),
        "clean": n_clean, "dirty": n_dirty, "unverifiable": n_unv,
        "clean_topics": t_clean, "dirty_topics": t_dirty,
        "unverifiable_topics": t_unv,
        "topics": topics_out,
    }
