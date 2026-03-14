"""add invite/reset token fields to users

Revision ID: a0b1c2d3e4f5
Revises: d3e4f5a6b7c8
Create Date: 2026-03-14

Ergänzungen:
  - users.invite_token          – One-time invite token (7 Tage gültig)
  - users.invite_expires_at     – Ablaufzeit Einladung
  - users.reset_token           – One-time password-reset token (1 Stunde gültig)
  - users.reset_expires_at      – Ablaufzeit Reset
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = 'a0b1c2d3e4f5'
down_revision = 'd3e4f5a6b7c8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    cols = {c['name'] for c in inspector.get_columns('users')}

    if 'invite_token' not in cols:
        op.add_column('users', sa.Column('invite_token', sa.String(100), nullable=True, unique=True))
    if 'invite_expires_at' not in cols:
        op.add_column('users', sa.Column('invite_expires_at', sa.DateTime(timezone=True), nullable=True))
    if 'reset_token' not in cols:
        op.add_column('users', sa.Column('reset_token', sa.String(100), nullable=True, unique=True))
    if 'reset_expires_at' not in cols:
        op.add_column('users', sa.Column('reset_expires_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'reset_expires_at')
    op.drop_column('users', 'reset_token')
    op.drop_column('users', 'invite_expires_at')
    op.drop_column('users', 'invite_token')
