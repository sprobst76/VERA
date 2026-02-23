"""add_schuljahrdienste

Revision ID: a1b2c3d4e5f6
Revises: 8eefccc3f51f
Create Date: 2026-02-23 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '8eefccc3f51f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'holiday_profiles',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('state', sa.String(length=10), nullable=False, server_default='BW'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'vacation_periods',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('profile_id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('color', sa.String(length=20), nullable=False, server_default='#a6e3a1'),
        sa.ForeignKeyConstraint(['profile_id'], ['holiday_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'custom_holidays',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('profile_id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('color', sa.String(length=20), nullable=False, server_default='#fab387'),
        sa.ForeignKeyConstraint(['profile_id'], ['holiday_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'recurring_shifts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('weekday', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('break_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('employee_id', sa.Uuid(), nullable=True),
        sa.Column('template_id', sa.Uuid(), nullable=True),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_until', sa.Date(), nullable=False),
        sa.Column('holiday_profile_id', sa.Uuid(), nullable=True),
        sa.Column('skip_public_holidays', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('label', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['template_id'], ['shift_templates.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['holiday_profile_id'], ['holiday_profiles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.add_column('shifts', sa.Column('recurring_shift_id', sa.Uuid(), nullable=True))
    op.add_column('shifts', sa.Column('is_override', sa.Boolean(), nullable=False, server_default='false'))
    op.create_foreign_key(
        'fk_shifts_recurring_shift_id',
        'shifts', 'recurring_shifts',
        ['recurring_shift_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_shifts_recurring_shift_id', 'shifts', type_='foreignkey')
    op.drop_column('shifts', 'is_override')
    op.drop_column('shifts', 'recurring_shift_id')
    op.drop_table('recurring_shifts')
    op.drop_table('custom_holidays')
    op.drop_table('vacation_periods')
    op.drop_table('holiday_profiles')
