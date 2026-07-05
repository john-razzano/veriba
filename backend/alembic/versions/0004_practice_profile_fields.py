"""Add bio, avatar_key, booking_url to practices for provider-managed public page.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("practices") as batch_op:
        batch_op.add_column(sa.Column("bio", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("avatar_key", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("booking_url", sa.String(500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("practices") as batch_op:
        batch_op.drop_column("booking_url")
        batch_op.drop_column("avatar_key")
        batch_op.drop_column("bio")
