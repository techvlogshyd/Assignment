"""initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("create type userrole as enum ('admin', 'editor', 'viewer')")
    op.execute("create type orderstatus as enum ('pending', 'processing', 'completed', 'failed')")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("admin", "editor", "viewer", name="userrole", create_type=False),
            nullable=False,
            server_default="viewer",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_id", sa.String(), nullable=False),  # TODO: add unique constraint
        sa.Column("customer_name", sa.String(), nullable=False),
        sa.Column("items", postgresql.JSONB(), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 4), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "processing", "completed", "failed",
                name="orderstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
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
    )


def downgrade() -> None:
    op.drop_table("orders")
    op.drop_table("users")
    op.execute("drop type orderstatus")
    op.execute("drop type userrole")
