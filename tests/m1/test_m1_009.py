"""M1-009 acceptance tests: first fixture batch for the four trend sources.

Acceptance (tasks.json M1-009):
  - the replay loader can load every sample
  - samples include one rate-limit and one failure scenario (per source)
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from flint.testing.replay import HttpReplay, load_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "fixtures"
SOURCES = ["gtrends", "weibo", "ghtrend", "arxiv"]
NORMAL_DAYS = [date(2026, 7, 23), date(2026, 7, 24), date(2026, 7, 25)]


def all_sample_files(source_id: str) -> list[Path]:
    # **排掉 provenance manifest**：它与夹具住在同一个目录、同样是 .json，
    # 而它不是一次录下来的往返（字段是 fetched_at / content_sha256）。
    # `CN-06` 真录一次之后这里当场 TypeError——manifest 被当成样本喂给了加载器。
    files = sorted(p for p in (FIXTURE_ROOT / source_id).glob("*.json")
                   if not p.name.endswith(".provenance.json"))
    assert files, f"no fixture files for {source_id}"
    return files


def test_each_source_has_at_least_three_normal_days() -> None:
    for src in SOURCES:
        for day in NORMAL_DAYS:
            path = FIXTURE_ROOT / src / f"{day.isoformat()}.json"
            assert path.is_file(), f"missing {path}"
            exchanges = load_fixture(path)
            assert exchanges, f"empty fixture {path}"
            assert all(e.status_code == 200 for e in exchanges), (
                f"normal-day fixture {path} must contain only 200 responses"
            )


def test_replay_loader_loads_every_sample() -> None:
    total = 0
    for src in SOURCES:
        for path in all_sample_files(src):
            exchanges = load_fixture(path)
            assert exchanges, f"empty fixture {path}"
            # the file must also be mountable by the replay session
            with HttpReplay(path, mode="replay"):
                pass
            total += 1
    assert total >= 4 * 5, "expected >=5 sample days per source (3 normal + 429 + 5xx)"


def test_rate_limit_scenario_present_per_source() -> None:
    for src in SOURCES:
        statuses = [
            e.status_code for path in all_sample_files(src) for e in load_fixture(path)
        ]
        assert 429 in statuses, f"{src}: no rate-limit (429) sample recorded"


def test_failure_scenario_present_per_source() -> None:
    for src in SOURCES:
        statuses = [
            e.status_code for path in all_sample_files(src) for e in load_fixture(path)
        ]
        assert any(s >= 500 for s in statuses), f"{src}: no failure (5xx) sample recorded"


def test_payload_shapes_match_each_source() -> None:
    """Raw bodies keep each source's native shape so the M1-011..014 adapters
    parse realistic input, not idealized JSON."""
    gtrends = load_fixture(FIXTURE_ROOT / "gtrends" / "2026-07-23.json")[0]
    # CN-04 / DEC-054：这一条原来断言的是 `)]}'` 反劫持前缀——**那是旧 dailytrends
    # 的形状**，而那个端点已被 Google 下线（实测 404）。新端点回的是 RSS，
    # 没有那个前缀。判据跟着真实契约走：形状从「JSON 带前缀」换成「RSS 带 ht: 命名空间」，
    # 而这一条要守的东西一字未变——**夹具保留每一源自己的原生形状**，
    # 好让适配器解析的是真实输入，不是一份理想化的 JSON。
    assert gtrends.body_text.startswith("<?xml"), "gtrends keeps its native RSS shape"
    assert "ht:approx_traffic" in gtrends.body_text, (
        "gtrends 的热度字段是 ht:approx_traffic（区间下界，DEC-054）")
    assert ")]}'" not in gtrends.body_text, "旧的反劫持前缀 NEVER 再出现"
    # 条目容器：旧契约是 JSON 的 "trendingSearches"，新契约是 RSS 的 <item>。
    # 判的仍是「这份夹具里真的有一批条目」，不是「它长成某个具体的 JSON 键」。
    assert gtrends.body_text.count("<item>") >= 10

    weibo = load_fixture(FIXTURE_ROOT / "weibo" / "2026-07-23.json")[0]
    assert weibo.body_text.count('class="td-02"') >= 50, "weibo board carries >=50 rows"

    ghtrend = load_fixture(FIXTURE_ROOT / "ghtrend" / "2026-07-23.json")[0]
    assert '"full_name"' in ghtrend.body_text
    assert '"topics"' in ghtrend.body_text
    assert '"description"' in ghtrend.body_text

    arxiv = load_fixture(FIXTURE_ROOT / "arxiv" / "2026-07-23.json")[0]
    assert "<feed" in arxiv.body_text
    assert arxiv.body_text.count("<entry>") >= 10
