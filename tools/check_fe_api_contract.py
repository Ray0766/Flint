"""FB-11：前端引用的每个端点必须在后端真存在。

用法：python tools/check_fe_api_contract.py [--json] [--frontend <目录>]
退出码 0 = 前端每条调用都能在后端路由表里找到；1 = 有对不上的（逐条点名）。

## 这条缝为什么只能靠尺子堵

前端与后端之间没有编译期检查。一个拼错的路径、一个把 POST 写成 GET 的调用，
**在两边各自的测试里都是绿的**——前端 mock 了 fetch，后端根本不知道有人在调它。

HOTSPOT-03 的卡面 `inputs` 里就写着一个真件里不存在的端点
（`GET /clusters/{id}/verdict`）。卡面写错不致命，**前端照着卡面写才致命**：
那一屏会 404，而 404 在界面上长什么样，取决于前端怎么处理——
处理得好是「接口未提供」，处理得不好就是一片空白。

## 注释里的路径 NEVER 算一次调用（`GAUGE-10`）

扫描前先把注释**换成等长空白**（`_blank_comments`）。理由是实测出来的：

```ts
// 说明：`/projects/{}/proposal` 此前藏在 `/projects/{}/{}` 那条「扫不动」里
```

`//` 后面那对**反引号本身就长得像模板串**，于是一句解释性注释被读成三次真调用。
「只在字符串里找就等于排除了注释」这句话——两把尺子的说明都写过——
**对反引号引的路径不成立**。

换空白而不是删掉，是因为本工具报的是 `file:line`：整段删会让后面每一行左移，
尺子于是指向别处，而**一个指错地方的红比不报更糟**（人会去改一段本来对的代码）。

## 两侧各读什么

- **前端**：`web/lib/` 里 `${base}/…` 形态的模板字面量 URL。`${…}` 归一成 `{}`，
  方法从同一个调用里的 `method:` 取，取不到按 `GET`（`fetch` 的默认值）。
  `new EventSource(…)` 也算 GET。
- **后端**：把每个 `create_*_app` 工厂**真造出来读它的路由表**——
  不是读文档、不是读注释，是读 FastAPI 自己注册的那一份。
  路径里的 `{param}` 同样归一成 `{}`：前端拼的是值，后端写的是参数名，
  两边只有形状可比。

## 造不出来的 app 必须报出来

少枚举一个 app，它的路由就全变成「后端没有」，那会造出一堆假红；
反过来把「造不出来」当成「没有路由」，真正缺的端点就藏在噪音里了。
所以 `unbuildable_apps` 单独列出来，**NEVER 悄悄跳过**。
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
# 以脚本方式跑时仓库根不在 sys.path 上，import flint.* 会全军覆没——
# 而那会让**每一条**前端调用都变成「后端没有」，一屏假红。
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
FRONTEND_DEFAULT = REPO_ROOT / "web" / "lib"

# `${...}/path/${...}/suffix` —— 取反引号模板里、以 `${` 开头紧跟 `/` 的那种 URL。
# 后面可以跟任意多段 `+ \`…\``：真实代码里长 URL 是拼出来的（`interventionClient.ts:84`
# 就是三段拼成 `/deliverables/{}/sections/{}/regenerate?project_id=…`）。
# **只读第一段会把它截成 `/deliverables/{}`，然后报一条根本不存在的不匹配**——
# 首版就是这么造出两条假红的。
_TEMPLATE_URL = re.compile(r"`\$\{[^`]*?\}(/[^`]*)`((?:\s*\+\s*`[^`]*`)*)")
_CONCAT_PIECE = re.compile(r"`([^`]*)`")
# 路径也可能不在调用点上：`derefClient.ts` 把六条路径放在一张表里
# （`` `/facts/${enc(id)}` ``），调用处只写 `${base}${PATHS[kind](id)}`。
# 只认调用点的话，这六条**一条都扫不到**——而扫不到与「全都对得上」长得一模一样。
_PATH_LITERAL = re.compile(r"`(/[a-z][^`]*)`")
_INTERP = re.compile(r"\$\{[^}]*\}")
# 同一个调用里的 method: "POST"
_METHOD = re.compile(r"""method:\s*["']([A-Z]+)["']""")

# 后端 app 工厂：模块 → (工厂名, Deps 类名 | None)
_FACTORIES = [
    ("flint.api.views", "create_views_app", "ViewsApiDeps"),
    ("flint.api.combo", "create_combo_app", "ComboApiDeps"),
    ("flint.api.analysis", "create_analysis_app", "AnalysisApiDeps"),
    ("flint.api.deliverables", "create_deliverables_app", "DeliverableApiDeps"),
    ("flint.api.interventions", "create_interventions_app", "InterventionApiDeps"),
    ("flint.api.deref", "create_deref_app", "DerefApiDeps"),
    ("flint.api.compose", "create_compose_app", "ComposeApiDeps"),
    ("flint.api.graph_edges", "create_graph_edge_app", "GraphEdgeDeps"),
    ("flint.api.pack", "create_pack_app", "PackApiDeps"),
    ("flint.api.app", "create_app", None),
]


def normalize(path: str) -> str:
    """`/deliverables/{id}/blocks` 与 `/deliverables/${x}/blocks` 归一成同一形状。

    前端拼的是**值**，后端写的是**参数名**——两边只有形状可比。
    """
    path = _INTERP.sub("{}", path)
    path = re.sub(r"\{[^}]*\}", "{}", path)
    path = path.split("?")[0].rstrip("/")
    return path or "/"


def _dummy(field: dataclasses.Field[Any]) -> Any:
    """给 Deps 造一个占位值。**只为枚举路由**——路由表与依赖的取值无关。"""
    if field.name == "dsn":
        return "postgresql://x/x"
    if field.default is not dataclasses.MISSING:
        return field.default
    if field.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
        return field.default_factory()  # type: ignore[misc]
    return _Anything()


class _Anything:
    """对任何调用都回自己的占位件（工厂若在构造期用了依赖，也不会当场炸）。"""

    def __call__(self, *_a: Any, **_k: Any) -> _Anything:
        return self

    def __getattr__(self, _n: str) -> _Anything:
        return self


def backend_routes() -> tuple[dict[str, set[str]], list[str]]:
    """(归一路径 → 方法集, 造不出来的 app 清单)。"""
    import importlib

    routes: dict[str, set[str]] = {}
    unbuildable: list[str] = []
    for module_name, factory_name, deps_name in _FACTORIES:
        try:
            module = importlib.import_module(module_name)
            factory = getattr(module, factory_name)
            if deps_name is None:
                app = factory("postgresql://x/x")
            else:
                deps_cls = getattr(module, deps_name)
                kwargs = {f.name: _dummy(f) for f in dataclasses.fields(deps_cls)}
                app = factory(deps_cls(**kwargs))
        except Exception as err:  # noqa: BLE001 — 造不出来要报出来，不是跳过
            unbuildable.append(f"{module_name}.{factory_name}: {type(err).__name__}: {err}")
            continue
        for route in app.routes:
            path = getattr(route, "path", None)
            methods = getattr(route, "methods", None)
            if path is None or methods is None:
                continue
            routes.setdefault(normalize(path), set()).update(methods)
    return routes, unbuildable


def _display(path: Path) -> str:
    """仓库内给相对路径，仓库外（测试的 tmp 目录）给绝对路径。

    首版直接 relative_to(REPO_ROOT)，对着 tmp 目录跑当场 ValueError——
    而那正是阴性对照要用的跑法：**尺子自己不能只在仓库里活着**。
    """
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _blank_comments(text: str) -> str:
    """把 `//` 行注释与 `/* */` 块注释**换成等长空白**，换行原样留着。

    保长是硬要求：本工具报 `file:line`，而行号是按偏移量数换行数出来的。
    删掉注释会让后面每一行左移——尺子指错地方比不报更糟。

    字符串字面量里的 `//`（比如 `"http://x"`）不能误伤，所以按状态机走一遍，
    在引号内（`'` `"` 反引号）时不认注释起点。
    """
    out: list[str] = []
    i, n = 0, len(text)
    quote: str | None = None
    while i < n:
        ch = text[i]
        if quote is not None:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"`":
            quote = ch; out.append(ch); i += 1; continue
        if text.startswith("//", i):
            end = text.find("\n", i)
            end = n if end == -1 else end
            out.append(" " * (end - i))
            i = end
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end == -1 else end + 2
            # 块注释里的换行要留着，否则后面每一行的行号都会往上跳。
            out.append("".join(
                "\n" if c == "\n" else " " for c in text[i:end]))
            i = end
            continue
        out.append(ch); i += 1
    return "".join(out)


def frontend_calls(root: Path) -> list[dict[str, Any]]:
    """`web/lib/` 里的请求调用（路径形状 + 方法 + 位置）。

    **先剥注释**（`_blank_comments`）：注释里写着的路径会随代码改动而过时，
    把它当成「前端在调这条」是假实况。见模块说明里那段根因。
    """
    calls: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.ts")):
        if ".test." in path.name or ".spec." in path.name:
            continue
        # **先归一行尾再剥注释**：CRLF 下按 `\n` 找注释末尾会漏掉 `\r`，
        # 那正是兄弟单 `CRLF-BREAKS-COMMENT-STRIPPING` 记的那种失效。
        text = _blank_comments(
            path.read_text(encoding="utf-8").replace("\r\n", "\n"))
        lines = text.split("\n")
        seen_spans: list[tuple[int, int]] = []
        for match in _TEMPLATE_URL.finditer(text):
            seen_spans.append(match.span())
            line_no = text[: match.start()].count("\n") + 1
            # 方法在同一个调用里：从 URL 往后看几行，取第一个 method:
            window = "\n".join(lines[line_no - 1: line_no + 6])
            method = _METHOD.search(window)
            tail = "".join(_CONCAT_PIECE.findall(match.group(2) or ""))
            calls.append({
                "path": normalize(match.group(1) + tail),
                "method": method.group(1) if method else "GET",
                "file": _display(path),
                "line": line_no,
            })
        # 表里的路径字面量（不在调用点上的那种）。跳过已被上面收走的片段。
        for match in _PATH_LITERAL.finditer(text):
            if any(a <= match.start() < b for a, b in seen_spans):
                continue
            line_no = text[: match.start()].count("\n") + 1
            window = "\n".join(lines[line_no - 1: line_no + 6])
            method = _METHOD.search(window)
            calls.append({
                "path": normalize(match.group(1)),
                "method": method.group(1) if method else "GET",
                "file": _display(path),
                "line": line_no,
            })
    return calls


def shape_matches(call_path: str, route_path: str) -> bool:
    """前端路径与后端路由**按段**比。

    前端的 `{}` 段可以对上后端的字面量段：`/projects/{}/${kind}` 里的 `${kind}`
    取值是 `report` / `proposal` / `analysis`，而后端那三条是**字面量**路由。
    从静态文本看不出它取哪个值，所以这一段只能按「可能是任何值」处理。
    反过来不成立：前端写死的字面量必须对上后端的字面量或参数段。
    """
    a, b = call_path.split("/"), route_path.split("/")
    if len(a) != len(b):
        return False
    return all(x == y or x == "{}" or y == "{}" for x, y in zip(a, b, strict=True))


def _allowed_methods(call_path: str, routes: dict[str, set[str]]) -> set[str] | None:
    exact = routes.get(call_path)
    if exact is not None:
        return exact
    loose: set[str] = set()
    for route_path, methods in routes.items():
        if shape_matches(call_path, route_path):
            loose |= methods
    return loose or None


def audit(frontend: Path) -> dict[str, Any]:
    routes, unbuildable = backend_routes()
    calls = frontend_calls(frontend)
    mismatches = []
    for call in calls:
        allowed = _allowed_methods(call["path"], routes)
        if allowed is None:
            mismatches.append({**call, "why": "后端没有这条路径"})
        elif call["method"] not in allowed:
            mismatches.append({
                **call,
                "why": f"路径在，但方法不允许（后端允许 {sorted(allowed)}）",
            })
    return {
        "schema": "fe-api-contract/1",
        "backend_routes": {p: sorted(m) for p, m in sorted(routes.items())},
        "unbuildable_apps": unbuildable,
        "frontend_calls": calls,
        "mismatches": mismatches,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="前端调用 ↔ 后端路由 对账")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--frontend", default=str(FRONTEND_DEFAULT))
    args = parser.parse_args(argv)

    report = audit(Path(args.frontend))

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if report["mismatches"] else 0

    print(f"后端路由 {len(report['backend_routes'])} 条；"
          f"前端调用 {len(report['frontend_calls'])} 条")
    if report["unbuildable_apps"]:
        print(f"造不出来的 app {len(report['unbuildable_apps'])} 个（它们的路由没进对账面）：")
        for item in report["unbuildable_apps"]:
            print(f"    · {item}")

    if not report["mismatches"]:
        print("前端每条调用都能在后端路由表里找到。")
        return 0

    print(f"\n对不上的调用 {len(report['mismatches'])} 条：", file=sys.stderr)
    for m in report["mismatches"]:
        print(f"    ✗ {m['file']}:{m['line']}  {m['method']} {m['path']}  —— {m['why']}",
              file=sys.stderr)
    print("前端照着写就会 404 / 405，而那在界面上只是「没拿到」。", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
