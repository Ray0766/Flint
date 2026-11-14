"""M1-039 金标生成器：由 fixture 样本池直出血缘真值（owner 指令 2026-07-27）。

原理：30 天回放的每个场景都是本目录生成器构造的——每个关键词的逐日在场
集合完全已知，血缘生命周期真值可直接推导，无需人工/模型判读：
  - 首次在场 -> new；
  - 再次在场且距上次 <=14 天 -> continued；
  - 缺席使某运行日满足 (day - last_active) >= 14 -> 该日 dormant
    （匹配先于休眠判定：恰第 14 天回归按 continued，不出 dormant）；
  - dormant 之后回归（间隔 >=15 天）-> revived；
  - 窗口尾部缺席满 14 天 -> 尾部 dormant。
推导与管线共用同一 canonicalize / 关键词派生函数（规范化行为是被评测
管线的输入约定，非被评测对象；被评测的是血缘五步）。
运行：python -m fixtures._generate_labels（写 assets/labels.yaml）。
"""
from __future__ import annotations

import random
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fixtures._generate_4src import (
    REVIVAL_KEYWORD,
    WEIBO_DEGRADED_DAY,
    _arxiv_titles,
    _gh_repos,
    _gt_queries,
    _wb_words,
)
from flint.jobs.ingest import keyword_id_for
from flint.norm.canonical import canonicalize
from flint.norm.terms import load_term_map
from flint.sources.ghtrend import map_repo_keywords

REPO_ROOT = Path(__file__).resolve().parents[1]
WINDOW_START = date(2026, 6, 24)
WINDOW_END = date(2026, 7, 23)
DORMANT_AFTER_DAYS = 14
SAMPLE_SIZE = 50
SEED = 42


def day_raw_keywords(day: date) -> list[str]:
    raws: list[str] = list(_gt_queries(day))
    if day != WEIBO_DEGRADED_DAY:
        raws.extend(_wb_words(day))
    for name, desc, topics in _gh_repos(day):
        repo = {"full_name": name, "description": desc, "topics": list(topics)}
        raws.extend(k.text for k in map_repo_keywords(repo))
    raws.extend(_arxiv_titles(day))
    return raws


def presence_by_canonical() -> dict[str, tuple[str, list[date]]]:
    """canonical -> (lang, 在场日列表)。"""
    terms = load_term_map(REPO_ROOT / "assets" / "term-map.yaml")
    presence: dict[str, tuple[str, list[date]]] = {}
    day = WINDOW_START
    while day <= WINDOW_END:
        seen_today: set[str] = set()
        for raw in day_raw_keywords(day):
            ck = canonicalize(raw, terms)
            if not ck.canonical or ck.canonical in seen_today:
                continue
            seen_today.add(ck.canonical)
            _, days = presence.setdefault(ck.canonical, (ck.lang, []))
            days.append(day)
        day += timedelta(days=1)
    return presence


def expected_timeline(days_present: list[date]) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    previous: date | None = None
    for day in days_present:
        if previous is None:
            events.append({"day": day.isoformat(), "kind": "new"})
        else:
            gap = (day - previous).days
            if gap >= DORMANT_AFTER_DAYS + 1:
                dormant_day = previous + timedelta(days=DORMANT_AFTER_DAYS)
                events.append({"day": dormant_day.isoformat(), "kind": "dormant"})
                events.append({"day": day.isoformat(), "kind": "revived"})
            else:
                events.append({"day": day.isoformat(), "kind": "continued"})
        previous = day
    assert previous is not None
    tail_dormant = previous + timedelta(days=DORMANT_AFTER_DAYS)
    if tail_dormant <= WINDOW_END:
        events.append({"day": tail_dormant.isoformat(), "kind": "dormant"})
    return events


def main() -> None:
    presence = presence_by_canonical()
    rng = random.Random(SEED)
    pool = sorted(c for c in presence if c != REVIVAL_KEYWORD)
    sampled = [REVIVAL_KEYWORD, *rng.sample(pool, k=SAMPLE_SIZE - 1)]

    clusters = []
    for canonical in sampled:
        lang, days_present = presence[canonical]
        clusters.append(
            {
                "canonical": canonical,
                "keyword_id": keyword_id_for(canonical, lang),
                "expected": expected_timeline(days_present),
            }
        )
    payload = {
        "version": 0,
        "source": "generator-ground-truth",
        "directive": "owner 2026-07-27：金标由 fixture 生成器按构造场景直出",
        "window": {"start": WINDOW_START.isoformat(), "end": WINDOW_END.isoformat()},
        "dormant_after_days": DORMANT_AFTER_DAYS,
        "clusters": clusters,
    }
    out = REPO_ROOT / "assets" / "labels.yaml"
    out.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    print(f"labels written: {out} ({len(clusters)} clusters)")


if __name__ == "__main__":
    main()
