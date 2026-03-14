"""add time_correction fields to shifts

Revision ID: b1c2d3e4f5a6
Revises: a5b6c7d8e9f0
Create Date: 2026-03-14

Ergänzungen:
  - shifts.actual_break_minutes          – Tatsächliche Pause (Minuten)
  - shifts.time_correction_status        – none | pending | confirmed | rejected
  - shifts.time_correction_note          – Notiz des Mitarbeiters
  - shifts.time_correction_confirmed_by  – FK → users.id
  - shifts.time_correction_confirmed_at  – Zeitstempel der Bestätigung
"""
from alembic import op
import sqlalchemy as sa

revision = 'b1c2d3e4f5a6'
down_revision = 'a5b6c7d8e9f0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('shifts', sa.Column(
        'actual_break_minutes', sa.Integer(), nullable=True
    ))
    op.add_column('shifts', sa.Column(
        'time_correction_status', sa.String(20), nullable=True, server_default='none'
    ))
    op.add_column('shifts', sa.Column(
        'time_correction_note', sa.Text(), nullable=True
    ))
    op.add_column('shifts', sa.Column(
        'time_correction_confirmed_by', sa.UUID(), nullable=True
    ))
    op.add_column('shifts', sa.Column(
        'time_correction_confirmed_at', sa.DateTime(timezone=True), nullable=True
    ))


def downgrade() -> None:
    op.drop_column('shifts', 'time_correction_confirmed_at')
    op.drop_column('shifts', 'time_correction_confirmed_by')
    op.drop_column('shifts', 'time_correction_note')
    op.drop_column('shifts', 'time_correction_status')
    op.drop_column('shifts', 'actual_break_minutes')
