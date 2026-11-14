"""M1-009 fixture 生成器：四源首批样本（确定性，可复现——铁律 3）。

每源 5 个日文件：2026-07-23/24/25 正常（200）、07-26 限频（429）、07-27 失败（500）。
载荷保持各源原生形态，供 M1-011~014 适配器解析真实结构：
  gtrends  -> trending/rss?geo=HK 的 RSS XML（CN-04 / DEC-054 换端点；旧 dailytrends 已被 Google 下线）
  weibo    -> s.weibo.com 热搜榜 HTML（50 行，td-01/td-02 结构）
  ghtrend  -> GitHub search API JSON（full_name / topics / description 三来源）
  arxiv    -> export.arxiv.org Atom XML（>=10 entry）

本环境无法对四个真实站点做在线录制（网络与反爬均不可控），样本为按真实响应
形态确定性构造；重录真实数据时直接重跑本脚本的替换版即可，文件布局不变。
运行：python fixtures/_generate_4src.py（幂等覆盖）。
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xml.sax.saxutils import escape

from flint.testing.replay import RecordedExchange, save_fixture

ROOT = Path(__file__).resolve().parent
NORMAL_DAYS = [date(2026, 7, 23), date(2026, 7, 24), date(2026, 7, 25)]
RATE_LIMIT_DAY = date(2026, 7, 26)
FAILURE_DAY = date(2026, 7, 27)

# ── 30 天回放扩展（M1-037）──
# 演化日：2026-06-24 ~ 2026-07-22（29 天）。>= STATIC_FROM 的日子保持
# 首批静态逻辑不变（M1-011~014/035 的既有断言依赖其内容形态）。
STATIC_FROM = date(2026, 7, 23)
EVOLVED_DAYS = [date(2026, 6, 24) + timedelta(days=d) for d in range(29)]
WEIBO_DEGRADED_DAY = date(2026, 7, 5)  # 单源限频日：微博 429、其余照常

# 复活场景：出现 3 天 -> 缺席 18 天（>14 触发 dormant）-> 回归 -> revival
REVIVAL_KEYWORD = "复活测试词"
REVIVAL_PRESENT = {date(2026, 6, 24) + timedelta(days=d) for d in range(3)} | {
    date(2026, 7, 15) + timedelta(days=d) for d in range(8)
}

EXTRA_GT = [
    "钙钛矿组件", "自动驾驶卡车", "数字疗法审批", "开源大模型评测",
    "氢能重卡", "太空太阳能", "室温超导复现", "基因编辑疗法上市",
    "智能眼镜", "电子皮肤", "核聚变点火", "农业机器人",
]

GT_QUERIES = [
    "固态电池", "agent memory", "小米汽车", "量子计算", "具身智能",
    "低空经济", "solid-state battery", "钠离子电池", "ai coding", "脑机接口",
    "合成生物学", "液冷数据中心", "人形机器人", "卫星互联网", "端侧大模型",
    "无人机配送", "开源芯片", "长时储能", "ai 制药", "空间计算",
]

WB_WORDS = [
    "固态电池量产", "高考录取结果", "人形机器人马拉松", "台风路径", "新能源车降价",
    "ai 面试官", "暑期档票房", "楼市新政", "具身智能融资", "电竞世界杯",
] + [f"热搜话题{i:02d}" for i in range(1, 41)]

GH_REPOS = [
    ("anthropics/claude-flow", "Agent orchestration runtime", ["agents", "llm"]),
    ("acme/solid-sim", "Solid-state battery cell simulator", ["battery", "materials"]),
    ("openrobot/humanoid-rl", "RL training stack for humanoid robots", ["robotics", "rl"]),
    ("skyops/lowalt-atc", "Low-altitude airspace control toolkit", ["drones", "uav"]),
    ("bioforge/synbio-kit", "Synthetic biology design toolkit", ["synbio", "crispr"]),
    ("edgelab/tiny-llm", "On-device LLM inference engine", ["llm", "edge"]),
    ("quantumzoo/qsim-next", "Quantum circuit simulator", ["quantum", "simulator"]),
    ("gridcell/longstore", "Long-duration energy storage models", ["energy", "storage"]),
    ("neurolink/bci-sdk", "Brain-computer interface SDK", ["bci", "neurotech"]),
    ("coolrack/liqcool", "Liquid cooling telemetry for datacenters", ["datacenter"]),
    ("satnet/leo-mesh", "LEO satellite mesh routing", ["satellite", "networking"]),
    ("pharmax/ai-admet", "AI-driven ADMET prediction", ["drug-discovery", "ml"]),
    ("spatial/xr-anchor", "Spatial computing anchor service", ["xr", "spatial"]),
    ("chipforge/rv-open", "Open-source RISC-V core generator", ["riscv", "hardware"]),
    ("aeropack/drone-route", "Drone delivery route planner", ["drones", "logistics"]),
]

ARXIV_TITLES = [
    "Scaling Laws for Agentic Memory Systems",
    "Solid-State Electrolyte Interfaces: A Survey",
    "Embodied Intelligence Benchmarks Revisited",
    "Sodium-Ion Batteries for Grid Storage",
    "Spiking Neural Networks on Edge Devices",
    "Autonomous Lab Loops for Materials Discovery",
    "Retrieval-Augmented Planning in Robotics",
    "Low-Altitude Traffic Management via MARL",
    "Diffusion Policies for Dexterous Manipulation",
    "Quantum Error Mitigation in Near-Term Devices",
    "Synthetic Data Curricula for Code Agents",
    "Thermal-Aware Scheduling for Liquid-Cooled Clusters",
]


def gtrends_url(_day: date) -> str:
    """`CN-04` / `DEC-054`：换成真实还活着的那条 RSS，**并且它不吃日期**。

    旧的 `trends/api/dailytrends?…&ed=YYYYMMDD` 已被 Google 下线（实测 404）。
    新端点 `trending/rss?geo=HK` 回的恒是「当下这一份」——所以签名里的 `day`
    用不上了（保留形参是因为 `SOURCES` 那张表按同一个签名调四个源）。

    **34 天的 URL 键因此完全相同**，这是对的：夹具按天分文件，
    回放先按天取文件、再按 URL 取那一次往返。
    NEVER 为了「让每天的键看起来不一样」硬拼一个上游不认的 query——
    拼上去真实站点照样回今天那一份，而调用方会以为自己取到了那一天。

    `geo=HK` 而不是 `CN`：Google 不编大陆榜（实测 `geo=CN` 回 400），
    `DEC-054` 定的是采港区、`region` 落 CN，屏上署名「Google 趋势（港区）」。
    """
    return "https://trends.google.com/trending/rss?geo=HK"


def _gt_queries(day: date) -> list[str]:
    if day >= STATIC_FROM:
        return GT_QUERIES
    idx = day.toordinal()
    rotating = [EXTRA_GT[(idx + k) % len(EXTRA_GT)] for k in range(6)]
    queries = GT_QUERIES[:14] + rotating
    if day in REVIVAL_PRESENT:
        queries = [*queries[:19], REVIVAL_KEYWORD]
    return queries


def _wb_words(day: date) -> list[str]:
    if day >= STATIC_FROM:
        return WB_WORDS
    idx = day.toordinal()
    return WB_WORDS[:10] + [f"热搜话题{(idx * 3 + k) % 80:02d}" for k in range(40)]


def _gh_repos(day: date) -> list[tuple[str, str, list[str]]]:
    if day >= STATIC_FROM:
        return GH_REPOS
    idx = day.toordinal()
    rotated = [GH_REPOS[(idx + k) % len(GH_REPOS)] for k in range(12)]
    return rotated


def _arxiv_titles(day: date) -> list[str]:
    if day >= STATIC_FROM:
        return ARXIV_TITLES
    idx = day.toordinal()
    return [ARXIV_TITLES[(idx + k) % len(ARXIV_TITLES)] for k in range(12)]


def gtrends_body(day: date) -> str:
    """`CN-04`：**只换信封**——词面与数值一个都没动。

    形状照 `fixtures/_probe/gtrends/real-hk-rss.xml`（`CN-04` 当天从真实站点
    抓下来的那一份）写：`channel/item` 下 `title` · `ht:approx_traffic` ·
    `pubDate` · `link`，`ht:` 命名空间在根元素上声明。

    **词面来自同一个 `_gt_queries(day)`，热度来自同一个公式**
    （`f"{50 + (idx + i * 7) % 450}K+"`）——所以 34 天的关键词与数值逐字不变。
    改的只有它们被装在什么信封里。这一条是 `CN-04` acceptance 的护栏：
    信封换了下游只会报 `ReplayMiss` 一族；数值动了的话，
    血缘与热度那些判据也会红，**而那时没人分得清哪条红是谁造成的**。
    """
    idx = day.toordinal()
    items = []
    for i, q in enumerate(_gt_queries(day)):
        traffic = f"{50 + (idx + i * 7) % 450}K+"
        items.append(
            "<item>"
            f"<title>{escape(q)}</title>"
            f"<ht:approx_traffic>{traffic}</ht:approx_traffic>"
            "<description/>"
            "<link>https://trends.google.com/trending/rss?geo=HK</link>"
            f"<pubDate>{day.strftime('%a, %d %b %Y')} 08:00:00 -0700</pubDate>"
            "<ht:picture/><ht:picture_source/>"
            "</item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<rss xmlns:atom="http://www.w3.org/2005/Atom"'
        ' xmlns:ht="https://trends.google.com/trending/rss" version="2.0">'
        "<channel><title>Daily Search Trends</title>"
        "<description>Recent searches</description>"
        "<link>https://trends.google.com/trending/rss?geo=HK</link>"
        + "".join(items) +
        "</channel></rss>"
    )


def weibo_url(_day: date) -> str:
    return "https://s.weibo.com/top/summary?cate=realtimehot"


def weibo_body(day: date) -> str:
    idx = day.toordinal()
    rows = []
    for i, word in enumerate(_wb_words(day), start=1):
        heat = 3_000_000 - i * 37_000 + (idx * 911 + i * i * 13) % 25_000
        tag = "爆" if i == 1 else ("热" if i <= 5 else ("新" if i % 9 == 0 else ""))
        tag_html = f'<td class="td-03"><i class="icon-txt">{tag}</i></td>' if tag else (
            '<td class="td-03"></td>'
        )
        rows.append(
            f'<tr><td class="td-01 ranktop">{i}</td>'
            f'<td class="td-02"><a href="/weibo?q=%23{word}%23" target="_blank">{word}</a>'
            f"<span>{heat}</span></td>{tag_html}</tr>"
        )
    return (
        "<html><body><table><tbody>"
        + "".join(rows)
        + f"</tbody></table><!-- day:{day.isoformat()} --></body></html>"
    )


def ghtrend_url(day: date) -> str:
    """`CN-07`：窗口从「晚于今天」改成「近 7 天」——**只换信封，条目一个没动**。

    改前 `created:>{day}` 查的是「创建晚于**今天**」的仓，**结构上恒 0**
    （`CN-06` 真跑实测 `total_count: 0`）。`LOOKBACK_DAYS` 的理由写在
    `flint/sources/ghtrend.py` 那一处，**这里跟着它走，NEVER 各写一个数**。
    """
    from flint.sources.ghtrend import GitHubTrendingSource

    since = day - timedelta(days=GitHubTrendingSource.LOOKBACK_DAYS)
    return (
        "https://api.github.com/search/repositories"
        f"?q=created:>{since.isoformat()}&sort=stars&order=desc&per_page=15"
    )


def ghtrend_body(day: date) -> str:
    idx = day.toordinal()
    repos = _gh_repos(day)
    items = [
        {
            "full_name": name,
            "description": desc,
            "topics": list(topics),
            "stargazers_count": 800 + (idx * 17 + i * 61) % 4200,
            "html_url": f"https://github.com/{name}",
        }
        for i, (name, desc, topics) in enumerate(repos)
    ]
    return json.dumps({"total_count": len(repos), "items": items}, ensure_ascii=False)


def arxiv_url(day: date) -> str:
    """`CN-07`：窗口改成「近 7 天且截到昨天」——**只换信封，条目一个没动**。

    arXiv 有公告延迟、周末整天不公告；以「当天」为窗口时凌晨跑必空、周末跑必空。
    天数取自 `flint/sources/arxiv.py`，**NEVER 在这里另写一个**。
    """
    from flint.sources.arxiv import ArxivSource

    since = (day - timedelta(days=ArxivSource.LOOKBACK_DAYS)).strftime("%Y%m%d")
    until = (day - timedelta(days=1)).strftime("%Y%m%d")
    return (
        "https://export.arxiv.org/api/query"
        f"?search_query=cat:cs.AI+AND+submittedDate:[{since}0000+TO+{until}2359]"
        "&max_results=50"
    )


def arxiv_body(day: date) -> str:
    entries = "".join(
        (
            "<entry>"
            f"<id>http://arxiv.org/abs/2607.{10000 + i}v1</id>"
            f"<title>{title}</title>"
            f"<summary>We study {title.lower()} with new benchmarks.</summary>"
            f'<category term="{"cs.AI" if i % 3 else "cs.LG"}"/>'
            f"<published>{day.isoformat()}T04:00:00Z</published>"
            "</entry>"
        )
        for i, title in enumerate(_arxiv_titles(day))
    )
    return (
        # `CN-05`：真 feed 的根元素上逐字声明着 opensearch 命名空间，
        # 且带 `<opensearch:totalResults>`——**它是分辨「那天没有」与「结构变了」
        # 的唯一信号**（`flint/sources/arxiv.py` 文件头详述）。
        # 合成夹具此前没有它，于是适配器接上那道判断之后它们全红。
        # **只换信封**：条目的标题与 id 一个字没动。
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom"'
        ' xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">'
        f"<opensearch:totalResults>{len(_arxiv_titles(day))}"
        "</opensearch:totalResults>"
        f"<updated>{day.isoformat()}T06:00:00Z</updated>{entries}</feed>"
    )


SOURCES = {
    "gtrends": (gtrends_url, gtrends_body, "text/xml; charset=UTF-8"),
    "weibo": (weibo_url, weibo_body, "text/html; charset=utf-8"),
    "ghtrend": (ghtrend_url, ghtrend_body, "application/json; charset=utf-8"),
    "arxiv": (arxiv_url, arxiv_body, "application/atom+xml; charset=UTF-8"),
}


def main() -> None:
    for source_id, (url_fn, body_fn, ctype) in SOURCES.items():
        for day in EVOLVED_DAYS:
            if source_id == "weibo" and day == WEIBO_DEGRADED_DAY:
                save_fixture(
                    ROOT / source_id / f"{day.isoformat()}.json",
                    [
                        RecordedExchange(
                            "GET", url_fn(day), 429, "text/plain",
                            "rate limited: retry after 300 seconds",
                        )
                    ],
                )
                continue
            save_fixture(
                ROOT / source_id / f"{day.isoformat()}.json",
                [RecordedExchange("GET", url_fn(day), 200, ctype, body_fn(day))],
            )
        for day in NORMAL_DAYS:
            save_fixture(
                ROOT / source_id / f"{day.isoformat()}.json",
                [RecordedExchange("GET", url_fn(day), 200, ctype, body_fn(day))],
            )
        save_fixture(
            ROOT / source_id / f"{RATE_LIMIT_DAY.isoformat()}.json",
            [
                RecordedExchange(
                    "GET", url_fn(RATE_LIMIT_DAY), 429, "text/plain",
                    "rate limited: retry after 300 seconds",
                )
            ],
        )
        save_fixture(
            ROOT / source_id / f"{FAILURE_DAY.isoformat()}.json",
            [
                RecordedExchange(
                    "GET", url_fn(FAILURE_DAY), 503, "text/plain",
                    "upstream unavailable",
                )
            ],
        )
    print("fixtures written for:", ", ".join(SOURCES))


if __name__ == "__main__":
    main()
