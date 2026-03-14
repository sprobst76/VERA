"""add shift_types table and shift_type_id to shifts

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-03-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "e3f4a5b6c7d8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shift_types",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(20), nullable=False, server_default="#1E3A5F"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("reminder_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("reminder_minutes_before", sa.Integer, nullable=False, server_default="60"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), onupdate=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_shift_types_tenant_id", "shift_types", ["tenant_id"])

    op.add_column("shifts", sa.Column(
        "shift_type_id",
        UUID(as_uuid=True),
        sa.ForeignKey("shift_types.id", ondelete="SET NULL"),
        nullable=True,
    ))


def downgrade() -> None:
    op.drop_column("shifts", "shift_type_id")
    op.drop_index("ix_shift_types_tenant_id", table_name="shift_types")
    op.drop_table("shift_types")
