"""add key_prefix to api_keys

Fixes the "prefix for recognition" shown once at key creation never
matching what the list endpoint showed afterwards (it derived a
different, unrelated value from key_hash instead of storing the real
prefix). Existing keys have no recoverable prefix (only the hash is
stored) - they simply show nothing until rotated.

Revision ID: o9p0q1r2s3t4
Revises: n8o9p0q1r2s3
Create Date: 2026-07-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = 'o9p0q1r2s3t4'
down_revision = 'n8o9p0q1r2s3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    cols = [c["name"] for c in inspector.get_columns("api_keys")]
    if "key_prefix" not in cols:
        op.add_column(
            "api_keys",
            sa.Column("key_prefix", sa.String(20), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("api_keys", "key_prefix")
