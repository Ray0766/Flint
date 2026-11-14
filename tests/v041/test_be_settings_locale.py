"""BE-07 · 语言与地区端点 `GET/PUT /settings/locale`（v2 屏 2.13）。

`flint/profile/prefs.py`（I18N-06-a）把「服务端为真相 + A3 正交 + 越界当场拒」
都实现好了，但**零 API 出口**——前端改语言/地区没有地方可调。本卡暴露它。

四条判据线：

1. **A3 正交，18 组合逐个走一遍**——改语言不改地区、改地区不改语言。
   判据不是抽查两组，是 2 语言 × 9 地区**全跑**。
2. **NEVER 静默回落**——无效值 422 并列出可选值，且**库里一个字都不许变**。
   静默回落到默认值的话，用户以为自己切成了 JP，实际还在 CN。
3. **可选值来自冻结件**（`contracts_v04.Region` / `SystemLanguage`），
   且判据断言它与 `prefs.py` 认的那一套**逐字相同**——两处不一致时，
   端点会把一个 prefs 根本不收的值列成「可选」。
4. **合成的 `zh-CN` 一个都不许出现**——把两轴绑成一根字符串，就是 A3 的反面：
   切地区必然连语言一起切。
"""
from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any, get_args

from fastapi.testclient import TestClient

from flint.api.settings import LocaleApiDeps, create_settings_app
from flint.profile.prefs import PrefsStore
from tools.check_locale_seam import scan_source

MODULE = Path("flint/api/settings.py")
URL = "/settings/locale"

ME = "u-me"
OTHER = "u-other"


def _contract() -> Any:
    """冻结件 v0.4 加件（`contracts_v04/models_v04.py`）——按既有测试的加载法。"""
    path = Path("contracts_v04/models_v04.py")
    spec = importlib.util.spec_from_file_location("models_v04_be07", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04_be07"] = module
    spec.loader.exec_module(module)
    return module


def _app(store: PrefsStore | None = None) -> tuple[TestClient, PrefsStore]:
    kept = store or PrefsStore()
    return TestClient(create_settings_app(LocaleApiDeps(store=kept))), kept


def _get(client: TestClient, user: str = ME) -> dict[str, Any]:
    response = client.get(URL, headers={"X-User-Id": user})
    assert response.status_code == 200, response.text
    out: dict[str, Any] = response.json()
    return out


def _put(client: TestClient, body: dict[str, Any], user: str = ME) -> Any:
    return client.put(URL, json=body, headers={"X-User-Id": user})


# ───────────────────────── 一、读：默认值是声明过的，不是猜的（acceptance①⑤）


def test_the_endpoint_exists_and_reads_the_declared_defaults() -> None:
    client, _ = _app()

    body = _get(client)

    assert body["lang"] == "zh"
    assert body["region"] == "CN"


def test_reading_never_writes() -> None:
    """只读端点 NEVER 写库：读一个没设置过的用户，**不许**把默认值落成一行。

    落了的话，日后默认值一改，这个人还留在旧默认上——而他从没设置过。
    """
    client, store = _app()

    _get(client)

    assert store._rows == {}


def test_identity_is_required_on_both_verbs() -> None:
    client, _ = _app()

    assert client.get(URL).status_code == 422
    assert client.put(URL, json={"lang": "en"}).status_code == 422


def test_the_routes_have_no_path_parameter() -> None:
    """越权在结构上不可达：改的恒是调用方自己的设置。"""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    routes = [
        d.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
        for d in node.decorator_list
        if isinstance(d, ast.Call) and d.args
        and isinstance(d.args[0], ast.Constant) and isinstance(d.args[0].value, str)
        and d.args[0].value.startswith("/")
    ]

    assert routes == [URL, URL]
    assert "{" not in URL


# ───────────────────────── 二、可选值来自冻结件（acceptance⑥）


def test_the_options_come_from_the_frozen_contract() -> None:
    client, _ = _app()
    contract = _contract()

    options = _get(client)["options"]

    assert options["lang"] == sorted(get_args(contract.SystemLanguage))
    assert options["region"] == sorted(get_args(contract.Region))
    assert "EU" not in options["region"], "EU 是区域联盟，不是地区"


def test_the_options_agree_with_what_the_store_accepts() -> None:
    """两处不一致 → 端点会把一个 prefs 根本不收的值列成「可选」。

    读私有名是故意的：这条判据要钉的正是「另一处的真相」，
    换成公开别名就等于把两处抹成一处，判据也就不判了。
    """
    from flint.profile import prefs as prefs_module

    client, _ = _app()
    options = _get(client)["options"]

    assert set(options["lang"]) == prefs_module._LANGS
    assert set(options["region"]) == prefs_module._REGIONS


def test_no_combined_locale_string_is_returned() -> None:
    """`zh-CN` 这种合成串把两轴绑死：切地区必然连语言一起切（A3 的反面）。"""
    client, _ = _app()

    body = _get(client)

    assert not re.search(r"[a-z]{2}-[A-Z]{2}", str(body))
    assert "locale" not in body


def test_the_module_never_hardcodes_a_locale() -> None:
    """拿既有那把尺子（BL-09）量自己：分支假设与写死实参一处都不许有。"""
    findings = scan_source(MODULE.read_text(encoding="utf-8"), str(MODULE))

    assert findings == [], f"本模块硬编码了地区/语言：{findings}"


def test_the_module_contains_no_locale_literal_at_all() -> None:
    """本卡自带的第二把尺：**十一个值一个都不许作为字面量出现在模块里**。

    上面那把（BL-09）的 `LOCALE_LITERALS` 只收 zh/中文/weibo 这类语言标记，
    **不收九区代码**——所以 `region == "CN"` 从它下面走得过去（变异⑳ 证过）。
    加宽那把尺子会动到全仓门禁，超出本卡 outputs（§六.1），
    已登记 `docs/blocked/LOCALE-SEAM-RULER-MISSES-REGION-CODES.md`；
    这里先用一把只管本模块的窄尺补上。
    """
    contract = _contract()
    values = {*get_args(contract.SystemLanguage), *get_args(contract.Region)}
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    docstrings = {ast.get_docstring(n) for n in ast.walk(tree)
                  if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef
                                | ast.AsyncFunctionDef)}
    literals = {n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and n.value not in docstrings}

    assert not literals & values, f"模块里写死了：{sorted(literals & values)}"


