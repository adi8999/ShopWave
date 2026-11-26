"""002_auth_accounts_audit

Add email verification, token_version, MFA fields to users, plus
refresh_tokens, verification_tokens, and audit_logs tables.
"""

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("users", sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("mfa_secret", sa.String(64), nullable=True))

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "verification_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", sa.String(50), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("verification_tokens")
    op.drop_table("refresh_tokens")
    op.drop_column("users", "mfa_secret")
    op.drop_column("users", "mfa_enabled")
    op.drop_column("users", "token_version")
    op.drop_column("users", "is_verified")
