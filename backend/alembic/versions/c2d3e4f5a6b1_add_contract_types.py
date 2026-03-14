"""add contract_types table and employee.contract_type_id

Revision ID: c2d3e4f5a6b1
Revises: b1c2d3e4f5a6
Create Date: 2026-03-14

Ergänzungen:
  - contract_types              – Neue Tabelle für Vertragstypen/Vorlagen
  - employees.contract_type_id  – FK auf contract_types (optional)
  - contract_history.contract_type_id – FK auf contract_types (optional, tracking)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = 'c2d3e4f5a6b1'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # Table may already exist if create_tables() ran before this migration
    if 'contract_types' not in existing_tables:
        op.create_table(
            'contract_types',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('tenant_id', sa.UUID(), nullable=False),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('contract_category', sa.String(50), nullable=False),
            sa.Column('hourly_rate', sa.Numeric(8, 2), nullable=False),
            sa.Column('monthly_hours_limit', sa.Numeric(6, 2), nullable=True),
            sa.Column('annual_salary_limit', sa.Numeric(10, 2), nullable=True),
            sa.Column('annual_hours_target', sa.Numeric(7, 1), nullable=True),
            sa.Column('weekly_hours', sa.Numeric(5, 2), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )

    # Add FK columns to employees if not present
    emp_cols = {c['name'] for c in inspector.get_columns('employees')}
    if 'contract_type_id' not in emp_cols:
        op.add_column('employees', sa.Column('contract_type_id', sa.UUID(), nullable=True))
        op.create_foreign_key(
            'fk_employees_contract_type_id',
            'employees', 'contract_types',
            ['contract_type_id'], ['id'],
            ondelete='SET NULL',
        )

    # Add FK column to contract_history if not present
    ch_cols = {c['name'] for c in inspector.get_columns('contract_history')}
    if 'contract_type_id' not in ch_cols:
        op.add_column('contract_history', sa.Column('contract_type_id', sa.UUID(), nullable=True))
        op.create_foreign_key(
            'fk_contract_history_contract_type_id',
            'contract_history', 'contract_types',
            ['contract_type_id'], ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    op.drop_constraint('fk_contract_history_contract_type_id', 'contract_history', type_='foreignkey')
    op.drop_column('contract_history', 'contract_type_id')
    op.drop_constraint('fk_employees_contract_type_id', 'employees', type_='foreignkey')
    op.drop_column('employees', 'contract_type_id')
    op.drop_table('contract_types')
