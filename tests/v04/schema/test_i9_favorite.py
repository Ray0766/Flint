"""SCHEMA-09 验收：I9 Favorite（基线内嵌快照；P1 采纳位注记）。

acceptance（tasks-v04.json#SCHEMA-09）：
  ① evidence_snapshot 内嵌 JSON；snapshot_stale 默认 False；
  ② P1 采纳时的 snapshot_id 替换位**以注释标记，不实现**。

## 为什么基线是「内嵌」而不是「引用 snapshot_id」

收藏要能长期翻回。若只存 `snapshot_id`，被引 snapshot 被 180 天周删任务清掉之后，
收藏就变成一个指向空处的壳——「已收藏但内容已被清理」。
基线因此**内嵌**证据快照：收藏自带内容，不依赖别人活着。

`§9-P1` 提案的做法是改回引用 + 给被引 snapshot 加冻结保护（周删跳过被收藏的）。
那是**提案**，owner 未采纳前 NEVER 实现——本卡只在替换位留注释标记，
并由测试断言「注释在、字段不在」。

## snapshot_stale 默认 False 的含义

stale 是**后端 Revalidator 的统一口径**算出来的（§6-H1），不是前端按时间戳推断的。
新收藏时还没算过，默认 False；置 True 只能来自 Revalidator。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

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
NOW = datetime(2026, 8, 2, tzinfo=UTC)

SNAPSHOT = {
    "cluster_id": "c-solid-state",
    "name_native": "全固体電池",
    "top_links": ["doc-1", "doc-2"],
    "captured_at": "2026-08-02T00:00:00Z",
}


def _favorite(**kw: object) -> object:
    base: dict[str, object] = {
        "favorite_id": "fav-1", "owner": M.Principal(kind="user", id="u1"),
        "target_kind": "cluster", "target_id": "c-solid-state",
        "evidence_snapshot": SNAPSHOT, "created_at": NOW}
    base.update(kw)
    return M.Favorite(**base)


def test_evidence_snapshot_is_embedded_json() -> None:
    fav = _favorite()
    assert isinstance(fav.evidence_snapshot, dict)
    assert fav.evidence_snapshot == SNAPSHOT, "内嵌快照 MUST 原样保存"


def test_snapshot_stale_defaults_to_false() -> None:
    """新收藏还没被 Revalidator 算过 → 默认 False。置 True 只能来自后端统一口径。"""
    assert _favorite().snapshot_stale is False


def test_favorite_survives_without_any_snapshot_id_reference() -> None:
    """基线不依赖外部 snapshot 存活——收藏自带内容。"""
    fav = _favorite()
    assert "snapshot_id" not in M.Favorite.__dataclass_fields__, (
        "基线 NEVER 用 snapshot_id 引用：被引快照被周删清掉后，收藏会变成指向空处的壳")
    assert fav.evidence_snapshot["name_native"] == "全固体電池"


def test_p1_replacement_site_is_marked_as_comment_only() -> None:
    """P1 采纳位：注释在、字段不在（提案未采纳前 NEVER 实现）。"""
    source = V04.read_text(encoding="utf-8")
    favorite_block = source[source.index("class Favorite:"):]
    favorite_block = favorite_block[:favorite_block.index("@dataclass", 10)]
    p1_comments = [ln for ln in favorite_block.split("\n")
                   if ln.strip().startswith("#") and "P1" in ln]
    assert p1_comments, "Favorite 里应有 P1 采纳位注释"
    assert any("snapshot_id" in ln for ln in favorite_block.split("\n")
               if ln.strip().startswith("#")), "P1 注释应写明将来替换成 snapshot_id 引用"
    # 「是不是真字段」以 dataclass 字段表为准，NEVER 按行文本猜——
    # docstring 里解释「若只存 snapshot_id 会怎样」的散文不是字段。
    assert "snapshot_id" not in M.Favorite.__dataclass_fields__, (
        "snapshot_id 只能停留在注释里，NEVER 成为真字段（P1 未采纳）")


def test_target_kind_covers_the_four_favoritable_things() -> None:
    from typing import get_args
    ann = M.Favorite.__dataclass_fields__["target_kind"].type
    assert set(get_args(eval(ann, vars(M)))) == {"cluster", "topic", "deliverable", "card"}
