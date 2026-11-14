"""I18N-06-a 验收：语言/地区偏好持久化（服务端为真相），后端半边。

原卡 I18N-06 按 §4.5 拆分：
  · **-a（本卡）**：`flint/profile/prefs.py` + 本测试
    → acceptance「**服务端为真相**」「**跨设备一致**：二端模拟读到同值」；
  · -b（blocked）：`web/…/stores/prefs.ts` → acceptance「前端 store 无 localStorage 读写（源码断言）」。
拆分 NEVER 改变原卡 acceptance 总集。

## 为什么服务端必须是真相

`PRINCIPLES#A3`：语言与地区是两个独立的用户设定。存在浏览器里意味着
换台设备就变了——用户在手机上看到中文、在电脑上看到英文，而他从没改过设置。
**「跨设备一致」不是附加功能，它就是「服务端为真相」的可观测形式**。
"""
from __future__ import annotations

import inspect

import pytest

from flint.profile import prefs as prefs_module
from flint.profile.prefs import (
    DEFAULT_LANG,
    DEFAULT_REGION,
    PrefsStore,
    get_prefs,
    set_prefs,
)


def _store() -> PrefsStore:
    return PrefsStore()


# ── 服务端为真相 ────────────────────────────────────────────────

def test_unset_user_gets_declared_defaults() -> None:
    """未设置 → zh/CN 的**默认值**，而不是「空」或「猜」。"""
    got = get_prefs(_store(), user_id="u1")
    assert (got.lang, got.region) == (DEFAULT_LANG, DEFAULT_REGION) == ("zh", "CN")


def test_set_then_get_round_trips() -> None:
    store = _store()
    set_prefs(store, user_id="u1", lang="en", region="JP")
    got = get_prefs(store, user_id="u1")
    assert (got.lang, got.region) == ("en", "JP")


def test_prefs_are_per_user() -> None:
    store = _store()
    set_prefs(store, user_id="u1", lang="en", region="US")
    assert get_prefs(store, user_id="u2").lang == "zh", "别人的偏好 NEVER 串到我这儿"


def test_partial_update_keeps_the_other_axis() -> None:
    """A3 正交：只改语言时地区不动，只改地区时语言不动。"""
    store = _store()
    set_prefs(store, user_id="u1", lang="en", region="JP")
    set_prefs(store, user_id="u1", lang="zh")
    got = get_prefs(store, user_id="u1")
    assert (got.lang, got.region) == ("zh", "JP"), "改语言不该动地区（A3 正交）"
    set_prefs(store, user_id="u1", region="US")
    assert get_prefs(store, user_id="u1").lang == "zh", "改地区不该动语言（A3 正交）"


@pytest.mark.parametrize(("lang", "region"), [("ja", "CN"), ("zh", "EU"), ("", "CN")])
def test_invalid_values_are_rejected(lang: str, region: str) -> None:
    """越界值当场拒——存进去之后每个读它的人都要再判一次。"""
    with pytest.raises(ValueError):
        set_prefs(_store(), user_id="u1", lang=lang, region=region)


# ── 跨设备一致（服务端为真相的可观测形式） ──────────────────────

def test_two_devices_read_the_same_value() -> None:
    """二端模拟：同一个 store 就是「服务端」，两端各读一次得到同值。"""
    server = _store()
    set_prefs(server, user_id="u1", lang="en", region="JP")

    device_a = get_prefs(server, user_id="u1")
    device_b = get_prefs(server, user_id="u1")
    assert (device_a.lang, device_a.region) == (device_b.lang, device_b.region) == ("en", "JP")


def test_change_on_one_device_is_visible_on_the_other() -> None:
    server = _store()
    set_prefs(server, user_id="u1", lang="zh", region="CN")
    _ = get_prefs(server, user_id="u1")                 # 设备 A 先读
    set_prefs(server, user_id="u1", lang="en")          # 设备 B 改
    assert get_prefs(server, user_id="u1").lang == "en", "设备 A 再读 MUST 看到新值"


def test_reads_return_copies_not_live_handles() -> None:
    """读出去的是值，不是句柄——否则一端改了对象，另一端凭空跟着变。"""
    server = _store()
    set_prefs(server, user_id="u1", lang="en", region="JP")
    got = get_prefs(server, user_id="u1")
    with pytest.raises((AttributeError, TypeError)):
        got.lang = "zh"                                  # type: ignore[misc]


# ── 后端不碰浏览器存储 ──────────────────────────────────────────

def test_backend_module_has_no_browser_storage_symbol() -> None:
    """localStorage 是前端的事；后端出现这个词说明真相源搞反了。"""
    source = inspect.getsource(prefs_module)
    for forbidden in ("localStorage", "sessionStorage", "cookie"):
        assert forbidden not in source, f"后端模块里出现浏览器存储符号 {forbidden!r}"
