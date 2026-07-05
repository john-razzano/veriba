"""Add featured_session_id, services, blurhashes for Phase 2 public page.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("practices") as batch_op:
        batch_op.add_column(sa.Column("featured_session_id", sa.String(36), sa.ForeignKey("sessions.id"), nullable=True))
        batch_op.add_column(sa.Column("services", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("avatar_blurhash", sa.String(64), nullable=True))

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(sa.Column("before_blurhash", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("after_blurhash", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_column("after_blurhash")
        batch_op.drop_column("before_blurhash")

    with op.batch_alter_table("practices") as batch_op:
        batch_op.drop_column("avatar_blurhash")
        batch_op.drop_column("services")
        batch_op.drop_column("featured_session_id")