# ───────────────────────── 三、A3 正交：18 组合全跑（acceptance②）


def test_changing_the_language_leaves_the_region_alone() -> None:
    client, _ = _app()
    _put(client, {"region": "JP"})

    body = _put(client, {"lang": "en"}).json()

    assert (body["lang"], body["region"]) == ("en", "JP")


def test_changing_the_region_leaves_the_language_alone() -> None:
    client, _ = _app()
    _put(client, {"lang": "en"})

    body = _put(client, {"region": "FR"}).json()

    assert (body["lang"], body["region"]) == ("en", "FR")


def test_all_eighteen_combinations_round_trip() -> None:
    contract = _contract()

    for lang in get_args(contract.SystemLanguage):
        for region in get_args(contract.Region):
            client, _ = _app()
            _put(client, {"lang": lang})
            _put(client, {"region": region})

            body = _get(client)
            assert (body["lang"], body["region"]) == (lang, region), \
                f"{lang}/{region} 没走通"


def test_the_two_axes_are_accepted_separately_in_one_call() -> None:
    client, _ = _app()

    body = _put(client, {"lang": "en", "region": "KR"}).json()

    assert (body["lang"], body["region"]) == ("en", "KR")


def test_an_empty_patch_changes_nothing() -> None:
    """一项都没给 = 不改任何东西。这不是错误态，是「没内容」。"""
    client, _ = _app()
    _put(client, {"lang": "en", "region": "SG"})

    response = _put(client, {})

    assert response.status_code == 200
    assert (response.json()["lang"], response.json()["region"]) == ("en", "SG")


# ───────────────────────── 四、无效值：422 + 列出可选值 + 库不许变（acceptance③）


def test_an_invalid_language_is_422_and_lists_the_options() -> None:
    client, _ = _app()

    response = _put(client, {"lang": "de"})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_FAILED"
    assert body["detail"]["field"] == "lang"
    assert body["detail"]["allowed"] == ["en", "zh"]


def test_an_invalid_region_is_422_and_lists_the_options() -> None:
    client, _ = _app()

    response = _put(client, {"region": "EU"})

    assert response.status_code == 422
    assert response.json()["detail"]["field"] == "region"
    assert "EU" not in response.json()["detail"]["allowed"]


def test_an_invalid_value_never_falls_back_to_the_default() -> None:
    """静默回落 = 用户以为切成了 JP，实际还在 CN。**库里一个字都不许变。**"""
    client, store = _app()
    _put(client, {"lang": "en", "region": "JP"})

    _put(client, {"region": "XX"})

    assert store.get(ME).region == "JP"
    assert _get(client)["region"] == "JP"


def test_a_partially_invalid_patch_writes_nothing_at_all() -> None:
    """一项对一项错时 NEVER 只写对的那项——写了一半的设置比全不写更难查。"""
    client, store = _app()

    response = _put(client, {"lang": "en", "region": "XX"})

    assert response.status_code == 422
    assert store.get(ME).lang == "zh", "错的那项该拦下整次写入"


def test_an_unknown_field_is_422_not_silently_ignored() -> None:
    """`{"language": "en"}` 静默忽略的话，用户以为改了，其实什么都没发生。"""
    client, _ = _app()

    assert _put(client, {"language": "en"}).status_code == 422


# ───────────────────────── 五、多租户与形状（acceptance④⑥）


def test_two_users_do_not_see_each_others_settings() -> None:
    client, _ = _app()
    _put(client, {"lang": "en", "region": "US"}, user=ME)

    assert _get(client, user=OTHER)["lang"] == "zh"
    assert _get(client, user=OTHER)["region"] == "CN"


def test_a_write_touches_only_the_callers_row() -> None:
    client, store = _app()
    _put(client, {"region": "GB"}, user=ME)
    _put(client, {"region": "IT"}, user=OTHER)

    assert store.get(ME).region == "GB"
    assert store.get(OTHER).region == "IT"


def test_the_response_shape_is_exactly_four_things() -> None:
    """`SHELL-02` 加了第三根正交轴（主题），所以响应从三样变四样。

    判**等值**是有意的：多一样少一样都要有人回到这里确认一次。
    这条红是 `SHELL-02` 收卡时漏掉的——那一轮只跑了自己那个判据文件，
    没跑全量，于是它被带进了下一张卡才发现。
    """
    client, _ = _app()
    shape = {"lang", "region", "theme", "options"}

    assert set(_get(client)) == shape
    assert set(_put(client, {"lang": "en"}).json()) == shape


def test_the_write_returns_what_was_stored_not_what_was_asked() -> None:
    """回写后的响应恒是**库里那份**——否则前端显示的是它自己刚发出去的东西。"""
    client, store = _app()

    body = _put(client, {"lang": "en"}).json()

    assert (body["lang"], body["region"]) == (store.get(ME).lang, store.get(ME).region)
