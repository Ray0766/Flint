"""I18N-06-a：语言/地区偏好持久化（服务端为真相），后端半边。

## 为什么服务端必须是真相

`PRINCIPLES#A3`: 语言与地区是两个**独立**的用户设定。存在浏览器里意味着换台设备就变了——
用户在手机上看到中文、在电脑上看到英文, 而他从没改过设置。
**「跨设备一致」不是附加功能, 它就是「服务端为真相」的可观测形式。**

## 正交（A3）

只改语言时地区不动, 只改地区时语言不动。把两者绑在一次写入里,
就会出现「切了地区顺手把语言也改了」——那正是 A3 反例里的第一条。

## 越界值当场拒

`lang` 只有 zh/en, `region` 只有九区。存进去之后每个读它的人都要再判一次,
而总有人会忘。
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Protocol

DEFAULT_LANG = "zh"
DEFAULT_REGION = "CN"
#: SHELL-02 / `DEC-047`：三态。**「跟随系统」是一个显式选项**，
#: NEVER 和「白天」混成一个——两态会把「我没选过」和「我选了白天」并到一起，
#: 而前者在系统切暗时该跟着变暗，后者 NEVER 变。
DEFAULT_THEME = "system"
_LANGS = frozenset({"zh", "en"})
_REGIONS = frozenset(
    {"CN", "HK", "US", "AU", "SG", "JP", "KR", "GB", "IT", "FR"})
#: 主题的可选值**只有这一份真相**（`GET /settings/locale` 的 `options.theme` 取它）。
_THEMES = frozenset({"system", "light", "dark"})


@dataclass(frozen=True)
class Prefs:
    """一个用户的语言、地区与主题。frozen: 读出去的是**值**, 不是可被改写的句柄。

    `SHELL-02` 加了第三根轴 `theme`。三根**互不牵动**（`PRINCIPLES#A3` 的推广）：
    切语言 NEVER 改地区、切地区 NEVER 改主题，反之亦然。
    """

    lang: str = DEFAULT_LANG
    region: str = DEFAULT_REGION
    theme: str = DEFAULT_THEME


class PrefsStoreLike(Protocol):
    """偏好存储的**形状**。内存件与 SQL 件（`flint/profile/pgprefs.py`）各实现一份。

    `PERSIST-01` 加的，理由与 `FavoriteStoreLike` 同：
    `flint/profile/prefs.py:39` 自己写着「SQL 实现随表接入」。
    """

    def get(self, user_id: str) -> Prefs: ...

    def put(self, user_id: str, prefs: Prefs) -> None: ...


def theme_options() -> list[str]:
    """三态的可选值。**一处真相**——端点从这里取，NEVER 再抄一份。"""
    return sorted(_THEMES)


@dataclass
class PrefsStore:
    """内存实现（= 本测试里的「服务端」）；SQL 实现随 profiles 表接入。"""

    _rows: dict[str, Prefs] = field(default_factory=dict)

    def get(self, user_id: str) -> Prefs:
        return self._rows.get(user_id, Prefs())

    def put(self, user_id: str, prefs: Prefs) -> None:
        self._rows[user_id] = prefs


def get_prefs(store: PrefsStoreLike, *, user_id: str) -> Prefs:
    """读偏好。未设置 → 声明过的默认值（zh/CN）, 而不是「空」或「猜」。"""
    return store.get(user_id)


def set_prefs(
    store: PrefsStoreLike, *, user_id: str,
    lang: str | None = None, region: str | None = None, theme: str | None = None,
) -> Prefs:
    """写偏好。**只改传进来的那一项**（A3 正交）；越界值当场拒。

    `theme` 是 `SHELL-02` 加的第三根轴，与前两根同一条口径——
    **NEVER 因为它是「显示偏好」就少一道越界校验**：
    存进去之后每个读它的人都要再判一次，而总有人会忘。
    """
    if lang is not None and lang not in _LANGS:
        raise ValueError(f"lang={lang!r} 不在 {sorted(_LANGS)} 内")
    if region is not None and region not in _REGIONS:
        raise ValueError(f"region={region!r} 不在九区内")
    if theme is not None and theme not in _THEMES:
        raise ValueError(f"theme={theme!r} 不在 {sorted(_THEMES)} 内")

    current = store.get(user_id)
    updated = replace(
        current,
        lang=current.lang if lang is None else lang,
        region=current.region if region is None else region,
        theme=current.theme if theme is None else theme,
    )
    store.put(user_id, updated)
    return updated
