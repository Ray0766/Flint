"""NAV-01 · 可达性尺子：从顶栏入口出发，**走不到的屏判红并点名**。

## 为什么需要第四把尺子

owner 2026-08-09 亲自点过界面之后说「前端和后端还没有连接上」。**他是对的**，
而三把既有尺子没有一把量得到这件事：

| 尺子 | 它量什么 | 它不量什么 |
|---|---|---|
| `GAUGE-13`（屏覆盖） | 屏在不在 | **走不走得到** |
| `GAUGE-12`（组件对照） | 屏上有没有那些组件 | **屏与屏之间有没有路** |
| `check_fe_be_parity` | 端点接没接 | **用户点不点得到** |

每一张卡的验收都是逐屏写的（「这一屏渲染出 X」「这条端点回 Y」），
**没有一条问过「从 A 屏能不能走到 B 屏」**——所以 16 座孤岛可以一路绿灯建到今天。

## 三件事一起判，缺一件这把尺子就会说谎

1. **图遍历**：从 `entries` 出发沿 `goes_to` 走，走不到的屏点名。
   **NEVER 用入度计数代替**：`/projects/[id]/topics` 有一条真边指向它，
   而那条边的起点（`/combo`）自己走不到——按入度算它是可达的，按遍历算它不是。
   那种**二级孤岛**正是最难被发现的一类。
2. **图与代码比对**：图里声明的每条边都要在源码里找得到；
   源码里有而图里没有的边也要报。**一份与代码对不上的图比没有图更坏**——
   它会让人以为路已经查过了。
3. **两个方向自洽**：每条 `goes_to` 在对面要有一条对应的 `reached_by`。
   只写出口的话，`/favorites` 这种「有出口、没入口」的孤岛查不出来。

## exempt 是给谁的

给**本来就不该从站内点到**的屏（`/share/[token]` 的 token 由站外拿到）。
**NEVER 把「还没接线」写进去顶掉红**——待办就该红着，它红着才说明这把尺子在量。

用法：

    python tools/check_reachability.py [--json]

退出码 0 = 每一屏都走得到（或有 exempt 理由）；1 = 有孤岛或图与代码对不上。
"""
from __future__ import annotations

import json
import re
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GRAPH = REPO / "assets" / "screen_graph.json"
WEB = REPO / "web"
APP = WEB / "app"
SHELL = WEB / "components" / "shell" / "AppShell.tsx"

# 顶栏那份清单（`NAV_ITEMS`）。**入口也要与代码对得上**：
# 图里多写一个入口，遍历会从一个屏上根本没有的地方出发，
# 于是一批孤岛被算成可达——**而那正是这把尺子要治的那句假话**。
# 顶栏的链接是 `href={item.href}`（变量），边扫描器看不见它们，
# 所以入口这一层单独比对。
_NAV_ITEM = re.compile(r'\{\s*href:\s*"([^"]+)"\s*,\s*key:\s*"[^"]+"\s*\}')

# 站内跳转的三种写法。`href` 之外还有两种，漏掉任何一种都会让图与代码
# 对不上——而那时报出来的是「图里多了一条边」，读起来像图写错了。
#
# **模板字面量要一路读到反引号**，NEVER 用 `[^}]` 收边：
# `href={`/deliverables/${id}/export`}` 在 `${id}` 的右花括号处就被截断，
# 只剩 `/deliverables/${id` ——于是这条真边被报成「图里有、源码里没有」，
# 而同一条又被报成「源码里有、图里没声明」（截断后的那半）。
# 一个正则的收边错误，会同时造出两条互相矛盾的假发现。
_HREF = re.compile(r"href=\{`([^`]+)`\}|href=\"([^\"]+)\"")
_PUSH = re.compile(
    r'(?:router\.push|location\.assign|window\.location\.href)\s*(?:=\s*)?\(?\s*'
    r'[`"\']([^`"\']+)')
# 动态段：`${id}` / `${encodeURIComponent(x)}` → `[id]` 形态，与路由目录对齐。
_SEGMENT = re.compile(r"\$\{[^}]*\}?")


