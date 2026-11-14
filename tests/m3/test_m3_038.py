"""M3-038 acceptance tests: private evidence export marks (audit 5).

Acceptance (tasks.json M3-038):
  - private evidence exported with the mandatory "user-supplied, externally
    unverifiable" mark
  - links never leave the export (no private url in the artifact)
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from flint.domain.models import Doc
from flint.render.private_marks import PRIVATE_MARK, citation_section

FETCHED = datetime(2026, 7, 29, tzinfo=UTC).isoformat()


def doc(doc_id: str, access: str, url: str) -> Doc:
    return Doc(
        doc_id=doc_id, source_id="crossref" if access == "public" else "user_upload",
        kind="paper" if access == "public" else "user_upload",
        title=f"title-{doc_id}", url=url, published_at=date(2026, 1, 1),
        meta={"fetched_at": FETCHED},
        origin="retrieved" if access == "public" else "user_provided",
        access=access,  # type: ignore[arg-type]
    )


def test_private_marked_and_link_suppressed() -> None:
    docs = [
        doc("d-pub", "public", "https://paper.example/1"),
        doc("d-priv", "private", "user://ue-1"),
    ]
    section = citation_section(docs)
    assert "https://paper.example/1" in section, "public link kept"
    assert "user://ue-1" not in section, "private link never leaves the export"
    assert PRIVATE_MARK in section
    assert "title-d-priv" in section, "private evidence still listed, marked"


def test_all_public_no_mark() -> None:
    section = citation_section([doc("d-1", "public", "https://a/1")])
    assert PRIVATE_MARK not in section
