"""ENTRY-01：`design_generate` 的提交入口——消费者有了，**入口没有**。

## 改前

第 5 批建了消费者（`flint/jobs/design_generate.py`），第 6 批把它接进了 worker。
但**没有任何端点能把这类作业塞进队列**：openapi 的作业一族只有

```
GET /jobs/{id} · GET /jobs/{id}/events · GET /jobs/{id}/verdict
```

前端提交器 `web/lib/jobClient.ts#submitJob` 打的是
`POST /projects/{id}/{kind}`——对 `design_generate` 这条，实测回的是**框架那种
没有 `code` 的 404**（`{"detail":"Not Found"}`）。

那种 404 与「这一条不存在」长得一模一样，而它说的是**这个能力还没挂**。
本仓把两种 404 分开是有判据的（`FETCH-LAYER` 那一族），
所以这里补的不只是一条路由——是让「能力在不在」这件事有正确的答案。

## 鉴权照 `AUTH-03`：三种拒绝 NEVER 混成一个

```
缺头        → 401 IDENTITY_MISSING     调用方漏了身份头
身份查不到  → 401 IDENTITY_UNKNOWN     这个人不存在
有身份没角色 → 403 PERMISSION_DENIED    你是谁没问题，你对这个资源没有角色
项目不存在  → 404 NOT_FOUND            id 打错了
```

混成一句的后果：拿到 403 的人会去要权限，而真相可能是他把项目 id 打错了。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
ANALYSIS = REPO / "flint" / "api" / "analysis.py"
SHEET = REPO / "docs" / "blocked" / "DESIGN-GENERATE-HAS-NO-SUBMIT-ENDPOINT.md"
NOW = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)

PROJECT = "proj-1"
OWNER = "u-owner"
STRANGER = "u-stranger"
UNKNOWN_USER = "u-nobody"


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


@dataclass
class _Runner:
    """只记下被塞进队列的是什么。**NEVER 真起 worker**——本卡判的是入口。"""

    submitted: list[dict[str, Any]]

    async def submit(self, **kwargs: Any) -> str:
        self.submitted.append(dict(kwargs))
        return f"job-{len(self.submitted)}"


def _roles(user_id: str, scope: Any) -> str | None:
    """`u-owner` 对 owner scope 有角色，别人没有。"""
    return "owner" if user_id == OWNER else None


def _owner_scope(project_id: str) -> Any:
    from flint.authz import ProjectNotFound
    from flint.domain.models import Principal

    if project_id != PROJECT:
        raise ProjectNotFound(project_id)
    return Principal(kind="user", id=OWNER)


async def _check_user(header_value: str | None) -> str:
    """`build_user_check` 的 fixture 版：判据面 NEVER 连库。"""
    from flint.api.identity import IdentityMissing, IdentityUnknown

    if header_value is None or not header_value.strip():
        raise IdentityMissing("X-User-Id")
    user_id = header_value.strip()
    if user_id == UNKNOWN_USER:
        raise IdentityUnknown(user_id)
    return user_id


def _app(runner: _Runner) -> Any:
    import httpx
    from fastapi import FastAPI

    from flint.api.analysis import AnalysisApiDeps, create_analysis_app
    from flint.api.identity import install_identity_handlers

    deps = AnalysisApiDeps(
        dsn="postgresql://unused", runner=runner,          # type: ignore[arg-type]
        events=None,                                        # type: ignore[arg-type]
        owner_scope_for_project=_owner_scope,
        role_resolver=_roles,                               # type: ignore[arg-type]
        user_check=_check_user,
    )
    inner = create_analysis_app(deps)
    outer = FastAPI()
    install_identity_handlers(inner)
    _ = outer, httpx
    return inner


def _post(runner: _Runner, path: str, body: Any, user: str | None) -> Any:
    import httpx

    from flint.authz import ProjectNotFound

    app = _app(runner)

    async def go() -> Any:
        headers = {} if user is None else {"x-user-id": user}
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            return await c.post(path, json=body, headers=headers)

    _ = ProjectNotFound
    return _run(go())


BODY = {"brief": "一句话出一个设计", "template_id": None}


# ───────────────────────── 一、端点存在，且**塞进队列的是对的那个 kind**


def test_the_endpoint_exists_and_enqueues_a_design_generate_job() -> None:
    """改前这条路径回的是框架那种没有 `code` 的 404（= 能力没挂）。"""
    runner = _Runner(submitted=[])
    resp = _post(runner, f"/projects/{PROJECT}/design_generate", BODY, OWNER)

    assert resp.status_code == 200, resp.text
    assert resp.json()["job_id"], "没回 job_id——那前端订阅不了"
    assert len(runner.submitted) == 1, "没往队列里塞东西"
    assert runner.submitted[0]["kind"] == "design_generate", (
        f"塞进去的 kind 不对：{runner.submitted[0]['kind']}"
    )


def test_the_payload_carries_what_the_consumer_reads() -> None:
    """payload 里要有消费者真会读的字段。

    **判的是消费者读什么**，不是「payload 非空」：塞一个消费者不认的形状，
    作业会跑起来然后失败，而失败信息里只会说「缺 xxx」——
    没人会想到是入口塞错了。

    ## 这条判据自己写错过一次

    改前它断言的是 `payload["brief"]`——**而消费者读的是
    `payload["prompt"]`**（`flint/jobs/design_generate.py:118`）。
    也就是说：**一条名叫「payload 带的是消费方读的那个」的判据，
    钉住的正是那个对不上的键**，而它一直是绿的。

    `SMOKE-01` 第一次真跑这一族才撞见：每条设计作业都以
    「没有 prompt」失败——**这一族从来没有跑通过一次**。

    所以这里不只改字面，还把**消费方那一侧一起读进来**：
    两边从此对着同一个名字，谁先动都会红。
    """
    consumer = (REPO / "flint" / "jobs" / "design_generate.py").read_text(
        encoding="utf-8")
    runner = _Runner(submitted=[])
    _post(runner, f"/projects/{PROJECT}/design_generate", BODY, OWNER)

    payload = runner.submitted[0]["payload"]
    assert payload["project_id"] == PROJECT
    assert 'payload.get("prompt"' in consumer, (
        "消费方读的键变了——提交那一侧要跟着改")
    assert payload["prompt"] == BODY["brief"], (
        f"提交塞的键与消费方读的对不上：payload 里有 {sorted(payload)}")


def test_the_job_is_owned_so_the_stream_can_be_subscribed() -> None:
    """acceptance④：提交后可经既有 SSE 通道订阅。

    订阅那一头（`GET /jobs/{id}/events`）判的是
    `initiated_by` 或 owner-scope 成员——所以提交时**两样都要带上**，
    否则提交成功、订阅 403，而屏上看起来是「作业不见了」。
    """
    runner = _Runner(submitted=[])
    _post(runner, f"/projects/{PROJECT}/design_generate", BODY, OWNER)

    assert runner.submitted[0]["initiated_by"] == OWNER
    assert runner.submitted[0]["owner_scope"] is not None


# ───────────────────────── 二、`AUTH-03` 三种拒绝，各说各的


def test_a_missing_header_is_401_not_403() -> None:
    runner = _Runner(submitted=[])
    resp = _post(runner, f"/projects/{PROJECT}/design_generate", BODY, None)

    assert resp.status_code == 401, resp.text
    assert resp.json()["code"] == "IDENTITY_MISSING"
    assert runner.submitted == [], "没身份也把作业塞进去了"


def test_an_unknown_identity_is_401_too_but_a_different_code() -> None:
    """两种 401 **修法相反**：一个是调用方补头，一个是这个人根本不存在。"""
    runner = _Runner(submitted=[])
    resp = _post(runner, f"/projects/{PROJECT}/design_generate", BODY, UNKNOWN_USER)

    assert resp.status_code == 401
    assert resp.json()["code"] == "IDENTITY_UNKNOWN"


def test_a_known_user_without_a_role_is_403() -> None:
    """身份没问题、对这个项目没角色 → 403。**NEVER 401**：

    回 401 会让人去重新登录，而他已经登录了——要的是有人给他授权。
    """
    runner = _Runner(submitted=[])
    resp = _post(runner, f"/projects/{PROJECT}/design_generate", BODY, STRANGER)

    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "PERMISSION_DENIED"
    assert runner.submitted == [], "无角色也把作业塞进去了"


def test_an_unknown_project_is_404_not_403() -> None:
    """项目不存在 → 404。**与 403 分开**：

    混成 403 的话，拿到它的人会去要权限，而真相是他把项目 id 打错了。
    """
    runner = _Runner(submitted=[])
    resp = _post(runner, "/projects/nope/design_generate", BODY, OWNER)

    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "NOT_FOUND"


def test_the_four_rejections_are_four_distinct_answers() -> None:
    """**阴性对照**：四种拒绝的 (状态码, code) 两两不同。

    没有这一条，把三种都实现成 403 也能让上面四条里的三条各自绿——
    只要每条单独看都「拒绝了」。
    """
    runner = _Runner(submitted=[])
    seen = {
        (r.status_code, r.json().get("code"))
        for r in (
            _post(runner, f"/projects/{PROJECT}/design_generate", BODY, None),
            _post(runner, f"/projects/{PROJECT}/design_generate", BODY, UNKNOWN_USER),
            _post(runner, f"/projects/{PROJECT}/design_generate", BODY, STRANGER),
            _post(runner, "/projects/nope/design_generate", BODY, OWNER),
        )
    }

    assert len(seen) == 4, f"四种拒绝没有四个不同的答案：{sorted(seen)}"


# ───────────────────────── 三、这条 404 与「能力没挂」的那条 404 分得开


def test_the_capability_is_no_longer_reported_as_missing() -> None:
    """改前是框架那种**没有 `code`** 的 404（`{"detail":"Not Found"}`）。

    那种 404 说的是「这个能力还没挂」；带 `code` 的 404 说的是「这一条不存在」。
    两者混起来，前端分不出该显示「接口未提供」还是「没有这条」。
    """
    runner = _Runner(submitted=[])
    resp = _post(runner, "/projects/nope/design_generate", BODY, OWNER)

    assert "code" in resp.json(), "回的是框架 404——路由没挂上"
    assert "detail" not in resp.json() or resp.json().get("code")


# ───────────────────────── 四、单据关掉，且关的条件是事情做完了


def test_the_sheet_is_closed_because_the_endpoint_exists() -> None:
    """先验端点在，再验状态行——关单的条件是**事情做完了**，不是「卡跑完了」。"""
    source = ANALYSIS.read_text(encoding="utf-8")
    assert "design_generate" in source, "端点不在源码里"

    text = SHEET.read_text(encoding="utf-8")
    state = next(ln for ln in text.splitlines()[:8] if ln.startswith("**状态**"))

    assert state.startswith("**状态** closed"), f"单据还开着：{state!r}"
    assert "ENTRY-01" in text, "单子里没写是哪张卡落的地"


# ───────────────────────── 五、那个 cast 藏不住拼错


def test_the_kind_is_a_real_member_of_the_union_not_just_a_string() -> None:
    """端点用了 `cast(JobKind, …)`——**那把类型检查关掉了**，所以这里补上。

    `design_generate` 在 **v0.4 冻结加件**的 `JobKind` 里，而
    `flint/domain/models.py#JobKind`（运行期那一份）是 v0.3 的七值。
    两份契约都在被引用，`dispatch.known_job_kinds()` 取的正是并集。

    不 cast 就得改冻结件（`S2-1` 禁止）；cast 了就得有人守着拼错——
    拼错的那一版会**提交成功**，然后 worker 抛 `UnknownJobKind`，
    而那时错误信息指向的是 worker，不是这条端点。
    """
    from flint.api.analysis import DESIGN_GENERATE_KIND
    from flint.jobs.dispatch import WIREABLE_KINDS, known_job_kinds

    assert DESIGN_GENERATE_KIND in known_job_kinds(), (
        f"{DESIGN_GENERATE_KIND!r} 不在判别联合里——cast 盖住了一个拼错"
    )
    assert DESIGN_GENERATE_KIND in WIREABLE_KINDS, (
        "这条 kind 没有消费者——提交进去只会一直排队"
    )


def test_the_literal_lives_in_exactly_one_place() -> None:
    """字面量只写一处：端点与本判据引同一个常量，拼错时两边一起红。

    各写一份的话，改了一处而另一处没改时，**判据仍然是绿的**。
    """
    source = ANALYSIS.read_text(encoding="utf-8")
    body = source[source.index("async def submit_design"):]
    body = body[: body.index("@app.get")]

    assert '"design_generate"' not in body, "端点里又写了一遍字面量"
    assert "DESIGN_GENERATE_KIND" in body