@dataclass
class Report:
    routes: list[str] = field(default_factory=list)
    entries: list[str] = field(default_factory=list)
    reachable: list[str] = field(default_factory=list)
    islands: list[str] = field(default_factory=list)
    #: 路接上了，而那条路今天走不通（边上写了 `blocked`）。**第三种状态**——
    #: 与孤岛合并会掩盖「前端已经接完了」，与可达合并会说出一句假话
    #: （屏上点不到）。honest-state 纪律：两者 NEVER 合并（DEC-032 同口径）。
    blocked_screens: list[str] = field(default_factory=list)
    exempt: list[str] = field(default_factory=list)
    edges_declared_not_in_code: list[str] = field(default_factory=list)
    edges_in_code_not_declared: list[str] = field(default_factory=list)
    one_way_edges: list[str] = field(default_factory=list)
    undeclared_routes: list[str] = field(default_factory=list)
    stale_declarations: list[str] = field(default_factory=list)
    #: 图里写的入口与顶栏 `NAV_ITEMS` 对不上的那些（两个方向都报）。
    entry_mismatches: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not (
            self.islands or self.blocked_screens
            or self.edges_declared_not_in_code
            or self.edges_in_code_not_declared or self.one_way_edges
            or self.undeclared_routes or self.stale_declarations
            or self.entry_mismatches
        )


def app_routes(app_dir: Path = APP) -> list[str]:
    """`web/app/**/page.tsx` 反推出来的路由表。**这是屏的真相，不是图。**"""
    found = [
        "/" + path.parent.relative_to(app_dir).as_posix()
        for path in app_dir.rglob("page.tsx")
    ]
    return sorted("/" if route == "/." else route for route in found)


def nav_items(shell: Path = SHELL) -> list[str]:
    """顶栏常驻入口，从 `NAV_ITEMS` 读出来。**这是入口的真相，不是图。**"""
    return _NAV_ITEM.findall(shell.read_text(encoding="utf-8"))


def normalise(target: str) -> str:
    """`/jobs/${jobId}` → `/jobs/[id]`；尾部 query 与 hash 去掉。

    动态段一律折成 `[id]`：图与路由目录对齐的唯一办法。
    `[token]` 那种别名在下面按路由表回填。
    """
    cleaned = _SEGMENT.sub("[id]", target).split("?")[0].split("#")[0]
    return cleaned.rstrip("/") or "/"


def code_edges(web_dir: Path = WEB) -> set[tuple[str, str]]:
    """源码里真实存在的站内边：`(哪个文件, 指向哪条路由)`。

    **剥注释**：注释里写着的路径不是一条路。本仓在这一形状上栽过十二次，
    每一次的修法都是给「引用」一个位置，而不是把判据放宽。
    """
    edges: set[tuple[str, str]] = set()
    for path in sorted(web_dir.rglob("*.tsx")):
        if ".test." in path.name or "node_modules" in path.parts:
            continue
        code = "\n".join(
            line for line in path.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("//"))
        # `_HREF` 有两个捕获组（模板字面量 / 普通字符串），没命中的那组是空串。
        targets = {group for match in _HREF.findall(code) for group in match if group}
        for target in targets | set(_PUSH.findall(code)):
            if not target.startswith("/") or target.startswith("/_"):
                continue          # 外链与 `_ds` 静态资源不是站内边
            edges.add((path.relative_to(web_dir).as_posix(), normalise(target)))
    return edges


def _alias(route: str, routes: set[str]) -> str:
    """把 `[id]` 折回真实路由名（`/share/[id]` → `/share/[token]`）。"""
    if route in routes:
        return route
    head = route.rsplit("/", 1)[0]
    for candidate in routes:
        if (candidate.startswith(head + "/")
                and candidate.count("/") == route.count("/")
                and candidate.rsplit("/", 1)[1].startswith("[")):
            return candidate
    return route


