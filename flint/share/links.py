"""HOTSPOT-08：只读外链的解析与门禁。

## 三个状态码为什么不能合并成一个 404

- **410 Gone**: 链接曾经有效、现在过期或被撤销。告诉持链人「你没走错, 它到期了」——
  这决定他是去找人续期, 还是以为自己拿错了链接。
- **401**: 需要口令而没给对。
- **403**: 链接有效、身份也对, 但**这个动作**不允许（只读外链上的写请求）。

全报 404 看起来「更安全」, 实际是把三种完全不同的处境糊成一句「没有」,
让持链人无从判断下一步。真正需要藏的是「这个 token 存不存在」——
那一种才用 404（枚举防护属路由层, 本模块不涉及）。

## 判断顺序: 先「还有效吗」, 再「你是谁」

过期链接即使给对口令也不放行。反过来（先验口令再验有效期）会把「已过期」
泄露成「口令错」, 也让一条死链接还能被拿来试口令。

## viewer 不是绕过鉴权的特例（§6-H2）

匿名 viewer 是 `Principal` 的一种, 复用既有身份类型与中间件;
id 里带 token, 便于审计追到是哪条链接。NEVER 新写一个 viewer 身份类。

## 口令只以 hash 存在

`ShareLink` 上没有明文字段（SCHEMA-11 已钉死）。本模块的 `hash_password`
是**确定性**的（同口令同 hash, 可校验）; 报错文本 NEVER 回显口令——错误信息会进日志。
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime
from typing import Any

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# 口令 hash 的固定盐。生产实现应换成 per-link 随机盐 + argon2（K 组选型）;
# 本轮是 fixture 档: 确定性、可校验、且明文永不落库。
_SALT = b"flint-share-v04"


class ShareAccessError(Exception):
    """外链访问被拒。`status` 是要回给调用方的 HTTP 码。"""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def anonymous_viewer(token: str) -> Any:
    """匿名 viewer 身份。复用既有 `Principal`（§6-H2）, id 带 token 便于审计。"""
    from contracts_v04.models_v04 import Principal

    return Principal(kind="user", id=f"share-viewer:{token}")


def hash_password(password: str) -> str:
    """确定性口令 hash。明文 NEVER 落库、NEVER 出现在返回值里。"""
    return hashlib.sha256(_SALT + password.encode("utf-8")).hexdigest()


def resolve_share(link: Any, *, now: datetime, password: str | None) -> Any:
    """解析一条外链。先判有效期与撤销, 再判口令。"""
    if link.revoked:
        raise ShareAccessError(410, "该分享链接已被撤销（曾经有效，现在不是）")
    if link.expires_at is not None and link.expires_at <= now:
        raise ShareAccessError(410, "该分享链接已过期（曾经有效，现在不是）")

    if link.password_hash is not None:
        if password is None:
            raise ShareAccessError(401, "该分享链接需要口令")
        if not hmac.compare_digest(hash_password(password), link.password_hash):
            raise ShareAccessError(401, "口令不正确")   # NEVER 回显口令本身
    return link


def verify_write_forbidden(*, method: str) -> None:
    """只读外链上的写请求 → 403（不是 401, 也不是 410: 身份没问题, 动作不允许）。"""
    if method.upper() not in _SAFE_METHODS:
        raise ShareAccessError(403, f"只读分享链接不接受 {method.upper()} 请求")
