"""add start_date to employees

Revision ID: g1h2i3j4k5l6
Revises: f5a6b7c8d9e0
Create Date: 2026-03-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = 'g1h2i3j4k5l6'
down_revision = 'f5a6b7c8d9e0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    cols = [c["name"] for c in inspector.get_columns("employees")]
    if "start_date" not in cols:
        op.add_column(
            "employees",
            sa.Column("start_date", sa.Date(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("employees", "start_date")
