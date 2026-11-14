"""主题子系统 repo（TS-001，冻结件 Origin/TopicSeed/Topic/Project）。

save→load 保真；照冻结类型只读消费冻结件、NEVER 改契约。owner(Principal)/payload/
why_now(WhyNow)/keyword_mapping/topic_ids 均经 jsonb；topics.embedding vector(1024)
以 pgvector 文本形往返。
"""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Literal, cast

import asyncpg

from flint.domain.models import (
    JSON,
    Origin,
    OriginKind,
    Principal,
    Project,
    Topic,
    TopicSeed,
    Vector,
    WhyNow,
    WhyNowEvidence,
)


def _principal_json(p: Principal) -> str:
    return json.dumps({"kind": p.kind, "id": p.id}, ensure_ascii=False)


def _principal(raw: str) -> Principal:
    d = json.loads(raw)
    return Principal(kind=cast('Literal["user", "org"]', d["kind"]), id=str(d["id"]))


def _vec_text(v: Vector) -> str:
    return "[" + ",".join(repr(float(x)) for x in v) + "]"


def _vec(raw: object) -> Vector:
    text = raw if isinstance(raw, str) else str(raw)
    return [float(x) for x in json.loads(text)]


def _whynow_json(w: WhyNow) -> str:
    return json.dumps({
        "claim": w.claim,
        "evidences": [
            {"event": e.event, "event_date": e.event_date.isoformat(),
             "citation_id": e.citation_id}
            for e in w.evidences
        ],
        "speculative": w.speculative,
    }, ensure_ascii=False)


def _whynow(raw: str) -> WhyNow:
    d = json.loads(raw)
    return WhyNow(
        claim=str(d["claim"]),
        evidences=[
            WhyNowEvidence(event=str(e["event"]),
                          event_date=date.fromisoformat(str(e["event_date"])),
                          citation_id=str(e["citation_id"]))
            for e in d["evidences"]
        ],
        speculative=bool(d["speculative"]),
    )


class PgOriginStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def save(self, origin: Origin) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(
                "INSERT INTO origins (origin_id, kind, owner, payload, created_at) "
                "VALUES ($1, $2, $3::jsonb, $4::jsonb, $5)",
                origin.origin_id, origin.kind, _principal_json(origin.owner),
                json.dumps(origin.payload, ensure_ascii=False), origin.created_at)
        finally:
            await conn.close()

    async def load(self, origin_id: str) -> Origin:
        conn = await asyncpg.connect(self._dsn)
        try:
            row = await conn.fetchrow(
                "SELECT * FROM origins WHERE origin_id = $1", origin_id)
        finally:
            await conn.close()
        if row is None:
            raise KeyError(origin_id)
        return Origin(
            origin_id=str(row["origin_id"]),
            kind=cast("OriginKind", row["kind"]),
            owner=_principal(row["owner"]),
            payload=cast("JSON", json.loads(row["payload"])),
            created_at=cast("datetime", row["created_at"]))


class PgTopicSeedStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def save(self, seed: TopicSeed) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(
                "INSERT INTO topic_seeds (seed_id, origin_id, keywords, hypothesis, "
                "context_text) VALUES ($1, $2, $3::jsonb, $4, $5)",
                seed.seed_id, seed.origin_id,
                json.dumps(seed.keywords, ensure_ascii=False),
                seed.hypothesis, seed.context_text)
        finally:
            await conn.close()

    async def load(self, seed_id: str) -> TopicSeed:
        conn = await asyncpg.connect(self._dsn)
        try:
            row = await conn.fetchrow(
                "SELECT * FROM topic_seeds WHERE seed_id = $1", seed_id)
        finally:
            await conn.close()
        if row is None:
            raise KeyError(seed_id)
        return TopicSeed(
            seed_id=str(row["seed_id"]), origin_id=str(row["origin_id"]),
            keywords=[str(k) for k in json.loads(row["keywords"])],
            hypothesis=None if row["hypothesis"] is None else str(row["hypothesis"]),
            context_text=str(row["context_text"]))


class PgTopicStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def save(self, topic: Topic) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(
                "INSERT INTO topics (topic_id, seed_id, one_liner, target_user_tag, "
                "form_factor_tag, why_now, keyword_mapping, embedding) "
                "VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8)",
                topic.topic_id, topic.seed_id, topic.one_liner,
                topic.target_user_tag, topic.form_factor_tag,
                _whynow_json(topic.why_now),
                json.dumps(topic.keyword_mapping, ensure_ascii=False),
                _vec_text(topic.embedding))
        finally:
            await conn.close()

    def _to_topic(self, row: asyncpg.Record) -> Topic:
        return Topic(
            topic_id=str(row["topic_id"]), seed_id=str(row["seed_id"]),
            one_liner=str(row["one_liner"]),
            target_user_tag=str(row["target_user_tag"]),
            form_factor_tag=str(row["form_factor_tag"]),
            why_now=_whynow(row["why_now"]),
            keyword_mapping=cast("JSON", json.loads(row["keyword_mapping"])),
            embedding=_vec(row["embedding"]))

    async def load(self, topic_id: str) -> Topic:
        conn = await asyncpg.connect(self._dsn)
        try:
            row = await conn.fetchrow(
                "SELECT * FROM topics WHERE topic_id = $1", topic_id)
        finally:
            await conn.close()
        if row is None:
            raise KeyError(topic_id)
        return self._to_topic(row)

    async def by_seed(self, seed_id: str) -> list[Topic]:
        conn = await asyncpg.connect(self._dsn)
        try:
            rows = await conn.fetch(
                "SELECT * FROM topics WHERE seed_id = $1 ORDER BY topic_id", seed_id)
        finally:
            await conn.close()
        return [self._to_topic(r) for r in rows]


class ProjectVersionConflict(Exception):
    """写的时候这一行已经被别人改过了。

    ## 形状照 `LedgerVersionConflict` 抄（`LOCK-01` acceptance③）

    冻结件那一个（`contracts/models.py#LedgerVersionConflict`）携带
    `current_version` + 当前事实；`flint/ledger/store.py#_conflict` 把它填满，
    理由是**败者要看得见胜者写了什么**。

    只给一句「版本不符」的话，调用方要重试就得自己再读一次——
    **而它读到的可能已经是第三个人写的了**。

    **NEVER 与 `LedgerVersionConflict` 共用一个类型**：那一个说的是
    「这个项目的**事实账本**变了」（重试策略按来源分派：inject_evidence 自动重放、
    dispute 提示用户、revalidation 整个 job 重跑），这一个说的是
    「这个 **project 行**被别人改了」。共用会让接的人分不清撞的是哪一条。
    """

    def __init__(
        self, current_version: int, current_project: Project | None,
    ) -> None:
        super().__init__(
            f"project version conflict: current version is {current_version}")
        self.current_version = current_version
        self.current_project = current_project


class PgProjectStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def save(
        self, project: Project, *, expected_version: int | None = None,
    ) -> None:
        """建（`expected_version=None`）或更新（带上你读到的那个版本）。

        ## 这里原先是纯 `INSERT`，然后是**没有锁的全行 upsert**

        改前它只能建：唯一的调用方（`flint/api/combo.py`）永远是新建，
        所以那个缺口一直没被执行到。`ENTRY-02` 补选主题的写端点时当场撞上——
        第二次 `save` 直接 500（主键冲突）。**那个改动是对的**：
        `save` 只能建、不能更，是一个潜伏的缺陷。

        **但它没有锁，而 `change_log` 在被覆盖的列里**（`LOCK-01`）：

            A 读（change_log=[e1]） → B 读 → A 写 [e1,e2] → B 写 [e1,e3]
                                                            ↑ e2 无声消失

        改前是「第二次写大声失败（500）」，改后是「并发下静默丢失」——
        **它把一个响亮的错换成了一个安静的错**。本方法把响亮的错找回来。

        ## 两种语义，各自对应一个前提

        - `expected_version=None` = 「**我在新建**」。那一行已经在库里时，
          调用方的前提就是错的 → 抛冲突。**NEVER 静默覆盖**：
          覆盖会把它现有的 `change_log` 整段抹掉。
        - `expected_version=n` = 「我读到的是第 n 版，请在那之上改」。
          条件落在 **SQL 的 `WHERE` 里**，不是先读一次再判断——
          先读后判有竞态窗口（两个写者都读到 1、都判相符、都写），
          而 `WHERE version = $n` 把互斥交给行锁，**那个窗口不存在**。

        ## 为什么不在端点里自己写一条 UPDATE

        那就是把 project 的持久化形状写进第二个地方——本仓反复禁的那件事
        （两处对同一件事的定义迟早分叉，而它们守的是同一条不变量）。

        `created_at` **不在更新列里**（`ENTRY-02` 定下的，本卡不改）：
        它是这条记录的出生时间，一次更新把它改成「现在」，
        等于让这个项目看起来是刚建的。
        """
        # `deliverable_ids` 这一列照冻结件 `Project` 原样落库，但它**不是交付物清单的真相**：
        # 组稿与重写都不回写它。项目有哪些交付物只认 `deliverables` 表
        # （`flint/api/project_overview.py`，`DEC-063` / `OVERVIEW-01`）。NEVER 拿这一列去列产物。
        conn = await asyncpg.connect(self._dsn)
        try:
            if expected_version is None:
                inserted = await conn.execute(
                    "INSERT INTO projects (project_id, owner, origin_id, topic_ids, "
                    "chosen_topic_id, deliverable_ids, change_log, status, "
                    "created_at, version) VALUES ($1, $2::jsonb, $3, $4::jsonb, $5, "
                    "$6::jsonb, $7::jsonb, $8, $9, 1) "
                    "ON CONFLICT (project_id) DO NOTHING",
                    project.project_id, _principal_json(project.owner),
                    project.origin_id,
                    json.dumps(project.topic_ids, ensure_ascii=False),
                    project.chosen_topic_id,
                    json.dumps(project.deliverable_ids, ensure_ascii=False),
                    json.dumps(project.change_log, ensure_ascii=False),
                    project.status, project.created_at)
                if inserted.endswith(" 0"):
                    raise await self._conflict(conn, project.project_id)
                return
            updated = await conn.execute(
                "UPDATE projects SET owner = $2::jsonb, origin_id = $3, "
                "topic_ids = $4::jsonb, chosen_topic_id = $5, "
                "deliverable_ids = $6::jsonb, change_log = $7::jsonb, status = $8, "
                "version = version + 1 "
                "WHERE project_id = $1 AND version = $9",
                project.project_id, _principal_json(project.owner),
                project.origin_id,
                json.dumps(project.topic_ids, ensure_ascii=False),
                project.chosen_topic_id,
                json.dumps(project.deliverable_ids, ensure_ascii=False),
                json.dumps(project.change_log, ensure_ascii=False),
                project.status, expected_version)
            if updated.endswith(" 0"):
                # 一行都没动 = 版本不符（或这一行不在了）。**先读再抛**，
                # 让败者拿到胜者的状态——照 `LedgerStore._conflict` 的形状。
                raise await self._conflict(conn, project.project_id)
        finally:
            await conn.close()

    async def _conflict(
        self, conn: asyncpg.Connection, project_id: str,
    ) -> ProjectVersionConflict:
        row = await conn.fetchrow(
            "SELECT * FROM projects WHERE project_id = $1", project_id)
        if row is None:
            # 这一行不在了（被删）。版本报 0——**NEVER 报一个猜的数**：
            # 0 在本仓的账本口径里就是「还没有版本」（`derive` 里同一个约定）。
            return ProjectVersionConflict(0, None)
        return ProjectVersionConflict(int(row["version"]), self._to_project(row))

    async def load_with_version(self, project_id: str) -> tuple[Project, int]:
        """连版本一起读回来——**要改它就得先知道自己在改第几版**。

        为什么不把版本放进 `Project`：那是冻结件（`S2-1`），加字段禁止。
        版本是**存储层的并发记号**，不是 project 的业务属性——
        它不该出现在任何一个域函数的签名里。
        """
        conn = await asyncpg.connect(self._dsn)
        try:
            row = await conn.fetchrow(
                "SELECT * FROM projects WHERE project_id = $1", project_id)
        finally:
            await conn.close()
        if row is None:
            raise KeyError(project_id)
        return self._to_project(row), int(row["version"])

    def _to_project(self, row: asyncpg.Record) -> Project:
        """行 → `Project`。

        原先这段逐字写在 `load` 里。`LOCK-01` 抽出来，是因为
        `load_with_version` 与 `_conflict` 都要同一份转换——
        **抄三份的话，哪天多一列，只有一处会跟上**，
        而症状是「同一个项目在三条路径上长得不一样」。
        """
        return Project(
            project_id=str(row["project_id"]), owner=_principal(row["owner"]),
            origin_id=str(row["origin_id"]),
            topic_ids=[str(t) for t in json.loads(row["topic_ids"])],
            chosen_topic_id=(None if row["chosen_topic_id"] is None
                             else str(row["chosen_topic_id"])),
            deliverable_ids=[str(d) for d in json.loads(row["deliverable_ids"])],
            change_log=cast("list[JSON]", json.loads(row["change_log"])),
            status=str(row["status"]),
            created_at=cast("datetime", row["created_at"]))

    async def load(self, project_id: str) -> Project:
        conn = await asyncpg.connect(self._dsn)
        try:
            row = await conn.fetchrow(
                "SELECT * FROM projects WHERE project_id = $1", project_id)
        finally:
            await conn.close()
        if row is None:
            raise KeyError(project_id)
        return self._to_project(row)
