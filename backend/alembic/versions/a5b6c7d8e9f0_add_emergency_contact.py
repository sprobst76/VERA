"""add emergency_contact to employees

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-03-14

"""
from alembic import op
import sqlalchemy as sa

revision = 'a5b6c7d8e9f0'
down_revision = 'f4a5b6c7d8e9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('employees', sa.Column(
        'emergency_contact', sa.JSON(), nullable=True
    ))


def downgrade() -> None:
    op.drop_column('employees', 'emergency_contact')
