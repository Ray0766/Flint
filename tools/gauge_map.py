"""GAUGE-02 清点器：把「每条 acceptance 归哪把尺子、那把尺子在不在全局门」机械地算出来。

用法：
  python tools/gauge_map.py                      # 重算并写 assets/gauge_map.json + docs/尺子清点-v041.md
  python tools/gauge_map.py --check              # 只算不写；与落盘副本不一致则 exit 1

## 这张卡要回答的问题

终检的一句话病理：**8 条缺陷里有 4 条不是尺子量错了，是压根没有那把尺子**。
逐条补洞治不了这个——补完还是不知道**还剩多少条没人守**。所以这里不补洞，
只做一件事：对 `tasks-v04.json` 全部 104 张卡的每一条 acceptance，机械地推出四元组

    卡号 / acceptance 原文 / 对应尺子 / 该尺子在不在全局门

## 全局门的口径（`worker.md` §5）

    ruff check . --no-cache && mypy --strict flint && pytest -q

三条命令，逐字。**前端 `npm test` 不在里面**——它要单独跑，所以由 vitest 守的
acceptance 一律归「有尺子但不在门内」。这不是贬低前端测试，是陈述一个事实：
合并时跑的那三条命令碰不到它们，忘了单独跑就没有人会知道。

## 尺子归属为什么只认 verify_cmd 与 outputs

acceptance③ 写死了：**NEVER 靠人肉判断**。人肉判断在这里恰恰最危险——
读一条 acceptance 然后"想起来"某个测试大概覆盖了它，得到的覆盖率是自我安慰。
所以归属只走两条机械路径：

  · `verify_cmd` 拆成命令序列，逐条解析出尺子（pytest 路径 / vitest 过滤器 / 工具脚本）；
  · 每把尺子的目标**必须在磁盘上真解析得到**，否则不算数（F-08 的形态：过滤器谁都匹配不上，
    却报绿）。

推不出的一律进第三类「查不到尺子」，**NEVER 猜一个塞进去凑覆盖率**。

## 工具脚本算不算"在门内"

`python tools/check_principles_doc.py` 这类尺子本身不是测试，`pytest -q` 不会跑它。
它在门内当且仅当 **`tests/` 下有文件把它起起来**——这一条也是机械查的（全文搜工具路径）。
F-11 的全部内容就是这一格从 False 变 True 之前没人看见：GAUGE-01 之后
`tests/v041/test_doc_gates.py` 把六把文档尺接进去了，这里就会如实报 True 并给出证据文件。

## 弱关联（`weak_link`）是另一把独立的尺，不参与三分类

三分类回答"有没有尺子、在不在门里"，但回答不了"那把尺子真的在量这条 acceptance 吗"。
所以另加一个正交信号：把 acceptance 里可机械提取的标识符（反引号片段、拉丁标识符、
路径）拿去尺子文件正文里搜，一个都搜不到就标 `weak_link`。

它**不**改变三分类（那会把机械判定和启发式判定混成一锅），只单独成表——
"有尺子、在门内、但 acceptance 提到的东西在尺子里一次都没出现"，这份名单是人该去看的地方。

## 这把尺子看不见什么（如实登记）

F-05 那一类——**尺子在、也在门里、但施加的压力够不到被测机制**（`GRAPH-06` acceptance②
的"服务端并发双写"打在一个纯函数上）。那需要抽掉机制看会不会红，属 `GAUGE-03`。
本工具是静态归属清点，NEVER 声称能查出这一类。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Final

REPO_ROOT = Path(__file__).resolve().parents[1]
TASKS = REPO_ROOT / "tasks-v04.json"
MAP_JSON = REPO_ROOT / "assets" / "gauge_map.json"
REPORT_MD = REPO_ROOT / "docs" / "尺子清点-v041.md"

# `GAUGE-09`：**同一套办法**对第 2 批再跑一遍。
#
# 为什么参数化而不是复制一份工具：复制出来的第二份从复制那一刻起就开始各走各的，
# 而这张卡的全部价值在于「用**同一把**尺子量两批」——两把尺子量出来的数没法比。
BATCHES: Final[dict[str, dict[str, Path]]] = {
    "v04": {
        "tasks": TASKS,
        "json": MAP_JSON,
        "md": REPORT_MD,
    },
    "b2": {
        "tasks": REPO_ROOT / "docs" / "steward" / "tasks-v041-b2.json",
        "json": REPO_ROOT / "assets" / "gauge_map_b2.json",
        "md": REPO_ROOT / "docs" / "尺子清点-v041-b2.md",
    },
}

GATE_COMMANDS = ("ruff check . --no-cache", "mypy --strict flint", "pytest -q")

CLASS_IN_GATE = "in_gate"
CLASS_OUTSIDE_GATE = "gauged_outside_gate"
CLASS_NO_GAUGE = "no_gauge"

CLASS_LABEL = {
    CLASS_IN_GATE: "有尺子且在门内",
    CLASS_OUTSIDE_GATE: "有尺子但不在门内",
    CLASS_NO_GAUGE: "查不到尺子",
}

_PYTEST_RE = re.compile(r"^(?:python -m )?pytest\s+(.*)$")
_VITEST_RE = re.compile(r"^npm test\s+--\s+--run\s+(\S+)")
_TOOL_PY_RE = re.compile(r"^python\s+(tools/\S+\.py)")
_TOOL_NODE_RE = re.compile(r"^node\s+(tools/\S+\.mjs)")

# 标识符：反引号片段里的 token + 正文里的拉丁/路径 token。长度 <3 的丢掉（i、id、to 这类
# 短 token 在任何文件里都能命中，留着会让 weak_link 恒为 False —— 那就等于没有这把尺。
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_./-]{2,}")
_IDENT_STOPWORDS = frozenset({
    "never", "and", "the", "not", "for", "with", "web", "src", "run", "npm", "test",
    "true", "false", "none", "null", "all", "any", "one", "two",
})


def _posix(path: Path) -> str:
    """排序键：按 posix 字符串逐码位比，各平台同序。

    `sorted(Path)` 在 Windows 上不分大小写、在 POSIX 上分——同一棵树两边排出来不一样，
    落盘的 json 换一台机器就「过期」。
    """
    return path.as_posix()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


class Repo:
    """一份仓库快照：磁盘解析与「谁在 tests/ 里起了这把工具」的索引都在这里。

    做成对象是为了测试能注入**构造的**索引（阴性对照要模拟「GAUGE-01 之前」那一刻，
    那时没有任何测试起 check_principles_doc.py）。
    """

    def __init__(self, root: Path, tool_invokers: dict[str, list[str]] | None = None) -> None:
        self.root = root
        self._text_cache: dict[str, str] = {}
        self._web_tests = [
            p for p in sorted((root / "web").rglob("*"), key=_posix)
            if ".test." in p.name and "node_modules" not in p.as_posix()
        ] if (root / "web").exists() else []
        self._tool_invokers = tool_invokers if tool_invokers is not None else self._scan_tools()

    def _scan_tools(self) -> dict[str, list[str]]:
        """哪些工具脚本被 `tests/` 下的文件起过 —— 逐字搜工具路径，不做语义分析。"""
        invokers: dict[str, list[str]] = {}
        tools_dir = self.root / "tools"
        tests_dir = self.root / "tests"
        if not tools_dir.exists() or not tests_dir.exists():
            return invokers
        tool_names = [f"tools/{p.name}" for p in sorted(tools_dir.iterdir(), key=_posix) if p.is_file()]
        for test_file in sorted(tests_dir.rglob("*.py"), key=_posix):
            body = _read_text(test_file)
            rel = test_file.relative_to(self.root).as_posix()
            for tool in tool_names:
                if tool in body:
                    invokers.setdefault(tool, []).append(rel)
        return invokers

    def resolve_path(self, rel: str) -> list[str]:
        target = self.root / rel
        if target.is_file():
            return [rel]
        if target.is_dir():
            return [
                p.relative_to(self.root).as_posix()
                for p in sorted(target.rglob("*.py"), key=_posix)
                if p.is_file()
            ]
        return []

    def resolve_vitest(self, pattern: str) -> list[str]:
        """vitest `--run <pattern>` 是路径子串过滤器，不是文件名——按子串解析。"""
        hits = [
            p.relative_to(self.root).as_posix()
            for p in self._web_tests
            if f"/{pattern}" in p.as_posix() or p.as_posix().startswith(f"web/{pattern}")
        ]
        return hits

    def tool_invokers(self, tool: str) -> list[str]:
        return self._tool_invokers.get(tool, [])

    def text_of(self, rel: str) -> str:
        if rel not in self._text_cache:
            self._text_cache[rel] = _read_text(self.root / rel)
        return self._text_cache[rel]


def parse_gauges(verify_cmd: str, repo: Repo) -> list[dict[str, Any]]:
    """把 verify_cmd 拆成尺子清单。解析不出的命令原样登记为 kind=unparsed。"""
    gauges: list[dict[str, Any]] = []
    for raw in verify_cmd.split("&&"):
        cmd = raw.strip()
        if not cmd or cmd.startswith("cd "):        # `cd web` 是换目录，不是尺子
            continue
        if m := _PYTEST_RE.match(cmd):
            paths = [tok for tok in m.group(1).split() if not tok.startswith("-")]
            files = [f for tok in paths for f in repo.resolve_path(tok)]
            gauges.append({
                "kind": "pytest", "command": cmd, "targets": paths,
                "files": files, "resolved": bool(files),
                # pytest -q 的 testpaths = ["tests"]（pyproject.toml），所以 tests/ 下的一律在门内
                "in_gate": bool(files) and all(f.startswith("tests/") for f in files),
                "gate_evidence": "pytest -q（testpaths=[\"tests\"]）" if files else "",
            })
        elif m := _VITEST_RE.match(cmd):
            files = repo.resolve_vitest(m.group(1))
            gauges.append({
                "kind": "vitest", "command": cmd, "targets": [m.group(1)],
                "files": files, "resolved": bool(files),
                "in_gate": False,
                "gate_evidence": "前端套件不在 ruff·mypy·pytest 三条命令里，须单独跑",
            })
        elif tool_match := (_TOOL_PY_RE.match(cmd) or _TOOL_NODE_RE.match(cmd)):
            tool = tool_match.group(1)
            invokers = repo.tool_invokers(tool)
            exists = bool(repo.resolve_path(tool))
            gauges.append({
                "kind": "tool", "command": cmd, "targets": [tool],
                "files": [tool] if exists else [], "resolved": exists,
                "in_gate": exists and bool(invokers),
                "gate_evidence": ("被 " + "、".join(invokers) + " 起起来") if invokers
                                 else "tests/ 下没有任何文件起它，pytest -q 碰不到",
            })
        else:
            gauges.append({
                "kind": "unparsed", "command": cmd, "targets": [], "files": [],
                "resolved": False, "in_gate": False,
                "gate_evidence": "命令形态无法机械解析",
            })
    return gauges


def identifiers_of(acceptance: str) -> list[str]:
    """acceptance 里可机械提取的标识符（去重、保序、去停用词）。

    斜杠既是路径分隔符也是**顿号**——`created_at/region/verdict_at_save` 是三个字段名并列，
    不是一个路径。整串与切分后的每一段都收进来：整串留着是为了真路径（`docs/x.md`）
    仍能整体命中，切段是为了并列写法不会因为"整串在测试里当然搜不到"而被误报成弱关联。
    误报会让弱关联表迅速失去可信度，而它唯一的用处就是被人真的看一眼。
    """
    found: list[str] = []
    seen: set[str] = set()

    def add(tok: str) -> None:
        low = tok.lower()
        if len(tok) < 3 or low in _IDENT_STOPWORDS or low in seen:
            return
        seen.add(low)
        found.append(tok)

    for tok in _IDENT_RE.findall(acceptance):
        add(tok)
        if "/" in tok:
            for part in tok.split("/"):
                add(part)
    return found


def classify_card(task: dict[str, Any], repo: Repo) -> list[dict[str, Any]]:
    """一张卡 → 它每条 acceptance 的四元组 + 弱关联标记。"""
    gauges = parse_gauges(task.get("verify_cmd", ""), repo)
    live = [g for g in gauges if g["resolved"]]
    corpus = "\n".join(repo.text_of(f) for g in live for f in g["files"])
    entries: list[dict[str, Any]] = []
    for index, acceptance in enumerate(task.get("acceptance", []), start=1):
        if not live:
            klass, reason = CLASS_NO_GAUGE, (
                "verify_cmd 为空" if not gauges
                else "verify_cmd 里的尺子一把都没在磁盘上解析出来"
            )
        elif any(g["in_gate"] for g in live):
            klass, reason = CLASS_IN_GATE, ""
        else:
            klass, reason = CLASS_OUTSIDE_GATE, "尺子解析得到，但不在 ruff·mypy·pytest 里"
        idents = identifiers_of(acceptance)
        hits = [tok for tok in idents if tok in corpus]
        entries.append({
            "task_id": task["id"],
            "acceptance_index": index,
            "acceptance": acceptance,
            "gauges": [
                {"kind": g["kind"], "command": g["command"], "files": g["files"],
                 "in_gate": g["in_gate"], "gate_evidence": g["gate_evidence"]}
                for g in gauges
            ],
            "class": klass,
            "in_gate": klass == CLASS_IN_GATE,
            "reason": reason,
            "identifiers": idents,
            "identifier_hits": hits,
            "weak_link": bool(idents) and not hits and klass != CLASS_NO_GAUGE,
        })
    return entries


def build_map(tasks_path: Path = TASKS, repo: Repo | None = None) -> dict[str, Any]:
    repo = repo or Repo(REPO_ROOT)
    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))["tasks"]
    entries: list[dict[str, Any]] = []
    for task in tasks:
        entries += classify_card(task, repo)
    counts = {k: sum(1 for e in entries if e["class"] == k)
              for k in (CLASS_IN_GATE, CLASS_OUTSIDE_GATE, CLASS_NO_GAUGE)}
    return {
        "generated_from": tasks_path.name,
        "gate_commands": list(GATE_COMMANDS),
        "cards": len(tasks),
        "acceptance_total": len(entries),
        "counts": counts,
        "weak_link_total": sum(1 for e in entries if e["weak_link"]),
        "entries": entries,
    }


def _report(data: dict[str, Any]) -> str:
    counts, entries = data["counts"], data["entries"]
    no_gauge = [e for e in entries if e["class"] == CLASS_NO_GAUGE]
    outside = [e for e in entries if e["class"] == CLASS_OUTSIDE_GATE]
    weak = [e for e in entries if e["weak_link"]]
    source = data["generated_from"]
    batch = "第 2 批（GAUGE-09）" if "b2" in source else "v0.4（GAUGE-02）"
    lines = [
        f"# 尺子清点 · {batch}",
        "",
        (f"> 本文件由 `python tools/gauge_map.py`（源：`{source}`）生成，"
         "NEVER 手改——手改会被 `pytest tests/v041/ -q` 里对应的那条判据抓红。"),
        "",
        "## 它回答的问题",
        "",
        ("终检的一句话病理是「8 条缺陷里有 4 条不是尺子量错了，是压根没有那把尺子」。"
         "逐条补洞回答不了「还剩多少条没人守」，所以这里对 "
         f"`{source}` 全部 **{data['cards']} 张卡、{data['acceptance_total']} 条 acceptance** "
         "机械地推出四元组：卡号 / acceptance 原文 / 对应尺子 / 那把尺子在不在全局门。"),
        "",
        "## 口径",
        "",
        ("- **全局门** = `" + "` · `".join(data["gate_commands"]) + "`（`worker.md` §5 逐字）。"
         "前端 `npm test` 要单独跑，故不算门内。"),
        ("- **尺子归属只认 `verify_cmd` 与 `outputs`**，且目标必须在磁盘上真解析得到；"
         "推不出的进第三类，NEVER 猜一个塞进去凑覆盖率。"),
        "- **工具脚本在门内** 当且仅当 `tests/` 下有文件把它起起来（逐字搜工具路径）。",
        "",
        "## 三类计数",
        "",
        "| 类 | 条数 | 含义 |",
        "|---|---|---|",
        f"| 有尺子且在门内 | **{counts[CLASS_IN_GATE]}** | 合并时跑那三条命令就会量到 |",
        f"| 有尺子但不在门内 | **{counts[CLASS_OUTSIDE_GATE]}** | 尺子存在，但门里跑不到它——F-11 就是这一格 |",
        f"| 查不到尺子 | **{counts[CLASS_NO_GAUGE]}** | 机械推不出任何尺子 |",
        "",
    ]

    lines += ["## 第三类逐条：查不到尺子", ""]
    if no_gauge:
        lines += ["| 卡号 | # | acceptance | 为什么推不出 |", "|---|---|---|---|"]
        lines += [
            f"| `{e['task_id']}` | {e['acceptance_index']} | {e['acceptance']} | {e['reason']} |"
            for e in no_gauge
        ]
    else:
        lines.append("**零条**——104 张卡的每一条 acceptance 都能从 `verify_cmd` 机械推出一把"
                     "真实存在的尺子。这是一条**阴性结论**，不是「没查」："
                     "解析器对 vitest 过滤器、pytest 路径、工具脚本三种形态各有分支，"
                     "任何一种解析不到都会落进本表——构造用例 "
                     "`tests/v041/test_gauge_map.py::test_control_unresolvable_gauge_lands_in_class_three` "
                     "对四种形态各造了一个反例，证明本表真的会落条目。")
    lines.append("")

    lines += [
        "## 第二类逐条：有尺子但不在门内",
        "",
        f"**{len(outside)} 条**。这一格是 F-11 的形态——尺子在，红了也没人看见。",
        "",
        "| 卡号 | # | 尺子 | 为什么不在门内 |",
        "|---|---|---|---|",
    ]
    for e in outside:
        gauge_desc = "；".join(f"`{g['command']}`" for g in e["gauges"]) or "（无）"
        why = "；".join(dict.fromkeys(g["gate_evidence"] for g in e["gauges"] if g["gate_evidence"]))
        lines.append(f"| `{e['task_id']}` | {e['acceptance_index']} | {gauge_desc} | {why} |")
    lines.append("")

    lines += [
        "## 弱关联：有尺子，但 acceptance 里的标识符在尺子正文里零命中",
        "",
        (f"**{len(weak)} 条**。这不参与三分类（三分类是机械判定，这一栏是启发式），单独成表："
         "acceptance 说要断言的东西，在那把尺子的源码里一次都没出现——该人去看一眼的就是这些。"),
        "",
        "| 卡号 | # | acceptance | 提取到的标识符 |",
        "|---|---|---|---|",
    ]
    for e in weak:
        lines.append(
            f"| `{e['task_id']}` | {e['acceptance_index']} | {e['acceptance']} | "
            f"{'、'.join('`' + i + '`' for i in e['identifiers'][:8])} |"
        )
    lines.append("")

    lines += [
        "## 这把尺子看不见什么（如实登记）",
        "",
        ("**F-05 那一类**：尺子在、也在门内、但施加的压力够不到被测机制"
         "（`GRAPH-06` acceptance② 的「服务端并发双写」打在一个纯函数上）。"
         "静态归属清点判不出这一类——要判它得抽掉机制看会不会红，那是 `GAUGE-03`。"),
        "",
        ("**acceptance 语义是否被真断言**：本工具只查标识符是否出现，不理解语义。"
         "弱关联表是提示，不是判决。"),
        "",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="acceptance ↔ 尺子清点器（GAUGE-02）")
    parser.add_argument("--check", action="store_true", help="只算不写；与落盘副本不一致则 exit 1")
    parser.add_argument("--batch", choices=sorted(BATCHES), default="v04",
                        help="量哪一批（v04 = GAUGE-02 的 104 卡；b2 = GAUGE-09 的 89 卡）")
    args = parser.parse_args(argv[1:])

    paths = BATCHES[args.batch]
    map_json, report_md = paths["json"], paths["md"]
    data = build_map(paths["tasks"])
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    report = _report(data)

    if args.check:
        stale: list[str] = []
        if not map_json.exists() or map_json.read_text(encoding="utf-8") != payload:
            stale.append(str(map_json.relative_to(REPO_ROOT)))
        if not report_md.exists() or report_md.read_text(encoding="utf-8") != report:
            stale.append(str(report_md.relative_to(REPO_ROOT)))
        if stale:
            print("落盘副本已过期：" + "、".join(stale) + "；跑 python tools/gauge_map.py 重生成",
                  file=sys.stderr)
            return 1
        print("gauge_map 落盘副本与实况一致")
        return 0

    map_json.parent.mkdir(parents=True, exist_ok=True)
    # **写回 `paths` 里那两个**，NEVER 写死 MAP_JSON/REPORT_MD——
    # 写死的话 `--batch b2` 会把第 2 批的结果盖到 v04 的文件上，
    # 而两份报告的标题都写着自己是对的（本卡实测差点这么干）。
    map_json.write_text(payload, encoding="utf-8")
    report_md.write_text(report, encoding="utf-8")
    counts = data["counts"]
    print(
        f"{data['cards']} 张卡 / {data['acceptance_total']} 条 acceptance："
        f"在门内 {counts[CLASS_IN_GATE]}、有尺子但不在门内 {counts[CLASS_OUTSIDE_GATE]}、"
        f"查不到尺子 {counts[CLASS_NO_GAUGE]}；弱关联 {data['weak_link_total']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
