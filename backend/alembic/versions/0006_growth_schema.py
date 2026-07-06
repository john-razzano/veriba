"""Growth Phase 3: consult_requests, session_photos, push_tokens, practices.hours.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "consult_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("practice_id", sa.String(36), sa.ForeignKey("practices.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id"), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=False),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_consult_requests_practice_id", "consult_requests", ["practice_id"])
    op.create_index("ix_consult_requests_user_id", "consult_requests", ["user_id"])

    op.create_table(
        "session_photos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("image_key", sa.String(500), nullable=False),
        sa.Column("blurhash", sa.String(64), nullable=True),
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_session_photos_session_id", "session_photos", ["session_id"])

    op.create_table(
        "push_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token", sa.String(255), nullable=False, unique=True),
        sa.Column("platform", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_push_tokens_user_id", "push_tokens", ["user_id"])

    with op.batch_alter_table("practices") as batch_op:
        batch_op.add_column(sa.Column("hours", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("practices") as batch_op:
        batch_op.drop_column("hours")

    op.drop_index("ix_push_tokens_user_id", table_name="push_tokens")
    op.drop_table("push_tokens")

    op.drop_index("ix_session_photos_session_id", table_name="session_photos")
    op.drop_table("session_photos")

    op.drop_index("ix_consult_requests_user_id", table_name="consult_requests")
    op.drop_index("ix_consult_requests_practice_id", table_name="consult_requests")
    op.drop_table("consult_requests")
