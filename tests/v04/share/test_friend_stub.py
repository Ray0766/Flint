"""HOTSPOT-09 验收（后端半）：friend 通道是**诚实的缝**，不是一个假装能用的开关。

acceptance（tasks-v04.json#HOTSPOT-09）第二条的后端一侧：
**friend 项……后端抛 NotImplementedError 断言**。

## 为什么占位形态本身就是验收对象

`enabled=False` 式的 flag 占位意味着「有人把它打开就能用」——而背后既没有好友关系模型，
也没有鉴权路径。真打开的那天，分享给朋友这个动作会以**未定义的权限语义**执行。
抛 `NotImplementedError` 是唯一诚实的占位：调用点存在、语义已定、实现明确没有。

同样要守的是**没有人偷偷吞掉它**：一处 `except NotImplementedError: pass` 就会让
「分享给朋友」在界面上看起来成功了，而什么都没发生。
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
V04_SRC = REPO_ROOT / "contracts_v04" / "models_v04.py"


def _models() -> Any:
    spec = importlib.util.spec_from_file_location("models_v04", V04_SRC)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _models()


def _link() -> Any:
    from datetime import UTC, datetime

    return M.ShareLink(
        token="tok-1", target_kind="cluster", target_id="c-1",
        created_by=M.Principal(kind="user", id="u1"),
        expires_at=None, revoked=False, created_at=datetime(2026, 8, 3, tzinfo=UTC),
    )


def test_share_with_friend_raises_the_exact_contract_message() -> None:
    """消息逐字为 `friends: post-v1`：调用方（前端「即将上线」态）按它分派。"""
    with pytest.raises(NotImplementedError) as err:
        M.share_with_friend(_link(), "u2")

    assert str(err.value) == "friends: post-v1"


def test_the_stub_is_a_raise_not_a_flag() -> None:
    """占位形态断言：函数体只有一个 raise，且 friend 通道没有任何开关字段。

    `enabled=False` 式的占位意味着「打开就能用」，而背后没有好友关系模型、
    没有鉴权路径——打开的那天，这个动作会以未定义的权限语义执行。
    """
    tree = ast.parse(V04_SRC.read_text(encoding="utf-8"))
    funcs = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "share_with_friend"
    ]
    assert len(funcs) == 1
    body = [n for n in funcs[0].body if not isinstance(n, ast.Expr)]  # 去掉 docstring
    assert len(body) == 1
    assert isinstance(body[0], ast.Raise)

    for forbidden in ("friends_enabled", "friend_enabled", "enable_friends"):
        assert forbidden not in V04_SRC.read_text(encoding="utf-8")


def test_nobody_swallows_the_stub() -> None:
    """仓库里没有任何地方 `except NotImplementedError` 把这条缝吞掉。

    吞掉之后，「分享给朋友」在界面上看起来成功了，而什么都没发生——
    比报错难查得多，因为用户会以为对方收到了。
    """
    offenders: list[str] = []
    for path in (REPO_ROOT / "flint").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler) or node.type is None:
                continue
            names = (
                [node.type] if isinstance(node.type, ast.Name)
                else list(getattr(node.type, "elts", []))
            )
            if any(isinstance(n, ast.Name) and n.id == "NotImplementedError"
                   for n in names):
                offenders.append(f"{path}:{node.lineno}")
    assert offenders == [], f"有人吞掉了 NotImplementedError：{offenders}"


def test_share_link_keeps_expiry_and_revocation_apart() -> None:
    """「已过期」与「已撤销」是两件事：过期可续期，撤销不可逆，NEVER 合成一个 bool。

    合成之后，一条被撤销的链接会因为「续期」而复活——而撤销的本意是**永久收回**。
    """
    link = _link()
    assert hasattr(link, "expires_at")
    assert hasattr(link, "revoked")
    assert not hasattr(link, "password")      # 明文口令连字段都不留
    assert hasattr(link, "password_hash")
