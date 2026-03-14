"""add shift_type_id to recurring_shifts

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b1
Create Date: 2026-03-14

"""
from alembic import op
import sqlalchemy as sa

revision = 'd3e4f5a6b7c8'
down_revision = 'c2d3e4f5a6b1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'recurring_shifts',
        sa.Column('shift_type_id', sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        'fk_recurring_shifts_shift_type_id',
        'recurring_shifts', 'shift_types',
        ['shift_type_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_recurring_shifts_shift_type_id', 'recurring_shifts', type_='foreignkey')
    op.drop_column('recurring_shifts', 'shift_type_id')
