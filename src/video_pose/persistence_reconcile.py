from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .reindex import ReindexResult, reindex_session
from .session_audit import SessionAuditMetadata
from .session_store import SessionStore


class SessionConsistencyReport(BaseModel):
    session_id: str
    finalized: bool
    consistent: bool
    reasons: list[str] = Field(default_factory=list)
    expected_actions: int = 0
    actual_actions: int = 0
    expected_violations: int = 0
    actual_violations: int = 0
    expected_steps: int = 0
    actual_steps: int = 0
    expected_reviews: int = 0
    actual_reviews: int = 0


class ReconcileSessionResult(BaseModel):
    session_id: str
    action: str
    consistency: SessionConsistencyReport | None = None
    reindex: ReindexResult | None = None
    error: str | None = None


class ReconcileRootReport(BaseModel):
    repaired_count: int
    skipped_count: int
    failed_count: int
    incomplete_count: int
    sessions: list[ReconcileSessionResult]


def _load_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    output: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if isinstance(payload, dict):
                output.append(payload)
    return output


def _violation_key(payload: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(payload.get("rule_id", "")),
        str(payload.get("step", payload.get("step_code", ""))),
        str(payload.get("event_id", "")),
    )


def _audit_expectations(
    directory: Path,
) -> tuple[
    SessionAuditMetadata,
    bool,
    str | None,
    set[str],
    set[tuple[str, str, str]],
    set[str],
    dict[tuple[str, str, str], str],
    float | None,
    bool | None,
]:
    metadata = SessionAuditMetadata.model_validate_json(
        (directory / "metadata.json").read_text(encoding="utf-8")
    )
    action_ids: set[str] = set()
    violations: set[tuple[str, str, str]] = set()
    steps: set[str] = set()

    for record in _load_json_lines(directory / "updates.jsonl"):
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        for action in payload.get("actions", []):
            if isinstance(action, dict):
                event_id = str(action.get("event_id", ""))
                if event_id:
                    action_ids.add(event_id)
        for rule_update in payload.get("rule_updates", []):
            if not isinstance(rule_update, dict):
                continue
            for violation in rule_update.get("new_violations", []):
                if isinstance(violation, dict):
                    key = _violation_key(violation)
                    if all(key):
                        violations.add(key)
            for step in rule_update.get("changed_steps", []):
                if isinstance(step, dict):
                    code = str(step.get("code", ""))
                    if code:
                        steps.add(code)

    final_path = directory / "final.json"
    finalized = final_path.exists()
    final_status: str | None = None
    final_score: float | None = None
    final_passed: bool | None = None
    if finalized:
        final_document = json.loads(
            final_path.read_text(encoding="utf-8")
        )
        final_status = str(
            final_document.get("status", "COMPLETED")
        )
        update = final_document.get("result")
        if isinstance(update, dict):
            result = update.get("result")
            if isinstance(result, dict):
                for violation in result.get("violations", []):
                    if isinstance(violation, dict):
                        key = _violation_key(violation)
                        if all(key):
                            violations.add(key)
                for step in result.get("steps", []):
                    if isinstance(step, dict):
                        code = str(step.get("code", ""))
                        if code:
                            steps.add(code)
                raw_score = result.get("score")
                if raw_score is not None:
                    final_score = float(raw_score)
                raw_passed = result.get("passed")
                if raw_passed is not None:
                    final_passed = bool(raw_passed)

    reviews: dict[tuple[str, str, str], str] = {}
    for record in _load_json_lines(directory / "reviews.jsonl"):
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        review = payload.get("review")
        if not isinstance(review, dict):
            continue
        key = (
            str(payload.get("rule_id", "")),
            str(payload.get("step_code", "")),
            str(payload.get("event_id", "")),
        )
        decision = str(review.get("decision", ""))
        if all(key) and decision:
            reviews[key] = decision

    return (
        metadata,
        finalized,
        final_status,
        action_ids,
        violations,
        steps,
        reviews,
        final_score,
        final_passed,
    )


