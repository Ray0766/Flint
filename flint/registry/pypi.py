"""registry 客户端·PyPI（M4-011，冻结协议 RegistryValidator / 技术方案 E1）。

- 存在性 + latest_stable：releases 键过滤纯数字段版本（rc/dev/后缀一律
  非稳定），数值元组序取最大——info.version 可能是预发布，不作为
  latest_stable 来源。
- 判别口径：404 = 不存在（PackageStatus.exists=False，可走替换）；
  网络错误 / 非 200 非 404 = **不可用**（RegistryUnavailable，S2-6：
  校验不可用时 NEVER 引入新依赖——两态不可混）。
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

import httpx

from flint.domain.models import PackageStatus

_STABLE_RE = re.compile(r"^\d+(\.\d+)*$")

PYPI_URL = "https://pypi.org/pypi/{package}/json"


class RegistryUnavailable(Exception):
    """校验通道不可用（≠ 包不存在）。"""


def latest_stable_of(versions: Iterable[str]) -> str | None:
    stable = [v for v in versions if _STABLE_RE.match(v)]
    if not stable:
        return None
    return max(stable, key=lambda v: tuple(int(p) for p in v.split(".")))


def check_pypi(client: httpx.Client, package: str) -> PackageStatus:
    url = PYPI_URL.format(package=package)
    try:
        response = client.get(url)
    except httpx.HTTPError as err:
        raise RegistryUnavailable(f"pypi unreachable for {package}: {err}") from err
    if response.status_code == 404:
        return PackageStatus(
            package=package, ecosystem="pypi", exists=False,
            latest_stable=None, replaced_with=None,
            reason="not found on PyPI",
        )
    if response.status_code != 200:
        raise RegistryUnavailable(
            f"pypi returned {response.status_code} for {package}"
        )
    data: dict[str, Any] = response.json()
    return PackageStatus(
        package=package, ecosystem="pypi", exists=True,
        latest_stable=latest_stable_of(data["releases"].keys()),
        replaced_with=None, reason=None,
    )
