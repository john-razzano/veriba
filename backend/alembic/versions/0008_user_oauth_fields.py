"""Add auth_provider, oauth_subject to users; make password_hash nullable.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(255),
            nullable=True,
        )
        batch_op.add_column(
            sa.Column("auth_provider", sa.String(20), nullable=False, server_default="email")
        )
        batch_op.add_column(
            sa.Column("oauth_subject", sa.String(255), nullable=True)
        )
        batch_op.create_unique_constraint(
            "uq_user_auth_subject", ["auth_provider", "oauth_subject"]
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_user_auth_subject", type_="unique")
        batch_op.drop_column("oauth_subject")
        batch_op.drop_column("auth_provider")
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(255),
            nullable=False,
        )
