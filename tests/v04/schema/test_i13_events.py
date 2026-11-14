"""SCHEMA-13 验收：事件与作业增量（3 JobKind + 7 payload 判别成员）。

acceptance（tasks-v04.json#SCHEMA-13）：
  ① 事件名全集唯一且 payload 判别可解析；**design_check 三态含 unreported**；
  ② P3 基线：delta 入 replay；ephemeral 位**以注释标记采纳位**。

## design_check 为什么要三态

`passed: bool` 只有过与不过——**「没跑过自检」被迫伪装成其中一个**。
报 False 是冤枉（没跑不等于不合格），报 True 是撒谎。第三态 `unreported` 让
「这次没自检」能如实说出来，前端才可能显示「未自检」而不是绿勾或红叉。

## P3：delta 入 replay 是基线

设计台流式增量若不入 replay，断线重连后用户看到的是**残缺的一半**——
SSE 的 `Last-Event-ID` 补发机制拿不到没存的东西。
`§9-P3` 提案的 ephemeral（delta 不落库、只走内存）是**提案**，owner 未采纳前 NEVER 实现，
只在采纳位留注释。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import get_args

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"


def _load() -> object:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _load()

NEW_JOB_KINDS = {"translate", "design_generate", "template_solidify"}
NEW_PAYLOAD_KINDS = {
    "design_delta", "design_tool_call", "design_clarify", "design_check",
    "translate_progress", "solidify_result", "graph_stale_notice",
}


def test_three_new_job_kinds_added_without_losing_old_ones() -> None:
    kinds = set(get_args(M.JobKind))
    assert NEW_JOB_KINDS <= kinds
    assert {"gate1_analysis", "report", "proposal", "spec_export",
            "revalidation", "daily_ingest", "pricebook_scan"} <= kinds, "既有七值 NEVER 丢"
    assert len(kinds) == 10


def test_event_names_are_unique_across_the_whole_union() -> None:
    """事件名全集唯一：判别字段撞名 = 解析出错的对象却看不出错。"""
    members = get_args(M.JobEventPayload)
    kinds: list[str] = []
    for member in members:
        kind_ann = member.__dataclass_fields__["kind"].type
        values = get_args(eval(kind_ann, vars(M)))
        assert len(values) == 1, f"{member.__name__}.kind 应是单值 Literal，实为 {values}"
        kinds.append(values[0])
    assert len(kinds) == len(set(kinds)), f"事件名有重复：{kinds}"
    assert NEW_PAYLOAD_KINDS <= set(kinds)
    assert len(members) == 11, f"四旧 + 七新 = 11，实为 {len(members)}"


def test_payload_discriminator_resolves_to_exactly_one_member() -> None:
    """判别可解析：按 kind 能唯一定位到成员类。"""
    by_kind = {}
    for member in get_args(M.JobEventPayload):
        kind = get_args(eval(member.__dataclass_fields__["kind"].type, vars(M)))[0]
        by_kind[kind] = member
    assert by_kind["design_delta"].__name__ == "DesignDelta"
    assert by_kind["translate_progress"].__name__ == "TranslateProgress"
    assert by_kind["graph_stale_notice"].__name__ == "GraphStaleNotice"


def test_design_check_has_three_states_including_unreported() -> None:
    """三态：过 / 不过 / **没跑过**。bool 会逼「没跑过」伪装成其中一个。"""
    states = set(get_args(M.DesignCheckState))
    assert states == {"passed", "failed", "unreported"}, f"三态不符：{sorted(states)}"

    ann = M.DesignCheck.__dataclass_fields__["state"].type
    assert "DesignCheckState" in str(ann)
    assert "passed" not in M.DesignCheck.__dataclass_fields__, (
        "NEVER 保留 passed: bool —— 它正是逼「没自检」撒谎的那个字段")


def test_design_check_unreported_is_constructible() -> None:
    c = M.DesignCheck(kind="design_check", state="unreported", findings=[])
    assert c.state == "unreported"


def test_delta_enters_replay_by_baseline() -> None:
    """P3 基线：delta 入 replay —— 不入的话断线重连只能拿到残缺的一半。"""
    d = M.DesignDelta(kind="design_delta", seq=3, fragment="<section>")
    assert d.seq == 3, "有 seq 才能进 replay 补发（SSE Last-Event-ID）"
    assert "seq" in M.DesignDelta.__dataclass_fields__


def test_p3_ephemeral_is_comment_only() -> None:
    """P3 的 ephemeral（delta 不落库）是提案，采纳位只留注释，NEVER 成为字段。"""
    source = V04.read_text(encoding="utf-8")
    block = source[source.index("class DesignDelta:"):]
    block = block[:block.index("@dataclass", 10)]
    comments = [ln for ln in block.split("\n") if ln.strip().startswith("#")]
    assert any("P3" in ln for ln in comments), "DesignDelta 处应有 P3 采纳位注释"
    assert any("ephemeral" in ln for ln in comments), "注释应写明 ephemeral 的采纳方式"
    assert "ephemeral" not in M.DesignDelta.__dataclass_fields__, (
        "ephemeral 只能停留在注释里（P3 未采纳）")


def test_new_job_kinds_reuse_the_existing_stream() -> None:
    """§6-H4：新 payload 进的是同一个 JobEventPayload 联合，NEVER 另开一条流。"""
    with pytest.raises(AttributeError):
        _ = M.DesignEventPayload  # 不该存在第二条事件流的联合类型
