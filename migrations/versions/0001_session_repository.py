"""Create session repository tables.

Revision ID: 0001_session_repository
Revises:
Create Date: 2026-09-20
"""
import sqlalchemy as sa
from alembic import op


revision = "0001_session_repository"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vp_sessions",
        sa.Column("session_id", sa.String(length=128), primary_key=True),
        sa.Column("operator_id", sa.String(length=128)),
        sa.Column("operation", sa.String(length=255), nullable=False),
        sa.Column("workstation_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rule_set_version", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("final_score", sa.Float()),
        sa.Column("passed", sa.Boolean()),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    op.create_table(
        "vp_actions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.String(length=128),
            sa.ForeignKey("vp_sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("sequence", sa.BigInteger()),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("object_class", sa.String(length=128)),
        sa.Column("source_zone", sa.String(length=128)),
        sa.Column("target_zone", sa.String(length=128)),
        sa.Column("started_at_ms", sa.BigInteger()),
        sa.Column("ended_at_ms", sa.BigInteger()),
        sa.Column("confidence", sa.Float()),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "session_id",
            "event_id",
            name="uq_vp_actions_session_event",
        ),
    )
    op.create_table(
        "vp_violations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.String(length=128),
            sa.ForeignKey("vp_sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_id", sa.String(length=128), nullable=False),
        sa.Column("step_code", sa.String(length=128), nullable=False),
        sa.Column("violation_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "session_id",
            "rule_id",
            "step_code",
            "event_id",
            name="uq_vp_violations_identity",
        ),
    )
    op.create_table(
        "vp_steps",
        sa.Column(
            "session_id",
            sa.String(length=128),
            sa.ForeignKey("vp_sessions.session_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("step_code", sa.String(length=128), primary_key=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.String(length=128)),
        sa.Column("confidence", sa.Float()),
        sa.Column("payload_json", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("vp_steps")
    op.drop_table("vp_violations")
    op.drop_table("vp_actions")
    op.drop_table("vp_sessions")
