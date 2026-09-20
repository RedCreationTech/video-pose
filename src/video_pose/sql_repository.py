from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Connection, Engine

from .session_audit import SessionAuditMetadata
from .violation_review import ViolationReviewRequest

metadata = MetaData()

sessions = Table(
    "vp_sessions",
    metadata,
    Column("session_id", String(128), primary_key=True),
    Column("operator_id", String(128)),
    Column("operation", String(255), nullable=False),
    Column("workstation_id", String(128), nullable=False),
    Column("status", String(32), nullable=False),
    Column("rule_set_version", Integer, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("ended_at", DateTime(timezone=True)),
    Column("final_score", Float),
    Column("passed", Boolean),
    Column("metadata_json", JSON, nullable=False),
)

actions = Table(
    "vp_actions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "session_id",
        String(128),
        ForeignKey("vp_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("event_id", String(128), nullable=False),
    Column("sequence", BigInteger),
    Column("action", String(64), nullable=False),
    Column("object_class", String(128)),
    Column("source_zone", String(128)),
    Column("target_zone", String(128)),
    Column("started_at_ms", BigInteger),
    Column("ended_at_ms", BigInteger),
    Column("confidence", Float),
    Column(
        "review_status",
        String(32),
        nullable=False,
        default="UNREVIEWED",
        server_default="UNREVIEWED",
    ),
    Column("reviewed_by", String(128)),
    Column("reviewed_at", DateTime(timezone=True)),
    Column("review_reason_code", String(128)),
    Column("review_comment", String(2000)),
    Column("payload_json", JSON, nullable=False),
    UniqueConstraint(
        "session_id",
        "event_id",
        name="uq_vp_actions_session_event",
    ),
)

violations = Table(
    "vp_violations",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "session_id",
        String(128),
        ForeignKey("vp_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("rule_id", String(128), nullable=False),
    Column("step_code", String(128), nullable=False),
    Column("violation_type", String(64), nullable=False),
    Column("severity", String(32), nullable=False),
    Column("event_id", String(128), nullable=False),
    Column("confidence", Float),
    Column("payload_json", JSON, nullable=False),
    UniqueConstraint(
        "session_id",
        "rule_id",
        "step_code",
        "event_id",
        name="uq_vp_violations_identity",
    ),
)

steps = Table(
    "vp_steps",
    metadata,
    Column(
        "session_id",
        String(128),
        ForeignKey("vp_sessions.session_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("step_code", String(128), primary_key=True),
    Column("state", String(32), nullable=False),
    Column("event_id", String(128)),
    Column("confidence", Float),
    Column("payload_json", JSON, nullable=False),
)


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


class SQLAlchemySessionRepository:
    """Portable query repository for SQLite PoC and PostgreSQL production."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.engine: Engine = create_engine(
            database_url,
            pool_pre_ping=True,
        )

    def create_schema(self) -> None:
        metadata.create_all(self.engine)

    def start_session(self, audit: SessionAuditMetadata) -> None:
        payload = audit.model_dump(mode="json")
        with self.engine.begin() as connection:
            connection.execute(
                insert(sessions).values(
                    session_id=audit.session_id,
                    operator_id=audit.operator_id,
                    operation=audit.operation,
                    workstation_id=audit.workstation_id,
                    status="RUNNING",
                    rule_set_version=audit.rule_set_version,
                    started_at=_parse_datetime(audit.started_at),
                    metadata_json=payload,
                )
            )

    def record_update(
        self,
        session_id: str,
        payload: dict[str, Any],
    ) -> None:
        with self.engine.begin() as connection:
            for action_payload in payload.get("actions", []):
                if isinstance(action_payload, dict):
                    self._insert_action(
                        connection,
                        session_id,
                        action_payload,
                    )

            for rule_update in payload.get("rule_updates", []):
                if not isinstance(rule_update, dict):
                    continue
                for violation_payload in rule_update.get(
                    "new_violations",
                    [],
                ):
                    if isinstance(violation_payload, dict):
                        self._insert_violation(
                            connection,
                            session_id,
                            violation_payload,
                        )
                for step_payload in rule_update.get("changed_steps", []):
                    if isinstance(step_payload, dict):
                        self._upsert_step(
                            connection,
                            session_id,
                            step_payload,
                        )
                if "score" in rule_update:
                    connection.execute(
                        update(sessions)
                        .where(sessions.c.session_id == session_id)
                        .values(
                            final_score=rule_update.get("score"),
                            passed=rule_update.get("passed"),
                        )
                    )

    def finalize(
        self,
        session_id: str,
        final_payload: dict[str, Any],
        *,
        status: str,
    ) -> None:
        result = final_payload.get("result", {})
        if not isinstance(result, dict):
            result = {}

        with self.engine.begin() as connection:
            for step_payload in result.get("steps", []):
                if isinstance(step_payload, dict):
                    self._upsert_step(
                        connection,
                        session_id,
                        step_payload,
                    )
            for violation_payload in result.get("violations", []):
                if isinstance(violation_payload, dict):
                    self._insert_violation(
                        connection,
                        session_id,
                        violation_payload,
                    )
            connection.execute(
                update(sessions)
                .where(sessions.c.session_id == session_id)
                .values(
                    status=status,
                    ended_at=datetime.now().astimezone(),
                    final_score=result.get("score"),
                    passed=result.get("passed"),
                )
            )

    def list_sessions(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 1000))
        statement = (
            select(sessions)
            .order_by(sessions.c.started_at.desc())
            .limit(safe_limit)
        )
        with self.engine.connect() as connection:
            return [
                dict(row._mapping)
                for row in connection.execute(statement)
            ]

    def get_session(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            session_row = connection.execute(
                select(sessions).where(
                    sessions.c.session_id == session_id
                )
            ).first()
            if session_row is None:
                return None

            action_rows = connection.execute(
                select(actions)
                .where(actions.c.session_id == session_id)
                .order_by(actions.c.started_at_ms, actions.c.id)
            )
            violation_rows = connection.execute(
                select(violations)
                .where(violations.c.session_id == session_id)
                .order_by(violations.c.id)
            )
            step_rows = connection.execute(
                select(steps)
                .where(steps.c.session_id == session_id)
                .order_by(steps.c.step_code)
            )
            return {
                "session": dict(session_row._mapping),
                "actions": [
                    dict(row._mapping) for row in action_rows
                ],
                "violations": [
                    dict(row._mapping) for row in violation_rows
                ],
                "steps": [
                    dict(row._mapping) for row in step_rows
                ],
            }

    def list_pending_reviews(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 1000))
        statement = (
            select(violations)
            .where(violations.c.review_status == "UNREVIEWED")
            .order_by(violations.c.id)
            .limit(safe_limit)
        )
        with self.engine.connect() as connection:
            return [
                dict(row._mapping)
                for row in connection.execute(statement)
            ]

    def review_violation(
        self,
        session_id: str,
        violation_id: int,
        review: ViolationReviewRequest,
        *,
        reviewer: str,
        reviewed_at: datetime | None = None,
    ) -> dict[str, Any] | None:
        return self._review_violation(
            session_id=session_id,
            review=review,
            reviewer=reviewer,
            reviewed_at=reviewed_at,
            violation_id=violation_id,
        )

    def review_violation_by_identity(
        self,
        session_id: str,
        *,
        rule_id: str,
        step_code: str,
        event_id: str,
        review: ViolationReviewRequest,
        reviewer: str,
        reviewed_at: datetime | None = None,
    ) -> dict[str, Any] | None:
        return self._review_violation(
            session_id=session_id,
            review=review,
            reviewer=reviewer,
            reviewed_at=reviewed_at,
            rule_id=rule_id,
            step_code=step_code,
            event_id=event_id,
        )

    def _review_violation(
        self,
        *,
        session_id: str,
        review: ViolationReviewRequest,
        reviewer: str,
        reviewed_at: datetime | None,
        violation_id: int | None = None,
        rule_id: str | None = None,
        step_code: str | None = None,
        event_id: str | None = None,
    ) -> dict[str, Any] | None:
        statement = select(violations).where(
            violations.c.session_id == session_id
        )
        if violation_id is not None:
            statement = statement.where(violations.c.id == violation_id)
        else:
            statement = statement.where(
                violations.c.rule_id == rule_id,
                violations.c.step_code == step_code,
                violations.c.event_id == event_id,
            )

        timestamp = reviewed_at or datetime.now().astimezone()
        values = {
            "review_status": review.decision.value,
            "reviewed_by": reviewer,
            "reviewed_at": timestamp,
            "review_reason_code": review.reason_code,
            "review_comment": review.comment,
        }
        with self.engine.begin() as connection:
            row = connection.execute(statement).first()
            if row is None:
                return None
            target_id = row._mapping["id"]
            connection.execute(
                update(violations)
                .where(violations.c.id == target_id)
                .values(**values)
            )
            updated_row = connection.execute(
                select(violations).where(violations.c.id == target_id)
            ).first()
            return (
                dict(updated_row._mapping)
                if updated_row is not None
                else None
            )

    def delete_session(self, session_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                delete(sessions).where(
                    sessions.c.session_id == session_id
                )
            )

    @staticmethod
    def _insert_action(
        connection: Connection,
        session_id: str,
        payload: dict[str, Any],
    ) -> None:
        event_id = str(payload.get("event_id", ""))
        if not event_id:
            return
        exists = connection.execute(
            select(actions.c.id).where(
                actions.c.session_id == session_id,
                actions.c.event_id == event_id,
            )
        ).first()
        if exists is not None:
            return

        object_payload = payload.get("object")
        object_class = None
        if isinstance(object_payload, dict):
            raw_class = object_payload.get("class")
            object_class = (
                str(raw_class) if raw_class is not None else None
            )

        connection.execute(
            insert(actions).values(
                session_id=session_id,
                event_id=event_id,
                sequence=payload.get("sequence"),
                action=str(payload.get("action", "")),
                object_class=object_class,
                source_zone=payload.get("source_zone"),
                target_zone=payload.get("target_zone"),
                started_at_ms=payload.get("started_at_ms"),
                ended_at_ms=payload.get("ended_at_ms"),
                confidence=payload.get("confidence"),
                payload_json=payload,
            )
        )

    @staticmethod
    def _insert_violation(
        connection: Connection,
        session_id: str,
        payload: dict[str, Any],
    ) -> None:
        rule_id = str(payload.get("rule_id", ""))
        step_code = str(payload.get("step", ""))
        event_id = str(payload.get("event_id", ""))
        if not rule_id or not step_code or not event_id:
            return

        exists = connection.execute(
            select(violations.c.id).where(
                violations.c.session_id == session_id,
                violations.c.rule_id == rule_id,
                violations.c.step_code == step_code,
                violations.c.event_id == event_id,
            )
        ).first()
        if exists is not None:
            return

        connection.execute(
            insert(violations).values(
                session_id=session_id,
                rule_id=rule_id,
                step_code=step_code,
                violation_type=str(payload.get("type", "")),
                severity=str(payload.get("severity", "")),
                event_id=event_id,
                confidence=payload.get("confidence"),
                payload_json=payload,
            )
        )

    @staticmethod
    def _upsert_step(
        connection: Connection,
        session_id: str,
        payload: dict[str, Any],
    ) -> None:
        step_code = str(payload.get("code", ""))
        if not step_code:
            return
        values = {
            "state": str(payload.get("state", "")),
            "event_id": payload.get("event_id"),
            "confidence": payload.get("confidence"),
            "payload_json": payload,
        }
        exists = connection.execute(
            select(steps.c.step_code).where(
                steps.c.session_id == session_id,
                steps.c.step_code == step_code,
            )
        ).first()
        if exists is None:
            connection.execute(
                insert(steps).values(
                    session_id=session_id,
                    step_code=step_code,
                    **values,
                )
            )
        else:
            connection.execute(
                update(steps)
                .where(
                    steps.c.session_id == session_id,
                    steps.c.step_code == step_code,
                )
                .values(**values)
            )
