"""add employee_contract_type_memberships table

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-03-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = 'i3j4k5l6m7n8'
down_revision = 'h2i3j4k5l6m7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if "employee_contract_type_memberships" not in tables:
        op.create_table(
            "employee_contract_type_memberships",
            sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", sa.UUID(), nullable=False),
            sa.Column("employee_id", sa.UUID(), nullable=False),
            sa.Column("contract_type_id", sa.UUID(), nullable=True),
            sa.Column("valid_from", sa.Date(), nullable=False),
            sa.Column("valid_to", sa.Date(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.UUID(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["contract_type_id"], ["contract_types.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_employee_contract_type_memberships_employee_id",
            "employee_contract_type_memberships",
            ["employee_id"],
        )

        # Backfill: bestehende Zuweisungen in die History-Tabelle übertragen
        conn.execute(sa.text("""
            INSERT INTO employee_contract_type_memberships
                (id, tenant_id, employee_id, contract_type_id, valid_from, note)
            SELECT
                gen_random_uuid(),
                e.tenant_id,
                e.id,
                e.contract_type_id,
                COALESCE(e.start_date, e.created_at::date),
                'Migriert aus Stammdaten'
            FROM employees e
            WHERE e.contract_type_id IS NOT NULL
        """))


def downgrade() -> None:
    op.drop_index(
        "ix_employee_contract_type_memberships_employee_id",
        "employee_contract_type_memberships",
    )
    op.drop_table("employee_contract_type_memberships")
