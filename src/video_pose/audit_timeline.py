from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .session_audit import SessionAuditMetadata


class SessionTimelineEvent(BaseModel):
    event_id: str
    timestamp: str
    type: str
    severity: str | None = None
    title: str
    detail: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class SessionTimeline(BaseModel):
    session_id: str
    events: list[SessionTimelineEvent]


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    output: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                output.append(payload)
    return output


def _timestamp_sort_key(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)


def _object_class(action: dict[str, Any]) -> str | None:
    payload = action.get("object")
    if not isinstance(payload, dict):
        return None
    value = payload.get("class")
    return str(value) if value is not None else None


def build_session_timeline(
    session_directory: str | Path,
) -> SessionTimeline:
    directory = Path(session_directory)
    metadata_path = directory / "metadata.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(
            f"session metadata not found: {directory}"
        )
    metadata = SessionAuditMetadata.model_validate_json(
        metadata_path.read_text(encoding="utf-8")
    )
    events: list[SessionTimelineEvent] = [
        SessionTimelineEvent(
            event_id="session-started",
            timestamp=metadata.started_at,
            type="SESSION_STARTED",
            title="Session started",
            detail=(
                f"{metadata.operation} @ "
                f"{metadata.workstation_id}"
            ),
            data={
                "operator_id": metadata.operator_id,
                "trace_id": metadata.trace_id,
                "release_fingerprint": (
                    metadata.release_fingerprint
                ),
            },
        )
    ]

    update_index = 0
    for record in _read_jsonl(directory / "updates.jsonl"):
        recorded_at = str(
            record.get("recorded_at", metadata.started_at)
        )
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        update_index += 1

        for action_index, action in enumerate(
            payload.get("actions", [])
        ):
            if not isinstance(action, dict):
                continue
            action_name = str(
                action.get("action", "ACTION")
            )
            event_id = str(
                action.get(
                    "event_id",
                    f"{update_index}-{action_index}",
                )
            )
            events.append(
                SessionTimelineEvent(
                    event_id=f"action:{event_id}",
                    timestamp=recorded_at,
                    type="ACTION",
                    title=action_name,
                    detail=(
                        f"{_object_class(action) or '-'} "
                        f"{action.get('source_zone') or ''} "
                        f"→ {action.get('target_zone') or ''}"
                    ).strip(),
                    data={
                        "event_id": event_id,
                        "sequence": action.get("sequence"),
                        "object_class": _object_class(action),
                        "source_zone": action.get(
                            "source_zone"
                        ),
                        "target_zone": action.get(
                            "target_zone"
                        ),
                        "confidence": action.get("confidence"),
                    },
                )
            )

        for rule_index, rule_update in enumerate(
            payload.get("rule_updates", [])
        ):
            if not isinstance(rule_update, dict):
                continue
            for violation_index, violation in enumerate(
                rule_update.get("new_violations", [])
            ):
                if not isinstance(violation, dict):
                    continue
                rule_id = str(
                    violation.get("rule_id", "VIOLATION")
                )
                violation_event_id = str(
                    violation.get(
                        "event_id",
                        (
                            f"{update_index}-{rule_index}-"
                            f"{violation_index}"
                        ),
                    )
                )
                severity = str(
                    violation.get("severity", "")
                ) or None
                events.append(
                    SessionTimelineEvent(
                        event_id=(
                            f"violation:{rule_id}:"
                            f"{violation_event_id}"
                        ),
                        timestamp=recorded_at,
                        type="VIOLATION",
                        severity=severity,
                        title=rule_id,
                        detail=str(
                            violation.get(
                                "message",
                                violation.get("type", ""),
                            )
                        ),
                        data={
                            "rule_id": rule_id,
                            "step_code": violation.get(
                                "step"
                            ),
                            "violation_type": violation.get(
                                "type"
                            ),
                            "event_id": violation_event_id,
                            "confidence": violation.get(
                                "confidence"
                            ),
                        },
                    )
                )

            for step_index, step in enumerate(
                rule_update.get("changed_steps", [])
            ):
                if not isinstance(step, dict):
                    continue
                code = str(
                    step.get(
                        "code",
                        f"step-{update_index}-{step_index}",
                    )
                )
                state = str(step.get("state", ""))
                events.append(
                    SessionTimelineEvent(
                        event_id=(
                            f"step:{code}:"
                            f"{update_index}:{step_index}"
                        ),
                        timestamp=recorded_at,
                        type="STEP",
                        title=f"{code} → {state}",
                        detail=str(
                            step.get("event_id", "")
                        ),
                        data={
                            "step_code": code,
                            "state": state,
                            "event_id": step.get("event_id"),
                            "confidence": step.get(
                                "confidence"
                            ),
                        },
                    )
                )

        evidence = payload.get("evidence_scheduled")
        if isinstance(evidence, dict):
            evidence_id = str(
                evidence.get(
                    "evidence_id",
                    f"evidence-{update_index}",
                )
            )
            events.append(
                SessionTimelineEvent(
                    event_id=f"evidence:{evidence_id}",
                    timestamp=recorded_at,
                    type="EVIDENCE",
                    title="Evidence scheduled",
                    detail=evidence_id,
                    data={
                        "evidence_id": evidence_id,
                        "rule_id": evidence.get("rule_id"),
                        "step_code": evidence.get("step"),
                        "event_id": evidence.get("event_id"),
                    },
                )
            )

    for review_index, record in enumerate(
        _read_jsonl(directory / "reviews.jsonl")
    ):
        recorded_at = str(
            record.get("recorded_at", metadata.started_at)
        )
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        review = payload.get("review")
        if not isinstance(review, dict):
            continue
        decision = str(
            review.get("decision", "REVIEWED")
        )
        event_id = str(payload.get("event_id", ""))
        events.append(
            SessionTimelineEvent(
                event_id=(
                    f"review:{event_id or review_index}:"
                    f"{review_index}"
                ),
                timestamp=str(
                    payload.get("reviewed_at", recorded_at)
                ),
                type="REVIEW",
                title=f"Review {decision}",
                detail=(
                    f"{payload.get('rule_id', '')} by "
                    f"{payload.get('reviewer', '')}"
                ).strip(),
                data={
                    "decision": decision,
                    "rule_id": payload.get("rule_id"),
                    "step_code": payload.get("step_code"),
                    "event_id": event_id,
                    "reviewer": payload.get("reviewer"),
                    "reason_code": review.get("reason_code"),
                    "comment": review.get("comment"),
                },
            )
        )

    recovery = _read_json(directory / "recovery.json")
    if recovery is not None:
        events.append(
            SessionTimelineEvent(
                event_id="session-recovery",
                timestamp=str(
                    recovery.get(
                        "recovered_at",
                        metadata.started_at,
                    )
                ),
                type="RECOVERY",
                severity="CRITICAL",
                title="Session recovered as ABORTED",
                detail=str(recovery.get("reason", "")),
                data={
                    "recovered_by": recovery.get(
                        "recovered_by"
                    ),
                    "update_count": recovery.get(
                        "update_count"
                    ),
                    "last_timestamp_ms": recovery.get(
                        "last_timestamp_ms"
                    ),
                },
            )
        )

    final = _read_json(directory / "final.json")
    if final is not None:
        status = str(final.get("status", "COMPLETED"))
        result_wrapper = final.get("result")
        passed = None
        score = None
        if isinstance(result_wrapper, dict):
            result = result_wrapper.get("result")
            if isinstance(result, dict):
                passed = result.get("passed")
                score = result.get("score")
        events.append(
            SessionTimelineEvent(
                event_id="session-finished",
                timestamp=str(
                    final.get("ended_at", metadata.started_at)
                ),
                type="SESSION_FINISHED",
                severity=(
                    "CRITICAL"
                    if status == "ABORTED"
                    else None
                ),
                title=f"Session {status}",
                detail=f"passed={passed}, score={score}",
                data={
                    "status": status,
                    "passed": passed,
                    "score": score,
                },
            )
        )

    events.sort(
        key=lambda item: _timestamp_sort_key(item.timestamp)
    )
    return SessionTimeline(
        session_id=metadata.session_id,
        events=events,
    )
