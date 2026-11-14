"""STALE-01 / DEC-039：全仓禁止用时间戳算术得出「陈旧」。

## 禁的是什么

`clusters.last_active` 就在手边，拿它跟今天一比就能算出「多少天没动了」，
再把结果叫做 `stale`。**那一版看起来更完整，而它说的每一句都是假的**——

热点簇不是一份分析：它不引用事实，**它是事实的来源之一**。`Revalidator`
判的是「一份分析引用过的事实变没变」，要 `project_id`、账本版本、被引用的那些事实三样，
而 `clusters` 表一样都没有。拿时间戳顶上去，**是新写一套比对**
（`SLOT-02` acceptance① 明令禁止），**而且它说的是系统不知道的事**。

## 不禁的是什么（这条边界比禁令本身更要紧）

库里今天有三处正当的时间戳算术，一处都不该被这把尺子碰：

| 出处 | 算什么 |
|---|---|
| `flint/signals.py` | `novelty`：`first_seen` 距今 ≤ 7 天，规格 `#3.3` 的信号 |
| `flint/lineage/s4.py` | `dormant`：**沉寂**，血缘状态机 S4 |
| `flint/hotness.py` | `age_days`：热度衰减的年龄项 |

三处都不叫「陈旧」。`SLOT-02` 单里那句话是这条边界的出处：
**「沉寂」是个有用的东西，但它不叫「陈旧」**。把它们一起禁掉的尺子会当场废掉三个
正确实现，而那种尺子会在第一次误报之后被人整条注释掉——**那时它一条都不再守**。

所以规则是**两个条件同时成立**才算违规：

1. 表达式里有 `last_active` / `first_seen`（含驼峰）参与的**算术或比较**；
2. 这个表达式被绑到一个**陈旧词**上——赋值目标 / 字典键 / 关键字参数 / 函数名。

## 为什么走 AST 而不是逐行正则

`flint/fav/stale.py` 的 docstring 逐字写着「更 NEVER 按时间戳推断新鲜度」，
`StaleNotEvaluated` 抛出的中文里带着「不陈旧」。**它们是禁令的解释，不是违规。**
逐行正则会把写清楚这条禁令的人罚掉——本仓已经栽在这同一个形状上七次。

Python 侧只看**真的把表达式绑到陈旧名上**的 AST 节点（docstring 是 `Expr`、
异常消息是 `Call` 的实参，天然不在其列）；TS 侧没有 AST 可用（NEVER 新增依赖），
所以**先剥注释再判**，并且同样要求两个条件同时成立。

## 词是按 token 比的，不是按子串

`refresh_snapshot` 里有 `fresh`，`expires_at` 里有 `expire`。按子串比的话，
一次正当的刷新逻辑会被判成伪造陈旧。所以名字先按下划线与驼峰切成 token 再逐个比对；
中文词（陈旧 / 过期 / 新鲜）没有 token 边界，按子串比。

用法：

    python tools/check_no_timestamp_staleness.py [根目录]

退出码 0 = 干净；1 = 有违规（逐条点名文件与行）。
"""
from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# 参与算术就构成第一个条件的那些字段。驼峰形态是前端搬运层的命名法——
# 只认下划线的话，这条捷径过一次搬运就隐身了。
TIMESTAMP_FIELDS: tuple[str, ...] = (
    "last_active", "lastActive", "first_seen", "firstSeen",
)

# 绑定名里出现这些 token（或中文子串）= 第二个条件。
STALE_TOKENS: frozenset[str] = frozenset({
    "stale", "staleness", "outdated", "expired", "fresh", "freshness",
})
STALE_SUBSTRINGS: tuple[str, ...] = ("陈旧", "过期", "新鲜")

# 扫描面：产品代码与判据。构建产物与第三方目录跳过——
# 它们里面的匹配既不是本仓写的，也改不动。
SOURCE_SUFFIXES: frozenset[str] = frozenset({".py", ".ts", ".tsx"})
PRUNED_DIRS: frozenset[str] = frozenset({
    "node_modules", ".next", "__pycache__", ".git", ".venv", "venv",
    "dist", "build", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".ui-probe", "htmlcov", "site-packages",
})

