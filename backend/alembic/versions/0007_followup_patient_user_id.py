"""Add followups.patient_user_id for QR-based member identity binding.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("followups") as batch_op:
        batch_op.add_column(
            sa.Column("patient_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True)
        )
        batch_op.create_index("ix_followups_patient_user_id", ["patient_user_id"])


def downgrade() -> None:
    with op.batch_alter_table("followups") as batch_op:
        batch_op.drop_index("ix_followups_patient_user_id")
        batch_op.drop_column("patient_user_id")
