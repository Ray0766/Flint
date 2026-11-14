"""K2-01：实测各源的 robots.txt（A 档只读调研），产出 `assets/source_legal_status.yaml`。

## 这是唯一一个真发请求的地方

`flint/region/legal_probe.py` 零网络（判读是纯函数）。**取 robots.txt 的动作只在这里**，
而且只取 `robots.txt` 这一个路径——**NEVER 碰任何数据端点**：那属首次真实抓取，
是红线（需 owner 在场）。robots.txt 是「能不能抓」这个问题的答案本身，
取它正是抓之前该做的第一件事。

## 抓完必录

每个响应落 `fixtures/robots/{source_id}.txt` + 同名 manifest（NET-02 的三件套：
URL / 时间 / sha256）。测试永远回放 fixtures，CI 一次网络都不发（S2-7）。

## 取不到也是一条结论——但 4xx 不算「取不到」

超时 / 域名不解析 / 5xx 记 `unreachable`，并把**为什么取不到**写进证据位：
不写的话，「取不到」与「没去测」在盘上长得一模一样。

**4xx 是另一回事**：RFC 9309 §2.3.1.4 规定 4xx = 该主机没有 robots.txt，
此时协议本身给的结论是全放行。记成 `unreachable` 会把一条明确结论降级成
「不知道」——那是另一种蒙混。
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml

from flint.region.legal_probe import robots_verdict
from flint.sources.provenance import make_provenance, manifest_path_for, write_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "fixtures" / "robots"
OUT = REPO_ROOT / "assets" / "source_legal_status.yaml"

# （source_id, robots.txt 地址, 我们真正要抓的那条路径, 服务条款地址）
# 路径写的是**各源模块实际请求的那一条**，不是首页——robots 是按路径判的。
TARGETS: list[tuple[str, str, str, str | None]] = [
    ("gtrends", "https://trends.google.com/robots.txt",
     "/trends/api/dailytrends", "https://policies.google.com/terms"),
    ("weibo", "https://s.weibo.com/robots.txt",
     "/top/summary", "https://weibo.com/signup/v5/protocol"),
    ("ghtrend", "https://api.github.com/robots.txt",
     "/search/repositories", "https://docs.github.com/site-policy/github-terms/github-terms-of-service"),
    ("arxiv", "https://export.arxiv.org/robots.txt",
     "/api/query", "https://info.arxiv.org/help/api/tou.html"),
    ("google_trends_api", "https://trends.google.com/robots.txt",
     "/trends/api/dailytrends", "https://policies.google.com/terms"),
    ("yahoo_jp_realtime", "https://search.yahoo.co.jp/robots.txt",
     "/realtime", "https://about.yahoo.co.jp/common/terms/"),
    # 判的是**我们真会请求的那个主机**：K1-01 记的 datalab.naver.com 是首页，
    # 而 API 在 openapi.naver.com。判错主机 = 判了一份与我们无关的 robots。
    ("naver_datalab", "https://openapi.naver.com/robots.txt",
     "/v1/datalab/search", "https://policy.naver.com/policy/service_en.html"),
    ("reddit_data_api", "https://www.reddit.com/robots.txt",
     "/api/v1/", "https://redditinc.com/policies/data-api-terms"),
]

_UA = "flint-compliance-probe/0.4.1 (robots.txt only)"


def probe(client: httpx.Client, robots_url: str, path: str) -> tuple[str, str, str | None]:
    """取一次 robots.txt 并判读。返回（实测态, 证据, 原文或 None）。"""
    try:
        response = client.get(robots_url, headers={"User-Agent": _UA})
    except httpx.HTTPError as err:
        return "unreachable", f"取 robots.txt 失败：{type(err).__name__}: {err}", None
    if 400 <= response.status_code < 500:
        # RFC 9309 §2.3.1.4：4xx 表示**没有 robots.txt**，此时协议规定全放行。
        # 记成 unreachable 会把一条明确结论降级成「不知道」——那是另一种蒙混。
        evidence = (f"HTTP {response.status_code}：该主机没有 robots.txt，"
                    "按 RFC 9309 §2.3.1.4（unavailable status）全放行")
        return "allowed", evidence, None
    if response.status_code != 200:
        # 5xx / 3xx 收尾异常：RFC 9309 §2.3.1.3 说 5xx 期间应按全禁处理，
        # 但那是**临时**结论——记 unreachable 让它下次重测，NEVER 固化成 restricted。
        evidence = (f"取 robots.txt 得到 HTTP {response.status_code}"
                    f"（{response.reason_phrase}）：服务端异常，结论未定，须重测")
        return "unreachable", evidence, None
    text = response.text
    state, hit = robots_verdict(text, path=path)
    return state, f"{hit}（HTTP 200，{len(text)} 字节）", text


def main() -> int:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).date()
    entries: list[dict[str, object]] = []
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        for source_id, robots_url, path, tos_url in TARGETS:
            state, evidence, text = probe(client, robots_url, path)
            if text is not None:
                fixture = FIXTURE_DIR / f"{source_id}.txt"
                fixture.write_text(text, encoding="utf-8", newline="\n")
                write_manifest(manifest_path_for(fixture), [make_provenance(
                    url=robots_url, fetched_at=datetime.now(UTC), content=text)])
            entries.append({
                "source_id": source_id, "robots_url": robots_url, "probe_path": path,
                "state": state, "evidence": evidence, "probed_on": today,
                "tos_url": tos_url,
            })
            print(f"{source_id:20s} {state:12s} {evidence[:70]}")
    OUT.write_text(
        "# K2-01 实测：各源 robots.txt 判读结果（harness/probe_robots.py 生成）\n"
        "# 服务条款（tos_url）只记地址不记结论——条款是人读的，结论属 owner/法务面，\n"
        "# 见 docs/blocked/K2-COMPLIANCE-BEFORE-LAUNCH.md。\n"
        + yaml.safe_dump({"entries": entries}, allow_unicode=True, sort_keys=False),
        encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
