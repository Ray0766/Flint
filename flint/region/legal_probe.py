"""K2-01：抓取合规状态的**实测记录**（robots 判读 + 结论派生）。

## 为什么不能继续「一律 unknown」

K2 未决期间全仓一律填 `unknown`。那在「还没测」的时候是诚实的，
在「测得到却不去测」的时候就是**蒙混**——两者在盘上长得一模一样，
而下游 REGION-07 的门对它们的处置也一样（不放行），于是九区一条源都抓不了。

owner 2026-08-04 裁决非商业用途先取数之后，`unknown` 只许留在**真的取不到**的位置：

| 实测态 | 什么意思 | 派生的 `FetchLegalStatus` |
|---|---|---|
| `allowed` | robots 里没有禁这条路径 | `allowed` |
| `disallowed` | robots 明写 `Disallow` 命中 | `restricted` |
| `unreachable` | robots.txt 取不到（超时 / 4xx / 域名不解析） | `unknown` |

**不阻断的是动作，不是结论**：`disallowed` 照样派生 `restricted`，
只是 `legal_policy.py` 现在不拿它去拦人。把 `disallowed` 记成 `allowed` 才是蒙混。

## ToS 不在这里判

robots.txt 是机器可判的；**服务条款是人读的**。本模块只记 `tos_url`（测的时候
一并记下在哪），条款本身的结论属 owner/法务面，留在
`docs/blocked/K2-COMPLIANCE-BEFORE-LAUNCH.md`。
**机器判不了的东西 NEVER 由机器给个结论顶上。**

## 本模块零网络

抓 robots.txt 的动作在 `harness/probe_robots.py` 里，不在 `flint/` 里。
门自己发请求去「看看能不能抓」，门就成了第一次越界的人（REGION-07 原话）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Final, Literal

import yaml

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
MEASURED_STATUS: Final[Path] = REPO_ROOT / "assets" / "source_legal_status.yaml"

ProbeState = Literal["allowed", "disallowed", "unreachable"]


@dataclass(frozen=True)
class MeasuredStatus:
    """一个源的合规实测记录。**证据位是必填的**：

    只写一个结论而不留证据，与凭印象填没有区别——下一个人无从判断
    它是测出来的还是猜出来的。
    """

    source_id: str
    robots_url: str
    state: ProbeState
    evidence: str
    probed_on: date
    tos_url: str | None


def robots_verdict(robots_text: str, *, path: str, agent: str = "*") -> tuple[ProbeState, str]:
    """按 robots.txt 原文判一条路径能不能抓。返回（结论, 命中的那一行）。

    只认 `User-agent: *` 与精确匹配 `agent` 的两组规则——
    别的 agent 段落写什么与我们无关，混进来会判错。

    命中多条时**最长的那条赢**（RFC 9309 §2.2.2），长度相同则 `Allow` 赢。
    通配 `*` 与行尾锚 `$` 按协议处理：`Allow: /$` 只匹配根路径本身，
    照前缀判会把整站都放行——**判宽比判严更危险**。
    """
    rules = _rules_for(robots_text, agent)
    hit = ""
    verdict: ProbeState = "allowed"
    for directive, value in rules:
        # `Disallow:` 后面留空 = 全放行（robots 协议原义）。这里**没有**为它单写一个
        # 提前 continue：空串长度为 0，永远输给下面那条「同长则 Allow 赢」的定序，
        # 于是自动落到 allowed。写一道额外的守卫会让人以为它在担事，
        # 而实际抽掉它行为一个字不变（变异考实测：抽掉后 31 条全绿）。
        if not _matches(value, path):
            continue
        if len(value) < len(hit) or (len(value) == len(hit) and directive == "disallow"):
            continue
        hit = value
        verdict = "disallowed" if directive == "disallow" else "allowed"
    if hit:
        return verdict, f"{'Disallow' if verdict == 'disallowed' else 'Allow'}: {hit}"
    # 「文件里根本没有适用于我们的规则组」与「有规则但没命中这条路径」是两件事。
    # 写成同一句话，读的人无从判断这个源到底管不管我们——而后者才是常态，
    # 前者（只针对具名爬虫）意味着这份 robots 压根没考虑过通用 agent。
    if not rules:
        return verdict, "该文件里没有适用于本 agent 的规则组（只针对具名爬虫）"
    return verdict, f"该 agent 有 {len(rules)} 条规则，没有一条命中这条路径"


def _matches(pattern: str, path: str) -> bool:
    """robots 路径匹配：前缀匹配 + `*` 任意串 + `$` 行尾锚（RFC 9309 §2.2.3）。"""
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
    return re.match(regex + ("$" if anchored else ""), path) is not None


def _rules_for(robots_text: str, agent: str) -> list[tuple[str, str]]:
    rules: list[tuple[str, str]] = []
    applies = False
    for raw in robots_text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            applies = value in ("*", agent)
            continue
        if applies and key in ("allow", "disallow"):
            rules.append((key, value))
    return rules


def derive_fetch_legal_status(entry: MeasuredStatus) -> str:
    """实测态 → `FetchLegalStatus`。映射见模块 docstring 的表。

    只有 `unreachable` 派生 `unknown`：**测到了就 NEVER 记 unknown**，
    那是把实测结果扔掉。
    """
    if entry.state == "unreachable":
        return "unknown"
    return "restricted" if entry.state == "disallowed" else "allowed"


def load_measured_status(path: Path | None = None) -> dict[str, MeasuredStatus]:
    """读实测记录表。表不在盘上即抛错——**空表 NEVER 被当作「都测过了、都没事」**。"""
    target = path or MEASURED_STATUS
    raw: dict[str, Any] = dict(yaml.safe_load(target.read_text(encoding="utf-8")))
    return {
        str(item["source_id"]): MeasuredStatus(
            source_id=str(item["source_id"]),
            robots_url=str(item["robots_url"]),
            state=item["state"],
            evidence=str(item["evidence"]),
            probed_on=item["probed_on"],
            tos_url=item.get("tos_url"),
        )
        for item in raw["entries"]
    }
