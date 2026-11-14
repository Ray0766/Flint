"""测试用的 Python 源码扫描口径（共享，NEVER 每张卡各写一遍）。

由来：「源码里不该出现 X」这类断言在 Python 侧踩了两次同一个坑——
**解释自己不做 X 的那句 docstring 被当成做了 X**（GRAPH-07 后端、DESIGN-11）。
前端侧同一个坑踩了六次后抽出了 `web/test-utils/source.ts#codeOnly`；
这里是它的 Python 对应物。

口径：按 **AST** 判而不是按字符串扫——注释与 docstring 根本不进 AST，
所以「解释」永远不会被误判成「实现」。
"""
from __future__ import annotations

import ast
from pathlib import Path


def code_names(path: Path) -> set[str]:
    """源码里**代码层面**出现过的名字：变量名、属性名、参数名、import 的模块与别名。

    用于断言「这个模块没有碰某个东西」。docstring 与注释里提到它是允许的
    （那通常正是在说明为什么不碰）。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
                if alias.asname:
                    names.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
            for alias in node.names:
                names.add(alias.name)
                if alias.asname:
                    names.add(alias.asname)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
            for arg in [*node.args.args, *node.args.kwonlyargs]:
                names.add(arg.arg)
        elif isinstance(node, ast.ClassDef):
            names.add(node.name)
    return names


def code_strings(path: Path) -> list[str]:
    """源码里的**字符串字面量**（不含 docstring）。

    用于断言「没有硬编码某段 SQL / 某个 URL」这类事——同样避开注释与 docstring。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                docstrings.add(doc)
    return [
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and n.value not in docstrings
    ]
