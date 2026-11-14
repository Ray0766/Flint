"""BE-08：收藏端点族（暴露 `flint/fav` · v2 屏 2.15 收藏图书馆）。

五个动作：列收藏 / 加收藏 / 取消收藏 / 看快照陈旧态 / 更新到最新。
判定、合并、pin、历史**全部转调 `flint/fav`**，本模块只做出口。

## 四处「既有函数单独看是对的，接成端点就会漏」

既有模块各自的口径都写得很清楚，漏在**接线处**——所以这四道补在这里：

1. `remove_favorite` **不判归属**（它只按 id 删）。端点先判归属再删，
   否则任何人都能删别人的收藏。
2. `add_favorite` 同 id 幂等且**直接返回既有那条**。端点先判归属，
   否则拿别人的 favorite_id 一发请求就读到了别人的快照内容。
3. `evaluate_snapshot_stale` **会落库**。所以它挂在 **POST** 上，不挂 GET——
   挂 GET 就是一个藏起来的写，而列表页每刷一次就写一次库。
   列表报的是**库里存着的**那个标记，重算是显式动作。
4. 取消收藏时 **NEVER 顺手 unpin**：另一条收藏可能还引用着同一个快照，
   解钉等于把它放回周删名单，而删的人完全不知道自己动了别人的东西。
   刷新时同理——旧快照要留给「查看当时版本」（FAV-02 的历史正是为它保的）。

## 越权与不存在同一行

`flint/fav/stale.py#_owned` 把两者分成 `KeyError` 与 `PermissionError`（模块内诊断用），
到了 HTTP 边界**合成一句 404 一个码**：403 会用状态码本身泄露存在性。

## pin 是补充，不是前提

冻结靠内嵌（`Favorite.evidence_snapshot` 是本体）。快照里没有 `snapshot_id`
时照样收藏成功，只是没有可钉的东西——**NEVER 因为钉不上就拒绝收藏**。

## `PERSIST-01`：处理函数从 `async def` 改成 `def`

本族的 store 换成 SQL 实现（`flint/fav/pgstore.py`）之后，
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
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final, get_args, get_type_hints

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from flint.analysis.stale_adapter import DiffChannel
from flint.api.schemas import ErrorBody, ErrorCode
from flint.domain.models import Principal
from flint.fav.pin import SnapshotPins
from flint.fav.stale import (
    SnapshotHistoryStore,
    StaleNotEvaluated,
    evaluate_snapshot_stale,
    refresh_snapshot,
)
from flint.fav.store import (
    FavoriteStoreLike,
    add_favorite,
    list_favorites,
    remove_favorite,
)

_CONTRACT_PATH: Final[Path] = (
    Path(__file__).resolve().parents[2] / "contracts_v04" / "models_v04.py"
)
_SNAPSHOT_ID_KEY: Final[str] = "snapshot_id"


def _contract() -> Any:
    cached = sys.modules.get("models_v04_favorites")
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(
        "models_v04_favorites", _CONTRACT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04_favorites"] = module
    spec.loader.exec_module(module)
    return module


def target_kinds() -> list[str]:
    """四种收藏目标。**唯一真相是冻结件** `Favorite.target_kind`，这里只取不抄。

    走 `get_type_hints` 而不是 `__annotations__`：冻结件开了
    `from __future__ import annotations`，`__annotations__` 里存的是**字符串**，
    对它 `get_args` 恒得空元组——那会让「四种之内」悄悄变成「一种都不许」。
    """
    contract = _contract()
    hints = get_type_hints(contract.Favorite)
    return sorted(get_args(hints["target_kind"]))


class FavoriteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    favorite_id: str
    target_kind: str
    target_id: str
    #: `DEC-055`（owner 2026-08-10）：**从必填改成可选**。
    #:
    #: 广场那个收藏动作手上只有热点卡面（`cluster_id` / 名称 / 热度），
    #: 拼不出真快照——前端拼一份就是**编一份证据**（`FAV-WRITES` acceptance④
    #: 逐字禁止）。于是它送 `{}`，而屏上每一条都说「内容不在了」：
    #: 那句是实话，**而真相是没有人往里面放东西**。
    #:
    #: `None` = 「请后端自取」。传了就用调用方那一份（既有调用点不受影响）。
    #: **`{}` 与 `None` 不是一回事**：前者是「我给你一份空的」，
    #: 后者是「我没有，你去取」——合成一个的话，一份真的空快照会被悄悄替换掉。
    evidence_snapshot: dict[str, Any] | None = None


class SnapshotRefresh(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: `FAV-CARD-01`：与 `FavoriteCreate.evidence_snapshot` 同一姿态——
    #: **可选**，不给就由后端自取当刻的那一份。
    #:
    #: 必填的话，「更新到最新」这个按钮就要前端自己拼一份快照，
    #: 而那正是 `DEC-055` 明禁的事（前端拼一份就是编一份证据）。
    fresh_snapshot: dict[str, Any] | None = None


@dataclass
class FavoritesApiDeps:
    # `WIRE-12`：**`None` = 这一族没有存储面**（迁移里没有 `favorites` 表）。
    # 有它才分得开「查过了、你确实没有收藏」与「这功能还没有库，我们根本没查」——
    # 两件事在 `{"items": []}` 这一个表示里长得一模一样。
    store: FavoriteStoreLike | None
    pins: SnapshotPins
    history: SnapshotHistoryStore
    diff_channel: DiffChannel
    now: Callable[[], datetime]
    project_id_for: Callable[[Any], str]
    current_version: Callable[[], int]
    #: `DEC-055`：按 `(target_kind, target_id)` 取当刻的证据卡组，组一份内嵌快照。
    #:
    #: **`None` = 这一族没有取证面**——与上面 `store` 那条同一姿态：
    #: 有它才分得开「取过了、这个热点确实没有证据卡」与「我们根本没去取」。
    #: 冻结件 `Favorite` 的「内嵌不引用」语义**一字未动**：
    #: 改的是**谁来放**，不是放什么。
    snapshot_for: Callable[[str, str], dict[str, Any]] | None = None


def _error(status: int, code: ErrorCode, message: str,
           detail: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorBody(code=code, message=message, detail=detail).model_dump(
            exclude_none=True),
    )


def _not_found(favorite_id: str) -> JSONResponse:
    # 越权与不存在**同一行**：403 会用状态码本身泄露存在性。
    return _error(404, "NOT_FOUND", f"unknown favorite: {favorite_id}")


def favorite_json(favorite: Any) -> dict[str, Any]:
    """逐字对齐冻结件 `Favorite`，**owner 除外**——调用方就是 owner，不必回给他自己。"""
    return {
        "favorite_id": favorite.favorite_id,
        "target_kind": favorite.target_kind,
        "target_id": favorite.target_id,
        "evidence_snapshot": favorite.evidence_snapshot,
        "created_at": favorite.created_at.isoformat(),
        "snapshot_stale": favorite.snapshot_stale,
    }


_NOT_PROVIDED = {
    "status": "not_provided",
    "reason": "收藏还没有存储面（迁移里没有 favorites 表）："
              "本端点 NEVER 拿一个空列表冒充「你确实没有收藏」",
}


def create_favorites_app(deps: FavoritesApiDeps) -> FastAPI:
    app = FastAPI(title="Flint favorites (BE-08)")

    def _mine(store: FavoriteStoreLike, favorite_id: str, owner: Principal) -> Any:
        """我的那条，或 None。**归属判在端点这一层**（见模块 docstring 的四处）。

        `store` 由调用方传进来（而不是读 `deps.store`）：调用点都在
        「没有存储面」的守卫之后，传进来的一定是真 store——**类型上也说得清**。
        """
        row = store.get(favorite_id)
        if row is None:
            return None
        if row.owner.kind != owner.kind or row.owner.id != owner.id:
            return None
        return row

    def _pin_snapshot(snapshot: dict[str, Any]) -> None:
        """有 snapshot_id 就钉住；没有就算了（pin 是补充，不是前提）。"""
        snapshot_id = snapshot.get(_SNAPSHOT_ID_KEY)
        if isinstance(snapshot_id, str) and snapshot_id:
            deps.pins.pin(snapshot_id)

    def _snapshot_for_target(
        given: dict[str, Any] | None, target_kind: str, target_id: str,
    ) -> tuple[dict[str, Any] | None, Response | None]:
        """按 `(target_kind, target_id)` 拿那一份快照。

        `FAV-CARD-01` 把它从「只服务 `POST /favorites`」抽成通用件——
        「更新到最新」走的是**同一条自取路**，NEVER 让前端拼第二份。
        """
        return _snapshot_or_refusal(given, target_kind, target_id)

    def _snapshot_for(
        body: FavoriteCreate,
    ) -> tuple[dict[str, Any] | None, Response | None]:
        """这一条收藏该存的那份内嵌快照（`DEC-055`）。

        三条路，**三种不同的答复**：

        | 情形 | 答复 |
        |---|---|
        | 调用方自己带了 | 用他那份（既有调用点逐字不变） |
        | 没带、而这一族没有取证面 | **503 · `FAMILY_NOT_CONFIGURED`** |
        | 没带、取证面在但取不着 | **502 · `EVIDENCE_FETCH_FAILED`** |

        后两条 NEVER 合并，也 NEVER 与列表屏那句「内容已被清理」共用一句话
        （`DEC-055` 边界逐字）：三者该让用户做的事完全不同——
        一个是这功能还没上，一个是这次取证失败可以重试，
        一个是内容真的被清掉了、重试一万次也回不来。

        **NEVER 存空快照冒充成功**：那样收藏会带着 200 存下去，
        而屏上说「内容不在了」——一句实话盖住一次失败。
        """
        return _snapshot_or_refusal(
            body.evidence_snapshot, body.target_kind, body.target_id)

    def _snapshot_or_refusal(
        given: dict[str, Any] | None, target_kind: str, target_id: str,
    ) -> tuple[dict[str, Any] | None, Response | None]:
        if given is not None:
            return given, None
        if deps.snapshot_for is None:
            return None, JSONResponse(
                status_code=503,
                content={"code": "FAMILY_NOT_CONFIGURED", "family": "favorites",
                         "status": "not_provided",
                         "reason": "收藏还没有取证面：本端点 NEVER 存一份空快照"
                                   "冒充「收藏成功」"})
        try:
            fetched = deps.snapshot_for(target_kind, target_id)
        except Exception as exc:                      # noqa: BLE001
            # 取证这一步失败的原因由下游决定（库不通、目标不存在、…）。
            # **照实失败**：吞掉它就等于替用户决定「没有证据也算收藏成功」。
            return None, _error(
                502, "EVIDENCE_FETCH_FAILED",
                f"取这一条的证据卡失败，收藏没有存下：{exc}",
                {"target_kind": target_kind, "target_id": target_id})
        if not fetched:
            return None, _error(
                502, "EVIDENCE_FETCH_FAILED",
                "这一条今天取不到证据卡，收藏没有存下——"
                "这与「内容已被清理」不是一回事",
                {"target_kind": target_kind, "target_id": target_id})
        return fetched, None

    def _read_or_absent() -> tuple[FavoriteStoreLike | None, Response | None]:
        """没有存储面时的答复。**读回 200 + 说明**。

        读用 200 是因为「这功能还没上」本身就是一个成功的回答；
        返回 store 是为了让类型收窄——守卫过后调用方拿到的一定是真 store。
        """
        if deps.store is None:
            return None, JSONResponse(
                status_code=200, content=dict(_NOT_PROVIDED))
        return deps.store, None

    def _write_or_absent() -> tuple[FavoriteStoreLike | None, Response | None]:
        """**写回 503**：调用方的那次写确实没有发生——回 200 会让它以为存下了。"""
        if deps.store is None:
            return None, JSONResponse(
                status_code=503,
                content={"code": "FAMILY_NOT_CONFIGURED", "family": "favorites",
                         **_NOT_PROVIDED})
        return deps.store, None

    @app.get("/favorites")
    def list_all(x_user_id: str = Header()) -> Response:
        store, absent = _read_or_absent()
        if store is None:
            return absent or JSONResponse(status_code=500, content={})
        # 只读：列表报的是**库里存着的** snapshot_stale，NEVER 顺手重算（那会写库）。
        owner = Principal(kind="user", id=x_user_id)
        rows = list_favorites(store, owner=owner)
        return JSONResponse(
            status_code=200,
            content={"items": [favorite_json(row) for row in rows]},
        )

    @app.post("/favorites")
    def create(body: FavoriteCreate, x_user_id: str = Header()) -> Response:
        store, absent = _write_or_absent()
        if store is None:
            return absent or JSONResponse(status_code=500, content={})
        owner = Principal(kind="user", id=x_user_id)
        existing = store.get(body.favorite_id)
        if existing is not None and _mine(store, body.favorite_id, owner) is None:
            # 别人占着这个 id：`add_favorite` 会把**他那条**原样返回。
            return _not_found(body.favorite_id)
        if body.target_kind not in target_kinds():
            return _error(
                422, "VALIDATION_FAILED",
                "target_kind 不在冻结件声明的四种之内",
                {"field": "target_kind", "allowed": target_kinds()},
            )
        snapshot, refused = _snapshot_for(body)
        if snapshot is None:
            return refused or JSONResponse(status_code=500, content={})
        try:
            row = add_favorite(
                store, favorite_id=body.favorite_id, owner=owner,
                target_kind=body.target_kind, target_id=body.target_id,
                evidence_snapshot=snapshot, now=deps.now(),
                model=_contract().Favorite,
            )
        except ValueError as exc:
            return _error(422, "VALIDATION_FAILED", str(exc))
        _pin_snapshot(snapshot)
        return JSONResponse(status_code=200, content=favorite_json(row))

    @app.delete("/favorites/{favorite_id}")
    def remove(favorite_id: str, x_user_id: str = Header()) -> Response:
        store, absent = _write_or_absent()
        if store is None:
            return absent or JSONResponse(status_code=500, content={})
        owner = Principal(kind="user", id=x_user_id)
        if _mine(store, favorite_id, owner) is None:
            return _not_found(favorite_id)
        remove_favorite(store, favorite_id=favorite_id)
        # **NEVER 顺手 unpin**：另一条收藏可能还引用着同一个快照。
        return Response(status_code=204)

    @app.post("/favorites/{favorite_id}/staleness")
    def staleness(favorite_id: str, x_user_id: str = Header()) -> Response:
        store, absent = _write_or_absent()
        if store is None:
            return absent or JSONResponse(status_code=500, content={})
        owner = Principal(kind="user", id=x_user_id)
        row = _mine(store, favorite_id, owner)
        if row is None:
            return _not_found(favorite_id)
        try:
            updated = evaluate_snapshot_stale(
                store, favorite_id=favorite_id, owner=owner,
                project_id=deps.project_id_for(row),
                current_version=deps.current_version(),
                diff_channel=deps.diff_channel,
            )
        except StaleNotEvaluated as exc:
            # 判不了就说判不了。**连 `snapshot_stale` 这个键都不给**——
            # 给一个 false 等于告诉用户「这份是最新的」，而我们根本没能力知道。
            return JSONResponse(
                status_code=200,
                content={"favorite_id": favorite_id, "status": "not_checked",
                         "missing": exc.missing, "reason": str(exc)},
            )
        return JSONResponse(
            status_code=200,
            content={"favorite_id": favorite_id, "status": "checked",
                     "snapshot_stale": updated.snapshot_stale},
        )

    @app.post("/favorites/{favorite_id}/refresh-snapshot")
    def refresh(
        favorite_id: str, body: SnapshotRefresh, x_user_id: str = Header()
    ) -> Response:
        store, absent = _write_or_absent()
        if store is None:
            return absent or JSONResponse(status_code=500, content={})
        owner = Principal(kind="user", id=x_user_id)
        if _mine(store, favorite_id, owner) is None:
            return _not_found(favorite_id)
        mine = _mine(store, favorite_id, owner)
        fresh, refused = _snapshot_for_target(
            body.fresh_snapshot, str(mine.target_kind), str(mine.target_id))
        if fresh is None:
            return refused or JSONResponse(status_code=500, content={})
        try:
            row = refresh_snapshot(
                store, deps.history, favorite_id=favorite_id, owner=owner,
                fresh_snapshot=fresh, now=deps.now(),
            )
        except ValueError as exc:
            return _error(422, "VALIDATION_FAILED", str(exc))
        # 钉住新的；**旧的照旧钉着**——「查看当时版本」要的正是那一份。
        _pin_snapshot(fresh)
        return JSONResponse(status_code=200, content=favorite_json(row))

    return app
