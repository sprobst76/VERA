"""add shift_swap_offers table

Revision ID: n8o9p0q1r2s3
Revises: m7n8o9p0q1r2
Create Date: 2026-07-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "n8o9p0q1r2s3"
down_revision = "m7n8o9p0q1r2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "shift_swap_offers" not in existing_tables:
        # Kein server_default für id/created_at/updated_at: die ORM liefert diese
        # Werte Python-seitig (uuid.uuid4()/datetime.now()) vor jedem Insert, und
        # gen_random_uuid()/now() sind Postgres-spezifisch (bricht auf SQLite in
        # Dev/Tests, falls die Migration vor dem ersten create_all() läuft).
        op.create_table(
            "shift_swap_offers",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("shift_id", UUID(as_uuid=True), sa.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("offering_employee_id", UUID(as_uuid=True), sa.ForeignKey("employees.id"), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="open"),
            sa.Column("note", sa.Text, nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("accepted_by_employee_id", UUID(as_uuid=True), sa.ForeignKey("employees.id"), nullable=True),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("review_note", sa.Text, nullable=True),
            sa.Column("resolution_reason", sa.String(50), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_shift_swap_offers_tenant_status", "shift_swap_offers", ["tenant_id", "status"])
        op.create_index("ix_shift_swap_offers_shift_id", "shift_swap_offers", ["shift_id"])


def downgrade() -> None:
    op.drop_index("ix_shift_swap_offers_shift_id", table_name="shift_swap_offers")
    op.drop_index("ix_shift_swap_offers_tenant_status", table_name="shift_swap_offers")
    op.drop_table("shift_swap_offers")
