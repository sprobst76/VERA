"""add_compliance_indexes

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-13 00:00:00.000000

Indexes für häufige Compliance-Queries:
  - GET /compliance/violations filtert auf rest_period_ok / break_ok / minijob_limit_ok
  - GET /shifts filtert auf tenant_id + date
  - GET /shifts filtert auf employee_id + date (für Employee-Self-View)
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Compliance-Flag-Index: wird bei Violations-Query genutzt
    # WHERE (rest_period_ok = false OR break_ok = false OR minijob_limit_ok = false)
    op.create_index(
        "ix_shifts_compliance_flags",
        "shifts",
        ["rest_period_ok", "break_ok", "minijob_limit_ok"],
    )

    # Tenant + Datum: Haupt-Query für GET /shifts (date-range)
    op.create_index(
        "ix_shifts_tenant_date",
        "shifts",
        ["tenant_id", "date"],
    )

    # Employee + Datum: für Employee-Self-View und Payroll
    op.create_index(
        "ix_shifts_employee_date",
        "shifts",
        ["employee_id", "date"],
    )

    # Absences: Tenant + Status (für pending-Badge-Query im Sidebar)
    op.create_index(
        "ix_employee_absences_tenant_status",
        "employee_absences",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_employee_absences_tenant_status", table_name="employee_absences")
    op.drop_index("ix_shifts_employee_date", table_name="shifts")
    op.drop_index("ix_shifts_tenant_date", table_name="shifts")
    op.drop_index("ix_shifts_compliance_flags", table_name="shifts")
