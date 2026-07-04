"""Add saved_cases and followed_practices for consumer saves/follows.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "session_id", name="uq_saved_cases_user_session"),
    )
    op.create_index("ix_saved_cases_user_id", "saved_cases", ["user_id"])
    op.create_index("ix_saved_cases_session_id", "saved_cases", ["session_id"])

    op.create_table(
        "followed_practices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("practice_id", sa.String(36), sa.ForeignKey("practices.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "practice_id", name="uq_followed_practices_user_practice"),
    )
    op.create_index("ix_followed_practices_user_id", "followed_practices", ["user_id"])
    op.create_index("ix_followed_practices_practice_id", "followed_practices", ["practice_id"])


def downgrade() -> None:
    op.drop_index("ix_followed_practices_practice_id", table_name="followed_practices")
    op.drop_index("ix_followed_practices_user_id", table_name="followed_practices")
    op.drop_table("followed_practices")
    op.drop_index("ix_saved_cases_session_id", table_name="saved_cases")
    op.drop_index("ix_saved_cases_user_id", table_name="saved_cases")
    op.drop_table("saved_cases")
