from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .contracts import Severity, Violation
from .session_audit import SessionAuditMetadata, SessionAuditWriter


class IncompleteRecoveryRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class IncompleteAuditSession(BaseModel):
    session_id: str
    operation: str
    workstation_id: str
    started_at: str
    update_count: int
    last_recorded_at: str | None = None


class IncompleteRecoveryResult(BaseModel):
    session_id: str
    recovered_at: str
    recovered_by: str
    reason: str
    update_count: int
    last_timestamp_ms: float
    retained_violation_count: int
    retained_step_count: int
    final_status: str = "ABORTED"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


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


def list_incomplete_audit_sessions(
    audit_root: str | Path,
) -> list[IncompleteAuditSession]:
    root = Path(audit_root)
    if not root.exists():
        return []
    output: list[IncompleteAuditSession] = []
    for directory in sorted(root.iterdir()):
        if not directory.is_dir():
            continue
        metadata_path = directory / "metadata.json"
        if not metadata_path.is_file():
            continue
        if (directory / "final.json").exists():
            continue
        try:
            metadata = SessionAuditMetadata.model_validate_json(
                metadata_path.read_text(encoding="utf-8")
            )
            updates = _load_json_lines(
                directory / "updates.jsonl"
            )
        except Exception:
            continue
        last_recorded_at = None
        if updates:
            value = updates[-1].get("recorded_at")
            if value is not None:
                last_recorded_at = str(value)
        output.append(
            IncompleteAuditSession(
                session_id=metadata.session_id,
                operation=metadata.operation,
                workstation_id=metadata.workstation_id,
                started_at=metadata.started_at,
                update_count=len(updates),
                last_recorded_at=last_recorded_at,
            )
        )
    return output


def _collect_recovery_state(
    updates: list[dict[str, Any]],
) -> tuple[
    float,
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    last_timestamp_ms = 0.0
    violations: dict[
        tuple[str, str, str],
        dict[str, Any],
    ] = {}
    steps: dict[str, dict[str, Any]] = {}

    for record in updates:
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        timestamp = payload.get("timestamp_ms")
        if isinstance(timestamp, int | float):
            last_timestamp_ms = max(
                last_timestamp_ms,
                float(timestamp),
            )
        for rule_update in payload.get("rule_updates", []):
            if not isinstance(rule_update, dict):
                continue
            for violation in rule_update.get(
                "new_violations",
                [],
            ):
                if not isinstance(violation, dict):
                    continue
                key = (
                    str(violation.get("rule_id", "")),
                    str(violation.get("step", "")),
                    str(violation.get("event_id", "")),
                )
                if all(key):
                    violations[key] = violation
            for step in rule_update.get("changed_steps", []):
                if not isinstance(step, dict):
                    continue
                code = str(step.get("code", ""))
                if code:
                    steps[code] = step

    return (
        last_timestamp_ms,
        list(violations.values()),
        list(steps.values()),
    )


def recover_incomplete_audit_session(
    session_directory: str | Path,
    request: IncompleteRecoveryRequest,
    *,
    recovered_by: str,
) -> IncompleteRecoveryResult:
    directory = Path(session_directory)
    metadata_path = directory / "metadata.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(
            f"session metadata not found: {directory}"
        )
    if (directory / "final.json").exists():
        raise ValueError(
            f"session is already finalized: {directory.name}"
        )

    metadata = SessionAuditMetadata.model_validate_json(
        metadata_path.read_text(encoding="utf-8")
    )
    updates = _load_json_lines(directory / "updates.jsonl")
    (
        last_timestamp_ms,
        retained_violations,
        retained_steps,
    ) = _collect_recovery_state(updates)

    recovered_at = _utc_now()
    recovery_violation = Violation(
        rule_id="SYSTEM-QUALITY-RECOVERY",
        step="SYSTEM",
        type="SYSTEM_QUALITY",
        severity=Severity.CRITICAL,
        message=(
            "session recovered after unclean termination"
        ),
        event_id=f"recovery-{metadata.session_id}",
        confidence=1.0,
        expected={
            "finalized_cleanly": True,
        },
        actual={
            "reason": request.reason,
            "recovered_by": recovered_by,
            "recovered_at": recovered_at,
            "last_timestamp_ms": last_timestamp_ms,
        },
    )
    final_violations = [
        *retained_violations,
        recovery_violation.model_dump(mode="json"),
    ]
    final_update = {
        "result": {
            "session_id": metadata.session_id,
            "operation": metadata.operation,
            "rule_set_version": metadata.rule_set_version,
            "steps": retained_steps,
            "violations": final_violations,
            "score": 0.0,
            "passed": False,
        },
        "new_violations": [
            recovery_violation.model_dump(mode="json")
        ],
        "changed_steps": [],
    }

    recovery_document = {
        "session_id": metadata.session_id,
        "recovered_at": recovered_at,
        "recovered_by": recovered_by,
        "reason": request.reason,
        "update_count": len(updates),
        "last_timestamp_ms": last_timestamp_ms,
        "recovery_violation": recovery_violation.model_dump(
            mode="json"
        ),
    }
    (directory / "recovery.json").write_text(
        json.dumps(
            recovery_document,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    SessionAuditWriter(directory.parent).finish(
        metadata.session_id,
        final_update,
        status="ABORTED",
    )

    return IncompleteRecoveryResult(
        session_id=metadata.session_id,
        recovered_at=recovered_at,
        recovered_by=recovered_by,
        reason=request.reason,
        update_count=len(updates),
        last_timestamp_ms=last_timestamp_ms,
        retained_violation_count=len(retained_violations),
        retained_step_count=len(retained_steps),
    )
