"""ENTRY-02：选主题的**写入口**——topic 一族此前三条全是 GET。

## 改前

`GET /projects/{id}/topics` 回的 `chosen_topic_id` 是**读**的那一半；
写的那一半不存在。屏上那个「选它」按钮因此点了没用，
`web/app/projects/[id]/topics/page.tsx` 逐字写着：

> 点「选它」时如实说这条还没接——NEVER 前端自己记一份：
> 记了的话，刷新一次就没了，而用户以为自己已经选过。

**那句纪律是对的**，所以本卡补的是端点，不是前端的一份影子状态。
判据里最要紧的一条正是「刷新之后选择仍在」——它只能靠后端为真。

## 域函数已经在了，本卡一行判断都不重写

`flint/topic/project.py#choose_topic` 已经守着两件事：
越界的 topic 直接拒（`ProjectValidationError`）、选定时往 `change_log` 追一条。
端点只做**转调 + 鉴权 + 幂等**。

## 幂等在端点这一侧

`choose_topic` **每调一次就追一条** change_log——那对域函数是对的
（它不知道调用方是不是重复点了）。而「同一主题重复选」不该留下第二条记录：
那会让变更历史看起来像用户改了两次主意。所以短路判在端点里，
并有一条阴性对照钉住：**换**主题时第二条必须留下。
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
API = REPO / "flint" / "api" / "topics.py"
VIEWS = REPO / "flint" / "api" / "views.py"
PAGE = REPO / "web" / "app" / "projects" / "[id]" / "topics" / "page.tsx"
SHEET = REPO / "docs" / "blocked" / "TOPIC-CHOOSE-HAS-NO-WRITE-ENDPOINT.md"

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)
PROJECT = "tc-proj"
OWNER = "tc-owner"
STRANGER = "tc-stranger"
UNKNOWN_USER = "tc-nobody"
TOPIC_A, TOPIC_B, OUTSIDER = "tc-topic-a", "tc-topic-b", "tc-topic-zzz"


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture()
def seeded() -> Any:
    import asyncpg

    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", PROJECT)
        finally:
            await conn.close()

    async def seed() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "INSERT INTO projects (project_id, owner, origin_id, topic_ids, "
                "chosen_topic_id, deliverable_ids, change_log, status, created_at) "
                "VALUES ($1, $2::jsonb, 'tc-origin', $3::jsonb, NULL, '[]'::jsonb, "
                "'[]'::jsonb, 'active', $4)",
                PROJECT, json.dumps({"kind": "user", "id": OWNER}),
                json.dumps([TOPIC_A, TOPIC_B]), NOW)
        finally:
            await conn.close()

    _run(wipe())
    _run(seed())
    yield
    _run(wipe())


async def _check_user(header_value: str | None) -> str:
    from flint.api.identity import IdentityMissing, IdentityUnknown

    if header_value is None or not header_value.strip():
        raise IdentityMissing("X-User-Id")
    user_id = header_value.strip()
    if user_id == UNKNOWN_USER:
        raise IdentityUnknown(user_id)
    return user_id


def _owner_scope(project_id: str) -> Any:
    from flint.authz import ProjectNotFound
    from flint.domain.models import Principal

    if project_id != PROJECT:
        raise ProjectNotFound(project_id)
    return Principal(kind="user", id=OWNER)


def _roles(user_id: str, scope_id: str) -> str | None:
    return "owner" if user_id == OWNER else None


def _post(topic_id: str, user: str | None = OWNER, project: str = PROJECT) -> Any:
    import httpx

    from flint.api.identity import install_identity_handlers
    from flint.api.topics import TopicsApiDeps, create_topics_app

    app = create_topics_app(TopicsApiDeps(
        dsn=DSN, owner_scope_for_project=_owner_scope,
        role_resolver=_roles, user_check=_check_user))
    install_identity_handlers(app)

    async def go() -> Any:
        headers = {} if user is None else {"x-user-id": user}
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport,
                                     base_url="http://testserver") as client:
            return await client.post(
                f"/projects/{project}/chosen-topic",
                json={"topic_id": topic_id}, headers=headers)

    return _run(go())


def _stored() -> Any:
    import asyncpg

    async def go() -> Any:
        conn = await asyncpg.connect(DSN)
        try:
            return await conn.fetchrow(
                "SELECT chosen_topic_id, change_log FROM projects WHERE project_id = $1",
                PROJECT)
        finally:
            await conn.close()

    return _run(go())


# ───────────────────────── 一、写下去了，而且**刷新之后还在**


@pytest.mark.compose
def test_choosing_a_topic_lands_in_the_database(seeded: None) -> None:
    resp = _post(TOPIC_A)

    assert resp.status_code == 200, resp.text
    assert resp.json()["chosen_topic_id"] == TOPIC_A
    assert _stored()["chosen_topic_id"] == TOPIC_A


@pytest.mark.compose
def test_the_choice_survives_a_reload(seeded: None) -> None:
    """**本卡最要紧的一条**：重新读一次，选择仍在。

    前端自己记一份的话，这一条永远绿不了——那正是屏上那句纪律的由来：
    记了的话刷新一次就没了，而用户以为自己已经选过。

    读的那一头用**真端点**（`GET /projects/{id}/topics`），不是直查库：
    直查库测不出「读端点没把它带出来」这种断法。
    """
    import httpx

    from flint.api.views import ViewsApiDeps, create_views_app

    _post(TOPIC_B)

    async def read() -> Any:
        app = create_views_app(ViewsApiDeps(dsn=DSN))
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport,
                                     base_url="http://testserver") as client:
            return await client.get(f"/projects/{PROJECT}/topics")

    body = _run(read()).json()
    assert body["chosen_topic_id"] == TOPIC_B, "读端点没把选择带回来"


# ───────────────────────── 二、幂等，且换主题要留痕


@pytest.mark.compose
def test_choosing_the_same_topic_twice_leaves_one_record(seeded: None) -> None:
    """同一主题重复选 NEVER 产生第二条变更记录。

    留两条的话，变更历史看起来像**用户改了两次主意**——
    而他只是又点了一次同一个按钮。
    """
    _post(TOPIC_A)
    _post(TOPIC_A)

    log = json.loads(_stored()["change_log"])
    assert len(log) == 1, f"重复选留下了 {len(log)} 条记录：{log}"


@pytest.mark.compose
def test_switching_topics_does_leave_a_second_record(seeded: None) -> None:
    """**阴性对照**：换主题必须留第二条。

    没有这一条，把幂等实现成「永远不追加」也能让上一条绿——
    而那会把「改主意」这件事从历史里抹掉。
    """
    _post(TOPIC_A)
    _post(TOPIC_B)

    log = json.loads(_stored()["change_log"])
    assert len(log) == 2, f"换主题没留痕：{log}"
    assert [e["topic_id"] for e in log] == [TOPIC_A, TOPIC_B]
    assert _stored()["chosen_topic_id"] == TOPIC_B


# ───────────────────────── 三、越界的 topic 拒收


@pytest.mark.compose
def test_a_topic_outside_the_project_is_rejected(seeded: None) -> None:
    """不在 `topic_ids` 里的主题 → 400，NEVER 静默写进去。

    写进去的话，`chosen_topic_id` 会指向一个这个项目根本没有的主题，
    而下游（verdict↔topic 那条链）按它去取东西时只会拿到空。
    """
    resp = _post(OUTSIDER)

    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == "VALIDATION_FAILED"
    assert _stored()["chosen_topic_id"] is None, "越界的主题被写进去了"


@pytest.mark.compose
def test_the_range_check_is_the_domain_one(seeded: None) -> None:
    """越界判断**转调域函数**，端点里一行都不重写。

    重写一份的后果不是重复劳动，而是**两处对「越界」的定义迟早分叉**，
    而它们守的是同一条不变量。
    """
    source = API.read_text(encoding="utf-8")

    assert "choose_topic" in source, "端点没转调域函数"
    assert "ProjectValidationError" in source
    assert "topic_ids" not in source.replace("choose_topic", ""), (
        "端点里自己又判了一次 topic_ids"
    )


# ───────────────────────── 四、`AUTH-03` 四种拒绝，各说各的


@pytest.mark.compose
def test_the_four_rejections_are_four_distinct_answers(seeded: None) -> None:
    """缺头 401 · 身份查不到 401（另一个 code）· 无角色 403 · 项目不存在 404。

    **阴性对照**：四者两两不同。没有这一条，把三种都实现成 403
    也能让「拒绝了」这件事逐条为真。
    """
    seen = {
        (r.status_code, r.json().get("code"))
        for r in (
            _post(TOPIC_A, user=None),
            _post(TOPIC_A, user=UNKNOWN_USER),
            _post(TOPIC_A, user=STRANGER),
            _post(TOPIC_A, project="nope"),
        )
    }

    assert len(seen) == 4, f"四种拒绝没有四个不同的答案：{sorted(seen)}"
    assert _stored()["chosen_topic_id"] is None, "被拒的请求把东西写进去了"


# ───────────────────────── 五、读端点还是只读的


def test_the_read_only_module_stayed_read_only() -> None:
    """写端点**没有**塞进 `views.py`。

    那份文件的第一句就是「**既有模型上的只读端点**」。
    往里加一个写，等于让「这一族不改数据」这句话从此不成立——
    而下一个人读到那句话时会信它。
    """
    source = VIEWS.read_text(encoding="utf-8")

    assert "@app.post" not in source, "views.py 里出现了写端点"
    assert "只读端点" in source


# ───────────────────────── 六、屏上那个按钮真的接上了


def test_the_screen_wires_the_choose_action() -> None:
    """`TopicListView` 的 `onSelectTopic` 早就在，**屏没传**。

    判**调用点**：只 import 不传，「按钮点了没用」这件事在判据上看不出来。
    """
    code = PAGE.read_text(encoding="utf-8")
    code = "\n".join(
        line for line in code.splitlines() if not line.lstrip().startswith("//"))

    assert "onSelectTopic" in code, "屏没把选主题动作传下去"
    assert "chosen-topic" in code, "屏没打写端点"


def test_the_screen_still_never_keeps_its_own_copy() -> None:
    """选中态**恒取后端的值**——这条纪律一个字没松。

    接上写端点之后最容易顺手做的事，就是本地先改一下让它「看起来快」。
    那份影子状态刷新一次就没了，而用户以为自己已经选过。
    """
    code = PAGE.read_text(encoding="utf-8")
    body = "\n".join(
        line for line in code.splitlines() if not line.lstrip().startswith("//"))

    assert not re.search(r"useState[^\n]*chosen", body, re.IGNORECASE), (
        "屏上自己记了一份选中态"
    )
    assert "chosenTopicId={" in body


def test_the_stale_comment_about_the_missing_endpoint_is_gone() -> None:
    """那段注释说「写的那一半没有端点」——现在是假话。

    留着假话比没有注释更坏：下一个人会照它再立一次单。
    """
    code = PAGE.read_text(encoding="utf-8")

    assert "TOPIC-CHOOSE-HAS-NO-WRITE-ENDPOINT" not in code, "屏上还引着已关的单"


def test_the_sheet_is_closed() -> None:
    text = SHEET.read_text(encoding="utf-8")
    state = next(ln for ln in text.splitlines()[:8] if ln.startswith("**状态**"))

    assert state.startswith("**状态** closed"), f"单据还开着：{state!r}"
    assert "ENTRY-02" in text


# ───────────────────────── 七、路由真的挂上了


def test_the_write_app_is_mounted_in_the_assembly() -> None:
    """**挂上才算接线**。

    本批反复撞见的形状是「能力建好了路由没挂」——没挂时前端拿到的是
    框架那种**没有 `code`** 的 404（= 这个能力还没挂），
    与「这一条不存在」长得一模一样，而两者要做的事完全不同。
    """
    source = (REPO / "flint" / "api" / "app.py").read_text(encoding="utf-8")

    assert "create_topics_app" in source, "写端点没挂进装配"
    assert "TopicsApiDeps" in source


def test_the_mounted_route_is_the_one_the_screen_calls() -> None:
    """装配出来的应用里**真有**那条路径，且屏打的就是它。

    分开写死两处的话，改一处而另一处没改时，判据仍然是绿的。
    """
    from fastapi import FastAPI

    from flint.api.topics import TopicsApiDeps, create_topics_app

    app: FastAPI = create_topics_app(TopicsApiDeps(
        dsn="postgresql://unused", owner_scope_for_project=_owner_scope,
        role_resolver=_roles))
    paths = {getattr(r, "path", "") for r in app.routes}

    assert "/projects/{project_id}/chosen-topic" in paths, sorted(paths)
    assert "chosen-topic" in PAGE.read_text(encoding="utf-8")
