"""PRIN-02 反例 fixture 包：七条原则的反例样本 + 后续测试的取用入口。

后续里程碑的测试这样用（这就是 acceptance 里「可被后续校验测试 import」的那条路径）：

    from tests.v04.principles.fixtures import load
    bad = load("B5")["counter_examples"]        # 跨区合并的反例句

## 数据从哪来

唯一来源是 `docs/PRINCIPLES-v04.md` 的「反例」段（它本身与工单 §3 逐字一致，由
PRIN-01 的校验器守着）。解析**复用** `tools/check_principles_doc.py` 的
`extract_section` / `split_principles`，NEVER 在这里新写一份 Markdown 解析。

`regenerate()` 负责把解析结果落成 JSON；测试则独立地重新解析文档来比对。
两条路都从文档出发、但各自走一遍，所以谁改了文档没重生成（或反过来手改了 JSON），
`test_fixtures_load.py` 就会红——这是漂移探测，不是自证。

## 一句反例怎么切成多条

反例段的写法是「反例一；反例二；反例三。」——去掉句末的「。」后按「；」切。
本节全部反例句里，「；」只出现在顶层分隔位置（括号与反引号内没有），故直接切安全。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent
REPO_ROOT = FIXTURE_DIR.parents[3]
DOC = REPO_ROOT / "docs" / "PRINCIPLES-v04.md"
_MARKER = "- **反例**："

if str(REPO_ROOT) not in sys.path:                       # 让 tools/ 可被 import
    sys.path.insert(0, str(REPO_ROOT))

from tools.check_principles_doc import split_principles  # 复用，NEVER 新写 Markdown 解析


def _doc_blocks() -> list[tuple[str, list[str]]]:
    return split_principles(DOC.read_text(encoding="utf-8"))


def principle_ids() -> list[str]:
    """文档里的原则编号（顺序即文档顺序）——以文档为准，不以文件系统为准。"""
    return [pid for pid, _ in _doc_blocks()]


def _raw_counterexample(pid: str) -> str:
    for block_id, body in _doc_blocks():
        if block_id != pid:
            continue
        for line in body:
            if line.startswith(_MARKER):
                return line[len(_MARKER):].strip()
    raise KeyError(f"PRINCIPLES#{pid} 在文档里没有「反例」段")


def counter_examples_of(pid: str) -> list[str]:
    """从文档现解析该条原则的反例条目（测试用它做独立比对）。"""
    raw = _raw_counterexample(pid).rstrip("。")
    return [item.strip() for item in raw.split("；") if item.strip()]


def _title_of(pid: str) -> str:
    text = DOC.read_text(encoding="utf-8")
    for line in text.split("\n"):
        if line.startswith(f"### PRINCIPLES#{pid} "):
            return line.split(" ", 2)[2].strip()
    return ""


def load(pid: str) -> dict[str, object]:
    """读一条反例 fixture。"""
    path = FIXTURE_DIR / f"{pid}.json"
    if not path.exists():
        raise FileNotFoundError(f"PRINCIPLES#{pid} 的反例 fixture 未生成：{path}")
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return data


def load_all() -> dict[str, dict[str, object]]:
    return {pid: load(pid) for pid in principle_ids()}


def regenerate() -> list[Path]:
    """按文档重新生成七份 fixture（幂等）。返回写出的文件。"""
    written: list[Path] = []
    for pid in principle_ids():
        payload = {
            "principle": pid,
            "title": _title_of(pid),
            "source": "docs/PRINCIPLES-v04.md",
            "raw": _raw_counterexample(pid),
            "counter_examples": counter_examples_of(pid),
        }
        path = FIXTURE_DIR / f"{pid}.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n",
        )
        written.append(path)
    return written
