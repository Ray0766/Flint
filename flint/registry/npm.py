"""registry 客户端·npm（I18N-01，冻结协议 RegistryValidator / 技术方案 E1）。

与 `flint/registry/pypi.py` **同一套判别口径**（NEVER 另立一种）:
  · 404 = 不存在（`PackageStatus.exists=False`, 可走替换）;
  · 网络错误 / 非 200 非 404 = **不可用**（`RegistryUnavailable`）——
    S2-6: 校验不可用时 NEVER 引入新依赖。**两态不可混**:
    把「查不到」和「查不通」混成一个, 就会在 registry 抽风时把包判成不存在,
    然后有人「顺手」换一个包。

latest_stable 取纯数字段版本的最大者（`1.2.3` 形态）; 预发布（`-rc.1` / `-beta`）
一律非稳定, 且 npm 的 `dist-tags.latest` **不作为** latest_stable 来源——
它可能被指到预发布上。
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

import httpx

from flint.domain.models import PackageStatus
from flint.registry.pypi import RegistryUnavailable  # 复用同一异常语义

_STABLE_RE = re.compile(r"^\d+(\.\d+)*$")

NPM_URL = "https://registry.npmjs.org/{package}"


def latest_stable_of(versions: Iterable[str]) -> str | None:
    stable = [v for v in versions if _STABLE_RE.match(v)]
    if not stable:
        return None
    return max(stable, key=lambda v: tuple(int(p) for p in v.split(".")))


def check_npm(client: httpx.Client, package: str) -> PackageStatus:
    url = NPM_URL.format(package=package)
    try:
        response = client.get(url)
    except httpx.HTTPError as err:
        raise RegistryUnavailable(f"npm unreachable for {package}: {err}") from err
    if response.status_code == 404:
        return PackageStatus(
            package=package, ecosystem="npm", exists=False,
            latest_stable=None, replaced_with=None,
            reason="not found on npm registry",
        )
    if response.status_code != 200:
        raise RegistryUnavailable(f"npm returned {response.status_code} for {package}")
    data: dict[str, Any] = response.json()
    return PackageStatus(
        package=package, ecosystem="npm", exists=True,
        latest_stable=latest_stable_of(data.get("versions", {}).keys()),
        replaced_with=None, reason=None,
    )
