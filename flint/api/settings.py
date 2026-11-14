"""BE-07：语言与地区端点 `GET/PUT /settings/locale`（v2 屏 2.13）。

`flint/profile/prefs.py`（I18N-06-a）把三件事都实现好了——服务端为真相、
A3 正交、越界当场拒——但**零 API 出口**：前端改语言/地区没有地方可调。
本卡只做出口，判定与合并**全部转调 `set_prefs`**。

## 两轴分别接受，NEVER 合成一根字符串

`PRINCIPLES#A3`：语言只统治 UI 文案与生成内容语言，地区只决定数据源选集与
热点集合，两者正交。请求体里 `lang` 与 `region` **各自可省**，省掉的那一项不动。

响应里也 NEVER 出现 `zh-CN` 这种合成串：合成串把两轴绑死，
切地区必然连语言一起切——那正是 A3 的反面。
（冻结件 `AnalysisContext.locale` 是 v0.4 前的兼容字段，注释写明「由 lang 派生填充」，
所以它是**派生值**，不是这里的真相。）

## 无效值 422 并列出可选值，NEVER 静默回落

静默回落到默认值的话，用户以为自己切成了 JP，实际还在 CN——
而界面上看不出任何异常。所以：拒绝、说清楚、**一个字都不写**。

一项对一项错时也**整次拒绝**：写了一半的设置比全不写更难查。

## 可选值的真相是冻结件

`contracts_v04.SystemLanguage`（2）与 `contracts_v04.Region`（9）是唯一真相，
这里用 `get_args` 取，NEVER 在本模块里再抄一份清单——抄一份就是第二个真相，
而它会在加第十个地区那天悄悄少一项。

## `PERSIST-01`：处理函数从 `async def` 改成 `def`

本族的 store 换成 SQL 实现（`flint/profile/pgprefs.py`）之后，
store 的方法是**阻塞**调用——本仓只有 asyncpg 一个驱动，
同步接口与异步驱动之间那座桥（`flint/db/sync_bridge.py`）要阻塞调用它的线程。

FastAPI 的 `async def` 处理函数跑在**事件循环线程**上，在那里阻塞会把
**所有并发请求一起卡住**，而症状只是「服务偶尔很慢」，没有任何一条错误日志。
`def`（同步）处理函数由 FastAPI 放进**它自己的线程池**跑，阻塞只影响这一个请求。

所以这里去掉了 `async`。**处理函数体一行未动**——它们本来就没有 `await`
（改之前每一个都是「async 但从不 await」，那是 `BE-0x` 建族时的默认写法）。
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, get_args

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from flint.api.schemas import ErrorBody, ErrorCode
from flint.profile.prefs import (
    Prefs,
    PrefsStoreLike,
    get_prefs,
    set_prefs,
    theme_options,
)

_CONTRACT_PATH: Final[Path] = (
    Path(__file__).resolve().parents[2] / "contracts_v04" / "models_v04.py"
)


def _contract() -> Any:
    """加载 v0.4 冻结加件。与既有 schema 测试同一种加载法。"""
    cached = sys.modules.get("models_v04_settings")
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(
        "models_v04_settings", _CONTRACT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04_settings"] = module
    spec.loader.exec_module(module)
    return module


def options() -> dict[str, list[str]]:
    """可选值。**唯一真相是冻结件**，这里只取不抄（见模块 docstring）。"""
    contract = _contract()
    return {
        "lang": sorted(get_args(contract.SystemLanguage)),
        "region": sorted(get_args(contract.Region)),
        # SHELL-02：主题的可选值**不在冻结件里**（它是显示偏好，不是业务词表），
        # 唯一真相在 `flint/profile/prefs.py#_THEMES`，这里只取不抄。
        "theme": theme_options(),
    }


class LocalePatch(BaseModel):
    """两轴各自可省。`extra="forbid"`：拼错的字段名 NEVER 被静默忽略——
    忽略了，用户以为改了，其实什么都没发生。"""

    model_config = ConfigDict(extra="forbid")

    lang: str | None = None
    region: str | None = None
    #: SHELL-02 加的第三根轴。`extra="forbid"` 照旧——**只是多认一个合法键**。
    theme: str | None = None


@dataclass
class LocaleApiDeps:
    store: PrefsStoreLike


def _error(status: int, code: ErrorCode, message: str, detail: Any) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorBody(code=code, message=message, detail=detail).model_dump(
            exclude_none=True),
    )


def locale_json(prefs: Prefs) -> dict[str, Any]:
    """四样：三轴 + 可选值。**NEVER 造第五样**，也 NEVER 合成 `zh-CN`。

    `SHELL-02` 把 `theme` 加成第三轴——**与前两轴并排一格**，
    NEVER 塞进某一轴里：合成串把轴绑死，改一个必然连另一个一起改。
    """
    return {
        "lang": prefs.lang,
        "region": prefs.region,
        "theme": prefs.theme,
        "options": options(),
    }


def _invalid(patch: LocalePatch) -> str | None:
    """哪一项越界。**判据来自冻结件**，与 `set_prefs` 的那道判定同源。"""
    allowed = options()
    if patch.lang is not None and patch.lang not in allowed["lang"]:
        return "lang"
    if patch.region is not None and patch.region not in allowed["region"]:
        return "region"
    if patch.theme is not None and patch.theme not in allowed["theme"]:
        return "theme"
    return None


def create_settings_app(deps: LocaleApiDeps) -> FastAPI:
    app = FastAPI(title="Flint locale settings (BE-07)")

    @app.get("/settings/locale")
    def read_locale(x_user_id: str = Header()) -> Response:
        # 只读：`get_prefs` 未设置时返回**声明过的默认值**，不落库。
        return JSONResponse(
            status_code=200,
            content=locale_json(get_prefs(deps.store, user_id=x_user_id)),
        )

    @app.put("/settings/locale")
    def write_locale(
        patch: LocalePatch, x_user_id: str = Header()
    ) -> Response:
        field = _invalid(patch)
        if field is not None:
            # 整次拒绝：一项对一项错时 NEVER 只写对的那项。
            return _error(
                422, "VALIDATION_FAILED",
                f"{field} 不在可选值内：本端点 NEVER 静默回落到默认值",
                {"field": field, "allowed": options()[field]},
            )
        # 合并与越界复判都归 `set_prefs`（A3 正交：只改传进来的那一项）。
        updated = set_prefs(
            deps.store, user_id=x_user_id, lang=patch.lang, region=patch.region,
            theme=patch.theme)
        # 回的是**库里那份**，不是请求里那份。
        return JSONResponse(status_code=200, content=locale_json(updated))

    return app