def check(graph_path: Path = GRAPH) -> Report:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    routes = app_routes()
    route_set = set(routes)
    report = Report(routes=routes)

    declared = {s["route"]: s for s in graph["screens"]}
    report.entries = [e["route"] for e in graph["entries"]]
    report.exempt = [e["route"] for e in graph["exempt"]]

    # 图与屏对得上：多一条、少一条都要有人来看。
    report.undeclared_routes = sorted(route_set - set(declared))
    report.stale_declarations = sorted(set(declared) - route_set)

    # 入口与顶栏对得上（两个方向）。图里凭空多一个入口，遍历就会从一个
    # 屏上根本没有的地方出发——一批孤岛因此被算成可达。
    in_bar = set(nav_items())
    report.entry_mismatches = [
        f"{route}（图里写着是入口，顶栏 NAV_ITEMS 里没有）"
        for route in sorted(set(report.entries) - in_bar)
    ] + [
        f"{route}（顶栏里有这一项，图里没把它算成入口）"
        for route in sorted(in_bar - set(report.entries))
    ]

    # ── 两个方向自洽
    for screen in graph["screens"]:
        for edge in screen.get("goes_to", []):
            other = declared.get(_alias(edge["to"], route_set))
            if other is None:
                report.one_way_edges.append(
                    f"{screen['route']} -> {edge['to']}（对面那一屏没在图里）")
                continue
            if not any(back["from"] == screen["route"]
                       for back in other.get("reached_by", [])):
                report.one_way_edges.append(
                    f"{screen['route']} -> {edge['to']}"
                    f"（对面的 reached_by 里没有 {screen['route']}）")

    # ── 图与代码比对
    in_code = {(src, dst) for src, dst in code_edges()}
    code_targets = {(src, _alias(dst, route_set)) for src, dst in in_code}
    for screen in graph["screens"]:
        for edge in screen.get("goes_to", []):
            where = edge.get("where", "")
            wanted = (where.removeprefix("web/"), _alias(edge["to"], route_set))
            if wanted not in code_targets:
                report.edges_declared_not_in_code.append(
                    f"{screen['route']} -> {edge['to']}（图说在 {where}，源码里找不到）")
    graph_pairs = {
        (edge.get("where", "").removeprefix("web/"), _alias(edge["to"], route_set))
        for screen in graph["screens"] for edge in screen.get("goes_to", [])
    }
    for src, dst in sorted(code_targets):
        if dst not in route_set:
            continue              # 指向一个不存在的路由是别的尺子的事
        if (src, dst) not in graph_pairs:
            report.edges_in_code_not_declared.append(f"{src} -> {dst}")

    # ── 图遍历（NEVER 用入度代替：二级孤岛只有遍历查得出来）
    #
    # 写了 `blocked` 的边**不走**：那条路今天走不通（多半是它依赖的端点没挂），
    # 沿着它走下去会把一批点不到的屏算成可达——那正是这把尺子要治的那句假话。
    forward: dict[str, list[str]] = {r: [] for r in declared}
    blocked_to: dict[str, str] = {}
    for screen in graph["screens"]:
        live: list[str] = []
        for edge in screen.get("goes_to", []):
            target = _alias(edge["to"], route_set)
            if edge.get("blocked"):
                blocked_to.setdefault(target, str(edge["blocked"]))
                continue
            live.append(target)
        forward[screen["route"]] = live
    seen: set[str] = set()
    queue = deque(report.entries)
    while queue:
        node = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        queue.extend(forward.get(node, []))
    report.reachable = sorted(seen)
    unreached = set(declared) - seen - set(report.exempt)
    # 三种状态各自成一态：走得到 / **路接上了但走不通** / 孤岛（根本没有路）。
    report.blocked_screens = sorted(
        f"{route}（{blocked_to[route]}）" for route in unreached & set(blocked_to))
    report.islands = sorted(unreached - set(blocked_to))
    return report


def main(argv: list[str]) -> int:
    report = check()
    if "--json" in argv:
        sys.stdout.write(json.dumps(report.__dict__, ensure_ascii=False, indent=1))
        return 0 if report.clean else 1

    print(f"可达性：{len(report.routes)} 屏 · 入口 {len(report.entries)} 个 · "
          f"走得到 {len(report.reachable)} 屏 · 豁免 {len(report.exempt)} 屏")
    if report.islands:
        print(f"\n**孤岛 {len(report.islands)} 屏**（从入口出发走不到，且没有豁免理由）：")
        for route in report.islands:
            print(f"  ✗ {route}")
    for title, rows in (
        ("路接上了，而那条路今天走不通", report.blocked_screens),
        ("图里有、源码里没有的边", report.edges_declared_not_in_code),
        ("源码里有、图里没声明的边", report.edges_in_code_not_declared),
        ("只写了单向的边", report.one_way_edges),
        ("入口与顶栏对不上", report.entry_mismatches),
        ("有屏没进图", report.undeclared_routes),
        ("图里有一条屏已经不存在了", report.stale_declarations),
    ):
        if rows:
            print(f"\n**{title}（{len(rows)}）**：")
            for row in rows:
                print(f"  ✗ {row}")
    if report.clean:
        print("\n每一屏都走得到。")
    return 0 if report.clean else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
