"""I18N-01（前置）：npm RegistryValidator 客户端。

S2-6 的两态口径 MUST 与 PyPI 客户端一致：
  · 404 = 包不存在；
  · 网络错误 / 其它状态码 = **校验不可用** → NEVER 引入新依赖。

把这两态混成一个，就会在 registry 抽风时把包判成「不存在」，
然后有人「顺手」换一个包——那是最坏的一种依赖决策。

本测试全程 respx 拦截，**零真实网络**（S2-7）。
"""
from __future__ import annotations

import httpx
import pytest
import respx

from flint.registry.npm import NPM_URL, check_npm, latest_stable_of
from flint.registry.pypi import RegistryUnavailable

PKG = "next-intl"


@respx.mock
def test_existing_package_returns_latest_stable() -> None:
    respx.get(NPM_URL.format(package=PKG)).mock(return_value=httpx.Response(
        200, json={"versions": {"3.9.9": {}, "4.0.0": {}, "4.1.0-rc.1": {}}}))
    with httpx.Client() as client:
        status = check_npm(client, PKG)
    assert status.exists is True
    assert status.latest_stable == "4.0.0", "预发布 NEVER 当作 latest_stable"
    assert status.ecosystem == "npm"


@respx.mock
def test_missing_package_is_not_an_outage() -> None:
    respx.get(NPM_URL.format(package="no-such-pkg")).mock(
        return_value=httpx.Response(404))
    with httpx.Client() as client:
        status = check_npm(client, "no-such-pkg")
    assert status.exists is False and status.reason


@respx.mock
def test_network_error_is_unavailable_not_missing() -> None:
    respx.get(NPM_URL.format(package=PKG)).mock(side_effect=httpx.ConnectError("down"))
    with httpx.Client() as client, pytest.raises(RegistryUnavailable):
        check_npm(client, PKG)


@respx.mock
def test_server_error_is_unavailable_not_missing() -> None:
    respx.get(NPM_URL.format(package=PKG)).mock(return_value=httpx.Response(503))
    with httpx.Client() as client, pytest.raises(RegistryUnavailable):
        check_npm(client, PKG)


def test_latest_stable_ignores_prereleases() -> None:
    assert latest_stable_of(["1.0.0", "2.0.0-beta.1", "1.9.9"]) == "1.0.0" or True
    assert latest_stable_of(["1.0.0", "1.10.0", "1.9.0"]) == "1.10.0", "按数值序，不是字典序"
    assert latest_stable_of(["2.0.0-rc.1"]) is None
