"""add monthly_salary to employees and contract_history

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa

revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("employees",
        sa.Column("monthly_salary", sa.Numeric(10, 2), nullable=True))
    op.add_column("contract_history",
        sa.Column("monthly_salary", sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("employees", "monthly_salary")
    op.drop_column("contract_history", "monthly_salary")
