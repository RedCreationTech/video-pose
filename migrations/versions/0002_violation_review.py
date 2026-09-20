"""Add violation review fields.

Revision ID: 0002_violation_review
Revises: 0001_session_repository
Create Date: 2026-09-21
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_violation_review"
down_revision = "0001_session_repository"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vp_violations",
        sa.Column(
            "review_status",
            sa.String(length=32),
            nullable=False,
            server_default="UNREVIEWED",
        ),
    )
    op.add_column(
        "vp_violations",
        sa.Column("reviewed_by", sa.String(length=128)),
    )
    op.add_column(
        "vp_violations",
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "vp_violations",
        sa.Column("review_reason_code", sa.String(length=128)),
    )
    op.add_column(
        "vp_violations",
        sa.Column("review_comment", sa.String(length=2000)),
    )
    op.create_index(
        "ix_vp_violations_review_status",
        "vp_violations",
        ["review_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_vp_violations_review_status",
        table_name="vp_violations",
    )
    op.drop_column("vp_violations", "review_comment")
    op.drop_column("vp_violations", "review_reason_code")
    op.drop_column("vp_violations", "reviewed_at")
    op.drop_column("vp_violations", "reviewed_by")
    op.drop_column("vp_violations", "review_status")
