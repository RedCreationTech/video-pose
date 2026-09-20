from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .session_audit import SessionAuditMetadata
from .session_store import SessionStore
from .violation_review import ViolationReviewRequest


class ReindexResult(BaseModel):
    session_id: str
    update_count: int
    finalized: bool
    review_count: int = 0


def reindex_session(
    session_directory: str | Path,
    repository: SessionStore,
    *,
    replace: bool = True,
) -> ReindexResult:
    directory = Path(session_directory)
    metadata_path = directory / "metadata.json"
    updates_path = directory / "updates.jsonl"
    final_path = directory / "final.json"
    reviews_path = directory / "reviews.jsonl"

    metadata_payload = json.loads(
        metadata_path.read_text(encoding="utf-8")
    )
    audit = SessionAuditMetadata.model_validate(metadata_payload)

    existing = repository.get_session(audit.session_id)
    if existing is not None:
        if not replace:
            raise ValueError(
                f"session already exists: {audit.session_id}"
            )
        delete_method = getattr(repository, "delete_session", None)
        if not callable(delete_method):
            raise ValueError(
                "repository does not support replacing existing sessions"
            )
        delete_method(audit.session_id)

    repository.start_session(audit)
    update_count = 0
    if updates_path.exists():
        with updates_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                record = json.loads(stripped)
                payload = record.get("payload")
                if isinstance(payload, dict):
                    repository.record_update(
                        audit.session_id,
                        payload,
                    )
                    update_count += 1

    finalized = False
    if final_path.exists():
        final_document: dict[str, Any] = json.loads(
            final_path.read_text(encoding="utf-8")
        )
        final_payload = final_document.get("result")
        if isinstance(final_payload, dict):
            repository.finalize(
                audit.session_id,
                final_payload,
                status=str(
                    final_document.get("status", "COMPLETED")
                ),
            )
            finalized = True

    review_count = 0
    if reviews_path.exists():
        with reviews_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                record = json.loads(stripped)
                payload = record.get("payload")
                if not isinstance(payload, dict):
                    continue
                review_payload = payload.get("review")
                if not isinstance(review_payload, dict):
                    continue
                review_method = getattr(
                    repository,
                    "review_violation_by_identity",
                    None,
                )
                if not callable(review_method):
                    continue
                review_method(
                    audit.session_id,
                    rule_id=str(payload.get("rule_id", "")),
                    step_code=str(payload.get("step_code", "")),
                    event_id=str(payload.get("event_id", "")),
                    review=ViolationReviewRequest.model_validate(
                        review_payload
                    ),
                    reviewer=str(payload.get("reviewer", "")),
                    reviewed_at=(
                        datetime.fromisoformat(payload["reviewed_at"])
                        if payload.get("reviewed_at")
                        else None
                    ),
                )
                review_count += 1

    return ReindexResult(
        session_id=audit.session_id,
        update_count=update_count,
        finalized=finalized,
        review_count=review_count,
    )


def reindex_audit_root(
    audit_root: str | Path,
    repository: SessionStore,
    *,
    session_id: str | None = None,
) -> list[ReindexResult]:
    root = Path(audit_root)
    if session_id is not None:
        return [
            reindex_session(
                root / session_id,
                repository,
            )
        ]

    results: list[ReindexResult] = []
    for directory in sorted(root.iterdir()):
        if not directory.is_dir():
            continue
        if not (directory / "metadata.json").exists():
            continue
        results.append(
            reindex_session(
                directory,
                repository,
            )
        )
    return results
