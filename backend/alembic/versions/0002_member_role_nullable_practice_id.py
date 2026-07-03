"""Allow users without a practice (consumer "member" accounts).

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-03

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "practice_id", existing_type=sa.String(length=36), nullable=True
        )


def downgrade() -> None:
    # Member accounts (practice_id IS NULL) must be removed before downgrading.
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "practice_id", existing_type=sa.String(length=36), nullable=False
        )
