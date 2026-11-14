"""DESIGN-30：G5 模板注册表（CRUD / 版本递增 / checksum 去重）。

## 「不可用」的两种后果（E6 新降级行）

- **固化与生产渲染阻断**: 把一个存不进注册表的模板当成「已固化」, 下次生产渲染
  就会找不到它——而那时用户已经拿它出过东西了。
- **探索期不阻断**: 设计台里试样式、看预览不需要注册表参与。

把两者一起阻断, 会让一次存储故障变成「整个设计台不能用」;
所以报错文本里 MUST 写清**什么还能做**。

## 去重按内容, 不按名字

模板的身份是它的**内容**: 改个名字不构成新版本, 换了 HTML 才是。
checksum 由 `TemplateRecord` 侧的 `template_checksum(html)` 算出——
**NEVER 让调用方把 checksum 传进来**: 能传就意味着能传错, 而传错之后
「版本号没变、内容已变」就成立了（S2-2 第三条铁律: 产物可复现）。

## 旧版本不被覆盖

注册表是 append-only 的版本序列: 固化过的东西可能已经被别人拿去渲染了,
覆盖它等于让那些产物失去出处。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


class RegistryUnavailable(Exception):
    """注册表不可用：阻断固化与生产渲染，不阻断探索（E6）。"""


class TemplateRegistryLike(Protocol):
    """模板注册表的**形状**。内存件与 SQL 件（`pgregistry.py`）各实现一份。

    `PERSIST-03` 加的，与 `FavoriteStoreLike` 同一条理由：
    这个文件 39 行自己写着「SQL 实现随 E2 的表接入」，
    那么 `DesignApiDeps.registry` 本来就该声明成形状而不是内存件那一个类。

    `available` 在内存件上是一个字段、在 SQL 件上是一个 property——
    协议里写成属性，两种都满足。
    """

    @property
    def available(self) -> bool: ...

    def all(self) -> list[Any]: ...

    def append(self, record: Any) -> None: ...


@dataclass
class TemplateRegistry:
    """内存实现；SQL 实现随 E2 的 `template_registry` 表接入。"""

    available: bool = True
    _rows: list[Any] = field(default_factory=list)

    def all(self) -> list[Any]:
        return list(self._rows)

    def append(self, record: Any) -> None:
        self._rows.append(record)


def may_explore(registry: TemplateRegistryLike) -> bool:
    """探索期恒放行——试样式、看预览不需要注册表。"""
    return True


def register_template(
    registry: TemplateRegistryLike,
    *,
    template_id: str,
    owner: Any,
    name: str,
    slots: tuple[str, ...],
    html: str,
    source_deliverable_id: str | None,
    now: datetime,
    model: Any,
    checksum_of: Callable[[str], str],
) -> Any:
    """固化一个模板。同内容去重；内容变则版本 +1。"""
    if not registry.available:
        raise RegistryUnavailable(
            "模板注册表不可用：固化与生产渲染已阻断（E6）。"
            "探索仍可继续——设计台里试样式与预览不受影响。")

    checksum = checksum_of(html)
    mine = [r for r in registry.all()
            if r.owner.kind == owner.kind and r.owner.id == owner.id]
    for existing in mine:
        if existing.checksum == checksum:
            return existing                       # 同内容: 不产出新版本

    record = model(
        template_id=template_id, owner=owner, name=name,
        version=max((r.version for r in mine), default=0) + 1,
        slots=slots, source_deliverable_id=source_deliverable_id,
        html=html, checksum=checksum, solidified_at=now, enabled=True)
    registry.append(record)
    return record


def list_templates(registry: TemplateRegistryLike, *, owner: Any) -> list[Any]:
    """我的模板版本序列（旧版本 NEVER 被覆盖，按版本升序）。"""
    mine = [r for r in registry.all()
            if r.owner.kind == owner.kind and r.owner.id == owner.id]
    return sorted(mine, key=lambda r: r.version)
