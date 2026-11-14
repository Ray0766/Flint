"""Deliverable 版本与 GenerationRecord 落库（M3-010，冻结件对应表 0009/0012）。

- new_version：再生成出新 Deliverable（版本 +1、supersedes 指旧版）；旧版
  行不动（可回读，D1-b 版本语义）。
- GenerationRecord 十四字段全量往返（optin / alignment_rate /
  structured_output_failures 进账位在列）。
"""
from __future__ import annotations

import json
from dataclasses import replace
from typing import cast

import asyncpg

from flint.domain.models import (
    Deliverable,
    DeliverableType,
    GenerationRecord,
    Staleness,
    StaleReason,
)


class PgDeliverableStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def save_generation_record(self, record: GenerationRecord) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(
                "INSERT INTO generation_records (record_id, deliverable_id, job_id, "
                "prompt_version, model, params, retrieval_snapshot_id, "
                "ledger_version, pricebook_version, user_evidence_verdict_optin, "
                "ts, cost, alignment_rate, structured_output_failures) VALUES "
                "($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11, $12, $13, $14)",
                record.record_id, record.deliverable_id, record.job_id,
                record.prompt_version, record.model,
                json.dumps(record.params, ensure_ascii=False),
                record.retrieval_snapshot_id, record.ledger_version,
                record.pricebook_version, record.user_evidence_verdict_optin,
                record.ts, record.cost, record.alignment_rate,
                record.structured_output_failures,
            )
        finally:
            await conn.close()

    async def load_generation_record(self, record_id: str) -> GenerationRecord:
        conn = await asyncpg.connect(self._dsn)
        try:
            row = await conn.fetchrow(
                "SELECT * FROM generation_records WHERE record_id = $1", record_id
            )
        finally:
            await conn.close()
        if row is None:
            raise KeyError(f"unknown generation record: {record_id}")
        return GenerationRecord(
            record_id=row["record_id"],
            deliverable_id=row["deliverable_id"],
            job_id=row["job_id"],
            prompt_version=row["prompt_version"],
            model=row["model"],
            params=json.loads(row["params"]),
            retrieval_snapshot_id=row["retrieval_snapshot_id"],
            ledger_version=row["ledger_version"],
            pricebook_version=row["pricebook_version"],
            user_evidence_verdict_optin=row["user_evidence_verdict_optin"],
            ts=row["ts"],
            cost=row["cost"],
            alignment_rate=row["alignment_rate"],
            structured_output_failures=row["structured_output_failures"],
        )

    async def save_deliverable(self, deliverable: Deliverable) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(
                "INSERT INTO deliverables (deliverable_id, project_id, type, "
                "version, supersedes, inputs, ledger_version, "
                "generation_record_id, stale_reasons, created_at, reproducible) "
                "VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9::jsonb, $10, $11)",
                deliverable.deliverable_id, deliverable.project_id,
                deliverable.type, deliverable.version, deliverable.supersedes,
                json.dumps(deliverable.inputs, ensure_ascii=False),
                deliverable.ledger_version, deliverable.generation_record_id,
                json.dumps(
                    [
                        {
                            "reason": s.reason, "detail": s.detail,
                            "detected_at": s.detected_at.isoformat(),
                            "revalidation_report_id": s.revalidation_report_id,
                        }
                        for s in deliverable.stale_reasons
                    ],
                    ensure_ascii=False,
                ),
                deliverable.created_at, deliverable.reproducible,
            )
        finally:
            await conn.close()

    async def load_deliverable(self, deliverable_id: str) -> Deliverable:
        conn = await asyncpg.connect(self._dsn)
        try:
            row = await conn.fetchrow(
                "SELECT * FROM deliverables WHERE deliverable_id = $1",
                deliverable_id,
            )
        finally:
            await conn.close()
        if row is None:
            raise KeyError(f"unknown deliverable: {deliverable_id}")
        from datetime import datetime

        return Deliverable(
            deliverable_id=row["deliverable_id"],
            project_id=row["project_id"],
            type=cast(DeliverableType, row["type"]),
            version=row["version"],
            supersedes=row["supersedes"],
            inputs=[str(i) for i in json.loads(row["inputs"])],
            ledger_version=row["ledger_version"],
            generation_record_id=row["generation_record_id"],
            stale_reasons=[
                Staleness(
                    reason=cast(StaleReason, s["reason"]),
                    detail=str(s["detail"]),
                    detected_at=datetime.fromisoformat(s["detected_at"]),
                    revalidation_report_id=s["revalidation_report_id"],
                )
                for s in json.loads(row["stale_reasons"])
            ],
            created_at=row["created_at"],
            reproducible=row["reproducible"],
        )

    async def new_version(
        self,
        current: Deliverable,
        new_deliverable_id: str,
        generation_record_id: str,
    ) -> Deliverable:
        """再生成：版本 +1、supersedes 指旧版；旧版行保持可回读。"""
        bumped = replace(
            current,
            deliverable_id=new_deliverable_id,
            version=current.version + 1,
            supersedes=current.deliverable_id,
            generation_record_id=generation_record_id,
        )
        await self.save_deliverable(bumped)
        return bumped
