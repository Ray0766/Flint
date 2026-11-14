"""SCHEMA-00 校验器：v04 副本相对 v0.3.3 冻结件**只加不删**（AST 级）。

用法：
  python tools/check_frozen_additive.py contracts/models.py contracts_v04/models_v04.py
  python tools/check_frozen_additive.py contracts/protocols.py contracts_v04/protocols_v04.py

## 为什么必须是 AST 级

文本 diff 判不出「只加不删」：换行、注释、docstring 改写都会让 diff 满屏，
而真正要守的是**符号与字段的存在性与形状**。所以这里比对的是：

  · 模块级类型别名（`Literal[...]` / 联合 `A | B`）——成员集合 base ⊆ v04；
    其余别名——值的源码逐字相同；
  · 类 —— base 的每个类都在；每个**字段的类型标注逐字相同**；
  · 函数/方法 —— base 的每个都在，且**签名逐字相同**。

加字段、加类、加别名成员、加方法：全部允许。删、改名、改标注、改签名：全部报错。

## 为什么别名要按成员集合比

`JobKind` 与 `JobEventPayload` 这类在 v04 要**增成员**（新增三种 JobKind、七个 payload
判别成员）。若按源码逐字比，加成员即报错——那就没法做增量了。
按成员集合比：少一个成员就红，多的随便加。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path


def _src(node: ast.AST) -> str:
    """结点的规范化源码。

    **NEVER 用 `ast.get_source_segment`**：`arguments` 结点没有 lineno/col_offset，
    它对函数签名一律返回 None —— 于是「签名被改」那条断言会拿 ""=="" 比，
    40 个方法签名全部空转。这个坑是被变异体 s5（删掉 CitationAligner.align 的
    stage 参数却没报错）抓出来的。`ast.unparse` 对任何结点都给规范化源码，
    顺带把换行与引号风格差异抹平——那些本就不算「改动」。
    """
    return ast.unparse(node)


def _members(node: ast.expr) -> set[str] | None:
    """Literal[...] 的字面量成员集合，或联合 A | B 的成员名集合；都不是则 None。"""
    if isinstance(node, ast.Subscript) and getattr(node.value, "id", "") == "Literal":
        sl = node.slice
        elts = sl.elts if isinstance(sl, ast.Tuple) else [sl]
        out: set[str] = set()
        for e in elts:
            if isinstance(e, ast.Constant):
                out.add(repr(e.value))
        return out or None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left, right = _members(node.left), _members(node.right)
        lset = left if left is not None else {ast.unparse(node.left)}
        rset = right if right is not None else {ast.unparse(node.right)}
        return lset | rset
    return None


class Surface:
    """一个模块的「对外形状」：别名 / 类字段 / 函数签名。"""

    def __init__(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        self.path = path
        self.aliases: dict[str, str] = {}
        self.alias_members: dict[str, set[str]] = {}
        self.classes: dict[str, dict[str, str]] = {}
        self.methods: dict[str, str] = {}

        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name):
                    members = _members(node.value)
                    if members is not None:
                        self.alias_members[target.id] = members
                    else:
                        self.aliases[target.id] = _src(node.value)
            elif isinstance(node, ast.ClassDef):
                fields: dict[str, str] = {}
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        fields[item.target.id] = _src(item.annotation)
                    elif isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                        self.methods[f"{node.name}.{item.name}"] = _src(item.args)
                self.classes[node.name] = fields
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                self.methods[node.name] = _src(node.args)


def compare(base: Surface, v04: Surface) -> list[str]:
    problems: list[str] = []

    for name, value in base.aliases.items():
        if name not in v04.aliases and name not in v04.alias_members:
            problems.append(f"别名被删：{name}")
        elif name in v04.aliases and v04.aliases[name] != value:
            problems.append(f"别名被改：{name}\n      base: {value}\n      v04 : {v04.aliases[name]}")

    for name, members in base.alias_members.items():
        if name not in v04.alias_members:
            problems.append(f"判别联合/枚举被删或改形：{name}")
            continue
        lost = sorted(members - v04.alias_members[name])
        if lost:
            problems.append(f"{name} 丢了成员：{lost}（只加不删）")

    for cname, fields in base.classes.items():
        if cname not in v04.classes:
            problems.append(f"类被删：{cname}")
            continue
        for fname, ann in fields.items():
            if fname not in v04.classes[cname]:
                problems.append(f"字段被删：{cname}.{fname}")
            elif v04.classes[cname][fname] != ann:
                problems.append(
                    f"字段标注被改：{cname}.{fname}\n      base: {ann}\n      v04 : {v04.classes[cname][fname]}")

    for mname, sig in base.methods.items():
        if mname not in v04.methods:
            problems.append(f"函数/方法被删：{mname}")
        elif v04.methods[mname] != sig:
            problems.append(f"签名被改：{mname}\n      base: ({sig})\n      v04 : ({v04.methods[mname]})")

    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"用法：python {Path(__file__).name} <冻结件> <v04 副本>", file=sys.stderr)
        return 2
    base_path, v04_path = Path(argv[1]), Path(argv[2])
    for p in (base_path, v04_path):
        if not p.exists():
            print(f"文件不存在：{p}", file=sys.stderr)
            return 1

    base, v04 = Surface(base_path), Surface(v04_path)
    problems = compare(base, v04)
    if problems:
        print(f"additive 校验不通过（{len(problems)} 项）：{base_path.name} → {v04_path.name}",
              file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    added_classes = sorted(set(v04.classes) - set(base.classes))
    added_fields = sum(
        len(set(v04.classes[c]) - set(base.classes[c])) for c in base.classes if c in v04.classes)
    added_members = sum(
        len(v04.alias_members.get(k, set()) - v) for k, v in base.alias_members.items())
    print(
        f"additive 校验通过：{v04_path.name} 保留了 {base_path.name} 的全部 "
        f"{len(base.classes)} 类 / {sum(len(f) for f in base.classes.values())} 字段 / "
        f"{len(base.methods)} 函数签名 / {len(base.aliases) + len(base.alias_members)} 别名；"
        f"新增 {len(added_classes)} 类、{added_fields} 字段、{added_members} 枚举/联合成员"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