_TOKEN_SPLIT = re.compile(r"[^0-9A-Za-z]+|(?<=[a-z0-9])(?=[A-Z])")
_LINE_COMMENT = re.compile(r"//[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_QUOTED_STRING = re.compile(r"'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"")
# 一处绑定：`name =` 或 `name:`（`==` / `=>` / `<=` 之类不算赋值）。
_TS_BINDING = re.compile(r"(?P<name>[A-Za-z_$][\w$]*)\s*(?:=(?![=>])|:)")
# 右值里要有真的算术或比较，光有字段名不算。
_TS_ARITHMETIC = re.compile(r"[-+]|[<>]=?|\bgetTime\b|\bdiff\b")


@dataclass(frozen=True)
class Violation:
    """一处「据时间戳置陈旧」。**点名文件与行**——不点名的话，读到红的人要自己去全仓找。"""

    path: Path
    line: int
    binding: str
    field: str
    snippet: str

    def __str__(self) -> str:
        try:
            where = self.path.relative_to(REPO).as_posix()
        except ValueError:
            where = self.path.as_posix()
        return (
            f"{where}:{self.line}: 「{self.binding}」据 {self.field} 做算术得出陈旧"
            f" —— DEC-039 全仓禁止（{self.snippet}）"
        )


def is_staleness_name(name: str) -> bool:
    """名字是不是在说「陈旧」。**按 token 比**：`refresh_snapshot` 不算。"""
    if any(sub in name for sub in STALE_SUBSTRINGS):
        return True
    tokens = {t.lower() for t in _TOKEN_SPLIT.split(name) if t}
    return bool(tokens & STALE_TOKENS)


def _timestamp_in_arithmetic(node: ast.AST) -> tuple[str, str] | None:
    """表达式里有没有时间戳字段参与的算术或比较。返回 (字段, 片段)。"""
    for sub in ast.walk(node):
        if not isinstance(sub, (ast.BinOp, ast.Compare)):
            continue
        # `ast.unparse` 对 `ast.parse` 出来的树恒能还原——这里 NEVER 兜一个空 except：
        # 兜住之后，一个真的解析不出来的模块会被静静跳过，而**跳过与干净长得一模一样**。
        source = ast.unparse(sub)
        for field in TIMESTAMP_FIELDS:
            if field in source:
                return field, source[:120]
    return None


def _bindings(tree: ast.AST) -> list[tuple[str, ast.AST, int]]:
    """(绑定名, 值表达式, 行号)。

    四种写法都要收：落地成变量 / 塞进字典 / 当关键字实参传 / 从陈旧名的函数里返回。
    只认第一种的话，`return {"stale": now - t > N}` 一行就绕过去了。
    """
    found: list[tuple[str, ast.AST, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and node.value is not None:
            for target in node.targets:
                found.append((ast.unparse(target), node.value, node.value.lineno))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value:
            found.append((ast.unparse(node.target), node.value, node.value.lineno))
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    found.append((key.value, value, value.lineno))
        elif isinstance(node, ast.keyword) and node.arg:
            found.append((node.arg, node.value, node.value.lineno))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not is_staleness_name(node.name):
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return) and sub.value is not None:
                    found.append((node.name, sub.value, sub.value.lineno))
    return found


def scan_python(source: str, path: Path) -> list[Violation]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    seen: set[tuple[int, str]] = set()
    out: list[Violation] = []
    for name, value, line in _bindings(tree):
        if not is_staleness_name(name):
            continue
        hit = _timestamp_in_arithmetic(value)
        if hit is None:
            continue
        key = (line, name)
        if key in seen:
            continue
        seen.add(key)
        out.append(Violation(path, line, name, hit[0], hit[1]))
    return out


def _blank(match: re.Match[str]) -> str:
    """把一段抹成等长空白，**换行保留**——剥完还要按位置算行号。"""
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_ts_comments(source: str) -> str:
    return _LINE_COMMENT.sub(_blank, _BLOCK_COMMENT.sub(_blank, source))


def strip_ts_strings(source: str) -> str:
    """抹掉单双引号字符串字面量。

    **不抹不行**：`firstSeen: "2026-08-01"` 里那两个连字符长得和减法一模一样，
    于是一份纯数据的夹具会被判成「据时间戳算陈旧」。第一版就是这么误报了三处。
    反引号模板留着——`${}` 里可能是真代码，抹掉会把真违规藏起来。
    """
    return _QUOTED_STRING.sub(_blank, source)


def _right_hand_side(text: str, start: int) -> str:
    """从 `=` / `:` 之后取到同层的 `,` `;` `}` 为止。

    按**深度**收边而不是按行收边：箭头函数常把签名与函数体分成两行
    （`const isOutdated = (c) =>` 换行再算），逐行判的话两边各自都不成立。

    ## 值本身以 `{` 开头时，右值**到它自己那个配对的 `}` 为止**

    `WB-01` 现场逮到的一次误报：`FavoritesLibrary.tsx` 里那句

        data-favorite-stale={item.stale === null ? "not_checked" : String(item.stale)}

    右值以 `{` 开头，于是它自己的 `}` 只是把 depth 从 1 降回 0——
    **收不了边**，扫描一路往下跑，把整个组件剩下的 3787 个字符都算成右值，
    里面正好有 `firstSeen={item.face.firstSeen}`（另一处、另一件事），
    于是判成「据 firstSeen 算陈旧」。**那一处一次算术都没有。**

    `{` 单独处理而 `(` / `[` 照旧：`const f = (c) => Date.now() - c.firstSeen`
    的右值以 `(` 开头，收在配对括号处的话只剩一个 `(c)`，
    **真违规会被藏起来**。而以 `{` 开头的两种情况（JSX 属性值、对象字面量）
    都确实在配对的 `}` 处结束。
    """
    head = start
    while head < len(text) and text[head].isspace():
        head += 1

    if head < len(text) and text[head] == "{":
        depth = 0
        for index in range(head, len(text)):
            char = text[index]
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
                if depth == 0:
                    return text[head:index + 1]
        return text[head:]

    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            if depth == 0:
                return text[start:index]
            depth -= 1
        elif char in ",;" and depth == 0:
            return text[start:index]
    return text[start:]


def scan_typescript(source: str, path: Path) -> list[Violation]:
    """TS 侧没有 AST 可用（NEVER 新增依赖），所以：剥注释 → 抹字符串 → 按绑定取右值。

    **判的是右值，不是整段**。整段判会把 `const full = { firstSeen: "…", stale: true }`
    这种纯数据夹具报红——那一段里两个词都在，而它们之间没有任何关系。
    """
    text = strip_ts_strings(strip_ts_comments(source))
    out: list[Violation] = []
    seen: set[tuple[int, str]] = set()

    for match in _TS_BINDING.finditer(text):
        name = match.group("name")
        if not is_staleness_name(name):
            continue
        rhs = _right_hand_side(text, match.end())
        field = next((f for f in TIMESTAMP_FIELDS if f in rhs), None)
        if field is None or not _TS_ARITHMETIC.search(rhs):
            continue
        line = text.count("\n", 0, match.start("name")) + 1
        key = (line, name)
        if key in seen:
            continue
        seen.add(key)
        out.append(Violation(path, line, name, field, " ".join(rhs.split())[:120]))
    return out


def scan_file(path: Path) -> list[Violation]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    if path.suffix == ".py":
        return scan_python(source, path)
    return scan_typescript(source, path)


def scan_tree(root: Path) -> list[Violation]:
    """整棵树。稳定排序，让报告在两次运行之间逐字一致。"""
    out: list[Violation] = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in SOURCE_SUFFIXES or not path.is_file():
            continue
        if any(part in PRUNED_DIRS for part in path.parts):
            continue
        out.extend(scan_file(path))
    return sorted(out, key=lambda v: (v.path.as_posix(), v.line, v.binding))


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else REPO
    violations = scan_tree(root)
    if not violations:
        print(f"干净：{root} 下没有据时间戳推断的陈旧（DEC-039）")
        return 0
    print(f"发现 {len(violations)} 处据时间戳推断的陈旧（DEC-039 全仓禁止）：")
    for violation in violations:
        print(f"  {violation}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
