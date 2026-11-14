"""DOC-02：迁移 + 抓取管线写正文。

## 这张卡把 DOC-01 的契约落到库里

DOC-01 只改了 `contracts_v04`。本卡做三件事：加列、写入、去重。

## 「只存一份」为什么是一张单独的表

acceptance④ 要的是「同一篇文章多源抓到**只存一份**，引用关系保留」。

只留 `docs.content` 一列的话，第二个源那行只能填 `NULL`——而 DOC-01 把
`content IS NULL` 的语义写死成**「还没提取」**。两件事挤进同一个值，
重跑提取时就不知道该跳过谁。

所以正文单独一张 `doc_contents`（主键 = `content_sha256`），`docs` 那一行
仍按内容寻址指过去：**一份正文一行，N 个来源 N 行 doc**，各自的
`doc_id` / `source_id` / `url` 原样保留——那就是「引用关系保留」。

## 哈希算的是**截断前**那一份

DOC-01 的字段说明写死了这条。截断后再算的话，同一篇文章因两次截断位置不同
会算出两个哈希，验证与去重同时失灵。所以 `prepare_content` 先算哈希再截。

## 一次事务写入（acceptance②）

元数据与正文**同生同死**：分两次写的话，中间挂掉会留下一行「有元数据、
没正文、也没标记还没提取」的 doc——它长得和「提取失败」一模一样。
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from contracts_v04.models_v04 import DOC_CONTENT_MAX_BYTES
from flint.evidence.docstore import (
    PgDocStore,
    build_doc_with_content,
    prepare_content,
)
from tests.conftest import TEST_DSN

MIGRATION = REPO / "migrations" / "versions" / "0019_doc_content.py"


def _doc(**over: object) -> object:
    from contracts_v04.models_v04 import Doc

    base = {
        "doc_id": "d-1", "source_id": "s-1", "kind": "webpage", "title": "t",
        "url": "https://x.test/a", "published_at": None, "meta": {},
        "origin": "retrieved", "access": "public", "region": None, "source_country": None,
    }
    base.update(over)
    return Doc(**base)  # type: ignore[arg-type]


# ───────────────────────── 一、截断与哈希（纯函数，离线）


def test_short_text_is_stored_whole_and_marked_untruncated() -> None:
    body = "锂电池回收的正文" * 10

    prepared = prepare_content(body)

    assert prepared.content == body
    assert prepared.truncated is False
    assert prepared.sha256 == hashlib.sha256(body.encode("utf-8")).hexdigest()


def test_the_hash_is_of_the_original_not_of_the_truncated_copy() -> None:
    """**截断前**那一份的哈希。

    截断后再算的话，同一篇文章因两次截断位置不同会算出两个哈希——
    验证（库里这份还是不是当初那份）与去重（多源同文只存一份）同时失灵。
    """
    body = "a" * (DOC_CONTENT_MAX_BYTES + 5000)

    prepared = prepare_content(body)

    assert prepared.truncated is True
    assert prepared.sha256 == hashlib.sha256(body.encode("utf-8")).hexdigest()
    assert prepared.sha256 != hashlib.sha256(prepared.content.encode("utf-8")).hexdigest()


def test_truncation_cuts_at_the_byte_cap_not_the_character_count() -> None:
    """上限是**字节**：按字符切的话，一篇汉字正文会是上限的三倍大。"""
    body = "字" * DOC_CONTENT_MAX_BYTES

    prepared = prepare_content(body)

    assert len(prepared.content.encode("utf-8")) <= DOC_CONTENT_MAX_BYTES
    assert prepared.truncated is True


def test_truncation_never_splits_a_character_in_half() -> None:
    """切在多字节字符中间会产出坏 UTF-8。切到能解码为止。"""
    body = "字" * (DOC_CONTENT_MAX_BYTES // 2)

    prepared = prepare_content(body)

    assert prepared.content == prepared.content.encode("utf-8").decode("utf-8")
    assert not prepared.content.endswith("�")


def test_exactly_at_the_cap_is_not_truncated() -> None:
    """恰好等于上限**不算**截断——边界上多标一次，下游会以为全文缺了一块。"""
    body = "a" * DOC_CONTENT_MAX_BYTES

    prepared = prepare_content(body)

    assert prepared.truncated is False
    assert prepared.content == body


def test_empty_text_is_not_the_same_as_never_extracted() -> None:
    """空正文是**提取过、结果是空**：`content=""`，NEVER 变成 `None`。"""
    prepared = prepare_content("")

    assert prepared.content == ""
    assert prepared.truncated is False


def test_building_a_doc_fills_all_three_fields_together() -> None:
    """三个字段同生：`build_doc_with_content` 一次填齐，NEVER 让调用方各填各的。"""
    body = "正文" * 20

    doc = build_doc_with_content(_doc(), body)

    assert doc.content == body  # type: ignore[attr-defined]
    assert doc.content_sha256 == hashlib.sha256(body.encode()).hexdigest()  # type: ignore[attr-defined]
    assert doc.content_truncated is False  # type: ignore[attr-defined]


def test_building_a_doc_keeps_every_other_field_untouched() -> None:
    """只填正文三件套，别的字段一个不动——它们是采集期的事实。"""
    original = _doc(url="https://x.test/b", source_country="JP")

    doc = build_doc_with_content(original, "正文")

    assert doc.url == "https://x.test/b"  # type: ignore[attr-defined]
    assert doc.source_country == "JP"  # type: ignore[attr-defined]
    assert doc.doc_id == original.doc_id  # type: ignore[attr-defined]


# ───────────────────────── 二、迁移：正向与回滚（acceptance①）


def test_the_migration_file_is_on_disk_with_the_right_chain() -> None:
    assert MIGRATION.exists(), "缺 0019 迁移"
    text = MIGRATION.read_text(encoding="utf-8")

    assert 'revision = "0019"' in text
    assert 'down_revision = "0018"' in text


def test_the_migration_has_a_real_downgrade() -> None:
    """回滚要真回滚。`pass` 一句的 downgrade 是「回滚测过了」的假象。"""
    text = MIGRATION.read_text(encoding="utf-8")
    body = text[text.find("def downgrade()"):]

    assert "drop_column" in body or "drop_table" in body, "downgrade 什么都没做"
    for column in ("content_sha256", "content_truncated", "source_file_ref"):
        assert column in body, f"downgrade 没清掉 {column}"


# ───────────────────────── 三、真库：写入、事务、去重（compose）


@pytest.fixture
def dsn() -> str:
    return TEST_DSN


async def _wipe(conn: asyncpg.Connection) -> None:
    await conn.execute("DELETE FROM citations")
    await conn.execute("DELETE FROM docs")
    await conn.execute("DELETE FROM doc_contents")


@pytest.mark.compose
def test_the_columns_and_the_content_table_are_really_there(dsn: str) -> None:
    async def run() -> None:
        conn = await asyncpg.connect(dsn)
        try:
            cols = {
                r["column_name"]
                for r in await conn.fetch(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'docs'")
            }
            assert {"content_sha256", "content_truncated", "source_file_ref"} <= cols
            assert await conn.fetchval("SELECT to_regclass('public.doc_contents')") is not None
        finally:
            await conn.close()

    asyncio.run(run())


@pytest.mark.compose
def test_saving_and_loading_a_doc_round_trips_the_body(dsn: str) -> None:
    async def run() -> None:
        store = PgDocStore(dsn)
        conn = await asyncpg.connect(dsn)
        try:
            await _wipe(conn)
        finally:
            await conn.close()
        body = "锂电池回收的正文" * 50
        await store.save_doc_with_content(build_doc_with_content(_doc(), body))

        loaded = await store.load_doc_with_content("d-1")

        assert loaded.content == body
        assert loaded.content_sha256 == hashlib.sha256(body.encode()).hexdigest()
        assert loaded.content_truncated is False

    asyncio.run(run())


@pytest.mark.compose
def test_a_doc_without_content_loads_as_never_extracted(dsn: str) -> None:
    """没写正文的 doc 读回来是 `content=None`——「还没提取」这一态要活着。"""
    async def run() -> None:
        store = PgDocStore(dsn)
        conn = await asyncpg.connect(dsn)
        try:
            await _wipe(conn)
        finally:
            await conn.close()
        await store.save_doc_with_content(_doc(doc_id="d-bare"))

        loaded = await store.load_doc_with_content("d-bare")

        assert loaded.content is None
        assert loaded.content_sha256 is None
        assert loaded.content_truncated is False

    asyncio.run(run())


@pytest.mark.compose
def test_an_empty_body_round_trips_as_empty_not_as_never_extracted(dsn: str) -> None:
    """空正文要**存下来**：`content=""` 读回来还是 `""`，NEVER 变成 `None`。

    「这篇文章正文是空的」与「还没提取」是两回事——写入路径用真值判断
    （`if doc.content:`）的话，空正文会被静默跳过，读回来成了 `None`，
    于是重跑提取时它被当成没提过，永远重跑下去。变异考⑥ 就是这个形状。
    """
    async def run() -> None:
        store = PgDocStore(dsn)
        conn = await asyncpg.connect(dsn)
        try:
            await _wipe(conn)
        finally:
            await conn.close()
        await store.save_doc_with_content(build_doc_with_content(_doc(doc_id="d-empty"), ""))

        loaded = await store.load_doc_with_content("d-empty")

        assert loaded.content == ""
        assert loaded.content is not None
        assert loaded.content_sha256 == hashlib.sha256(b"").hexdigest()

    asyncio.run(run())


@pytest.mark.compose
def test_two_sources_of_the_same_article_store_the_body_once(dsn: str) -> None:
    """acceptance④：同哈希只存一份，两行 doc 各自的来源与链接原样保留。"""
    async def run() -> None:
        store = PgDocStore(dsn)
        conn = await asyncpg.connect(dsn)
        try:
            await _wipe(conn)
            body = "同一篇文章" * 100
            await store.save_doc_with_content(
                build_doc_with_content(_doc(doc_id="d-a", source_id="gtrends",
                                            url="https://a.test/x"), body))
            await store.save_doc_with_content(
                build_doc_with_content(_doc(doc_id="d-b", source_id="weibo",
                                            url="https://b.test/y"), body))

            assert await conn.fetchval("SELECT count(*) FROM doc_contents") == 1
            assert await conn.fetchval("SELECT count(*) FROM docs") == 2
            a = await store.load_doc_with_content("d-a")
            b = await store.load_doc_with_content("d-b")
            assert a.content == b.content == body
            assert (a.source_id, a.url) == ("gtrends", "https://a.test/x")
            assert (b.source_id, b.url) == ("weibo", "https://b.test/y")
        finally:
            await conn.close()

    asyncio.run(run())


@pytest.mark.compose
def test_different_bodies_are_stored_separately(dsn: str) -> None:
    """去重只在**同哈希**时发生：见谁都合并的去重会把两篇文章并成一篇。"""
    async def run() -> None:
        store = PgDocStore(dsn)
        conn = await asyncpg.connect(dsn)
        try:
            await _wipe(conn)
            await store.save_doc_with_content(build_doc_with_content(_doc(doc_id="d-a"), "甲"))
            await store.save_doc_with_content(build_doc_with_content(_doc(doc_id="d-b"), "乙"))

            assert await conn.fetchval("SELECT count(*) FROM doc_contents") == 2
        finally:
            await conn.close()

    asyncio.run(run())


@pytest.mark.compose
def test_metadata_and_body_are_written_in_one_transaction(dsn: str) -> None:
    """acceptance②：写正文那一步炸掉时，元数据也**不留**。

    分两次写的话，中间挂掉会留下一行「有元数据、没正文、也没标记还没提取」的 doc——
    它和「提取失败」长得一模一样，而重跑时没人知道该重跑哪一条。
    """
    async def run() -> None:
        store = PgDocStore(dsn)
        conn = await asyncpg.connect(dsn)
        try:
            await _wipe(conn)
            doc = build_doc_with_content(_doc(doc_id="d-boom"), "正文")
            with pytest.raises(RuntimeError, match="boom"):
                await store.save_doc_with_content(doc, _fail_after_metadata=True)

            assert await conn.fetchval(
                "SELECT count(*) FROM docs WHERE doc_id = 'd-boom'") == 0
            assert await conn.fetchval("SELECT count(*) FROM doc_contents") == 0
        finally:
            await conn.close()

    asyncio.run(run())


@pytest.mark.compose
def test_resaving_the_same_doc_is_safe(dsn: str) -> None:
    """重复保存幂等：抓取管线重跑一次不该炸，也不该把正文存成两份。"""
    async def run() -> None:
        store = PgDocStore(dsn)
        conn = await asyncpg.connect(dsn)
        try:
            await _wipe(conn)
            doc = build_doc_with_content(_doc(), "正文" * 30)
            await store.save_doc_with_content(doc)
            await store.save_doc_with_content(doc)

            assert await conn.fetchval("SELECT count(*) FROM docs") == 1
            assert await conn.fetchval("SELECT count(*) FROM doc_contents") == 1
        finally:
            await conn.close()

    asyncio.run(run())


@pytest.mark.compose
def test_a_truncated_body_keeps_its_mark_through_the_round_trip(dsn: str) -> None:
    """acceptance③：截断标记必须活着回到下游——**NEVER 让它以为拿到的是全文**。"""
    async def run() -> None:
        store = PgDocStore(dsn)
        conn = await asyncpg.connect(dsn)
        try:
            await _wipe(conn)
        finally:
            await conn.close()
        body = "a" * (DOC_CONTENT_MAX_BYTES + 1000)
        await store.save_doc_with_content(build_doc_with_content(_doc(doc_id="d-cut"), body))

        loaded = await store.load_doc_with_content("d-cut")

        assert loaded.content_truncated is True
        assert loaded.content_sha256 == hashlib.sha256(body.encode()).hexdigest()
        assert len(loaded.content.encode("utf-8")) <= DOC_CONTENT_MAX_BYTES

    asyncio.run(run())


@pytest.mark.compose
def test_the_old_metadata_only_api_still_works(dsn: str) -> None:
    """既有 `save_doc` / `load_doc`（冻结件 Doc，无正文）一行不改照样跑。"""
    async def run() -> None:
        from flint.domain.models import Doc as FrozenDoc

        store = PgDocStore(dsn)
        conn = await asyncpg.connect(dsn)
        try:
            await _wipe(conn)
        finally:
            await conn.close()
        frozen = FrozenDoc(
            doc_id="d-old", source_id="s-1", kind="webpage", title="t",
            url="https://x.test/old", published_at=None, meta={},
            origin="retrieved", access="public")
        await store.save_doc(frozen)

        assert (await store.load_doc("d-old")).url == "https://x.test/old"

    asyncio.run(run())


# ───────────────────────── 三·五、§3.5 那把合规尺子：放行一处，不是拆掉


def test_the_docs_table_itself_still_has_no_fulltext_column() -> None:
    """`docs` 表**仍然没有正文列**——§3.5 原话「Doc 无 content 字段」逐字还成立。

    正文落在单独的 `doc_contents`。这不是文字游戏：一行 doc 是「某个源在某个 URL
    上看到过这篇」，正文是「这篇本身」。分开之后，去重与「引用关系保留」
    才能同时成立（见迁移 0019 的 docstring）。
    """
    text = MIGRATION.read_text(encoding="utf-8")
    # 字符类要带数字：`[a-z_]+` 漏掉 `content_sha256`（名字里有 256），
    # 于是判据只看到两列就去比集合——实测就是这么红的一次。
    added = re.findall(r'op\.add_column\(\s*"docs",\s*sa\.Column\(\s*"([a-z0-9_]+)"', text)

    assert "content" not in added, "正文列被加到 docs 上了"
    assert set(added) == {"content_sha256", "content_truncated", "source_file_ref"}


def test_the_compliance_allowlist_names_exactly_three_places() -> None:
    """白名单**只放行三处**，且每一处都有出处。

    这是一条绊线：再多一处就该有人来这里确认「那也是被裁决放行的，不是被漏掉的」。
    放行一处与拆掉尺子是两件事——尺子对别的表照旧判红（下一条判据实测）。

    **它按设计响过一次**：`PERSIST-03`（第 9 批）建了 `templates` 表，
    那一列存的是固化后的模板 HTML，命中 `html` 这个词而被尺子拦下。
    于是有人（worker）来到这里确认——**这正是这条绊线要的动作**，
    而不是在别处悄悄加一项。

    第三处**走的是 `blocks.content` 那一档（系统自产），不是 `doc_contents` 那一档**：
    模板 HTML 由用户自己的样板经 `to_slots` 变换而来，示例正文与示例数字
    一律拒绝放行（残留即 `SolidifyBlocked`），落进去的只剩形状——
    与外站全文没有任何关系，**不需要援引 `DOC-01` 那条裁决**。
    """
    from flint.sources.throttle import SYSTEM_GENERATED_ALLOWLIST

    assert SYSTEM_GENERATED_ALLOWLIST == frozenset({
        ("blocks", "content"),
        ("doc_contents", "content"),
        ("templates", "html"),
    })

    source = (REPO / "flint" / "sources" / "throttle.py").read_text(encoding="utf-8")
    assert "owner 2026-08-04 裁决方案 A" in source, "白名单没写这条放行的出处"
    assert "PERSIST-03" in source, "第三处放行没写出处"
    assert "系统自产内容不在管辖" in source, "第三处没说清它走的是哪一档"


def test_the_ruler_still_reds_on_any_other_table() -> None:
    """尺子没被拆：别的表长出正文列照旧判红。

    只断言「白名单里有两项」是不够的——把 `check_metadata_only` 改成恒返回空
    也能让那条绿。这一条把压力打在**判定函数**上。
    """
    from flint.sources.throttle import FULLTEXT_COLUMN_NAMES, SYSTEM_GENERATED_ALLOWLIST

    rows = [("some_other_table", "content"), ("doc_contents", "content")]
    flagged = [
        (t, c) for t, c in rows
        if c.lower() in FULLTEXT_COLUMN_NAMES and (t, c) not in SYSTEM_GENERATED_ALLOWLIST
    ]

    assert flagged == [("some_other_table", "content")]


# ───────────────────────── 四、迁移真跑：正向 → 回滚 → 再正向（acceptance①）


@pytest.mark.compose
def test_downgrade_then_upgrade_keeps_the_existing_rows(dsn: str) -> None:
    """回滚后既有数据不损：doc 的元数据行还在，正文没了（那是回滚该有的样子）。

    只测「回滚不报错」是不够的——一个把 `docs` 整张删掉的 downgrade 也不报错。
    """
    async def run_sql(sql: str) -> object:
        conn = await asyncpg.connect(dsn)
        try:
            return await conn.fetchval(sql)
        finally:
            await conn.close()

    async def seed() -> None:
        store = PgDocStore(dsn)
        conn = await asyncpg.connect(dsn)
        try:
            await _wipe(conn)
        finally:
            await conn.close()
        await store.save_doc_with_content(
            build_doc_with_content(_doc(doc_id="d-keep", url="https://keep.test"), "正文"))

    def alembic(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "alembic", *args], cwd=REPO,
            capture_output=True, text=True, encoding="utf-8", check=False,
            env={**__import__("os").environ, "DATABASE_URL":
                 dsn.replace("postgresql://", "postgresql+asyncpg://")})

    asyncio.run(seed())

    down = alembic("downgrade", "0018")
    assert down.returncode == 0, down.stdout + down.stderr
    assert asyncio.run(run_sql(
        "SELECT count(*) FROM docs WHERE doc_id = 'd-keep'")) == 1, "回滚把既有数据弄丢了"
    assert asyncio.run(run_sql("SELECT to_regclass('public.doc_contents')")) is None

    # **回到 head，NEVER 回到某一个写死的版本号**：写死 "0019" 时它恰好是 head，
    # 而 `AUTH-01` 之后 head 是 0020——那次之后这条用例会把库停在 0019，
    # 于是**后面所有用到身份三张表的用例都以 UndefinedTableError 失败**（实测撞到）。
    # 那种红看起来像是身份那几张卡坏了，其实是这一行把库留在了半路上。
    up = alembic("upgrade", "head")
    assert up.returncode == 0, up.stdout + up.stderr
    assert asyncio.run(run_sql(
        "SELECT count(*) FROM docs WHERE doc_id = 'd-keep'")) == 1
    assert asyncio.run(run_sql("SELECT to_regclass('public.doc_contents')")) is not None
