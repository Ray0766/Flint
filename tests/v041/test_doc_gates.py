"""GAUGE-01：六把文档尺接进 `pytest -q`，并把「两把尺子一红一绿」钉成回归。

acceptance（tasks-v041-b2.json#GAUGE-01）：
  ① `python tools/check_principles_doc.py docs/PRINCIPLES-v04.md` exit 0；
  ② 逐把跑六把文档尺，任一 exit≠0 即红——`pytest -q` 从此覆盖它们；
  ③ 既有 `tests/v04/principles` 五条一字不改；构造用例证明「文档改歪 → 新测试红、旧测试仍绿」。

## F-11 是怎么发生的

`DEC-007` 把 `web/src/` 重映射成 `web/`，改了 `WORKORDER-v04.md#3` 的两条「校验点」，
**没改** `docs/PRINCIPLES-v04.md` 的同两行。于是 PRIN-01 的哈希不变量（落盘文档与工单
§3 正文逐字节相等）破了，`tools/check_principles_doc.py` 从那天起 exit 1。

而它 exit 1 这件事**没有任何人看见**：全局门是 `ruff && mypy && pytest -q`，
六把文档尺一把都不在里面。`pytest tests/v04/principles` 那 5 条量的是「反例 fixture
与文档反例段一一对应」——与哈希无关，所以它一直绿。两把尺子量同一份文档，一红一绿，
而门里跑的是绿的那把：`DEC-019` 当天引用的「5 passed」因此是**无效证据**。

## 这个文件为什么不是「再写一把尺子」

尺子已经有六把，缺的是**它们被跑**。所以这里不重新实现任何校验逻辑，只做两件事：
把六把尺子逐个 `subprocess` 起来断 exit 0（于是 `pytest -q` 覆盖它们），以及用一条
构造用例把 F-11 的形态本身钉成回归——文档改歪时，新尺子必须红，而旧的 5 条仍绿。
少了后半句，这个文件就只是「多跑了几条命令」，下次同类漂移仍可能只被绿的那把量到。

## 构造用例为什么敢改真文件

`test_tampered_doc_reddens_new_gate_while_old_tests_stay_green` 必须改**真** 文件：
旧那 5 条读的是 `docs/PRINCIPLES-v04.md` 这个固定路径，改副本证明不了「旧测试仍绿」。
原始字节在 try 前读出、finally 写回；用例最后再断言一次文件已复原且尺子回到 exit 0。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PRINCIPLES_DOC = REPO / "docs" / "PRINCIPLES-v04.md"

# 六把文档尺的**规范调用**，逐字取自 WORKORDER-v04.md#8 的 V0/V1 出口命令清单。
# id 用于测试名；argv 是相对仓库根的命令行（不含 python 解释器）。
DOC_GATES: list[tuple[str, list[str]]] = [
    ("check_principles_doc", ["tools/check_principles_doc.py", "docs/PRINCIPLES-v04.md"]),
    ("check_grounding_spec", ["tools/check_grounding_spec.py", "docs/grounding_spec_v04.md"]),
    ("check_techplan_delta", ["tools/check_techplan_delta.py", "docs/技术方案-v1.2-delta.md"]),
    ("check_fe_doc", ["tools/check_fe_doc.py", "docs/前端功能说明-v2.md", "--min-screens", "16"]),
    ("validate_dag_v04", ["tools/validate_dag_v04.py", "--file", "tasks-v04.json"]),
    (
        "check_frozen_additive_models",
        ["tools/check_frozen_additive.py", "contracts/models.py", "contracts_v04/models_v04.py"],
    ),
    (
        "check_frozen_additive_protocols",
        [
            "tools/check_frozen_additive.py",
            "contracts/protocols.py",
            "contracts_v04/protocols_v04.py",
        ],
    ),
]


def run_gate(argv: list[str]) -> subprocess.CompletedProcess[str]:
    """跑一把尺子。stdout/stderr 是中文，Windows 默认 GBK 会炸——恒 UTF-8 解码。"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [sys.executable, *argv],
        cwd=REPO,
        check=False,                       # 非 0 是本文件的**判据**，不是异常
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


@pytest.mark.parametrize("gate_id,argv", DOC_GATES, ids=[g[0] for g in DOC_GATES])
def test_doc_gate_exits_zero(gate_id: str, argv: list[str]) -> None:
    """② 六把尺子逐把 exit 0；任一非 0 即红。①（principles 那把）是其中一条。"""
    result = run_gate(argv)
    assert result.returncode == 0, (
        f"{gate_id} exit {result.returncode}（规范调用：python {' '.join(argv)}）\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


def test_all_six_gates_are_covered() -> None:
    """名单本身也要守：漏登记一把尺子，等于那把尺子仍在门外。"""
    tools = {argv[0] for _, argv in DOC_GATES}
    assert tools == {
        "tools/check_principles_doc.py",
        "tools/check_grounding_spec.py",
        "tools/check_techplan_delta.py",
        "tools/check_fe_doc.py",
        "tools/validate_dag_v04.py",
        "tools/check_frozen_additive.py",
    }
    for _, argv in DOC_GATES:
        assert (REPO / argv[0]).exists(), f"{argv[0]} 不存在"


def test_tampered_doc_reddens_new_gate_while_old_tests_stay_green() -> None:
    """③ 把 F-11 的形态钉成回归：同一份文档被改歪，新尺子红、旧那 5 条仍绿。

    改的是「校验点」段——F-11 就长在这里（`web/src/` 未随 DEC-007 重映射）。
    这一段不进旧测试的比对面（旧测试只看「反例」段），所以旧测试察觉不到，
    而哈希不变量会立刻破。这正是「两把尺子量同一件事、一红一绿」的可复现形态。
    """
    original = PRINCIPLES_DOC.read_bytes()
    text = original.decode("utf-8")
    marker = "- **校验点**："
    assert marker in text, "文档里找不到「校验点」段，构造用例的前提不成立"
    tampered = text.replace(marker, marker + "（构造漂移·GAUGE-01）", 1)
    assert tampered != text

    try:
        PRINCIPLES_DOC.write_bytes(tampered.encode("utf-8"))

        new_gate = run_gate(["tools/check_principles_doc.py", "docs/PRINCIPLES-v04.md"])
        assert new_gate.returncode != 0, (
            "文档已被改歪，principles 尺子仍 exit 0 —— 哈希不变量没在守\n"
            f"{new_gate.stdout}"
        )

        old_tests = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/v04/principles", "-q"],
            cwd=REPO,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=dict(os.environ, PYTHONIOENCODING="utf-8"),
        )
        assert old_tests.returncode == 0, (
            "旧那 5 条在同一次改歪下也红了 —— 构造用例没打在 F-11 的形态上"
            f"（它该是「旧测试看不见」的那一类漂移）\n{old_tests.stdout}"
        )
    finally:
        PRINCIPLES_DOC.write_bytes(original)

    assert PRINCIPLES_DOC.read_bytes() == original, "构造用例没把文档复原"
    restored = run_gate(["tools/check_principles_doc.py", "docs/PRINCIPLES-v04.md"])
    assert restored.returncode == 0, f"复原后尺子仍红：{restored.stdout}{restored.stderr}"
