"""add contract_type_history table

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-03-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = 'h2i3j4k5l6m7'
down_revision = 'g1h2i3j4k5l6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    if "contract_type_history" not in tables:
        op.create_table(
            "contract_type_history",
            sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", sa.UUID(), nullable=False),
            sa.Column("contract_type_id", sa.UUID(), nullable=False),
            sa.Column("valid_from", sa.Date(), nullable=False),
            sa.Column("valid_to", sa.Date(), nullable=True),
            sa.Column("hourly_rate", sa.Numeric(8, 2), nullable=False),
            sa.Column("monthly_hours_limit", sa.Numeric(6, 2), nullable=True),
            sa.Column("annual_salary_limit", sa.Numeric(10, 2), nullable=True),
            sa.Column("annual_hours_target", sa.Numeric(7, 1), nullable=True),
            sa.Column("weekly_hours", sa.Numeric(5, 2), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.UUID(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["contract_type_id"], ["contract_types.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_contract_type_history_contract_type_id", "contract_type_history", ["contract_type_id"])


def downgrade() -> None:
    op.drop_index("ix_contract_type_history_contract_type_id", "contract_type_history")
    op.drop_table("contract_type_history")
