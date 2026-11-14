"""GAUGE-13：蓝本 P 编号 ↔ 实仓路由 **双向**对账，缺屏判红。

## 为什么要双向

单向只能发现一半：

- 只查「蓝本有而实仓没有」→ 实仓多出来的屏没人管，蓝本会慢慢过期；
- 只查「实仓有而蓝本没有」→ **缺屏永远发现不了**，而本批开工时就缺六屏
  （`P3` combo · `P4` 主题列表 · `P5` 主题详情 · `P6` 发起分析 ·
  `P10` 干预页 · `P11` 受众分叉）——用户当时从广场走不到报告。

## 蓝本的路径与实仓的路由**本来就不一样**

蓝本写 `/combo/new`，实仓是 `/combo`；蓝本写 `/plaza/hot`，实仓是 `/plaza`。
这不是错，是**两套命名习惯**——蓝本 README 自己就写着
「仓库路由习惯亦可用 `/gate/[jobId]`」。

所以对账要一张**显式映射**（`ALIASES`）。它逐条带理由，
**NEVER 靠模糊匹配**：模糊匹配会在某天把两个不同的屏认成同一个，
而那时缺屏会静静地消失在报告里。

用法：
    python tools/check_screen_coverage.py [--json]

退出码：0 = 缺屏为 0；1 = 有缺屏或有对不上的条目。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BLUEPRINT = (REPO / "Claude design Flint 前端设计" / "Flint 应用 · 20 屏"
             / "design_handoff_flint_web" / "README.md")
APP = REPO / "web" / "app"

EXIT_OK = 0
EXIT_GAPS = 1

# 蓝本路径 → 实仓路由。**逐条带理由**，NEVER 靠模糊匹配。
ALIASES: dict[str, str] = {
    # 蓝本把列表页写成资源子路径，实仓按 App Router 惯例落在屏级路由上。
    "/plaza/hot": "/plaza",
    "/combo/new": "/combo",
    "/projects/[id]/analysis/new": "/projects/[id]/analysis",
    "/projects/[id]/proposal/new": "/projects/[id]/proposal",
    # 蓝本 README 自己写着「仓库路由习惯亦可用 /gate/[jobId]」。
    "/jobs/[id]/verdict": "/gate/[id]",
    # 蓝本把干预页写成 `edit`；实仓按它做的事命名（四个干预动作）。
    "/deliverables/[id]/edit": "/deliverables/[id]/interventions",
}

# `docs/前端功能说明-v2.md` 的 18 条 → 实仓路由。**蓝本没登记的屏由它认领**：
# 那份表按 §号列屏名、不写路径，所以映射写在这里，逐条带 §号。
# 名单外的屏才算「两边都没登记」——那才是真的没人管。
V2_SCREENS: dict[str, str] = {
    "/settings/locale": "2.13 语言/地区设置",
    "/favorites": "2.15 收藏图书馆",
    "/workbenches/[id]": "2.16 热点工作台·图谱",
    "/design": "2.17 AI 设计工作台",
    "/share/[token]": "2.18 外链只读查看页",
    "/deliverables/[id]/quality": "2.7 报告查看器的质量卡（UI-09 拆出的子屏）",
    "/deliverables/[id]/pack": "2.10 受众选择产出的 vibe_pack 查看器",
    "/account": "账户位（S0 外壳的账户屏，UI-08）",
    "/billing": "账户位的账单屏（UI-08）",
}

# 蓝本写了端点、而实仓那一屏确实还没接的：**各带理由**。
# 名单少一条即红（修好了要来删），多一条要停下登记——
# 与本仓既有的控制台噪声基线是同一套办法。
KNOWN_ENDPOINT_GAPS: dict[tuple[str, str], str] = {
    ("/plaza", "/categories"): (
        "大类筛选条还没做。AppShell 的说明逐字写着「筛不到东西的筛选条就是 A 类脚手架，"
        "它跟着广场屏一起来」——广场屏这一批做了卡片，筛选条留到地区筛选通了之后"
        "（docs/blocked/PLAZA-02-REGION-QUERY-AND-SOURCE-REGION-NOT-BUILT.md）"
    ),
}

# 蓝本列了、而**本仓有意不做**的屏：各带理由。名单少一条即红——
# 「有意不做」与「忘了做」NEVER 长得一样。
DELIBERATELY_ABSENT: dict[str, str] = {
    "/clusters/[id]": (
        "P2 工作台：实仓把它做成了图谱工作台 /workbenches/[id]（UI-03），"
        "簇级只读页没有单独建——证据卡在图谱里看"
    ),
}


@dataclass(frozen=True)
class Row:
    """蓝本表里的一行。"""

    path: str
    label: str
    endpoints: str


def blueprint_rows(text: str) -> list[Row]:
    """从蓝本 README 的表里解析 `| 路径 | P编号 标题 | 端点 |`。"""
    rows: list[Row] = []
    for line in text.splitlines():
        m = re.match(r"^\|\s*(/[^|]*?)\s*\|\s*(P\d+[^|]*?)\s*\|\s*([^|]*?)\s*\|$", line)
        if m:
            rows.append(Row(path=m.group(1).strip(), label=m.group(2).strip(),
                            endpoints=m.group(3).strip()))
    return rows


def repo_routes(app_dir: Path) -> list[str]:
    """`web/app/**/page.tsx` → 路由。与 `harness/fe_smoke.py` 的发现口径一致。"""
    routes: list[str] = []
    for page in sorted(app_dir.rglob("page.tsx")):
        rel = page.parent.relative_to(app_dir).as_posix()
        routes.append("/" if rel == "." else f"/{rel}")
    return routes


def normalise(path: str) -> str:
    """把蓝本的动态段与实仓的对齐：`[jobId]` / `[token]` 一律记成 `[id]` 之外的原名。

    只做**大小写与参数名**的归一，NEVER 归一路径段本身——
    段不一样就是两个屏，那正是要报出来的东西。
    """
    return re.sub(r"\[[^\]]+\]", lambda m: m.group(0).lower(), path.strip())


def audit(blueprint_text: str, routes: list[str]) -> dict[str, list[dict[str, str]]]:
    """三类报告。**每类各自成一类**，因为修法完全不同。"""
    rows = blueprint_rows(blueprint_text)
    have = {normalise(r) for r in routes}

    missing: list[dict[str, str]] = []      # 蓝本有而实仓没有 → 去建屏
    extra: list[dict[str, str]] = []        # 实仓有而蓝本没有 → 去补蓝本
    endpoint_gap: list[dict[str, str]] = []  # 两边都有但端点对不上 → 去核端点

    claimed: set[str] = set()
    for row in rows:
        wanted = normalise(ALIASES.get(row.path, row.path))
        if wanted in have:
            claimed.add(wanted)
            continue
        if row.path in DELIBERATELY_ABSENT:
            claimed.add(wanted)
            continue
        missing.append({"blueprint": row.path, "label": row.label,
                        "expected_route": wanted,
                        "detail": "蓝本有这一屏，实仓没有对应路由"})

    for route in sorted(have - claimed):
        if route in V2_SCREENS:
            continue          # v2 那份表认领了它
        extra.append({"route": route,
                      "detail": "蓝本与 v2 屏总表**都没有**登记它"})

    for row in rows:
        wanted = normalise(ALIASES.get(row.path, row.path))
        if wanted not in have or not row.endpoints:
            continue
        # 端点只做**存在性**对照：蓝本写了端点而实仓那一屏一个字都没提到它，
        # 说明两边对这屏该问谁有分歧。NEVER 判「参数逐字相同」——
        # 蓝本写的是意图，实仓写的是实现，逐字相同是过度约束。
        page = _page_source(wanted)
        for endpoint in _endpoints_of(row.endpoints):
            if (wanted, endpoint) in KNOWN_ENDPOINT_GAPS:
                continue
            if page is not None and endpoint not in page:
                endpoint_gap.append({
                    "route": wanted, "blueprint": row.path, "endpoint": endpoint,
                    "detail": "蓝本给这屏写了这条端点，实仓那一屏没提到它"})

    return {"missing": missing, "extra": extra, "endpoint_gap": endpoint_gap}


def _page_source(route: str) -> str | None:
    rel = route.lstrip("/")
    page = APP / rel / "page.tsx" if rel else APP / "page.tsx"
    if not page.exists():
        return None
    # 连它 import 的本仓文件一起看，**跟两层**：取数常常是
    # page → `useXxx` 钩子 → `xxxClient`。只跟一层会把 `/jobs/[id]` 报成
    # 「没提到 /jobs」——而它当然提到了，只是那句话在第二层里。
    # 三层就开始把无关文件也拖进来，那时「提到了」不再说明这屏在用它。
    text = page.read_text(encoding="utf-8")
    seen: set[Path] = set()
    frontier = [page]
    for _ in range(2):
        nxt: list[Path] = []
        for current in frontier:
            body = current.read_text(encoding="utf-8")
            for m in re.finditer(r'from "([./][^"]+)"', body):
                target = (current.parent / m.group(1)).resolve()
                for suffix in (".ts", ".tsx"):
                    candidate = target.with_suffix(suffix)
                    if candidate.exists() and candidate not in seen:
                        seen.add(candidate)
                        text += "\n" + candidate.read_text(encoding="utf-8")
                        nxt.append(candidate)
                        break
        frontier = nxt
    return text


def _endpoints_of(cell: str) -> list[str]:
    """从蓝本那格里抽出端点路径（`GET /plaza/hot?day=` → `/plaza/hot`）。"""
    found = re.findall(r"(/[A-Za-z0-9_{}\[\]/-]+)", cell)
    out: list[str] = []
    for raw in found:
        path = raw.split("?")[0].rstrip("/")
        # 蓝本用 `{id}`，实仓用模板串——只取**最后一段之前**那部分做包含判断。
        head = path.split("{")[0].rstrip("/")
        if len(head) > 3 and head not in out:
            out.append(head)
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="蓝本 P 编号 ↔ 实仓路由双向对账")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--blueprint", default=str(BLUEPRINT))
    parser.add_argument("--app", default=str(APP))
    args = parser.parse_args(argv)

    text = Path(args.blueprint).read_text(encoding="utf-8")
    routes = repo_routes(Path(args.app))
    report = audit(text, routes)
    gaps = len(report["missing"]) + len(report["endpoint_gap"])

    if args.json:
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        rows = len(blueprint_rows(text))
        sys.stdout.write(
            f"屏对照：蓝本 {rows} 条 / 实仓 {len(routes)} 屏；"
            f"缺屏 {len(report['missing'])} · 蓝本未登记 {len(report['extra'])} · "
            f"端点对不上 {len(report['endpoint_gap'])}\n")
        for kind in ("missing", "endpoint_gap", "extra"):
            for row in report[kind]:
                sys.stdout.write(f"  {kind} {json.dumps(row, ensure_ascii=False)}\n")
    return EXIT_OK if gaps == 0 else EXIT_GAPS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
