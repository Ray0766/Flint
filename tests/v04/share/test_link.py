"""HOTSPOT-08 验收：只读外链（匿名 viewer + 过期/密码 + 越权）。

acceptance（tasks-v04.json#HOTSPOT-08）：
  ① 匿名 viewer 走**同一 auth dependency**（H2 路由表断言）；
  ② 过期 **410** / 密码错 **401** / 改写请求 **403**；**明文密码不落库**。

## 三个状态码为什么不能合并成一个 404

- **410 Gone**：链接曾经有效、现在过期了。告诉持链人「你没走错，它到期了」——
  这决定他是去找人续期，还是以为自己拿错了链接。
- **401**：需要口令且没给对。
- **403**：链接有效、身份也对，但**这个动作**不允许（只读外链上的写请求）。

全都报 404 看起来「更安全」，实际是把三种完全不同的处境糊成一句「没有」，
让持链人无从判断下一步。真正需要藏的是「这个 token 存不存在」——
那一种才用 404（本卡不涉及枚举防护，留给路由层）。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"


def _models() -> object:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _models()
NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)

from flint.share.links import (
    ShareAccessError,
    anonymous_viewer,
    hash_password,
    resolve_share,
    verify_write_forbidden,
)


def _link(**kw: object) -> object:
    base: dict[str, object] = {
        "token": "tok-abc", "target_kind": "deliverable", "target_id": "del-1",
        "created_by": M.Principal(kind="user", id="u1"), "expires_at": None,
        "revoked": False, "created_at": NOW}
    base.update(kw)
    return M.ShareLink(**base)


# ── ① 匿名 viewer 走同一 auth 通道（H2） ────────────────────────

def test_anonymous_viewer_is_a_principal() -> None:
    """viewer 是 Principal 的一种，不是「绕过鉴权的特例」。

    这里按**实现的导入口径** `from contracts_v04.models_v04 import Principal` 取类型：
    本文件顶部用 `spec_from_file_location` 另加载了一份 models_v04，
    那会得到**两个不同的类对象**，isinstance 恒 False——错的是断言的取法，不是实现。
    """
    from contracts_v04.models_v04 import Principal

    viewer = anonymous_viewer("tok-abc")
    assert isinstance(viewer, Principal)
    assert viewer.kind == "user"
    assert "tok-abc" in viewer.id, "viewer 身份要带 token，便于审计追到是哪条链接"


def test_viewer_id_is_stable_for_the_same_token() -> None:
    assert anonymous_viewer("tok-abc") == anonymous_viewer("tok-abc")
    assert anonymous_viewer("tok-abc") != anonymous_viewer("tok-xyz")


def test_module_reuses_existing_principal_type() -> None:
    """H2：复用既有 Principal，NEVER 新写一个 viewer 身份类型。"""
    import inspect

    import flint.share.links as module

    source = inspect.getsource(module)
    assert "Principal" in source
    for forbidden in ("class ViewerPrincipal", "class AnonymousUser", "class ShareIdentity"):
        assert forbidden not in source, f"新写了身份类型：{forbidden}"


# ── ② 三个状态码 ────────────────────────────────────────────────

def test_valid_link_resolves() -> None:
    link = _link()
    got = resolve_share(link, now=NOW, password=None)
    assert got.target_id == "del-1"


def test_expired_link_is_410() -> None:
    link = _link(expires_at=NOW - timedelta(seconds=1))
    with pytest.raises(ShareAccessError) as err:
        resolve_share(link, now=NOW, password=None)
    assert err.value.status == 410
    assert "过期" in str(err.value)


def test_revoked_link_is_410_too() -> None:
    """撤销与过期都是「曾经有效、现在不是」——同一类处境，同一个码。"""
    with pytest.raises(ShareAccessError) as err:
        resolve_share(_link(revoked=True), now=NOW, password=None)
    assert err.value.status == 410


def test_missing_password_is_401() -> None:
    link = _link(password_hash=hash_password("s3cret"))
    with pytest.raises(ShareAccessError) as err:
        resolve_share(link, now=NOW, password=None)
    assert err.value.status == 401


def test_wrong_password_is_401() -> None:
    link = _link(password_hash=hash_password("s3cret"))
    with pytest.raises(ShareAccessError) as err:
        resolve_share(link, now=NOW, password="wrong")
    assert err.value.status == 401


def test_correct_password_passes() -> None:
    link = _link(password_hash=hash_password("s3cret"))
    assert resolve_share(link, now=NOW, password="s3cret").target_id == "del-1"


def test_write_request_is_403() -> None:
    """链接有效、身份也对，但**这个动作**不允许——403 不是 401 也不是 410。"""
    with pytest.raises(ShareAccessError) as err:
        verify_write_forbidden(method="POST")
    assert err.value.status == 403
    for safe in ("GET", "HEAD"):
        verify_write_forbidden(method=safe)


def test_expiry_is_checked_before_password() -> None:
    """过期链接即使给对口令也不放行——先判「还有效吗」，再判「你是谁」。"""
    link = _link(expires_at=NOW - timedelta(days=1), password_hash=hash_password("s3cret"))
    with pytest.raises(ShareAccessError) as err:
        resolve_share(link, now=NOW, password="s3cret")
    assert err.value.status == 410


# ── 明文密码不落库 ──────────────────────────────────────────────

def test_password_is_hashed_not_stored_plain() -> None:
    digest = hash_password("s3cret")
    assert digest != "s3cret"
    assert "s3cret" not in digest
    assert hash_password("s3cret") == digest, "同口令同 hash（可校验）"
    assert hash_password("s3cret") != hash_password("s3cret2")


def test_share_link_has_no_plaintext_password_field() -> None:
    assert "password" not in M.ShareLink.__dataclass_fields__
    assert "password_hash" in M.ShareLink.__dataclass_fields__


def test_error_never_echoes_the_password() -> None:
    """报错文本 NEVER 回显口令——错误信息会进日志。"""
    link = _link(password_hash=hash_password("s3cret"))
    with pytest.raises(ShareAccessError) as err:
        resolve_share(link, now=NOW, password="my-wrong-guess")
    assert "my-wrong-guess" not in str(err.value)
