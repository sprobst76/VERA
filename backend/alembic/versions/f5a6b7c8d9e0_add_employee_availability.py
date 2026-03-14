"""add availability_prefs to employees

Revision ID: f5a6b7c8d9e0
Revises: f4a5b6c7d8e9
Create Date: 2026-03-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = 'f5a6b7c8d9e0'
down_revision = 'a0b1c2d3e4f5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    cols = [c["name"] for c in inspector.get_columns("employees")]
    if "availability_prefs" not in cols:
        op.add_column(
            "employees",
            sa.Column("availability_prefs", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("employees", "availability_prefs")
