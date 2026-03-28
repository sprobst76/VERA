"""audit_log_indexes_and_revoke

Add composite indexes on audit_log for query performance and REVOKE
UPDATE/DELETE on PostgreSQL to make the table append-only at DB level.

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
Create Date: 2026-03-28

"""
from alembic import op
from sqlalchemy.engine.reflection import Inspector

revision = "k5l6m7n8o9p0"
down_revision = "j4k5l6m7n8o9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # Get existing index names on audit_log (table must already exist via create_tables())
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("audit_log")}

    # Composite index: (tenant_id, entity_type, entity_id) — supports entity-scoped lookups
    if "ix_audit_log_tenant_entity" not in existing_indexes:
        op.create_index(
            "ix_audit_log_tenant_entity",
            "audit_log",
            ["tenant_id", "entity_type", "entity_id"],
        )

    # Composite index: (tenant_id, created_at) — supports time-range queries per tenant
    if "ix_audit_log_tenant_created" not in existing_indexes:
        op.create_index(
            "ix_audit_log_tenant_created",
            "audit_log",
            ["tenant_id", "created_at"],
        )

    # REVOKE UPDATE, DELETE to make audit_log append-only at DB level.
    # Skipped on SQLite (development/test) — only applied on PostgreSQL (production).
    if conn.dialect.name == "postgresql":
        op.execute("REVOKE UPDATE, DELETE ON audit_log FROM vera")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("audit_log")}

    if "ix_audit_log_tenant_entity" in existing_indexes:
        op.drop_index("ix_audit_log_tenant_entity", table_name="audit_log")

    if "ix_audit_log_tenant_created" in existing_indexes:
        op.drop_index("ix_audit_log_tenant_created", table_name="audit_log")

    if conn.dialect.name == "postgresql":
        op.execute("GRANT UPDATE, DELETE ON audit_log TO vera")
