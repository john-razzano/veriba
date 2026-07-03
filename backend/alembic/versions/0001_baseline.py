"""Baseline: capture the pre-Alembic schema.

Existing deployments (created via Base.metadata.create_all) must be stamped
with this revision instead of running it — app.db.migrations.run_migrations
does that automatically when it finds tables but no alembic_version.

Revision ID: 0001
Revises:
Create Date: 2026-07-03

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "practices",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("widget_slug", sa.String(length=100), nullable=False),
        sa.Column("default_discount_full", sa.Integer(), nullable=False),
        sa.Column("default_discount_partial", sa.Integer(), nullable=False),
        sa.Column("default_discount_blur", sa.Integer(), nullable=False),
        sa.Column("credit_expiration_days", sa.Integer(), nullable=False),
        sa.Column("auto_publish", sa.Boolean(), nullable=False),
        # FK to users.id added below via batch_alter_table — the users table
        # doesn't exist yet (circular reference between practices and users).
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_practices_widget_slug", "practices", ["widget_slug"], unique=True
    )

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("initials", sa.String(length=5), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column(
            "practice_id",
            sa.String(length=36),
            sa.ForeignKey("practices.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_practice_id", "users", ["practice_id"])

    with op.batch_alter_table("practices") as batch_op:
        batch_op.create_foreign_key(
            "fk_practices_owner_id_users", "users", ["owner_id"], ["id"]
        )

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "practice_id",
            sa.String(length=36),
            sa.ForeignKey("practices.id"),
            nullable=False,
        ),
        sa.Column("patient_initials", sa.String(length=10), nullable=False),
        sa.Column("treatment", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("obscure_mode", sa.String(length=10), nullable=False),
        sa.Column("treatment_details", sa.Text(), nullable=True),
        sa.Column("before_image_key", sa.String(length=500), nullable=True),
        sa.Column("before_original_image_key", sa.String(length=500), nullable=True),
        sa.Column("after_image_key", sa.String(length=500), nullable=True),
        sa.Column("after_original_image_key", sa.String(length=500), nullable=True),
        sa.Column("before_image_width", sa.Integer(), nullable=True),
        sa.Column("before_image_height", sa.Integer(), nullable=True),
        sa.Column("after_image_width", sa.Integer(), nullable=True),
        sa.Column("after_image_height", sa.Integer(), nullable=True),
        sa.Column("capture_hash", sa.String(length=64), nullable=True),
        sa.Column("capture_lat", sa.Float(), nullable=True),
        sa.Column("capture_lng", sa.Float(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sign_hash", sa.String(length=64), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("after_capture_hash", sa.String(length=64), nullable=True),
        sa.Column("after_captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("after_provenance", sa.String(length=50), nullable=True),
        sa.Column("consent_tier", sa.String(length=20), nullable=True),
        sa.Column("consent_signature_key", sa.String(length=500), nullable=True),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_ip", sa.String(length=45), nullable=True),
        sa.Column("consent_user_agent", sa.String(length=500), nullable=True),
        sa.Column("consent_form_version", sa.String(length=50), nullable=True),
        sa.Column("discount_applied", sa.Integer(), nullable=True),
        sa.Column("publish_hash", sa.String(length=64), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_destinations", sa.JSON(), nullable=True),
        sa.Column("seo_title", sa.String(length=500), nullable=True),
        sa.Column("seo_alt_text", sa.String(length=500), nullable=True),
        sa.Column("seo_meta_description", sa.Text(), nullable=True),
        sa.Column("seo_filename", sa.String(length=255), nullable=True, unique=True),
        sa.Column("seo_url_slug", sa.String(length=255), nullable=True, unique=True),
        sa.Column("seo_template_variant", sa.Integer(), nullable=False),
        sa.Column("page_views", sa.Integer(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_practice_id", "sessions", ["practice_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index(
        "ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True
    )

    op.create_table(
        "followups",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("sessions.id"),
            nullable=False,
        ),
        sa.Column(
            "practice_id",
            sa.String(length=36),
            sa.ForeignKey("practices.id"),
            nullable=False,
        ),
        sa.Column("patient_email", sa.String(length=255), nullable=False),
        sa.Column("patient_first_name", sa.String(length=100), nullable=True),
        sa.Column("upload_token", sa.String(length=128), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("custom_message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("send_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("upload_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_1_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_2_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_followups_session_id", "followups", ["session_id"])
    op.create_index("ix_followups_practice_id", "followups", ["practice_id"])
    op.create_index(
        "ix_followups_upload_token", "followups", ["upload_token"], unique=True
    )

    op.create_table(
        "credits",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "practice_id",
            sa.String(length=36),
            sa.ForeignKey("practices.id"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("sessions.id"),
            nullable=False,
        ),
        sa.Column(
            "followup_id",
            sa.String(length=36),
            sa.ForeignKey("followups.id"),
            nullable=True,
        ),
        sa.Column("patient_initials", sa.String(length=10), nullable=False),
        sa.Column("patient_email", sa.String(length=255), nullable=True),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("consent_tier", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("earned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redeemed_by", sa.String(length=255), nullable=True),
        sa.Column("redeem_notes", sa.Text(), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_credits_practice_id", "credits", ["practice_id"])
    op.create_index("ix_credits_session_id", "credits", ["session_id"])
    op.create_index("ix_credits_code", "credits", ["code"], unique=True)


def downgrade() -> None:
    op.drop_table("credits")
    op.drop_table("followups")
    op.drop_table("refresh_tokens")
    op.drop_table("sessions")
    with op.batch_alter_table("practices") as batch_op:
        batch_op.drop_constraint("fk_practices_owner_id_users", type_="foreignkey")
    op.drop_table("users")
    op.drop_table("practices")
