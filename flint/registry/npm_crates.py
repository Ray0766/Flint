"""registry 客户端·npm/crates（M4-012，冻结件 PackageStatus）。

- 与 PyPI 同协议面：404 = 不存在；网络错误 / 非 200 非 404 = 不可用
  （RegistryUnavailable）——三生态判别一致由 tests/m4/test_m4_012.py
  参数化断言。
- latest_stable：npm 取 versions 键过滤稳定段（dist-tags.latest 可能指
  预发布，不直取）；crates 用 API 自带 max_stable_version。
"""
from __future__ import annotations

from typing import Any

import httpx

from flint.domain.models import PackageStatus
from flint.registry.pypi import RegistryUnavailable, latest_stable_of

NPM_URL = "https://registry.npmjs.org/{package}"
CRATES_URL = "https://crates.io/api/v1/crates/{package}"


def _fetch(client: httpx.Client, url: str, package: str) -> httpx.Response | None:
    """返回 None = 404 不存在；抛 RegistryUnavailable = 通道不可用。"""
    try:
        response = client.get(url)
    except httpx.HTTPError as err:
        raise RegistryUnavailable(
            f"registry unreachable for {package}: {err}"
        ) from err
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise RegistryUnavailable(
            f"registry returned {response.status_code} for {package}"
        )
    return response


def check_npm(client: httpx.Client, package: str) -> PackageStatus:
    response = _fetch(client, NPM_URL.format(package=package), package)
    if response is None:
        return PackageStatus(
            package=package, ecosystem="npm", exists=False,
            latest_stable=None, replaced_with=None,
            reason="not found on npm",
        )
    data: dict[str, Any] = response.json()
    return PackageStatus(
        package=package, ecosystem="npm", exists=True,
        latest_stable=latest_stable_of(data["versions"].keys()),
        replaced_with=None, reason=None,
    )


def check_crates(client: httpx.Client, package: str) -> PackageStatus:
    response = _fetch(client, CRATES_URL.format(package=package), package)
    if response is None:
        return PackageStatus(
            package=package, ecosystem="crates", exists=False,
            latest_stable=None, replaced_with=None,
            reason="not found on crates.io",
        )
    data: dict[str, Any] = response.json()
    stable = data["crate"].get("max_stable_version")
    return PackageStatus(
        package=package, ecosystem="crates", exists=True,
        latest_stable=str(stable) if stable is not None else None,
        replaced_with=None, reason=None,
    )
