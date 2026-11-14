"""BL-09：V2 护栏尺子——数据模型已给 locale 的地方 NEVER 硬编码 zh/中文/weibo。

用法：python tools/check_locale_seam.py [--json] [--root <目录>…]
退出码 0 = 没有硬编码的地区假设；1 = 有（逐条点名文件:行号）。

## 为什么现在挡

`docs/v2-backlog.md#V2-001`（owner @2026-07-30）：全球版是**往已留插槽里加东西**，
不是推倒重来——契约层的 `locale` / `region` / `lang` 已经是一等公民
（`contracts/models.py` 第 58/278/289/296/602/684/883/898 行）。

护栏原话：「V1 写 prompt / 模板 / 相关性判断时，**在数据模型已给 locale 字段的地方
NEVER 硬编码「中文/zh/微博」假设**」。

**现在挡比将来改便宜**：一处硬编码今天是一行，V2 时是一处要回头找的暗坑——
而它不会报错，只会在别的地区上悄悄给出中文口径的结果。

## 两条判据（都只认**代码**，不认注释与 docstring）

1. **分支假设**：`==` / `!=` / `in` 与写死的地区字面量比较
   （`lang == "zh"`、`source_id in ("weibo",)`）。
   这类代码写的是「只有一种地区」，V2 时每一处都要改。
2. **调用点写死**：给名为 `locale` / `lang` / `region` / `source_id` 的**关键字实参**
   传写死的地区值（`run_gate1(..., locale="zh-CN")`）。这类代码是**调用方替用户
   决定了地区**——值本该从 profile / 请求 / 配置里来。

   **构造一个值不算**（`UserProfile(locale="zh-CN")`）：那个字段是必填的，
   造一份档案/夹具就必须给它一个具体值。判据按被调者是不是**类名**（首字母大写）
   区分——首版没分，把三处夹具档案报成了违规（见 trace §5）。

## 三样**不算**违规（否则这把尺子会天天报噪音）

- **默认值**：`locale: str = "zh-CN"`、`payload.get("locale", "zh-CN")`
  ——默认说的是「今天跑哪个地区」，不是「只有这一个地区」；
- **类型标注**：`Literal["zh", "en"]`、`frozenset({"zh", "en"})`
  ——那是**声明支持面**，V2 时加一个成员即可；
- **数据表的键**：术语表里的 `"zh"` 列。

## 白名单：确实只属中国的源

`weibo` 源本体就是中国特有的（V2-001 原话：「现 4 源中 `weibo` 为中国特有」）。
豁免**逐条列名**，不是整目录放行——放一个目录，下一个人会把新代码写进那个目录。
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
DEFAULT_ROOTS: Final[tuple[str, ...]] = ("flint", "eval", "harness", "tools")
SKIP_DIRS: Final[frozenset[str]] = frozenset(
    {"__pycache__", ".venv", "node_modules", ".next", ".git"}
)

def _frozen_regions() -> frozenset[str]:
    """九区代码**从冻结件取**（`contracts_v04.Region`），NEVER 手抄一份。

    手抄的清单不会跟着冻结件变：V2 加一个地区，尺子仍按九个量，
    而**新加的那个地区从此不在护栏内**——最需要护栏的恰恰是新地区。

    取不到就 raise：**NEVER 退化成空集合**。空集合会让这半条护栏
    静静地不再报任何东西，而报告上写的是「0 处违规」。
    """
    from typing import get_args

    # 仓库根要在 `sys.path` 上：pytest 会替你放，`python tools/…` 不会。
    # 少了这句，CLI 跑法下这半条护栏会直接崩——
    # 而崩在**读冻结件**这一步，看起来像「冻结件坏了」。
    # （`WIRE-01` 在 `check_fe_be_parity.py` 撞过同一个坑。）
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from contracts_v04.models_v04 import Region

    regions = frozenset(str(x) for x in get_args(Region))
    if not regions:
        raise RuntimeError(
            "contracts_v04.Region 取不到成员——这半条护栏量不了，NEVER 当它通过")
    return regions


# 写死的地区字面量。
#
# ## 语言那一半（`GAUGE-07` 之前就有的）
#
# `en` 不在内——V1 是中文单市场，护栏挡的是「中文假设」；
# 把 en 也算进来会把「支持面声明」误报成假设。
#
# ## 地区那一半（`GAUGE-07` 补的）
#
# `A3` 明写是**两条轴**：语言与地区。而此前这个集合里**九区代码一个都没有**，
# 于是下面这两种写法从护栏下面走得过去：
#
#     if region == "CN":            # 分支假设
#     select_sources(region="CN")   # 调用点写死
#
# `BE-07` 的变异考⑳ 就是这么过的。
# 这把尺子自己的 docstring 写着「一处硬编码今天是一行，V2 全球版时是一处
# 要回头找的暗坑——**而它不会报错**」——地区那一半此前就在这个状态。
LOCALE_LITERALS: Final[frozenset[str]] = frozenset(
    {"zh", "zh-CN", "zh_CN", "zh-Hans", "中文", "weibo", "微博"}
) | _frozen_regions()
# 这些形参名意味着「这个值本该由上游给」
LOCALE_PARAMS: Final[frozenset[str]] = frozenset({"locale", "lang", "region", "source_id"})

# 豁免：确实只属中国的源本体，逐条列名 + 写明理由。
WHITELIST: Final[dict[str, str]] = {
    "flint/sources/weibo.py":
        "weibo 源本体就是中国特有的（V2-001：现 4 源中 weibo 为中国特有）",
    # `GAUGE-07` 加宽到九区之后新出现的**唯一**一处，逐条列名：
    "tools/orthogonality_check.py":
        "**另一把尺子的自证反例**。它的 `_BROKEN` 里故意写坏四条接线"
        "（`\"ja\" if region == \"JP\"`、`\"zh\" if region == \"CN\"`），"
        "用来证明自己报得出 A3 违规。把它判红等于逼那把尺子删掉自己的反例——"
        "而那条反例守的正是本尺子同一条纪律。"
        "（实测：加宽后全仓仅此文件 2 处命中，见 docs/trace/GAUGE-07.md）",
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    detail: str


def _locale_literals_in(node: ast.expr) -> list[str]:
    """节点里写死的地区字面量（含元组/列表/集合成员）。"""
    out: list[str] = []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if node.value in LOCALE_LITERALS:
            out.append(node.value)
    elif isinstance(node, ast.Tuple | ast.List | ast.Set):
        for element in node.elts:
            out.extend(_locale_literals_in(element))
    return out


def _is_construction(call: ast.Call) -> bool:
    """被调者是类名（首字母大写）→ 这是在**造一个值**，不是替调用链定地区。

    `UserProfile(locale="zh-CN")` 的 locale 字段是必填的，造夹具/档案就必须给值；
    `run_gate1(..., locale="zh-CN")` 则是把一个决定塞给了下游。
    """
    target = call.func
    name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
    return bool(name) and name[0].isupper()


def scan_source(source: str, display: str) -> list[Finding]:
    """一份源码里的两类命中。注释与 docstring 天然不进 AST，无需另剥。"""
    findings: list[Finding] = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            literals = _locale_literals_in(node.left)
            for comparator in node.comparators:
                literals.extend(_locale_literals_in(comparator))
            if literals:
                findings.append(Finding(
                    display, node.lineno, "branch",
                    f"分支假设：与写死的地区字面量比较 {sorted(set(literals))}",
                ))
        elif isinstance(node, ast.Call) and not _is_construction(node):
            for keyword in node.keywords:
                if keyword.arg in LOCALE_PARAMS:
                    literals = _locale_literals_in(keyword.value)
                    if literals:
                        findings.append(Finding(
                            display, node.lineno, "hardcoded-arg",
                            f"调用点写死：{keyword.arg}={literals[0]!r}"
                            "（该值本该来自 profile / 请求 / 配置）",
                        ))
    return findings


def _files(roots: list[str]) -> list[Path]:
    out: list[Path] = []
    for root in roots:
        base = REPO_ROOT / root
        if not base.exists():
            continue
        out.extend(
            p for p in sorted(base.rglob("*.py"))
            if not any(part in SKIP_DIRS for part in p.parts)
        )
    return out


def audit(roots: list[str], whitelist: dict[str, str] | None = None) -> dict[str, Any]:
    """扫一遍。`whitelist` 可注入——豁免机制本身要能被测，否则它是不是活的没人知道。"""
    rules = WHITELIST if whitelist is None else whitelist
    findings: list[Finding] = []
    exempted: list[Finding] = []
    unreadable: list[str] = []
    for path in _files(roots):
        display = path.relative_to(REPO_ROOT).as_posix()
        try:
            found = scan_source(path.read_text(encoding="utf-8"), display)
        except SyntaxError as err:            # 语法坏了要报出来，NEVER 当成「没命中」
            unreadable.append(f"{display}: {err}")
            continue
        # 豁免的**照样列出来**（进 exempted），只是不判红——
        # 藏起来的话，「白名单里那些文件有多少地区假设」就没人知道了。
        (exempted if display in rules else findings).extend(found)
    return {
        "schema": "locale-seam/1",
        "scanned": len(_files(roots)),
        "findings": [f.__dict__ for f in findings],
        "exempted": [f.__dict__ for f in exempted],
        "whitelist": rules,
        "unreadable": unreadable,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="V2 护栏：地区假设扫描")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--root", action="append", dest="roots")
    args = parser.parse_args(argv)

    report = audit(args.roots or list(DEFAULT_ROOTS))
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if report["findings"] or report["unreadable"] else 0

    print(f"扫描 {report['scanned']} 个 .py 文件")
    if report["exempted"]:
        print(f"白名单内命中 {len(report['exempted'])} 处（逐条列名豁免，见 WHITELIST）：")
        for item in report["exempted"]:
            print(f"    · {item['path']}:{item['line']} {item['detail']}")
    if report["unreadable"]:
        print(f"读不了的文件 {len(report['unreadable'])} 个（**没进扫描面**）：", file=sys.stderr)
        for item in report["unreadable"]:
            print(f"    ! {item}", file=sys.stderr)
    if not report["findings"]:
        print("没有硬编码的地区假设。")
        return 1 if report["unreadable"] else 0

    print(f"\n硬编码的地区假设 {len(report['findings'])} 处：", file=sys.stderr)
    for item in report["findings"]:
        print(f"    ✗ {item['path']}:{item['line']}  {item['detail']}", file=sys.stderr)
    print(
        "V2 全球版时，这些地方每一处都要回头改——而它们不会报错，"
        "只会在别的地区上悄悄给出中文口径的结果。", file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
