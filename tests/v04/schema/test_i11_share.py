"""SCHEMA-11 验收：I11 ShareLink + friend 缝。

acceptance（tasks-v04.json#SCHEMA-11）：
  ① password 明文字段不存在（仅 hash）；
  ② friend 通道调用抛 `NotImplementedError('friends: post-v1')` 断言。

## 明文口令为什么连字段都不能有

不是「别往里写明文」，是**连放明文的地方都不留**。只要存在 `password: str` 字段，
就一定有人在某个构造点把明文塞进去——然后它随 ShareLink 一起进日志、进快照、进导出。
契约里只留 `password_hash`，明文在进入模型之前就必须消失。

## friend 缝为什么是抛错而不是 flag

`friend` 分享（只给好友可见）是 post-v1 的东西。留一个 `enabled=False` 的 flag，
意味着有人打开它就「能用」——而背后没有好友关系模型、没有鉴权路径。
抛 `NotImplementedError` 是唯一诚实的占位：调用点存在、语义已定、实现明确没有。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
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
NOW = datetime(2026, 8, 2, tzinfo=UTC)


def _link(**kw: object) -> object:
    base: dict[str, object] = {
        "token": "tok-abc", "target_kind": "deliverable", "target_id": "del-1",
        "created_by": M.Principal(kind="user", id="u1"), "expires_at": None,
        "revoked": False, "created_at": NOW}
    base.update(kw)
    return M.ShareLink(**base)


def test_no_plaintext_password_field_exists() -> None:
    """连放明文的地方都不留——有字段就一定有人往里塞。"""
    fields = set(M.ShareLink.__dataclass_fields__)
    assert "password" not in fields, "ShareLink 有明文口令字段：它会随对象进日志、快照、导出"
    assert "password_hash" in fields, "口令保护只以 hash 形态存在"


def test_password_hash_is_optional_and_defaults_to_none() -> None:
    assert _link().password_hash is None, "默认无口令保护"
    assert _link(password_hash="argon2id$...").password_hash == "argon2id$..."


def test_share_target_is_three_values() -> None:
    assert set(get_args(M.ShareTarget)) == {"deliverable", "graph", "topic"}


def test_expiry_and_revocation_are_separate_states() -> None:
    """「已过期」与「已撤销」是两件事，NEVER 合并成一个 bool。"""
    fields = set(M.ShareLink.__dataclass_fields__)
    assert {"expires_at", "revoked"} <= fields
    assert _link(expires_at=None).expires_at is None, "None = 不过期"


def test_friend_channel_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError) as err:
        M.share_with_friend(_link(), friend_user_id="u2")
    assert str(err.value) == "friends: post-v1", f"错误文本要逐字可断言：{err.value!r}"


def test_friend_channel_is_not_a_flag() -> None:
    """NEVER 留 enabled=False 式的开关——打开它就「能用」，而背后什么都没有。"""
    fields = set(M.ShareLink.__dataclass_fields__)
    assert not [f for f in fields if "friend" in f.lower()], (
        f"ShareLink 不该有 friend 相关字段：{sorted(fields)}")
