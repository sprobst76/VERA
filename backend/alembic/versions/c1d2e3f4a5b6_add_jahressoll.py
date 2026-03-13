"""add_jahressoll

Revision ID: c1d2e3f4a5b6
Revises: b3c4d5e6f7a8
Create Date: 2026-03-13 00:00:00.000000

Ergänzungen:
  - employees.annual_hours_target          – Jahressoll in Stunden (Vollzeit/Teilzeit)
  - contract_history.annual_hours_target   – Snapshot pro Vertragsperiode
  - payroll_entries.ytd_hours              – Geleistete Stunden YTD (aus approved/paid)
  - payroll_entries.annual_hours_target    – Snapshot zum Berechnungszeitpunkt
  - payroll_entries.annual_hours_remaining – Verbleibendes Jahressoll
  - payroll_entries.monthly_hours_target   – Monatliches Soll (Jahressoll / 12)
  - payroll_entries.wage_details           – JSON: Lohnaufteilung bei Vertragsänderung im Monat
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("employees",
        sa.Column("annual_hours_target", sa.Numeric(7, 1), nullable=True))

    op.add_column("contract_history",
        sa.Column("annual_hours_target", sa.Numeric(7, 1), nullable=True))

    op.add_column("payroll_entries",
        sa.Column("ytd_hours", sa.Numeric(8, 2), nullable=False, server_default="0"))
    op.add_column("payroll_entries",
        sa.Column("annual_hours_target", sa.Numeric(7, 1), nullable=True))
    op.add_column("payroll_entries",
        sa.Column("annual_hours_remaining", sa.Numeric(7, 2), nullable=True))
    op.add_column("payroll_entries",
        sa.Column("monthly_hours_target", sa.Numeric(7, 2), nullable=True))
    op.add_column("payroll_entries",
        sa.Column("wage_details", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("payroll_entries", "wage_details")
    op.drop_column("payroll_entries", "monthly_hours_target")
    op.drop_column("payroll_entries", "annual_hours_remaining")
    op.drop_column("payroll_entries", "annual_hours_target")
    op.drop_column("payroll_entries", "ytd_hours")
    op.drop_column("contract_history", "annual_hours_target")
    op.drop_column("employees", "annual_hours_target")
