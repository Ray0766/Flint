"""GAUGE-05 / 终检 F-12：卡面 `outputs` 声明 ↔ 仓库实况 对账器。

用法：python tools/check_outputs_declared.py [--json] [tasks-v04.json]
退出码 0 = 三类差异都只剩白名单里的历史条目；1 = 有新差异（逐条点名）。

## F-12 是什么裂缝

隔离带六卡（`isolation.owner_droppable`）存在的**全部理由**是一句承诺：
**owner 划掉一张 = 删一个文件，零返工**。终检查出这句话有一道绕过去的路径——

`flint/design/mock_syntax.py` **没有任何一张卡声明它**，却被两张隔离卡的产物同时 import
（`solidify.py`←DESIGN-28、`solidify_validator.py`←DESIGN-29）。于是「划掉 DESIGN-28」
没有一致的执行方式：只删卡上声明的 → 它变成没人认领的孤儿、还被 DESIGN-29 用着；
把它一并删掉 → DESIGN-29 当场断线。

终检同时确证 v0.4 的卡**普遍少声明**：至少三个由 v0.4 卡新建的实现文件不在任何 `outputs` 里
（`flint/graph/roles.py` / `flint/design/mock_syntax.py` / `flint/design/comment_job.py`），
其中 `comment_job.py` 尤其说明问题——**该卡自己的测试 import 的就是这个未声明的文件**。

## 三类差异

- **A 声明了但仓库没有**：卡面写了一个路径形态的产物，磁盘上不存在。
- **B 隔离带裂缝**：B1 = 无卡认领的模块被**两张以上卡**的产物共用且其中有隔离卡；
  B2 = 隔离卡的声明产物被**带外**文件 import。两者都让「划掉即删一个文件」失效。
- **C 少声明**：模块 docstring 自述某张 v0.4 卡号，却不在任何卡的 `outputs` 里。

C 的判据是**自述**，不是 mtime。终检对此有过一次自我更正：按「v0.4 期间被写入」筛出 14 个，
核下来必须剔除 worker 正在跑的 v0.4.1 产物与「既有文件被修改」两类——**mtime 区分不了新建与修改**。
自述能区分：写 docstring 的人当时就说明了这个文件是哪张卡的产物。

## 两条不是豁免的规则（写在这里，因为它们看起来像豁免）

1. **非路径形态的 outputs 不进 A 类**：`api: POST /favorites` 这类声明的是端点不是文件，
   拿去 `os.path.exists` 只会得到假红。它们被单独列出来（`non_path`），**NEVER 悄悄丢掉**——
   丢掉就等于这把尺子替它们盖了章。
2. **`__init__.py` 由同包兄弟带进来**：卡声明 `flint/profile/prefs.py` 时不可能不建
   `flint/profile/__init__.py`。同包内有该卡声明的模块 → 视为同一份产物。
   同包内**没有**该卡声明的任何模块时不适用（那种 `__init__.py` 仍然是 C 类）。

## 白名单

`LEGACY_UNDECLARED` 是**冻结闭集**：按 `(路径, 卡号)` 逐条豁免，每条带理由。
NEVER 放宽规则本身，NEVER 增补新条目——新的少声明应当被抓红而不是入册。
测试里另有一条反向断言：**白名单里的每一条今天仍然必须是一个真发现**，
否则那条豁免就在悄悄扩大（它豁免的东西已经不存在，剩下的只有它盖住的口子）。
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASKS = REPO_ROOT / "tasks-v04.json"

# 冻结闭集（首次机械审计 @2026-08-04 采集）。采集命令见 docs/trace/GAUGE-05.md。
LEGACY_UNDECLARED: dict[tuple[str, str], str] = {
    ("flint/graph/roles.py", "GRAPH-06"):
        "终检 F-12 确证：GRAPH-06 建的运行时，卡面 outputs 只列了前端目录与测试",
    ("flint/design/mock_syntax.py", "DESIGN-28"):
        "终检 F-12 确证：DESIGN-28 建、DESIGN-27/29 也用；产权待 owner 定（升基线件 or 明确挂靠）",
    ("flint/design/mock_syntax.py", "DESIGN-27"):
        "同一个文件的第二张认领卡：docstring 原话「DESIGN-27 定表，DESIGN-28 复用」——"
        "一个文件在自己的 docstring 里认了两张卡，这正是 F-12 说的产权未定",
    ("flint/design/comment_job.py", "DESIGN-12"):
        "终检 F-12 确证：该卡自己的测试 import 的就是它",
    ("flint/api/graph_edges.py", "GRAPH-07"):
        "docstring 自述「GRAPH-07：连线落盘端点」，卡面 outputs 只列了前端目录与测试",
    ("flint/registry/npm.py", "I18N-01"):
        "docstring 自述「registry 客户端·npm（I18N-01…）」，卡面 outputs 只列了 web/ 与 docs/",
    ("flint/graph/__init__.py", "GRAPH-01"):
        "包 docstring 写的是里程碑范围「GRAPH-01~16」而非单卡；GRAPH-01 的 outputs 无 flint/ 兄弟模块",
    ("flint/i18n/__init__.py", "I18N-01"):
        "同上：docstring 写的是「I18N-01~08」范围；I18N-01 的 outputs 无 flint/ 兄弟模块",
}

# B 类的历史条目：产权归属是 owner 决定（F-12 修法 2），本工具只负责让它一直可见。
LEGACY_SHARED: dict[str, str] = {
    "flint/design/mock_syntax.py":
        "终检 F-12：DESIGN-28 与 DESIGN-29 的产物同时 import 它，而它无卡认领",
}


@dataclass(frozen=True)
class Finding:
    kind: str          # "A" | "B1" | "B2" | "C"
    path: str
    detail: str
    card: str = ""

    def key(self) -> tuple[str, str]:
        return (self.path, self.card)


def classify_output(raw: str) -> tuple[str, str]:
    """(形态, 归一后的路径)。形态 ∈ path / annotated / non_path。"""
    text = raw.strip()
    if text.startswith("api:") or "…" in text or "," in text:
        return "non_path", text
    core = text.split("(")[0].strip().rstrip("/")
    return ("annotated" if "(" in text else "path"), core



class AmbiguousCardId(ValueError):
    """同一个卡号在多份任务表里各是一张卡 —— **报错，NEVER 挑一张**。

    `FIX-14`（v0.4.1 第 6 批）加的。静默挑第一张的后果实测过一次：
    一个 v0.4.1 的模块被拿去与 v0.4 那张同号卡的 outputs 比，
    然后被报成「少声明了一个产物」——**而那句话是假的**，
    它在自己那张卡上写得清清楚楚。

    误报比漏报更贵：漏报只是没抓住，误报会逼人去改一个没病的文件。
    """


def resolve_card(card: str, sources: Mapping[str, list[str]]) -> str | None:
    """卡号 → **唯一**那份任务表。有歧义就抛。

    `sources` 是 `{卡号: [任务表文件名…]}`。本仓今天有四张历史撞车
    （`tests/v041/test_card_id_unique.py#LEGACY_COLLISIONS` 逐条列名），
    它们**改不动**（两侧都已 verified，而台账 append-only），
    所以这道拒绝是它们唯一的安全网。

    **不在任何表里 → 回 `None`，NEVER 抛**：那不是歧义，
    而是「这个卡号没有卡」——那件事由 C 类自己去报（它报得更准，
    还会带上是哪个文件自述的）。在这里抛的话，
    一次「卡号打错了」会以 `KeyError` 收场，读起来像尺子崩了。
    """
    files = sources.get(card, [])
    if len(files) > 1:
        raise AmbiguousCardId(
            f"卡号 {card} 在多份任务表里各是一张卡：{files}。"
            "NEVER 挑一张——两侧的 outputs 不同，挑错了会把一个模块"
            "报成「少声明了产物」，而那句话是假的。"
        )
    return files[0] if files else None


def card_id_sources(repo: Path) -> dict[str, list[str]]:
    """全部任务表里 `卡号 → 出自哪几份表`。**跨批次**，不是只看一份。

    `FIX-14`：本仓有四张历史撞车（同号在 v0.4 与 v0.4.1 各是一张卡，
    outputs 完全不同）。只读一份表的话，撞车看不见——
    而看不见的撞车会以「少声明了一个产物」的形式冒出来，
    **那句话是假的**。
    """
    sources: dict[str, list[str]] = {}
    candidates = [repo / "tasks-v04.json", *sorted(
        (repo / "docs" / "steward").glob("tasks-*.json"))]
    for path in candidates:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        rows = data["tasks"] if isinstance(data, dict) and "tasks" in data else data
        for row in rows:
            sources.setdefault(str(row["id"]), []).append(path.name)
    return sources

def declared_map(tasks: list[dict]) -> dict[str, list[str]]:
    """归一路径 → 声明它的卡号（一个文件可能被多张卡声明）。"""
    out: dict[str, list[str]] = {}
    for task in tasks:
        for raw in task.get("outputs", []):
            shape, core = classify_output(raw)
            if shape != "non_path":
                out.setdefault(core, []).append(task["id"])
    return out


def non_path_outputs(tasks: list[dict]) -> list[tuple[str, str]]:
    return [
        (task["id"], raw)
        for task in tasks
        for raw in task.get("outputs", [])
        if classify_output(raw)[0] == "non_path"
    ]


def _owners(path: str, declared: dict[str, list[str]]) -> list[str]:
    """声明这个文件的卡；祖先目录被声明也算（卡常以目录为产物单位）。"""
    if path in declared:
        return declared[path]
    parts = path.split("/")
    for i in range(len(parts) - 1, 0, -1):
        ancestor = "/".join(parts[:i])
        if ancestor in declared:
            return declared[ancestor]
    return []


def _package_sibling_owner(path: str, card: str, declared: dict[str, list[str]]) -> bool:
    """`__init__.py` 的同包兄弟规则（见模块 docstring 规则 2）。"""
    if not path.endswith("/__init__.py"):
        return False
    package = path.rsplit("/", 1)[0] + "/"
    return any(
        other.startswith(package) and card in cards and other != path
        for other, cards in declared.items()
    )


def flint_modules(repo: Path) -> dict[str, ast.Module]:
    """repo/flint 下全部 .py 的 AST，键为相对仓库根的正斜杠路径。"""
    root = repo / "flint"
    trees: dict[str, ast.Module] = {}
    if not root.exists():
        return trees
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(repo).as_posix()
        trees[rel] = ast.parse(path.read_text(encoding="utf-8"))
    return trees


def _module_name(rel_path: str) -> str:
    stem = rel_path[:-3].replace("/", ".")
    return stem.removesuffix(".__init__")


def _flint_imports(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("flint"):
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names if a.name.startswith("flint"))
    return names


def audit(tasks: list[dict], repo: Path, isolation: list[str]) -> list[Finding]:
    """三类差异全表。返回的是**全部**发现，白名单过滤由调用方做（见 `live`）。"""
    declared = declared_map(tasks)
    card_ids = {task["id"] for task in tasks}
    sources = card_id_sources(repo)
    trees = flint_modules(repo)
    findings: list[Finding] = []

    # A：声明了但仓库没有
    for path, cards in sorted(declared.items()):
        if not (repo / path).exists():
            for card in cards:
                findings.append(Finding("A", path, "卡面声明了这个产物，仓库里没有", card))

    # C：docstring 自述某张卡、却无人声明
    for rel, tree in trees.items():
        if _owners(rel, declared):
            continue
        # **只看 docstring 首行**：本仓库的房规是 `"""CARD-ID：标题`，首行才是「这是谁的产物」。
        # 正文里提到别的卡号是**引用**（说明为什么这么写），不是自述。
        # 首版扫整段 docstring，DEF-01 新建的 `flint/fav/pin.py` 当场被误报——
        # 它首行写的是 DEF-01（v0.4.1 卡，不在这 104 张里），正文引了 FAV-01/FAV-02 讲理由。
        # **「引用某张卡」与「是某张卡的产物」是两件事**，混起来就会逼着后人把理由从注释里删掉。
        doc = (ast.get_docstring(tree) or "").splitlines()
        first_line = doc[0] if doc else ""
        for card in sorted(c for c in card_ids if c in first_line):
            if _package_sibling_owner(rel, card, declared):
                continue
            # FIX-14：**要报 C 之前**才查歧义，NEVER 更早。
            # 更早的话，`flint/design/__init__.py` 那种首行只提了一个卡号区间
            # （「DESIGN-01~32」）的包入口会先被拦下——而它本来就该由
            # 同包兄弟规则豁免掉。**顺序错了的尺子与真有病长得一模一样。**
            #
            # 到了这一步才是真要拿这个卡号去查 outputs 的时刻：
            # 卡号有歧义时**抛**，NEVER 挑一张。挑错的后果实测过一次：
            # 模块被拿去与同号那张**别的**卡的 outputs 比，
            # 然后报「少声明了一个产物」——而那句话是假的。
            resolve_card(card, sources)
            findings.append(
                Finding("C", rel, f"docstring 自述 {card}，却不在任何卡的 outputs 里", card)
            )

    # B：隔离带的两种裂缝
    importers: dict[str, list[str]] = {}
    for rel, tree in trees.items():
        for name in _flint_imports(tree):
            importers.setdefault(name, []).append(rel)

    for rel in trees:
        module = _module_name(rel)
        users = importers.get(module, [])
        owners = _owners(rel, declared)
        user_cards = sorted({c for user in users for c in _owners(user, declared)})
        if not owners and len(user_cards) >= 2 and any(c in isolation for c in user_cards):
            findings.append(Finding(
                "B1", rel,
                f"无卡认领，却被 {user_cards} 的产物共用（其中有隔离卡）："
                "划掉任一张都没有一致的执行方式", ""))
        if owners and any(c in isolation for c in owners):
            outside = sorted({
                c for user in users for c in _owners(user, declared) if c not in owners
            })
            if outside:
                findings.append(Finding(
                    "B2", rel,
                    f"隔离卡 {owners} 的产物被带外卡 {outside} 的文件 import：划掉会带塌它们", ""))
    return findings


def live(findings: list[Finding]) -> list[Finding]:
    """滤掉白名单里的历史条目，剩下的就是新差异。"""
    return [
        f for f in findings
        if not (f.kind == "C" and f.key() in LEGACY_UNDECLARED)
        and not (f.kind == "B1" and f.path in LEGACY_SHARED)
    ]


def load_tasks(path: Path) -> tuple[list[dict], list[str]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    tasks = data["tasks"] if isinstance(data, dict) and "tasks" in data else data
    isolation = []
    if isinstance(data, dict):
        isolation = list(data.get("isolation", {}).get("owner_droppable", []))
    return tasks, isolation


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="卡面 outputs 声明 ↔ 仓库实况 对账")
    parser.add_argument("tasks", nargs="?", default=str(DEFAULT_TASKS))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    tasks, isolation = load_tasks(Path(args.tasks))
    findings = audit(tasks, REPO_ROOT, isolation)
    remaining = live(findings)
    non_path = non_path_outputs(tasks)

    if args.json:
        print(json.dumps({
            "cards": len(tasks),
            "isolation": isolation,
            "findings": [f.__dict__ for f in findings],
            "live": [f.__dict__ for f in remaining],
            "non_path": non_path,
        }, ensure_ascii=False, indent=2))
        return 1 if remaining else 0

    print(f"卡 {len(tasks)} 张；隔离带 {isolation}")
    print(f"非路径形态的 outputs {len(non_path)} 条（不进 A 类，逐条列出）：")
    for card, raw in non_path:
        print(f"    · {card}  {raw}")
    for kind in ("A", "B1", "B2", "C"):
        rows = [f for f in findings if f.kind == kind]
        exempt = [f for f in rows if f not in remaining]
        print(f"\n{kind} 类：{len(rows)} 条（白名单豁免 {len(exempt)}，新差异 {len(rows) - len(exempt)}）")
        for f in rows:
            mark = "免" if f in exempt else "✗"
            print(f"    {mark} {f.path} {f.card} —— {f.detail}")

    if remaining:
        print(f"\n新差异 {len(remaining)} 条，NEVER 靠加白名单消掉——白名单是冻结闭集。", file=sys.stderr)
        return 1
    print("\n三类差异都只剩白名单里的历史条目。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
