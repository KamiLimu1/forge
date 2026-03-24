"""Initial authentication schema.

Revision ID: 001
Revises:
Create Date: 2026-03-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Create enum types
    account_state = postgresql.ENUM(
        "pending", "active", "suspended",
        name="accountstate",
    )
    account_state.create(op.get_bind(), checkfirst=True)

    user_role = postgresql.ENUM(
        "mentee",
        "peer_mentor_1:1",
        "peer_mentor_ict",
        "professional_mentor",
        "committee",
        "partner",
        "alumni",
        "admin",
        name="userrole",
    )
    user_role.create(op.get_bind(), checkfirst=True)

    cohort_status = postgresql.ENUM(
        "draft", "active", "completed",
        name="cohortstatus",
    )
    cohort_status.create(op.get_bind(), checkfirst=True)

    programme_type = postgresql.ENUM(
        "undergraduate", "postgraduate",
        name="programmetype",
    )
    programme_type.create(op.get_bind(), checkfirst=True)

    # Create cohorts table (referenced by user_roles)
    op.create_table(
        "cohorts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "programme_type",
            postgresql.ENUM(
                "undergraduate", "postgraduate",
                name="programmetype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("graduation_threshold", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("kami_limu_month_boundaries", postgresql.JSONB(), nullable=True),
        sa.Column("ict_tracks_offered", postgresql.JSONB(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft", "active", "completed",
                name="cohortstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cohorts")),
        sa.UniqueConstraint("name", name=op.f("uq_cohorts_name")),
    )

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column(
            "account_state",
            postgresql.ENUM(
                "pending", "active", "suspended",
                name="accountstate",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)

    # Create user_roles table
    op.create_table(
        "user_roles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(
                "mentee",
                "peer_mentor_1:1",
                "peer_mentor_ict",
                "professional_mentor",
                "committee",
                "partner",
                "alumni",
                "admin",
                name="userrole",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("cohort_id", sa.UUID(), nullable=True),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("assigned_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["assigned_by"],
            ["users.id"],
            name=op.f("fk_user_roles_assigned_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["cohort_id"],
            ["cohorts.id"],
            name=op.f("fk_user_roles_cohort_id_cohorts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_roles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_roles")),
    )
    op.create_index(
        "ix_user_roles_user_id_cohort_id",
        "user_roles",
        ["user_id", "cohort_id"],
        unique=False,
    )

    # Create invitations table
    op.create_table(
        "invitations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invited_by", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("intended_roles", postgresql.JSONB(), nullable=True),
        sa.Column("intended_cohort_id", sa.UUID(), nullable=True),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["users.id"],
            name=op.f("fk_invitations_invited_by_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitations")),
        sa.UniqueConstraint("token", name=op.f("uq_invitations_token")),
    )
    op.create_index(op.f("ix_invitations_email"), "invitations", ["email"], unique=False)
    op.create_index(op.f("ix_invitations_token"), "invitations", ["token"], unique=False)

    # Create token_blacklist table
    op.create_table(
        "token_blacklist",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("token_jti", sa.String(length=255), nullable=False),
        sa.Column(
            "blacklisted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_token_blacklist")),
        sa.UniqueConstraint("token_jti", name=op.f("uq_token_blacklist_token_jti")),
    )
    op.create_index(
        op.f("ix_token_blacklist_token_jti"),
        "token_blacklist",
        ["token_jti"],
        unique=False,
    )

    # Create password_reset_tokens table
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_password_reset_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
        sa.UniqueConstraint("token", name=op.f("uq_password_reset_tokens_token")),
    )
    op.create_index(
        op.f("ix_password_reset_tokens_token"),
        "password_reset_tokens",
        ["token"],
        unique=False,
    )

    # Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("resource_id", sa.UUID(), nullable=True),
        sa.Column("meta_data", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(
        op.f("ix_audit_logs_created_at"),
        "audit_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_logs_user_id"),
        "audit_logs",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_table("audit_logs")
    op.drop_table("password_reset_tokens")
    op.drop_table("token_blacklist")
    op.drop_table("invitations")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("cohorts")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS programmetype")
    op.execute("DROP TYPE IF EXISTS cohortstatus")
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS accountstate")