def inspect_session_consistency(
    session_directory: str | Path,
    repository: SessionStore,
) -> SessionConsistencyReport:
    directory = Path(session_directory)
    (
        metadata,
        finalized,
        final_status,
        expected_actions,
        expected_violations,
        expected_steps,
        expected_reviews,
        final_score,
        final_passed,
    ) = _audit_expectations(directory)

    stored = repository.get_session(metadata.session_id)
    if stored is None:
        return SessionConsistencyReport(
            session_id=metadata.session_id,
            finalized=finalized,
            consistent=False,
            reasons=["session missing from query store"],
            expected_actions=len(expected_actions),
            expected_violations=len(expected_violations),
            expected_steps=len(expected_steps),
            expected_reviews=len(expected_reviews),
        )

    actual_actions = {
        str(item.get("event_id", ""))
        for item in stored.get("actions", [])
        if item.get("event_id")
    }
    actual_violations = {
        (
            str(item.get("rule_id", "")),
            str(item.get("step_code", "")),
            str(item.get("event_id", "")),
        )
        for item in stored.get("violations", [])
        if item.get("rule_id")
        and item.get("step_code")
        and item.get("event_id")
    }
    actual_steps = {
        str(item.get("step_code", ""))
        for item in stored.get("steps", [])
        if item.get("step_code")
    }
    actual_reviews = {
        (
            str(item.get("rule_id", "")),
            str(item.get("step_code", "")),
            str(item.get("event_id", "")),
        ): str(item.get("review_status", ""))
        for item in stored.get("violations", [])
        if str(item.get("review_status", "")) != "UNREVIEWED"
    }

    reasons: list[str] = []
    if actual_actions != expected_actions:
        reasons.append("action identity set mismatch")
    if actual_violations != expected_violations:
        reasons.append("violation identity set mismatch")
    if actual_steps != expected_steps:
        reasons.append("step identity set mismatch")
    if actual_reviews != expected_reviews:
        reasons.append("review state mismatch")

    session = stored.get("session", {})
    if finalized and final_status is not None:
        if str(session.get("status", "")) != final_status:
            reasons.append("final status mismatch")
        actual_score = session.get("final_score")
        if (
            final_score is not None
            and (
                actual_score is None
                or abs(float(actual_score) - final_score) > 1e-9
            )
        ):
            reasons.append("final score mismatch")
        actual_passed = session.get("passed")
        if (
            final_passed is not None
            and bool(actual_passed) != final_passed
        ):
            reasons.append("final passed mismatch")

    return SessionConsistencyReport(
        session_id=metadata.session_id,
        finalized=finalized,
        consistent=not reasons,
        reasons=reasons,
        expected_actions=len(expected_actions),
        actual_actions=len(actual_actions),
        expected_violations=len(expected_violations),
        actual_violations=len(actual_violations),
        expected_steps=len(expected_steps),
        actual_steps=len(actual_steps),
        expected_reviews=len(expected_reviews),
        actual_reviews=len(actual_reviews),
    )


def reconcile_session(
    session_directory: str | Path,
    repository: SessionStore,
    *,
    include_incomplete: bool = False,
) -> ReconcileSessionResult:
    directory = Path(session_directory)
    try:
        consistency = inspect_session_consistency(
            directory,
            repository,
        )
        if not consistency.finalized and not include_incomplete:
            return ReconcileSessionResult(
                session_id=consistency.session_id,
                action="INCOMPLETE",
                consistency=consistency,
            )
        if consistency.consistent:
            return ReconcileSessionResult(
                session_id=consistency.session_id,
                action="SKIPPED",
                consistency=consistency,
            )
        result = reindex_session(
            directory,
            repository,
            replace=True,
        )
        verified = inspect_session_consistency(
            directory,
            repository,
        )
        if not verified.consistent:
            raise RuntimeError(
                "session remains inconsistent after reindex: "
                + ", ".join(verified.reasons)
            )
        return ReconcileSessionResult(
            session_id=consistency.session_id,
            action="REPAIRED",
            consistency=verified,
            reindex=result,
        )
    except Exception as exc:
        session_id = directory.name
        return ReconcileSessionResult(
            session_id=session_id,
            action="FAILED",
            error=str(exc),
        )


def reconcile_audit_root(
    audit_root: str | Path,
    repository: SessionStore,
    *,
    include_incomplete: bool = False,
) -> ReconcileRootReport:
    root = Path(audit_root)
    if not root.exists():
        return ReconcileRootReport(
            repaired_count=0,
            skipped_count=0,
            failed_count=0,
            incomplete_count=0,
            sessions=[],
        )

    sessions: list[ReconcileSessionResult] = []
    for directory in sorted(root.iterdir()):
        if not directory.is_dir():
            continue
        if not (directory / "metadata.json").is_file():
            continue
        sessions.append(
            reconcile_session(
                directory,
                repository,
                include_incomplete=include_incomplete,
            )
        )

    return ReconcileRootReport(
        repaired_count=sum(
            item.action == "REPAIRED" for item in sessions
        ),
        skipped_count=sum(
            item.action == "SKIPPED" for item in sessions
        ),
        failed_count=sum(
            item.action == "FAILED" for item in sessions
        ),
        incomplete_count=sum(
            item.action == "INCOMPLETE" for item in sessions
        ),
        sessions=sessions,
    )
